"""bioRxiv/medRxiv API client — preprint search.

Base URL: https://api.biorxiv.org/details/
Content API: https://api.biorxiv.org/pubs/
Free, no API key required.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta
from typing import Any

import requests

from vaultlab.research.paper import Paper

logger = logging.getLogger(__name__)

_DETAILS_BASE = "https://api.biorxiv.org/details"
_PUBS_BASE = "https://api.biorxiv.org/pubs"


class BioRxivClient:
    """Client for the bioRxiv/medRxiv API."""

    def __init__(self, server: str = "biorxiv"):
        """Initialize client.

        Args:
            server: "biorxiv" or "medrxiv"
        """
        self.server = server
        self._base_url = f"{_DETAILS_BASE}/{server}"
        self._session = requests.Session()
        self._last_request_time = 0.0
        self._min_interval = 0.5

    def _rate_limit(self) -> None:
        elapsed = time.time() - self._last_request_time
        if elapsed < self._min_interval:
            time.sleep(self._min_interval - elapsed)
        self._last_request_time = time.time()

    def _get(self, url: str) -> dict[str, Any] | None:
        """Make a GET request with rate limiting."""
        self._rate_limit()
        try:
            resp = self._session.get(url, timeout=30)
            if resp.status_code != 200:
                return None
            return resp.json()
        except requests.RequestException as e:
            logger.warning("bioRxiv request failed: %s", e)
            return None

    def search(self, query: str, max_results: int = 20, days_back: int = 365) -> list[Paper]:
        """Search recent preprints by date range.

        The bioRxiv API doesn't have keyword search — it returns papers
        by date range. We fetch recent papers and filter client-side.

        Args:
            query: Search terms (filtered client-side).
            max_results: Maximum results.
            days_back: How many days back to search.

        Returns:
            List of matching Paper objects.
        """
        end = datetime.now().strftime("%Y-%m-%d")
        start = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")
        url = f"{self._base_url}/{start}/{end}/0/100"

        data = self._get(url)
        if not data:
            return []

        collection = data.get("collection", [])
        if not collection:
            return []

        # Client-side keyword filtering
        query_lower = query.lower()
        query_terms = query_lower.split()
        papers = []
        for item in collection:
            text = f"{item.get('title', '')} {item.get('abstract', '')}".lower()
            if all(term in text for term in query_terms):
                paper = self._parse_item(item)
                if paper:
                    papers.append(paper)
                    if len(papers) >= max_results:
                        break

        return papers

    def get_paper(self, doi: str) -> Paper | None:
        """Get a specific preprint by DOI.

        Args:
            doi: bioRxiv DOI (e.g., "10.1101/2024.01.15.575555")

        Returns:
            Paper or None.
        """
        # Use the details endpoint with the DOI
        url = f"{self._base_url}/{doi}/na/na"
        data = self._get(url)
        if not data:
            return None

        collection = data.get("collection", [])
        if not collection:
            return None

        return self._parse_item(collection[0])

    def _parse_item(self, item: dict[str, Any]) -> Paper | None:
        """Parse a bioRxiv item into a Paper."""
        try:
            doi = item.get("biorxiv_doi") or item.get("preprint_doi", "")
            date_str = item.get("date", "")
            year = int(date_str[:4]) if date_str and len(date_str) >= 4 else 0

            return Paper(
                title=item.get("title", ""),
                authors=self._parse_authors(item.get("authors", "")),
                year=year,
                journal=f"{self.server} preprint",
                doi=doi,
                abstract=item.get("abstract", ""),
                url=f"https://doi.org/{doi}" if doi else "",
                pdf_url=f"https://www.biorxiv.org/content/{doi}v1.full.pdf" if doi else "",
                source_api=self.server,
            )
        except Exception as e:
            logger.debug("Failed to parse bioRxiv item: %s", e)
            return None

    def _parse_authors(self, authors_str: str | None) -> list[str]:
        """Parse 'Last, F.; Last2, F2.' into ['Last F', 'Last2 F2']."""
        if not authors_str:
            return []
        authors = []
        for part in authors_str.split(";"):
            part = part.strip().rstrip(".")
            if not part:
                continue
            # "Smith, J." -> "Smith J"
            pieces = [p.strip().rstrip(".") for p in part.split(",", 1)]
            authors.append(" ".join(pieces))
        return authors
