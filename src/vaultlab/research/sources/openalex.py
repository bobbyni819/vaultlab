"""OpenAlex API client — DOI resolution and metadata.

Free, no API key required. OpenAlex is the successor to Microsoft Academic
Graph and indexes ~250M scholarly works (more than CrossRef's ~140M). It
frequently has full author metadata when CrossRef returns sparse results
or when CrossRef's reference array only includes a single author string.

Base URL: https://api.openalex.org/works/

OpenAlex asks API users to identify themselves via ``mailto`` query
parameter (the "polite pool"); we always send it.
"""

from __future__ import annotations

import logging
import time
from typing import Any

import requests

from vaultlab.research.paper import Paper

logger = logging.getLogger(__name__)

_BASE_URL = "https://api.openalex.org/works"
_USER_AGENT = "vaultlab/0.1 (mailto:bobby.ni@duke.edu)"
_MAILTO = "bobby.ni@duke.edu"


class OpenAlexClient:
    """Client for the OpenAlex REST API.

    Used primarily as a metadata-recovery fallback in the author-backfill
    chain. Always sends a polite ``mailto`` parameter so we land in the
    polite request pool (~10 req/sec sustainable).
    """

    def __init__(self, mailto: str = _MAILTO):
        self._mailto = mailto
        self._session = requests.Session()
        self._session.headers["User-Agent"] = _USER_AGENT
        self._last_request_time = 0.0
        self._min_interval = 0.1  # polite pool

    def _rate_limit(self) -> None:
        elapsed = time.time() - self._last_request_time
        if elapsed < self._min_interval:
            time.sleep(self._min_interval - elapsed)
        self._last_request_time = time.time()

    def _get(self, url: str, params: dict | None = None) -> dict[str, Any] | None:
        """GET ``url`` and return the parsed JSON body, or ``None`` on failure."""
        self._rate_limit()
        merged = dict(params or {})
        merged.setdefault("mailto", self._mailto)
        try:
            resp = self._session.get(url, params=merged, timeout=30)
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as exc:
            logger.warning("OpenAlex request failed: %s", exc)
            return None

    def resolve_doi(self, doi: str) -> Paper | None:
        """Resolve a DOI to a :class:`Paper` with full metadata.

        Args:
            doi: DOI string (e.g. ``"10.1083/jcb.200407073"``). Bare DOIs
                only — no ``https://doi.org/`` prefix.

        Returns:
            A :class:`Paper`, or ``None`` if OpenAlex doesn't know the DOI
            or the request fails. Authors are returned as
            ``"Last First"`` strings (matching CrossRef formatting).
        """
        if not doi or not doi.strip():
            return None
        url = f"{_BASE_URL}/doi:{doi.strip()}"
        data = self._get(url)
        if not data:
            return None
        return self._parse_work(data)

    def get_authors_by_doi(self, doi: str) -> list[str] | None:
        """Lookup authors for ``doi``. ``None`` on failure / not-found / empty.

        Convenience wrapper for the backfill chain — returns just the
        author list, suitable for slotting into ``Paper.authors``.
        """
        paper = self.resolve_doi(doi)
        if paper is None:
            return None
        return paper.authors or None

    # ------------------------------------------------------------------
    # Parsing helpers
    # ------------------------------------------------------------------

    def _parse_work(self, item: dict[str, Any]) -> Paper | None:
        """Parse one OpenAlex work object into a :class:`Paper`."""
        try:
            doi_url = item.get("doi") or ""
            # OpenAlex returns DOIs as full URLs (https://doi.org/...);
            # strip the prefix for parity with the rest of the corpus.
            doi = doi_url.replace("https://doi.org/", "").lower()

            title = item.get("title") or item.get("display_name") or ""

            year = int(item.get("publication_year") or 0)

            host = item.get("host_venue") or {}
            primary = item.get("primary_location") or {}
            source_obj = primary.get("source") or {}
            journal = (
                host.get("display_name")
                or source_obj.get("display_name")
                or ""
            )

            return Paper(
                title=title,
                authors=self._parse_authorships(item.get("authorships", [])),
                year=year,
                journal=journal,
                doi=doi,
                abstract=_reconstruct_abstract(
                    item.get("abstract_inverted_index")
                ),
                url=doi_url or item.get("id", ""),
                pdf_url=_pick_pdf_url(item),
                citation_count=int(item.get("cited_by_count") or 0),
                source_api="openalex",
            )
        except Exception as exc:
            logger.debug("Failed to parse OpenAlex work: %s", exc)
            return None

    def _parse_authorships(self, authorships: list[dict]) -> list[str]:
        """Parse OpenAlex ``authorships`` into ``"Last First"`` strings.

        OpenAlex returns ``display_name`` as ``"First Middle Last"``; we
        normalize to CrossRef's ``"Last F"`` style for consistency.
        """
        result: list[str] = []
        for entry in authorships or []:
            author = (entry or {}).get("author") or {}
            display = (author.get("display_name") or "").strip()
            if not display:
                continue
            result.append(_normalize_author_name(display))
        return result


def _normalize_author_name(display: str) -> str:
    """Convert ``"First Middle Last"`` into ``"Last F"`` style.

    Mirrors :func:`vaultlab.research.sources.crossref.CrossRefClient._parse_authors`
    so the corpus has a consistent author format regardless of source.
    Single-token names (initials, consortia) are returned as-is.
    """
    parts = [p for p in display.split() if p]
    if not parts:
        return ""
    if len(parts) == 1:
        return parts[0]
    last = parts[-1]
    first = parts[0]
    if first:
        return f"{last} {first[0]}"
    return last


def _reconstruct_abstract(inverted: dict | None) -> str:
    """Rebuild OpenAlex's inverted-index abstract into plain text.

    OpenAlex returns abstracts as ``{word: [position, position, ...]}``
    to dodge copyright. Reverse the mapping back into a flat string so
    the rest of the pipeline can use it like a normal abstract.
    """
    if not isinstance(inverted, dict) or not inverted:
        return ""
    pos_to_word: dict[int, str] = {}
    for word, positions in inverted.items():
        if not isinstance(positions, list):
            continue
        for pos in positions:
            try:
                pos_to_word[int(pos)] = word
            except (TypeError, ValueError):
                continue
    if not pos_to_word:
        return ""
    ordered = [pos_to_word[i] for i in sorted(pos_to_word.keys())]
    return " ".join(ordered)


def _pick_pdf_url(item: dict[str, Any]) -> str:
    """Return the best open-access PDF URL on the work, or ``""``."""
    primary = item.get("primary_location") or {}
    pdf = primary.get("pdf_url")
    if pdf:
        return pdf
    oa = item.get("open_access") or {}
    return oa.get("oa_url") or ""


__all__ = ["OpenAlexClient"]
