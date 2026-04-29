"""CrossRef API client — DOI resolution and metadata search.

Free, no API key required. Uses the polite pool (mailto in User-Agent).
Base URL: https://api.crossref.org/works/
"""

from __future__ import annotations

import logging
import re
import time
from typing import Any

import requests

from vaultlab.research.paper import Paper

logger = logging.getLogger(__name__)

_BASE_URL = "https://api.crossref.org/works"
_USER_AGENT = "bobby-research/1.0 (mailto:bobby@bobby-tools.local)"


class CrossRefClient:
    """Client for the CrossRef REST API."""

    def __init__(self):
        self._session = requests.Session()
        self._session.headers["User-Agent"] = _USER_AGENT
        self._last_request_time = 0.0
        self._min_interval = 0.2  # polite pool allows ~50 req/sec with mailto

    def _rate_limit(self) -> None:
        elapsed = time.time() - self._last_request_time
        if elapsed < self._min_interval:
            time.sleep(self._min_interval - elapsed)
        self._last_request_time = time.time()

    def _get(self, url: str, params: dict | None = None) -> dict[str, Any] | None:
        """Make a GET request with rate limiting."""
        self._rate_limit()
        try:
            resp = self._session.get(url, params=params, timeout=30)
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            data = resp.json()
            return data.get("message")
        except requests.RequestException as e:
            logger.warning("CrossRef request failed: %s", e)
            return None

    def resolve_doi(self, doi: str) -> Paper | None:
        """Resolve a DOI to a Paper with metadata.

        Args:
            doi: DOI string (e.g., "10.1083/jcb.200407073")

        Returns:
            Paper object or None if DOI not found.
        """
        url = f"{_BASE_URL}/{doi}"
        data = self._get(url)
        if not data:
            return None
        return self._parse_item(data)

    def search(self, query: str, max_results: int = 20) -> list[Paper]:
        """Search CrossRef for papers matching a query.

        Args:
            query: Search string.
            max_results: Maximum results to return.

        Returns:
            List of Paper objects.
        """
        params = {"query": query, "rows": min(max_results, 100)}
        data = self._get(_BASE_URL, params=params)
        if not data:
            return []

        items = data.get("items", [])
        papers = []
        for item in items[:max_results]:
            paper = self._parse_item(item)
            if paper:
                papers.append(paper)
        return papers

    def _parse_item(self, item: dict[str, Any]) -> Paper | None:
        """Parse a CrossRef work item into a Paper."""
        try:
            titles = item.get("title", [])
            title = titles[0] if titles else ""

            # Clean HTML from abstract
            abstract = item.get("abstract", "")
            if abstract:
                abstract = re.sub(r"<[^>]+>", "", abstract).strip()

            # Find PDF URL
            pdf_url = ""
            for link in item.get("link", []):
                if link.get("content-type") == "application/pdf":
                    pdf_url = link.get("URL", "")
                    break

            journals = item.get("container-title", [])

            return Paper(
                title=title,
                authors=self._parse_authors(item.get("author", [])),
                year=self._parse_year(
                    item.get("published-print")
                    or item.get("published-online")
                    or item.get("created")
                ),
                journal=journals[0] if journals else "",
                doi=item.get("DOI", ""),
                abstract=abstract,
                url=item.get("URL", ""),
                pdf_url=pdf_url,
                citation_count=item.get("is-referenced-by-count", 0),
                source_api="crossref",
            )
        except Exception as e:
            logger.debug("Failed to parse CrossRef item: %s", e)
            return None

    def _parse_authors(self, authors: list[dict]) -> list[str]:
        """Parse CrossRef author objects into 'Last First' strings."""
        result = []
        for a in authors:
            family = a.get("family", "")
            given = a.get("given", "")
            if family and given:
                result.append(f"{family} {given[0]}")
            elif family:
                result.append(family)
            elif given:
                result.append(given)
        return result

    def _parse_year(self, date_obj: dict | None) -> int:
        """Extract year from a CrossRef date object."""
        if not date_obj:
            return 0
        parts = date_obj.get("date-parts", [[]])
        try:
            if parts and parts[0]:
                first = parts[0]
                # Handle both [[2020]] and [2020] formats
                if isinstance(first, list):
                    return int(first[0])
                else:
                    return int(first)
        except (IndexError, TypeError, ValueError):
            return 0
        return 0
