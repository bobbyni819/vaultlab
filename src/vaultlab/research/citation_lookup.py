"""Citation lookup helpers for the literature-search v2 corpus layer.

This module centralizes the HTTP calls used to build a citation graph:

* :func:`get_references_via_crossref` — backward-references for a DOI from
  CrossRef. CrossRef is the citation-graph backbone: it's free, no key, and
  empirically returns ~95% of references for paywalled biomedical papers.
* :func:`get_citations_via_s2` — forward citations from Semantic Scholar.
  Used when S2 has the paper indexed (S2 has gaps for newer / niche work).
* :func:`get_influential_count_via_s2` — Semantic Scholar's
  ``citationCount`` and ``influentialCitationCount`` overlay.

All functions emit a polite User-Agent (with mailto) and raise
:class:`RateLimitError` on HTTP 429 so callers can back off — they do not
silently swallow rate-limit errors.

The PDF-extraction fallback (when CrossRef has no refs) is intentionally NOT
implemented here; callers should record ``references=None`` and let a later
PDF-reading task fill the gap.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

import requests

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

USER_AGENT = "vaultlab/0.1 (mailto:bobby.ni@duke.edu)"
"""Polite User-Agent string for all citation-lookup HTTP calls."""

CROSSREF_BASE = "https://api.crossref.org/works"
S2_BASE = "https://api.semanticscholar.org/graph/v1"

_DEFAULT_TIMEOUT = 30.0
_DEFAULT_S2_FIELDS = "title,authors,year,venue,externalIds,citationCount,influentialCitationCount"


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass
class Reference:
    """A single citation edge target.

    A ``Reference`` is intentionally lightweight: just enough to identify
    the cited paper and slot it into a citation graph. Use
    :class:`vaultlab.research.paper.Paper` for full metadata.

    Attributes:
        doi: DOI of the referenced paper (empty string if unknown — CrossRef
            populates DOI for ~95% of refs).
        title: Title (CrossRef calls this ``article-title``; may be empty).
        year: Publication year (0 if unknown).
        authors: List of author strings; CrossRef typically gives just one
            ``author`` field as a string, not a list.
    """

    doi: str = ""
    title: str = ""
    year: int = 0
    authors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "doi": self.doi,
            "title": self.title,
            "year": self.year,
            "authors": list(self.authors),
        }


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class CitationLookupError(Exception):
    """Base class for citation-lookup errors."""


class RateLimitError(CitationLookupError):
    """Raised when an upstream API returns HTTP 429 (rate limited).

    Callers should back off (e.g. exponential delay) before retrying.
    """

    def __init__(self, source: str, retry_after: float | None = None):
        self.source = source
        self.retry_after = retry_after
        msg = f"{source} rate-limited the request"
        if retry_after is not None:
            msg += f" (retry after {retry_after}s)"
        super().__init__(msg)


# ---------------------------------------------------------------------------
# CrossRef — backward references (citation-graph backbone)
# ---------------------------------------------------------------------------


def _get_json(
    url: str,
    *,
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout: float = _DEFAULT_TIMEOUT,
    source: str = "crossref",
) -> dict[str, Any] | None:
    """GET ``url`` and return the parsed JSON ``message`` body.

    Returns ``None`` on HTTP 404 (paper not in the source). Raises
    :class:`RateLimitError` on HTTP 429 so callers can back off.
    """
    merged_headers = {"User-Agent": USER_AGENT}
    if headers:
        merged_headers.update(headers)
    try:
        resp = requests.get(url, params=params, headers=merged_headers, timeout=timeout)
    except requests.RequestException as exc:
        logger.warning("%s request failed: %s", source, exc)
        return None

    if resp.status_code == 404:
        return None
    if resp.status_code == 429:
        retry_after_header = resp.headers.get("Retry-After")
        retry_after: float | None
        try:
            retry_after = float(retry_after_header) if retry_after_header else None
        except ValueError:
            retry_after = None
        raise RateLimitError(source, retry_after=retry_after)

    try:
        resp.raise_for_status()
    except requests.HTTPError as exc:
        logger.warning("%s HTTP error: %s", source, exc)
        return None

    try:
        return resp.json()
    except ValueError as exc:
        logger.warning("%s returned non-JSON: %s", source, exc)
        return None


def _parse_crossref_reference(raw: dict[str, Any]) -> Reference:
    """Parse one entry from a CrossRef ``reference`` array into a Reference.

    CrossRef reference entries are small dicts; the most useful fields are
    ``DOI`` and ``article-title`` (or ``volume-title`` for books). The
    ``year`` is in ``year``, and ``author`` is a single name string (often
    just the family name).
    """
    doi = (raw.get("DOI") or "").strip().lower()
    # CrossRef sometimes uses 'article-title', 'volume-title', or
    # 'series-title' — fall through in priority order.
    title = (
        raw.get("article-title")
        or raw.get("volume-title")
        or raw.get("series-title")
        or ""
    )
    year_str = raw.get("year") or ""
    try:
        year = int(year_str) if year_str else 0
    except (TypeError, ValueError):
        year = 0

    author = raw.get("author") or ""
    authors = [author] if author else []

    return Reference(doi=doi, title=title, year=year, authors=authors)


def get_references_via_crossref(
    doi: str,
    *,
    timeout: float = _DEFAULT_TIMEOUT,
) -> list[Reference] | None:
    """Fetch the backward-references for ``doi`` from CrossRef.

    Args:
        doi: The DOI to look up (e.g. ``"10.1126/science.1225829"``).
        timeout: HTTP timeout in seconds.

    Returns:
        A list of :class:`Reference` objects (possibly empty if CrossRef has
        the work but no ``reference`` array), or ``None`` if CrossRef does
        not have the DOI at all (HTTP 404 / network failure / no message).

    Raises:
        RateLimitError: If CrossRef returns HTTP 429.
    """
    if not doi or not doi.strip():
        return None
    url = f"{CROSSREF_BASE}/{doi.strip()}"
    data = _get_json(url, timeout=timeout, source="crossref")
    if data is None:
        return None
    message = data.get("message")
    if not isinstance(message, dict):
        return None
    refs_raw = message.get("reference")
    if not isinstance(refs_raw, list):
        # The work exists but has no reference array — this is the case
        # where the PDF-reading fallback should kick in.
        return None
    return [_parse_crossref_reference(r) for r in refs_raw if isinstance(r, dict)]


# ---------------------------------------------------------------------------
# Semantic Scholar — forward citations + influential count overlay
# ---------------------------------------------------------------------------


def _s2_headers(api_key: str | None) -> dict[str, str]:
    """Headers for Semantic Scholar requests (key is optional)."""
    headers: dict[str, str] = {}
    if api_key:
        headers["x-api-key"] = api_key
    return headers


def _parse_s2_paper_as_reference(raw: dict[str, Any]) -> Reference:
    """Parse an S2 paper object into a lightweight :class:`Reference`."""
    ext_ids = raw.get("externalIds") or {}
    doi = (ext_ids.get("DOI") or "").lower()
    title = raw.get("title") or ""
    year_val = raw.get("year") or 0
    try:
        year = int(year_val) if year_val else 0
    except (TypeError, ValueError):
        year = 0
    authors = []
    for author_obj in raw.get("authors", []) or []:
        name = (author_obj or {}).get("name", "")
        if name:
            authors.append(name)
    return Reference(doi=doi, title=title, year=year, authors=authors)


def get_citations_via_s2(
    doi: str,
    limit: int = 100,
    *,
    api_key: str | None = None,
    timeout: float = _DEFAULT_TIMEOUT,
) -> list[Reference]:
    """Fetch forward citations (papers that cite ``doi``) from Semantic Scholar.

    Args:
        doi: The DOI to look up.
        limit: Max number of citing papers to return (S2 caps at 1000).
        api_key: Optional S2 API key for the higher rate-limit pool.
        timeout: HTTP timeout in seconds.

    Returns:
        A list of :class:`Reference` objects, possibly empty.

    Raises:
        RateLimitError: If S2 returns HTTP 429.
    """
    if not doi or not doi.strip():
        return []
    url = f"{S2_BASE}/paper/DOI:{doi.strip()}/citations"
    params = {"fields": _DEFAULT_S2_FIELDS, "limit": min(max(int(limit), 1), 1000)}
    data = _get_json(
        url,
        params=params,
        headers=_s2_headers(api_key),
        timeout=timeout,
        source="semantic_scholar",
    )
    if data is None:
        return []
    out: list[Reference] = []
    for entry in data.get("data", []) or []:
        citing = (entry or {}).get("citingPaper") or {}
        if citing:
            out.append(_parse_s2_paper_as_reference(citing))
    return out


def get_influential_count_via_s2(
    doi: str,
    *,
    api_key: str | None = None,
    timeout: float = _DEFAULT_TIMEOUT,
) -> tuple[int, int] | None:
    """Fetch ``(citation_count, influential_citation_count)`` from Semantic Scholar.

    Args:
        doi: The DOI to look up.
        api_key: Optional S2 API key.
        timeout: HTTP timeout in seconds.

    Returns:
        ``(citation_count, influential_citation_count)`` or ``None`` if S2
        does not have the paper.

    Raises:
        RateLimitError: If S2 returns HTTP 429.
    """
    if not doi or not doi.strip():
        return None
    url = f"{S2_BASE}/paper/DOI:{doi.strip()}"
    params = {"fields": "citationCount,influentialCitationCount"}
    data = _get_json(
        url,
        params=params,
        headers=_s2_headers(api_key),
        timeout=timeout,
        source="semantic_scholar",
    )
    if data is None:
        return None
    citation_count = int(data.get("citationCount") or 0)
    influential = int(data.get("influentialCitationCount") or 0)
    return citation_count, influential


# ---------------------------------------------------------------------------
# Polite back-off helper (exposed so callers can reuse the same logic)
# ---------------------------------------------------------------------------


def back_off(error: RateLimitError, *, default: float = 2.0, cap: float = 30.0) -> None:
    """Sleep for ``error.retry_after`` (or a sensible default) up to ``cap`` s."""
    delay = error.retry_after if error.retry_after is not None else default
    delay = min(max(delay, 0.0), cap)
    if delay > 0:
        logger.info("Backing off %.1fs after %s rate limit", delay, error.source)
        time.sleep(delay)


__all__ = [
    "CROSSREF_BASE",
    "CitationLookupError",
    "RateLimitError",
    "Reference",
    "S2_BASE",
    "USER_AGENT",
    "back_off",
    "get_citations_via_s2",
    "get_influential_count_via_s2",
    "get_references_via_crossref",
]
