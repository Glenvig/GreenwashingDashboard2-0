"""
HTML content extractor.

Produces a list of TextSegment objects – one per "leaf" block element – that
carry the visible text, the HTML tag name, and an absolute character offset
so that match positions can be stored relative to the whole page.

Design mirrors the original Python crawler:
  • Only text inside ALLOWED_TAGS is indexed.
  • Entire sub-trees rooted at EXCLUDED_CONTAINERS are dropped before walking.
  • Nested allowed tags are not double-counted: only the outermost allowed
    ancestor in any branch emits a segment.
"""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup, Tag


# ---------------------------------------------------------------------------
# Tag sets
# ---------------------------------------------------------------------------

ALLOWED_TAGS: frozenset[str] = frozenset(
    {
        # Block-level content
        "p", "pre", "blockquote",
        # Headings
        "h1", "h2", "h3", "h4", "h5", "h6",
        # Lists
        "li", "dt", "dd",
        # Table cells
        "td", "th", "caption",
        # Generic containers that are direct leaf-level text holders
        "article", "section", "main",
        # Inline – only collected when they are the *outermost* allowed parent
        "a", "span", "strong", "em", "b", "i", "u", "label", "div",
        # Misc
        "q", "figcaption",
    }
)

# Sub-trees rooted at these tags are stripped from the document entirely.
EXCLUDED_CONTAINERS: frozenset[str] = frozenset(
    {"nav", "header", "footer", "aside", "script", "style", "noscript", "template"}
)


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class TextSegment:
    text: str         # visible text of the element (whitespace-normalised)
    tag: str          # lowercase HTML tag name
    char_offset: int  # absolute offset within the concatenated page text


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def extract_segments(html: str) -> list[TextSegment]:
    """
    Parse *html* and return one TextSegment per meaningful leaf block.

    The char_offset of each segment reflects where that segment's text would
    appear if all segment texts were joined with a single space.
    """
    soup = BeautifulSoup(html, "lxml")

    # Strip excluded containers first so their content never reaches us.
    for tag_name in EXCLUDED_CONTAINERS:
        for el in soup.find_all(tag_name):
            el.decompose()

    segments: list[TextSegment] = []
    running_offset = 0

    for el in soup.find_all(ALLOWED_TAGS):
        if not isinstance(el, Tag):
            continue

        # Skip if any ancestor is also an allowed tag – that ancestor will
        # emit this text as part of its own segment.
        if _has_allowed_ancestor(el):
            continue

        text = el.get_text(separator=" ", strip=True)
        # Collapse internal whitespace runs to a single space.
        text = " ".join(text.split())
        if not text:
            continue

        segments.append(TextSegment(text=text, tag=el.name, char_offset=running_offset))
        running_offset += len(text) + 1  # +1 for the inter-segment space

    return segments


def extract_links(html: str, base_url: str) -> list[str]:
    """
    Return all same-host <a href> URLs found in *html*, resolved against
    *base_url* and with fragments stripped.
    """
    soup = BeautifulSoup(html, "lxml")
    base_parsed = urlparse(base_url)
    seen: set[str] = set()
    links: list[str] = []

    for a in soup.find_all("a", href=True):
        href: str = a["href"].strip()
        if not href or href.startswith(("#", "javascript:", "mailto:", "tel:")):
            continue

        full = urljoin(base_url, href)
        parsed = urlparse(full)

        if parsed.scheme not in ("http", "https"):
            continue
        if parsed.netloc != base_parsed.netloc:
            continue

        # Normalise: drop fragment, keep query string
        normalised = parsed._replace(fragment="").geturl().rstrip("/")
        if normalised not in seen:
            seen.add(normalised)
            links.append(normalised)

    return links


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _has_allowed_ancestor(el: Tag) -> bool:
    """True if any ancestor tag is in ALLOWED_TAGS."""
    for parent in el.parents:
        if not isinstance(parent, Tag):
            continue
        if parent.name in ALLOWED_TAGS:
            return True
    return False
