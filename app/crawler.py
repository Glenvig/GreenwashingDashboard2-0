"""
Async BFS web crawler.

Entry point: crawl_run()
  • Launched as a FastAPI BackgroundTask immediately after the run row is
    created with status='pending'.
  • Fetches pages concurrently, bounded by a semaphore (CRAWL_CONCURRENCY).
  • Discovers new same-host links from each HTML page and enqueues them.
  • Writes every finding to Postgres via the crud module.
  • Updates run status / counters atomically as each page finishes.
"""

from __future__ import annotations

import asyncio
import logging
from collections import deque
from urllib.parse import urlparse
from uuid import UUID

import asyncpg
import httpx

from .config import settings
from . import crud
from .extractor import extract_links, extract_segments
from .matcher import Rule, any_match, compile_rules, find_matches

log = logging.getLogger(__name__)

_USER_AGENT = (
    "GreenwashingDashboard/2.0 "
    "(+https://github.com/Glenvig/GreenwashingDashboard2-0)"
)


# ---------------------------------------------------------------------------
# Snippet builder
# ---------------------------------------------------------------------------


def _make_snippet(text: str, pos: int, ctx: int | None = None) -> str:
    """Return *ctx* characters of context on each side of *pos*."""
    ctx = ctx or settings.snippet_context
    start = max(0, pos - ctx)
    end = min(len(text), pos + ctx)
    snippet = text[start:end]
    if start > 0:
        snippet = "\u2026" + snippet   # leading ellipsis
    if end < len(text):
        snippet = snippet + "\u2026"   # trailing ellipsis
    return snippet


# ---------------------------------------------------------------------------
# URL helpers
# ---------------------------------------------------------------------------


def _normalise_url(url: str) -> str:
    """Strip fragment and trailing slash for dedup purposes."""
    p = urlparse(url)
    return p._replace(fragment="").geturl().rstrip("/")


def _same_host(url: str, netloc: str) -> bool:
    return urlparse(url).netloc == netloc


# ---------------------------------------------------------------------------
# Per-page worker
# ---------------------------------------------------------------------------


async def _scan_page(
    url: str,
    run_id: UUID,
    netloc: str,
    keyword_rules: list[Rule],
    exclude_rules: list[Rule],
    client: httpx.AsyncClient,
    pool: asyncpg.Pool,
    sem: asyncio.Semaphore,
) -> list[str]:
    """
    Fetch *url*, extract text, match keywords, persist results.
    Returns a list of same-host links discovered on the page.
    """
    async with sem:
        # -----------------------------------------------------------------
        # 1. Register the page (skip if already seen in this run)
        # -----------------------------------------------------------------
        page_id = await crud.insert_page(pool, run_id, url)
        if page_id is None:
            return []   # duplicate – already queued or processed

        await crud.increment_pages_found(pool, run_id)
        await crud.update_page_scanning(pool, page_id)

        discovered_links: list[str] = []

        try:
            # -----------------------------------------------------------------
            # 2. HTTP fetch
            # -----------------------------------------------------------------
            response = await client.get(url)
            response.raise_for_status()

            content_type = response.headers.get("content-type", "")
            if "html" not in content_type:
                await crud.update_page_failed(pool, page_id, "Non-HTML content-type")
                await crud.increment_pages_scanned(pool, run_id)
                return []

            html = response.text

            # -----------------------------------------------------------------
            # 3. Link extraction (always, regardless of exclusion)
            # -----------------------------------------------------------------
            discovered_links = extract_links(html, url)

            # -----------------------------------------------------------------
            # 4. URL-pattern exclusion check
            # -----------------------------------------------------------------
            if exclude_rules:
                url_path = urlparse(url).path
                if any_match(url_path, exclude_rules):
                    await crud.update_page_skipped(
                        pool, page_id, "URL matched an exclude pattern"
                    )
                    await crud.increment_pages_scanned(pool, run_id)
                    return discovered_links

            # -----------------------------------------------------------------
            # 5. Text extraction + keyword matching
            # -----------------------------------------------------------------
            segments = extract_segments(html)
            all_matches: list[dict] = []
            hit_keywords: set[str] = set()

            for seg in segments:
                for mr in find_matches(seg.text, keyword_rules):
                    abs_pos = seg.char_offset + mr.position
                    snippet = _make_snippet(seg.text, mr.position)
                    all_matches.append(
                        {
                            "page_id": page_id,
                            "keyword": mr.keyword,
                            "matched_text": mr.matched_text,
                            "tag": seg.tag,
                            "position": abs_pos,
                            "snippet": snippet,
                        }
                    )
                    hit_keywords.add(mr.keyword)

            # -----------------------------------------------------------------
            # 6. Persist matches + mark page complete
            # -----------------------------------------------------------------
            await crud.insert_matches(pool, all_matches)

            keywords_csv = ",".join(sorted(hit_keywords)) or None
            await crud.update_page_completed(
                pool, page_id, len(all_matches), keywords_csv
            )
            await crud.increment_pages_scanned(pool, run_id)

            log.debug(
                "Scanned %s – %d matches across %d keyword(s)",
                url,
                len(all_matches),
                len(hit_keywords),
            )
            return discovered_links

        except httpx.HTTPStatusError as exc:
            notes = f"HTTP {exc.response.status_code}"
            log.warning("HTTP error on %s: %s", url, notes)
            await crud.update_page_failed(pool, page_id, notes)
            await crud.increment_error_count(pool, run_id)
            await crud.increment_pages_scanned(pool, run_id)
            return discovered_links

        except httpx.RequestError as exc:
            notes = f"Request error: {type(exc).__name__}"
            log.warning("Request error on %s: %s", url, exc)
            await crud.update_page_failed(pool, page_id, notes)
            await crud.increment_error_count(pool, run_id)
            await crud.increment_pages_scanned(pool, run_id)
            return []

        except Exception as exc:
            notes = str(exc)[:200]
            log.exception("Unexpected error scanning %s", url)
            await crud.update_page_failed(pool, page_id, notes)
            await crud.increment_error_count(pool, run_id)
            await crud.increment_pages_scanned(pool, run_id)
            return []


# ---------------------------------------------------------------------------
# Main crawl orchestrator
# ---------------------------------------------------------------------------


async def crawl_run(
    run_id: UUID,
    domain: str,
    keywords: list[str],
    excludes: list[str],
    pool: asyncpg.Pool,
) -> None:
    """
    BFS crawl of *domain*.  Meant to run as a long-lived background task.

    Algorithm
    ---------
    1. Mark the run as 'running'.
    2. Seed the BFS queue with the domain's root URL.
    3. Drain the queue in batches of CRAWL_CONCURRENCY, awaiting all tasks in
       each batch before starting the next.  (Semaphore inside _scan_page also
       limits true concurrent HTTP connections.)
    4. Enqueue newly discovered same-host links.
    5. Stop when the queue is empty or MAX_PAGES_PER_RUN is reached.
    6. Mark the run 'completed' or 'failed'.
    """
    log.info("Crawl run %s starting for domain=%s", run_id, domain)

    await crud.start_run(pool, run_id)

    # Ensure the seed URL has a scheme.
    seed = domain if domain.startswith(("http://", "https://")) else f"https://{domain}"
    netloc = urlparse(seed).netloc

    keyword_rules = compile_rules(keywords)
    exclude_rules = compile_rules(excludes)

    visited: set[str] = set()
    queue: deque[str] = deque([_normalise_url(seed)])
    sem = asyncio.Semaphore(settings.crawl_concurrency)

    try:
        async with httpx.AsyncClient(
            headers={"User-Agent": _USER_AGENT},
            timeout=settings.request_timeout,
            follow_redirects=True,
            max_redirects=5,
        ) as client:
            while queue:
                if len(visited) >= settings.max_pages_per_run:
                    log.info(
                        "Run %s reached max_pages_per_run=%d, stopping.",
                        run_id,
                        settings.max_pages_per_run,
                    )
                    break

                # Build the next batch of un-visited URLs.
                batch: list[str] = []
                while queue and len(batch) < settings.crawl_concurrency:
                    url = queue.popleft()
                    norm = _normalise_url(url)
                    if norm in visited:
                        continue
                    visited.add(norm)
                    batch.append(url)

                if not batch:
                    continue

                tasks = [
                    asyncio.create_task(
                        _scan_page(
                            url,
                            run_id,
                            netloc,
                            keyword_rules,
                            exclude_rules,
                            client,
                            pool,
                            sem,
                        )
                    )
                    for url in batch
                ]

                results = await asyncio.gather(*tasks, return_exceptions=True)

                for url, result in zip(batch, results):
                    if isinstance(result, Exception):
                        log.warning("Task-level error for %s: %s", url, result)
                        continue
                    for link in result:  # type: ignore[union-attr]
                        norm = _normalise_url(link)
                        if norm not in visited and _same_host(link, netloc):
                            queue.append(link)

        await crud.finish_run(pool, run_id, success=True)
        log.info("Crawl run %s completed. pages_visited=%d", run_id, len(visited))

    except Exception as exc:
        log.exception("Crawl run %s failed at orchestrator level: %s", run_id, exc)
        await crud.finish_run(pool, run_id, success=False)
