"""Springer Nature API client using requests directly (no springernature-api-client).

Two APIs:
    Meta API    — lightweight metadata search (fast, less detail)
    Open Access — full text of OA articles (JSON/XML)
"""

from __future__ import annotations

import logging
import time
from typing import Any

import requests

from vaultlab.research.paper import Paper

logger = logging.getLogger(__name__)

_META_BASE = "http://api.springernature.com/meta/v2/json"
_OA_BASE = "http://api.springernature.com/openaccess/json"


class SpringerClient:
    """Client for Springer Nature Meta and Open Access APIs."""

    def __init__(
        self,
        meta_api_key: str = "",
        oa_api_key: str = "",
    ):
        self.meta_api_key = meta_api_key
        self.oa_api_key = oa_api_key
        self._session = requests.Session()
        self._last_request_time = 0.0
        self._min_interval = 0.5  # conservative rate limit

    def _rate_limit(self) -> None:
        """Enforce rate limiting between requests."""
        elapsed = time.time() - self._last_request_time
        if elapsed < self._min_interval:
            time.sleep(self._min_interval - elapsed)
        self._last_request_time = time.time()

    def _get(self, url: str, params: dict, retries: int = 3) -> dict[str, Any] | None:
        """Make a GET request with rate limiting and retry."""
        for attempt in range(retries):
            self._rate_limit()
            try:
                resp = self._session.get(url, params=params, timeout=30)
                # Don't retry on auth errors
                if resp.status_code in (401, 403):
                    logger.warning(
                        "Springer API auth failed (%d). Check API key.", resp.status_code
                    )
                    return None
                resp.raise_for_status()
                return resp.json()
            except requests.RequestException as e:
                if attempt < retries - 1:
                    wait = 2**attempt
                    logger.warning(
                        "Springer request failed (attempt %d/%d): %s. Retrying in %ds...",
                        attempt + 1,
                        retries,
                        e,
                        wait,
                    )
                    time.sleep(wait)
                else:
                    logger.error("Springer request failed after %d attempts: %s", retries, e)
                    raise
        return None

    @property
    def _active_key(self) -> str:
        """Return whichever key is available (prefer meta key)."""
        return self.meta_api_key or self.oa_api_key

    def search(self, query: str, max_results: int = 20) -> list[Paper]:
        """Search Springer Nature Meta API for papers.

        Args:
            query: Search query string.
            max_results: Maximum number of results. Springer's free-tier
                Meta + Open Access APIs cap page-length at 25; values
                >= 30 return HTTP 403 "premium feature." Free-tier callers
                that pass ``max_results=50`` (the unified_search default
                as of 2026-05-01) are silently clamped to 25 here.

        Returns:
            List of Paper objects.
        """
        # Use Meta API if meta key available, otherwise fall back to OA API
        if self.meta_api_key:
            key = self.meta_api_key
            base_url = _META_BASE
        elif self.oa_api_key:
            key = self.oa_api_key
            base_url = _OA_BASE
        else:
            logger.warning("No Springer API key configured, skipping search.")
            return []

        # Free-tier cap: Springer rejects p>=30 with 403 "premium feature".
        # Clamp to 25 to stay safely under the threshold.
        page_length = min(max_results, 25)
        params = {
            "q": query,
            "api_key": key,
            "p": page_length,
            "s": 1,
        }

        data = self._get(base_url, params)
        if not data:
            return []

        records = data.get("records", [])
        if not records:
            logger.info("No Springer results for: %s", query)
            return []

        logger.info("Found %d Springer records for: %s", len(records), query)

        papers = []
        for rec in records[:max_results]:
            paper = self._parse_record(rec)
            if paper:
                papers.append(paper)

        return papers

    def get_open_access(self, doi: str) -> dict[str, Any]:
        """Fetch open access full text for a DOI.

        Args:
            doi: The DOI to look up.

        Returns:
            Full OA response dict, or empty dict if not found/not OA.
        """
        key = self.oa_api_key or self.meta_api_key
        if not key:
            logger.warning("No Springer API key configured.")
            return {}

        params = {
            "q": f'doi:"{doi}"',
            "api_key": key,
        }

        data = self._get(_OA_BASE, params)
        return data if data else {}

    def _parse_record(self, rec: dict[str, Any]) -> Paper | None:
        """Parse a Springer Meta API record into a Paper."""
        try:
            title = rec.get("title", "").strip()

            # Authors — Springer returns list of dicts with "creator" key
            authors = []
            creators = rec.get("creators", [])
            for c in creators:
                name = c.get("creator", "")
                if name:
                    authors.append(name)

            # Year from publicationDate (YYYY-MM-DD)
            year = 0
            pub_date = rec.get("publicationDate", "")
            if pub_date and len(pub_date) >= 4:
                try:
                    year = int(pub_date[:4])
                except ValueError:
                    pass

            # Journal
            journal = rec.get("publicationName", "")

            # DOI
            doi = rec.get("doi", "")

            # Abstract — Meta API returns string, OA API returns dict {"h1":..., "p":...}
            raw_abstract = rec.get("abstract", "")
            if isinstance(raw_abstract, dict):
                abstract = raw_abstract.get("p", "")
                if isinstance(abstract, list):
                    abstract = " ".join(str(p) for p in abstract)
                abstract = str(abstract).strip()
            elif isinstance(raw_abstract, str):
                abstract = raw_abstract.strip()
            else:
                abstract = ""

            # URL
            url = ""
            urls = rec.get("url", [])
            if isinstance(urls, list):
                for u in urls:
                    if isinstance(u, dict):
                        url = u.get("value", "")
                        break
            elif isinstance(urls, str):
                url = urls
            if not url and doi:
                url = f"https://doi.org/{doi}"

            # PDF URL from openAccess links
            pdf_url = ""
            if rec.get("openaccess") == "true" and doi:
                pdf_url = f"https://link.springer.com/content/pdf/{doi}.pdf"

            return Paper(
                title=title,
                authors=authors,
                year=year,
                journal=journal,
                doi=doi,
                abstract=abstract,
                url=url,
                pdf_url=pdf_url,
                source_api="springer",
            )

        except Exception as e:
            logger.error("Error parsing Springer record: %s", e)
            return None
