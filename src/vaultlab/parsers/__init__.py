"""Output parsers for agent responses.

The Critic produces ROBUST/NEEDS_VALIDATION/WEAK/UNSUPPORTED ratings in
free-form markdown. Every slash command needs to turn those into
structured updates against the session. This module centralises that
parsing so regex lives in one place.

Lifted from ``bobby_ailab._parsers`` — behaviourally identical apart from
namespace.

Public surface
--------------

* :func:`parse_critic_ratings` — extract ``{finding_id: rating}``
* :func:`parse_finding_ratings` — same, constrained to known IDs
* :func:`parse_next_round_tests` — extract priority-tagged Critic tests
* :func:`summarize_ratings` / :func:`summarize_tests` — one-line summaries
* :data:`ALL_RATINGS`, :data:`PRIORITY_LEVELS` — vocabulary constants
"""

from __future__ import annotations

import re
from typing import Optional

_RATING_WORDS_DATA = ("ROBUST", "NEEDS_VALIDATION", "WEAK", "UNSUPPORTED", "NEEDS_FOLLOWUP")
_RATING_WORDS_LIT = (
    "STRONG_CONSENSUS",
    "EMERGING_EVIDENCE",
    "SINGLE_STUDY",
    "CONTESTED",
)
ALL_RATINGS = _RATING_WORDS_DATA + _RATING_WORDS_LIT


# Matches finding IDs like F001, F023, etc. — the stable slug from /research-reason
_FINDING_ID_RE = re.compile(r"\bF\d{3,4}\b")

# Matches "Rating: ROBUST" or "**Rating:** ROBUST" or similar, on a single line
_RATING_LINE_RE = re.compile(r"(?i)\*{0,2}\s*rating\s*:?\s*\*{0,2}\s*([A-Z_]+)")


def parse_critic_ratings(text: str) -> dict[str, str]:
    """Extract ``{finding_id: rating}`` from Critic markdown output.

    Strategy:

    1. Split the text into per-finding sections (each starts with an H2/H3
       that contains a finding ID or the keyword "Finding").
    2. In each section, find the first ``Rating:`` line and extract the
       rating keyword.
    3. If the section heading has a finding ID, use that; otherwise fall
       back to an ordinal key like ``"F_1"``, ``"F_2"`` so downstream
       code can still map positionally.

    Returns an empty dict if no ratings are parsed — callers should treat
    that as a failed round, not a valid empty result.
    """
    sections = _split_into_finding_sections(text)
    ratings: dict[str, str] = {}
    for index, (heading, body) in enumerate(sections, start=1):
        rating = _find_rating_in(body)
        if rating is None:
            continue
        finding_id = _extract_finding_id(heading)
        if finding_id is None:
            finding_id = f"F_{index}"
        ratings[finding_id] = rating
    return ratings


def parse_finding_ratings(text: str, known_ids: list[str]) -> dict[str, str]:
    """Same as :func:`parse_critic_ratings` but constrained to known IDs.

    If a section heading contains a finding ID not in ``known_ids``, it is
    dropped. Ordinal fallbacks are mapped into ``known_ids`` in encounter
    order so positional parsing still works with a known-count session.
    """
    ordinal_fallbacks = iter(known_ids)
    known_set = set(known_ids)
    sections = _split_into_finding_sections(text)
    ratings: dict[str, str] = {}
    for heading, body in sections:
        rating = _find_rating_in(body)
        if rating is None:
            continue
        fid = _extract_finding_id(heading)
        if fid is not None:
            if fid in known_set:
                ratings[fid] = rating
            # unknown ID — skip
            continue
        # No explicit ID — use ordinal fallback
        try:
            fallback_id = next(ordinal_fallbacks)
            ratings[fallback_id] = rating
        except StopIteration:
            break
    return ratings


def _split_into_finding_sections(text: str) -> list[tuple[str, str]]:
    """Split markdown by H2/H3 headings whose title suggests a finding."""
    lines = text.splitlines()
    sections: list[tuple[str, str]] = []
    current_heading = ""
    current_body: list[str] = []
    heading_re = re.compile(r"^#{2,4}\s+(.+)$")
    for line in lines:
        m = heading_re.match(line)
        if m:
            heading_text = m.group(1).strip()
            if _looks_like_finding_heading(heading_text):
                if current_heading:
                    sections.append((current_heading, "\n".join(current_body)))
                current_heading = heading_text
                current_body = []
                continue
        if current_heading:
            current_body.append(line)
    if current_heading:
        sections.append((current_heading, "\n".join(current_body)))
    return sections


def _looks_like_finding_heading(heading: str) -> bool:
    lowered = heading.lower()
    if _FINDING_ID_RE.search(heading):
        return True
    return lowered.startswith("finding ") or lowered.startswith("finding:")


def _find_rating_in(body: str) -> str | None:
    for match in _RATING_LINE_RE.finditer(body):
        candidate = match.group(1).upper().strip()
        if candidate in ALL_RATINGS:
            return candidate
    # Fallback: any rating word alone on a line
    for line in body.splitlines():
        stripped = line.strip().strip("*").strip()
        if stripped.upper() in ALL_RATINGS:
            return stripped.upper()
    return None


def _extract_finding_id(heading: str) -> str | None:
    m = _FINDING_ID_RE.search(heading)
    return m.group(0) if m else None


def summarize_ratings(ratings: dict[str, str]) -> str:
    """One-line summary of a rating map, useful for progress reporting."""
    if not ratings:
        return "no ratings parsed"
    counts: dict[str, int] = {}
    for r in ratings.values():
        counts[r] = counts.get(r, 0) + 1
    parts = [f"{count} {rating}" for rating, count in sorted(counts.items())]
    return ", ".join(parts)


PRIORITY_LEVELS = ("CRITICAL", "HIGH", "MEDIUM", "LOW")


# Match a numbered list item with an optional bracketed priority tag:
#   "1. [CRITICAL] Recompute aggregate at K=50 ..."
#   "2. [HIGH] Permutation null for ..."
#   "3. **[MEDIUM]** Some test"
_PRIORITY_ITEM_RE = re.compile(
    r"^\s*(?:\d+\.|[-*])\s*\**\s*\[(?P<priority>CRITICAL|HIGH|MEDIUM|LOW)\]\**\s*(?P<rest>.+?)$",
    re.IGNORECASE,
)


def parse_next_round_tests(text: str) -> list[dict]:
    """Extract priority-tagged next-round test recommendations from Critic output.

    Finds lines like ``1. [CRITICAL] Recompute aggregate at K=50 ...`` under
    any section (typically "Priority next-round checks" or "Fix
    instructions") and returns them as structured records. Round 2 agenda
    builders consume this directly: each record becomes an agenda question
    + optional rule.

    Returns a list of dicts, ordered by appearance, each with:

    - ``priority``:    ``CRITICAL`` / ``HIGH`` / ``MEDIUM`` / ``LOW`` (uppercased)
    - ``description``: the first line of the test description (~one sentence)
    - ``detail``:      any continuation lines (may be empty)
    - ``position``:    line number in the source text (1-based)
    """
    lines = text.splitlines()
    records: list[dict] = []
    current: dict | None = None
    for i, line in enumerate(lines, start=1):
        match = _PRIORITY_ITEM_RE.match(line)
        if match:
            if current is not None:
                records.append(current)
            current = {
                "priority": match.group("priority").upper(),
                "description": match.group("rest").strip(),
                "detail": "",
                "position": i,
            }
            continue
        # continuation lines — indented or empty-blank then break
        if current is not None:
            stripped = line.rstrip()
            if not stripped:
                # blank line ends continuation
                records.append(current)
                current = None
                continue
            # indented or continued text
            if line.startswith((" ", "\t")):
                current["detail"] = (
                    current["detail"] + "\n" if current["detail"] else ""
                ) + line.strip()
                continue
            # non-blank, non-indented line ends the current record
            records.append(current)
            current = None
    if current is not None:
        records.append(current)
    return records


def summarize_tests(records: list[dict]) -> str:
    """One-line summary of parsed priority tests, useful for progress reporting."""
    if not records:
        return "no tests parsed"
    counts: dict[str, int] = {}
    for r in records:
        counts[r["priority"]] = counts.get(r["priority"], 0) + 1
    return ", ".join(f"{counts[p]} {p}" for p in PRIORITY_LEVELS if p in counts)


__all__ = [
    "ALL_RATINGS",
    "PRIORITY_LEVELS",
    "parse_critic_ratings",
    "parse_finding_ratings",
    "parse_next_round_tests",
    "summarize_ratings",
    "summarize_tests",
]
