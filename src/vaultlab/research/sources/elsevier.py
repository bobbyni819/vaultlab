"""Elsevier ScienceDirect API client — metadata + full-text PDF via API key.

The Elsevier Article Retrieval API allows institutional/authenticated access
to full-text at:

    https://api.elsevier.com/content/article/doi/{doi}

Auth header: ``X-ELS-APIKey: <key>``.  For full-text PDF, also send
``Accept: application/pdf``.  A valid institutional license is required;
without it the API returns 401/403 and you fall back to metadata.
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any

import requests

logger = logging.getLogger(__name__)

_ARTICLE_BASE = "https://api.elsevier.com/content/article/doi/"


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
