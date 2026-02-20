"""
Keyword rule compiler and match finder.

Supported rule formats
----------------------
/pattern/   – arbitrary regular expression (case-insensitive)
word*       – prefix wildcard: matches "word" followed by any word characters
              e.g. "green*" matches "greenwashing", "greentech", "greener" …
word        – whole-word, case-insensitive exact match

All three forms are compiled once per crawl run and reused across every page.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(slots=True)
class MatchResult:
    keyword: str       # original rule string from the request
    matched_text: str  # actual text that was matched in the document
    position: int      # character offset within the segment's text


Rule = tuple[str, re.Pattern[str]]


def compile_rule(keyword: str) -> Rule:
    """Compile a single keyword string into a (keyword, pattern) pair."""
    kw = keyword.strip()

    if kw.startswith("/") and kw.endswith("/") and len(kw) > 2:
        # /regex/ form – use the inner expression verbatim
        pattern = re.compile(kw[1:-1], re.IGNORECASE)
        return (kw, pattern)

    if kw.endswith("*"):
        # prefix wildcard – "green*" → \bgreen\w*
        prefix = re.escape(kw[:-1])
        pattern = re.compile(rf"\b{prefix}\w*", re.IGNORECASE)
        return (kw, pattern)

    # plain token – whole-word exact match
    escaped = re.escape(kw)
    pattern = re.compile(rf"\b{escaped}\b", re.IGNORECASE)
    return (kw, pattern)


def compile_rules(keywords: list[str]) -> list[Rule]:
    """Compile a list of keyword strings, skipping blanks."""
    return [compile_rule(k) for k in keywords if k.strip()]


def find_matches(text: str, rules: list[Rule]) -> list[MatchResult]:
    """
    Return every match for every rule found in *text*.
    Results are ordered by position within the text.
    """
    results: list[MatchResult] = []
    for keyword, pattern in rules:
        for m in pattern.finditer(text):
            results.append(
                MatchResult(
                    keyword=keyword,
                    matched_text=m.group(0),
                    position=m.start(),
                )
            )
    results.sort(key=lambda r: r.position)
    return results


def any_match(text: str, rules: list[Rule]) -> bool:
    """Return True as soon as the first rule hits – short-circuits."""
    return any(pattern.search(text) for _, pattern in rules)
