"""
Database helpers – thin wrappers around raw asyncpg queries.

All functions accept an asyncpg Pool (or Connection) as their first argument
so they can be composed inside transactions when needed.
"""

from __future__ import annotations

from uuid import UUID

import asyncpg


# ---------------------------------------------------------------------------
# crawl_runs
# ---------------------------------------------------------------------------


async def create_run(pool: asyncpg.Pool, domain: str, created_by: str) -> UUID:
    row = await pool.fetchrow(
        """
        INSERT INTO crawl_runs (domain, created_by, status)
        VALUES ($1, $2, 'pending')
        RETURNING id
        """,
        domain,
        created_by,
    )
    return row["id"]


async def start_run(pool: asyncpg.Pool, run_id: UUID) -> None:
    await pool.execute(
        """
        UPDATE crawl_runs
        SET status = 'running', started_at = NOW()
        WHERE id = $1
        """,
        run_id,
    )


async def finish_run(pool: asyncpg.Pool, run_id: UUID, *, success: bool) -> None:
    status = "completed" if success else "failed"
    await pool.execute(
        """
        UPDATE crawl_runs
        SET status = $2, finished_at = NOW()
        WHERE id = $1
        """,
        run_id,
        status,
    )


async def increment_pages_found(pool: asyncpg.Pool, run_id: UUID, count: int = 1) -> None:
    await pool.execute(
        "UPDATE crawl_runs SET pages_found = pages_found + $2 WHERE id = $1",
        run_id,
        count,
    )


async def increment_pages_scanned(pool: asyncpg.Pool, run_id: UUID) -> None:
    await pool.execute(
        "UPDATE crawl_runs SET pages_scanned = pages_scanned + 1 WHERE id = $1",
        run_id,
    )


async def increment_error_count(pool: asyncpg.Pool, run_id: UUID) -> None:
    await pool.execute(
        "UPDATE crawl_runs SET error_count = error_count + 1 WHERE id = $1",
        run_id,
    )


async def list_runs(pool: asyncpg.Pool) -> list[dict]:
    rows = await pool.fetch("SELECT * FROM crawl_runs ORDER BY created_at DESC")
    return [dict(r) for r in rows]


async def get_run(pool: asyncpg.Pool, run_id: UUID) -> dict | None:
    row = await pool.fetchrow("SELECT * FROM crawl_runs WHERE id = $1", run_id)
    return dict(row) if row else None


# ---------------------------------------------------------------------------
# pages
# ---------------------------------------------------------------------------


async def insert_page(pool: asyncpg.Pool, run_id: UUID, url: str) -> UUID | None:
    """
    Insert a page row.  Returns the new UUID, or None if the (run_id, url)
    pair already exists (ON CONFLICT DO NOTHING).
    """
    row = await pool.fetchrow(
        """
        INSERT INTO pages (run_id, url, status)
        VALUES ($1, $2, 'pending')
        ON CONFLICT ON CONSTRAINT idx_pages_run_id_url DO NOTHING
        RETURNING id
        """,
        run_id,
        url,
    )
    return row["id"] if row else None


async def update_page_scanning(pool: asyncpg.Pool, page_id: UUID) -> None:
    await pool.execute(
        "UPDATE pages SET status = 'scanning' WHERE id = $1",
        page_id,
    )


async def update_page_completed(
    pool: asyncpg.Pool,
    page_id: UUID,
    total_hits: int,
    keywords_csv: str | None,
) -> None:
    await pool.execute(
        """
        UPDATE pages
        SET status          = 'completed',
            total_hits      = $2,
            keywords_csv    = $3,
            last_scanned_at = NOW()
        WHERE id = $1
        """,
        page_id,
        total_hits,
        keywords_csv,
    )


async def update_page_skipped(pool: asyncpg.Pool, page_id: UUID, notes: str) -> None:
    await pool.execute(
        "UPDATE pages SET status = 'skipped', notes = $2 WHERE id = $1",
        page_id,
        notes,
    )


async def update_page_failed(pool: asyncpg.Pool, page_id: UUID, notes: str) -> None:
    await pool.execute(
        "UPDATE pages SET status = 'failed', notes = $2 WHERE id = $1",
        page_id,
        notes,
    )


async def list_pages(pool: asyncpg.Pool, run_id: UUID) -> list[dict]:
    rows = await pool.fetch(
        "SELECT * FROM pages WHERE run_id = $1 ORDER BY url",
        run_id,
    )
    return [dict(r) for r in rows]


async def get_page(pool: asyncpg.Pool, page_id: UUID) -> dict | None:
    row = await pool.fetchrow("SELECT * FROM pages WHERE id = $1", page_id)
    return dict(row) if row else None


# ---------------------------------------------------------------------------
# page_matches
# ---------------------------------------------------------------------------


async def insert_matches(pool: asyncpg.Pool, matches: list[dict]) -> None:
    """Bulk-insert a list of match dicts in a single round-trip."""
    if not matches:
        return
    await pool.executemany(
        """
        INSERT INTO page_matches (page_id, keyword, matched_text, tag, position, snippet)
        VALUES ($1, $2, $3, $4, $5, $6)
        """,
        [
            (
                m["page_id"],
                m["keyword"],
                m["matched_text"],
                m["tag"],
                m["position"],
                m["snippet"],
            )
            for m in matches
        ],
    )


async def list_matches(pool: asyncpg.Pool, page_id: UUID) -> list[dict]:
    rows = await pool.fetch(
        "SELECT * FROM page_matches WHERE page_id = $1 ORDER BY position",
        page_id,
    )
    return [dict(r) for r in rows]
