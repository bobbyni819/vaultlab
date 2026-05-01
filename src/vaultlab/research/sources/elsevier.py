"""Elsevier API client — Scopus search, metadata, full-text PDF.

Three Elsevier APIs covered through one ``X-ELS-APIKey`` credential:

* **Scopus Search** — broad cross-publisher search over Elsevier's
  Scopus citation database (~80M records covering ALL major publishers,
  not just Elsevier titles). Returns a real ``citedby-count`` per hit.
  Used as our seed-finding source::

    https://api.elsevier.com/content/search/scopus

* **Article Retrieval** — fetch full-text JSON or PDF for a DOI::

    https://api.elsevier.com/content/article/doi/{doi}

(ScienceDirect Search at ``/content/search/sciencedirect`` is *not*
supported with our current API-key tier — it returns 401
``AUTHORIZATION_ERROR`` for the requested view. Scopus works from the
same key and covers more publishers, so we use Scopus instead.)

For search and basic metadata, the API key alone works from any IP.
For full-text PDF retrieval, **institutional licensing is required** —
the simplest path is to call the API while connected to an institutional
VPN whose IP range Elsevier recognises (e.g. Duke). Without it, the
PDF endpoint returns 401/403 and the article-retrieval JSON omits the
full-text body.
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any

import requests

from vaultlab.research.paper import Paper

logger = logging.getLogger(__name__)

_ARTICLE_BASE = "https://api.elsevier.com/content/article/doi/"
_SCOPUS_SEARCH_BASE = "https://api.elsevier.com/content/search/scopus"


class ElsevierClient:
    """Client for Elsevier ScienceDirect Article Retrieval API."""

    def __init__(self, api_key: str = ""):
        self.api_key = api_key
        self._session = requests.Session()
        self._last_request_time = 0.0
        self._min_interval = 0.3  # conservative rate limit

    def _rate_limit(self) -> None:
        elapsed = time.time() - self._last_request_time
        if elapsed < self._min_interval:
            time.sleep(self._min_interval - elapsed)
        self._last_request_time = time.time()

    def is_configured(self) -> bool:
        return bool(self.api_key)

    def fetch_metadata(self, doi: str) -> dict[str, Any] | None:
        """Fetch article metadata as JSON.  Returns None if not licensed."""
        if not self.api_key:
            logger.debug("Elsevier: no api_key, skipping metadata for %s", doi)
            return None
        url = f"{_ARTICLE_BASE}{doi}"
        headers = {
            "X-ELS-APIKey": self.api_key,
            "Accept": "application/json",
        }
        self._rate_limit()
        try:
            r = self._session.get(url, headers=headers, timeout=30)
            if r.status_code in (401, 403):
                logger.info(
                    "Elsevier: DOI %s not accessible (%d, likely no institutional license)",
                    doi,
                    r.status_code,
                )
                return None
            if r.status_code != 200:
                logger.debug("Elsevier metadata %s → HTTP %d", doi, r.status_code)
                return None
            return r.json()
        except requests.RequestException as e:
            logger.warning("Elsevier metadata request failed for %s: %s", doi, e)
            return None

    def download_pdf(self, doi: str, output_dir: str, filename_hint: str = "") -> str:
        """Download full-text PDF for a DOI.

        Returns path to downloaded PDF, or empty string if not available.
        """
        if not self.api_key:
            return ""
        url = f"{_ARTICLE_BASE}{doi}"
        headers = {
            "X-ELS-APIKey": self.api_key,
            "Accept": "application/pdf",
        }
        self._rate_limit()
        try:
            r = self._session.get(url, headers=headers, timeout=90, allow_redirects=True)
            if r.status_code in (401, 403):
                logger.info(
                    "Elsevier PDF: %s not accessible (%d, no institutional license)",
                    doi,
                    r.status_code,
                )
                return ""
            if r.status_code != 200 or len(r.content) < 1000:
                logger.debug(
                    "Elsevier PDF %s → HTTP %d, size %d", doi, r.status_code, len(r.content)
                )
                return ""
            # Validate it really is a PDF
            if not (
                r.content[:5] == b"%PDF-" or "pdf" in r.headers.get("Content-Type", "").lower()
            ):
                logger.debug(
                    "Elsevier returned non-PDF content-type for %s: %s",
                    doi,
                    r.headers.get("Content-Type", ""),
                )
                return ""
            os.makedirs(output_dir, exist_ok=True)
            base = filename_hint or doi.replace("/", "_").replace(".", "-")
            filepath = os.path.join(output_dir, f"{base[:100]}.pdf")
            with open(filepath, "wb") as f:
                f.write(r.content)
            logger.info("Downloaded Elsevier PDF: %s", filepath)
            return filepath
        except requests.RequestException as e:
            logger.warning("Elsevier PDF request failed for %s: %s", doi, e)
            return ""

    # ------------------------------------------------------------------
    # Scopus Search — adds Elsevier as a (cross-publisher) seed-finding source.
    # ------------------------------------------------------------------

    def search(self, query: str, max_results: int = 50) -> list[Paper]:
        """Search Scopus for ``query`` and return :class:`Paper` rows.

        Uses the Elsevier Scopus Search API. The API key alone is
        sufficient — no institutional licensing or VPN required for
        search/metadata (only for full-text PDF retrieval at the
        Article Retrieval endpoint).

        Scopus is broader than ScienceDirect: it indexes works from
        most major publishers (Springer, Nature, Wiley, ACS, IEEE,
        Elsevier itself), not just Elsevier titles. Each hit comes with
        a real ``citedby-count`` from Scopus's citation database.

        Args:
            query: Free-text query string.
            max_results: Cap on returned hits. Scopus honours ``count``
                up to 25 per page on the standard tier; we issue one
                page request capped at ``min(max_results, 25)``.

        Returns:
            List of :class:`Paper` records with:
            title, authors, year, journal, doi, citation_count, pmid,
            url, source_api="scopus". Empty list on auth failure /
            network error / no hits.
        """
        if not self.api_key:
            logger.debug("Scopus search: no api_key, skipping query %r", query)
            return []
        params: dict[str, Any] = {
            "query": query,
            "count": max(1, min(25, int(max_results))),
        }
        headers = {
            "X-ELS-APIKey": self.api_key,
            "Accept": "application/json",
        }
        self._rate_limit()
        try:
            r = self._session.get(
                _SCOPUS_SEARCH_BASE,
                params=params,
                headers=headers,
                timeout=30,
            )
            if r.status_code in (401, 403):
                logger.info(
                    "Scopus search: %d for query %r (likely auth issue)",
                    r.status_code,
                    query,
                )
                return []
            r.raise_for_status()
            data = r.json()
        except (requests.RequestException, ValueError) as e:
            logger.warning("Scopus search failed for %r: %s", query, e)
            return []

        # Response shape: {"search-results": {"entry": [...]}}
        sr = (data or {}).get("search-results") or {}
        entries = sr.get("entry") or []
        if not isinstance(entries, list):
            return []

        papers: list[Paper] = []
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            doi = (entry.get("prism:doi") or "").strip()
            title = (entry.get("dc:title") or "").strip()
            cover_date = entry.get("prism:coverDate") or ""
            year = 0
            if cover_date and len(cover_date) >= 4 and cover_date[:4].isdigit():
                year = int(cover_date[:4])
            journal = (entry.get("prism:publicationName") or "").strip()
            # Scopus returns a single ``dc:creator`` (the lead author)
            # as a string. Full author list is only available via a
            # follow-up Abstract Retrieval call — we don't make that
            # for every hit.
            authors_raw = entry.get("dc:creator")
            authors: list[str] = []
            if isinstance(authors_raw, str) and authors_raw.strip():
                authors = [authors_raw.strip()]
            elif isinstance(authors_raw, list):
                for a in authors_raw:
                    if isinstance(a, dict):
                        name = a.get("$") or a.get("name")
                        if name:
                            authors.append(str(name))
                    elif isinstance(a, str):
                        authors.append(a)

            citedby = entry.get("citedby-count")
            try:
                citation_count = int(citedby) if citedby is not None else 0
            except (TypeError, ValueError):
                citation_count = 0

            pmid = (entry.get("pubmed-id") or "").strip()

            url = ""
            link = entry.get("link") or []
            if isinstance(link, list):
                for ln in link:
                    if isinstance(ln, dict) and ln.get("@ref") in (
                        "scopus",
                        "scidir",
                    ):
                        url = ln.get("@href") or ""
                        break

            paper = Paper(
                title=title,
                authors=authors,
                year=year,
                journal=journal,
                doi=doi,
                pmid=pmid,
                abstract="",  # Scopus search doesn't include abstracts
                url=url,
                citation_count=citation_count,
                source_api="scopus",
            )
            papers.append(paper)

        logger.info("Scopus search: %d hits for %r", len(papers), query)
        return papers
