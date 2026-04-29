"""Semantic Scholar API client.

Base URL: https://api.semanticscholar.org/graph/v1/
Rate limit: 1 req/sec with key, 100 req/5min without.
"""

from __future__ import annotations

import logging
import time
from typing import Any

import requests

from vaultlab.research.paper import Paper

logger = logging.getLogger(__name__)

_BASE_URL = "https://api.semanticscholar.org/graph/v1/"
_RECOMMENDATIONS_URL = "https://api.semanticscholar.org/recommendations/v1/papers/"
_FIELDS = "title,authors,year,venue,externalIds,abstract,citationCount,url"


class SemanticScholarClient:
    """Client for the Semantic Scholar Academic Graph API."""

    def __init__(self, api_key: str = ""):
        self.api_key = api_key
        self._session = requests.Session()
        if api_key:
            self._session.headers["x-api-key"] = api_key
        self._last_request_time = 0.0
        # 1 req/sec with key; be more conservative without
        self._min_interval = 1.0 if not api_key else 0.5

    def _rate_limit(self) -> None:
        """Enforce rate limiting between requests."""
        elapsed = time.time() - self._last_request_time
        if elapsed < self._min_interval:
            time.sleep(self._min_interval - elapsed)
        self._last_request_time = time.time()

    def _get(
        self, endpoint: str, params: dict | None = None, retries: int = 3
    ) -> dict[str, Any] | None:
        """Make a GET request with rate limiting and retry."""
        url = _BASE_URL + endpoint
        for attempt in range(retries):
            self._rate_limit()
            try:
                resp = self._session.get(url, params=params or {}, timeout=30)
                if resp.status_code == 404:
                    logger.debug("Semantic Scholar 404 for: %s", endpoint)
                    return None
                if resp.status_code == 429:
                    wait = 2 ** (attempt + 1)
                    logger.warning("Semantic Scholar rate limited. Waiting %ds...", wait)
                    time.sleep(wait)
                    continue
                resp.raise_for_status()
                return resp.json()
            except requests.RequestException as e:
                if attempt < retries - 1:
                    wait = 2**attempt
                    logger.warning(
                        "Semantic Scholar request failed (attempt %d/%d): %s. Retrying in %ds...",
                        attempt + 1,
                        retries,
                        e,
                        wait,
                    )
                    time.sleep(wait)
                else:
                    logger.error(
                        "Semantic Scholar request failed after %d attempts: %s",
                        retries,
                        e,
                    )
                    raise
        return None

    def _post(
        self, url: str, json_body: dict, params: dict | None = None, retries: int = 3
    ) -> dict[str, Any] | None:
        """Make a POST request with rate limiting and retry."""
        for attempt in range(retries):
            self._rate_limit()
            try:
                resp = self._session.post(url, json=json_body, params=params or {}, timeout=30)
                if resp.status_code == 429:
                    wait = 2 ** (attempt + 1)
                    logger.warning("Semantic Scholar rate limited. Waiting %ds...", wait)
                    time.sleep(wait)
                    continue
                resp.raise_for_status()
                return resp.json()
            except requests.RequestException as e:
                if attempt < retries - 1:
                    wait = 2**attempt
                    logger.warning(
                        "Semantic Scholar POST failed (attempt %d/%d): %s. Retrying in %ds...",
                        attempt + 1,
                        retries,
                        e,
                        wait,
                    )
                    time.sleep(wait)
                else:
                    logger.error(
                        "Semantic Scholar POST failed after %d attempts: %s",
                        retries,
                        e,
                    )
                    raise
        return None

    def search(self, query: str, max_results: int = 20) -> list[Paper]:
        """Search for papers by keyword query.

        Args:
            query: Search query string.
            max_results: Maximum number of results (max 100 per request).

        Returns:
            List of Paper objects.
        """
        params = {
            "query": query,
            "limit": min(max_results, 100),
            "fields": _FIELDS,
        }
        data = self._get("paper/search", params)
        if not data:
            return []

        papers_data = data.get("data", [])
        if not papers_data:
            logger.info("No Semantic Scholar results for: %s", query)
            return []

        logger.info("Found %d Semantic Scholar results for: %s", len(papers_data), query)

        papers = []
        for item in papers_data[:max_results]:
            paper = self._parse_paper(item)
            if paper:
                papers.append(paper)
        return papers

    def get_paper(self, paper_id: str) -> Paper | None:
        """Get a paper by Semantic Scholar ID, DOI, or PMID.

        Args:
            paper_id: Can be S2 paper ID, DOI (prefix with "DOI:"),
                      PMID (prefix with "PMID:"), or arXiv ID ("ARXIV:").

        Returns:
            Paper object or None.
        """
        params = {"fields": _FIELDS}
        data = self._get(f"paper/{paper_id}", params)
        if not data:
            return None
        return self._parse_paper(data)

    def get_citations(self, paper_id: str, limit: int = 100) -> list[Paper]:
        """Get papers that cite this paper.

        Args:
            paper_id: Semantic Scholar paper ID, DOI, or PMID (with prefix).
            limit: Maximum number of citing papers.

        Returns:
            List of Paper objects.
        """
        params = {
            "fields": _FIELDS,
            "limit": min(limit, 1000),
        }
        data = self._get(f"paper/{paper_id}/citations", params)
        if not data:
            return []

        papers = []
        for item in data.get("data", []):
            citing = item.get("citingPaper", {})
            if citing:
                paper = self._parse_paper(citing)
                if paper:
                    papers.append(paper)
        return papers

    def get_references(self, paper_id: str, limit: int = 100) -> list[Paper]:
        """Get papers that this paper cites (references).

        Args:
            paper_id: Semantic Scholar paper ID, DOI, or PMID (with prefix).
            limit: Maximum number of referenced papers.

        Returns:
            List of Paper objects.
        """
        params = {
            "fields": _FIELDS,
            "limit": min(limit, 1000),
        }
        data = self._get(f"paper/{paper_id}/references", params)
        if not data:
            return []

        papers = []
        for item in data.get("data", []):
            cited = item.get("citedPaper", {})
            if cited:
                paper = self._parse_paper(cited)
                if paper:
                    papers.append(paper)
        return papers

    def get_recommendations(self, paper_ids: list[str]) -> list[Paper]:
        """Get recommended papers based on a set of seed papers.

        Args:
            paper_ids: List of Semantic Scholar paper IDs or DOIs.

        Returns:
            List of recommended Paper objects.
        """
        if not paper_ids:
            return []

        body = {"positivePaperIds": paper_ids}
        params = {"fields": _FIELDS, "limit": 20}

        data = self._post(_RECOMMENDATIONS_URL, body, params)
        if not data:
            return []

        papers = []
        for item in data.get("recommendedPapers", []):
            paper = self._parse_paper(item)
            if paper:
                papers.append(paper)
        return papers

    @staticmethod
    def _parse_paper(item: dict[str, Any]) -> Paper | None:
        """Parse a Semantic Scholar paper JSON object into a Paper."""
        if not item or not item.get("title"):
            return None

        try:
            title = item.get("title", "")

            # Authors
            authors = []
            for a in item.get("authors", []):
                name = a.get("name", "")
                if name:
                    authors.append(name)

            year = item.get("year") or 0
            journal = item.get("venue", "") or ""

            # External IDs
            ext_ids = item.get("externalIds") or {}
            doi = ext_ids.get("DOI", "") or ""
            pmid = str(ext_ids.get("PubMed", "") or "")

            abstract = item.get("abstract", "") or ""
            citation_count = item.get("citationCount") or 0
            url = item.get("url", "") or ""

            return Paper(
                title=title,
                authors=authors,
                year=year,
                journal=journal,
                doi=doi,
                pmid=pmid,
                abstract=abstract,
                url=url,
                citation_count=citation_count,
                source_api="semantic",
            )
        except Exception as e:
            logger.error("Error parsing Semantic Scholar paper: %s", e)
            return None
