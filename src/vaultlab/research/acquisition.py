"""PDF acquisition waterfall for vaultlab corpora.

Given a paper DOI, try to obtain the full-text PDF using a most-permissive-
license-first cascade of free and licensed sources:

    1. **Unpaywall**  — universal OA locator (free, polite-pool email).
    2. **PMC**        — PubMed Central full-text PDFs (for biomedical OA).
    3. **bioRxiv/medRxiv** — preprint full-text PDFs (10.1101 prefix).
    4. **Springer**   — Springer/Nature OA + paid Article API.
    5. **Elsevier**   — Cell Press / ScienceDirect institutional license.

If every tier fails the result is marked ``source = "failed"`` and the
caller can flag the corresponding KB stub ``pdf_status: "paywalled"``.

Design notes
------------

* **Cache by DOI slug.**  ``10.1126/science.1225829`` → ``cache_dir /
  10-1126_science-1225829.pdf``.  If the cache file exists (and looks
  like a valid PDF) we short-circuit the entire waterfall.
* **Polite delays.**  100 ms between calls to the same source by default;
  PMC/NCBI uses 0.34 s (3 req/s) without a key, 0.1 s (10 req/s) with one.
* **User-Agent.**  Every HTTP request carries the standard vaultlab
  polite-pool header (``vaultlab/0.1 (mailto:bobby.ni@duke.edu)``).
* **HTTP error handling.**  ``404`` is "this source doesn't have it" (move
  to the next tier).  ``401``/``403`` is "no access" (move on).  ``5xx`` is
  retried once with a 2 s backoff before falling through.
* **Content-Type validation.**  Some publishers redirect to a landing
  page with HTML; we check ``Content-Type`` and the ``%PDF-`` magic
  number before saving.
* **License capture.**  Unpaywall provides ``oa_location.license`` as
  ``cc-by``/``cc-by-nc``/etc.  PMC files are typically OA but the licence
  string is lifted from Unpaywall when available.  Springer/Elsevier
  responses are tagged ``"subscription"`` because we cannot reliably tell
  the licence from the API alone.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests

from vaultlab.research.corpus import Corpus

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

USER_AGENT = "vaultlab/0.1 (mailto:bobby.ni@duke.edu)"
"""Polite User-Agent header sent on every acquisition request."""

UNPAYWALL_EMAIL = "bobby.ni@duke.edu"
"""Email passed to Unpaywall's polite-pool ``email=`` query parameter."""

UNPAYWALL_BASE = "https://api.unpaywall.org/v2/"
PMC_IDCONV_BASE = "https://www.ncbi.nlm.nih.gov/pmc/utils/idconv/v1.0/"
# NCBI's own /pmc/articles/{pmcid}/pdf/ endpoint now serves an HTML
# JavaScript redirect page; EuropePMC's render endpoint is the reliable
# OA PDF-bytes URL keyed by PMCID.
PMC_PDF_FMT = "https://europepmc.org/articles/{pmcid}?pdf=render"
PMC_PDF_FMT_FALLBACK = "https://www.ncbi.nlm.nih.gov/pmc/articles/{pmcid}/pdf/"
BIORXIV_PDF_FMT = "https://www.biorxiv.org/content/{doi}.full.pdf"
MEDRXIV_PDF_FMT = "https://www.medrxiv.org/content/{doi}.full.pdf"
SPRINGER_PDF_FMT = "https://link.springer.com/content/pdf/{doi}.pdf"
SPRINGER_OA_BASE = "http://api.springernature.com/openaccess/json"
ELSEVIER_ARTICLE_BASE = "https://api.elsevier.com/content/article/doi/"

_DEFAULT_PER_SOURCE_DELAY = 0.10  # seconds — 10 req/s polite default
_PMC_DELAY = 0.34  # seconds — 3 req/s without API key
_DEFAULT_TIMEOUT = 60
_MIN_PDF_BYTES = 1000
_PDF_MAGIC = b"%PDF-"


# ---------------------------------------------------------------------------
# Public dataclass
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AcquisitionResult:
    """Outcome of a single :func:`acquire_pdf` call.

    Attributes:
        doi: Lower-cased DOI we attempted to acquire.
        pdf_path: Local path to the downloaded PDF, or ``None`` on failure.
        source: Which tier succeeded; ``"failed"`` if every tier was
            exhausted.  One of ``"unpaywall" | "pmc" | "biorxiv" |
            "springer" | "elsevier" | "cache" | "failed"``.
        license: Best-effort licence string (e.g. ``"cc-by"``,
            ``"cc-by-nc"``, ``"subscription"``, ``"unknown"``) or ``None``
            when the result is a failure.
        error: Free-text reason populated when ``source == "failed"``.
    """

    doi: str
    pdf_path: Path | None
    source: str
    license: str | None
    error: str | None = None


# ---------------------------------------------------------------------------
# Cache helpers
# ---------------------------------------------------------------------------


def doi_slug(doi: str) -> str:
    """Convert a DOI into a filesystem-safe slug.

    ``10.1126/science.1225829`` -> ``10-1126_science-1225829``.

    The mapping is reversible-enough for humans (slashes -> underscores,
    dots -> dashes) without using percent encoding that confuses Windows
    file explorers.
    """
    return doi.strip().lower().replace("/", "_").replace(".", "-")


def cache_path_for(doi: str, cache_dir: Path) -> Path:
    """Return the canonical cache path for ``doi`` under ``cache_dir``."""
    return Path(cache_dir) / f"{doi_slug(doi)}.pdf"


def _looks_like_pdf(content: bytes, content_type: str = "") -> bool:
    """True when ``content`` plausibly is a PDF.

    Checks both the ``%PDF-`` magic number and the ``Content-Type`` header
    so we don't save HTML landing pages or login redirects.
    """
    if len(content) < _MIN_PDF_BYTES:
        return False
    if content[:5] == _PDF_MAGIC:
        return True
    return "pdf" in (content_type or "").lower()


def _save_pdf(content: bytes, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as fh:
        fh.write(content)


# ---------------------------------------------------------------------------
# HTTP plumbing
# ---------------------------------------------------------------------------


class _PoliteSession:
    """A :class:`requests.Session` with per-source rate limiting + retries.

    The session enforces a minimum gap between calls to the *same* source
    name to keep us in publishers' polite pools.  ``5xx`` responses are
    retried once with a 2 s backoff before being treated as a fall-through.
    """

    def __init__(
        self,
        *,
        timeout: int = _DEFAULT_TIMEOUT,
        session: requests.Session | None = None,
    ):
        self._session = session or requests.Session()
        self._session.headers.setdefault("User-Agent", USER_AGENT)
        self._timeout = timeout
        self._last_call: dict[str, float] = {}
        self._delays: dict[str, float] = {
            "unpaywall": _DEFAULT_PER_SOURCE_DELAY,
            "pmc": _PMC_DELAY,
            "biorxiv": _DEFAULT_PER_SOURCE_DELAY,
            "springer": _DEFAULT_PER_SOURCE_DELAY,
            "elsevier": _DEFAULT_PER_SOURCE_DELAY,
        }

    def _sleep_for(self, source: str) -> None:
        delay = self._delays.get(source, _DEFAULT_PER_SOURCE_DELAY)
        last = self._last_call.get(source, 0.0)
        elapsed = time.time() - last
        if elapsed < delay:
            time.sleep(delay - elapsed)
        self._last_call[source] = time.time()

    def get(
        self,
        source: str,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        stream: bool = False,
        allow_redirects: bool = True,
    ) -> requests.Response | None:
        """Issue a GET; return the response or ``None`` on hard failure.

        404/401/403 are returned as Response objects so callers can
        distinguish "tier doesn't have it" from "tier is broken".
        5xx is retried once.
        """
        self._sleep_for(source)
        for attempt in (1, 2):
            try:
                resp = self._session.get(
                    url,
                    params=params,
                    headers=headers,
                    timeout=self._timeout,
                    stream=stream,
                    allow_redirects=allow_redirects,
                )
            except requests.RequestException as exc:
                logger.debug("%s GET %s failed: %s", source, url, exc)
                if attempt == 1:
                    time.sleep(2.0)
                    continue
                return None
            if resp.status_code >= 500 and attempt == 1:
                logger.debug(
                    "%s GET %s -> %d (retrying once)", source, url, resp.status_code
                )
                time.sleep(2.0)
                continue
            return resp
        return None


# ---------------------------------------------------------------------------
# Tier 1: Unpaywall
# ---------------------------------------------------------------------------


def _extract_pmcid(url: str) -> str | None:
    """Extract a PMCID from a PMC/EuropePMC repository URL.

    Handles all of these:
        https://pmc.ncbi.nlm.nih.gov/articles/PMC9734028/pdf/main.pdf
        https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9734028/
        https://www.ncbi.nlm.nih.gov/pmc/articles/9734028
        http://europepmc.org/pmc/articles/PMC5995079
    """
    if "ncbi.nlm.nih.gov" not in url and "europepmc.org" not in url:
        return None
    marker = "/articles/"
    idx = url.find(marker)
    if idx == -1:
        return None
    tail = url[idx + len(marker) :]
    head = tail.split("/")[0].split("?")[0]
    if head.startswith("PMC") and head[3:].isdigit():
        return head
    if head.isdigit():
        return f"PMC{head}"
    return None


def _rewrite_pmc_url(pdf_url: str) -> str:
    """Rewrite NCBI/PMC PDF URLs to EuropePMC's render endpoint.

    NCBI's ``pmc.ncbi.nlm.nih.gov/articles/{pmcid}/pdf/main.pdf`` returns
    an HTML JS-redirect page rather than PDF bytes; EuropePMC's
    ``europepmc.org/articles/{pmcid}?pdf=render`` is the equivalent
    bytes-returning endpoint.  Pass-through for any URL that doesn't
    match the NCBI pattern.
    """
    pmcid = _extract_pmcid(pdf_url)
    if pmcid is None:
        return pdf_url
    return PMC_PDF_FMT.format(pmcid=pmcid)


def _try_unpaywall(
    doi: str,
    session: _PoliteSession,
) -> tuple[str, str] | None:
    """Return ``(pdf_url, license)`` from Unpaywall or ``None``.

    Unpaywall's ``best_oa_location`` is preferred; we fall back to the
    first entry in ``oa_locations`` that has a ``url_for_pdf``.  PMC
    repository URLs are rewritten to EuropePMC's render endpoint because
    NCBI's path returns an HTML interstitial.
    """
    url = f"{UNPAYWALL_BASE}{doi}"
    resp = session.get("unpaywall", url, params={"email": UNPAYWALL_EMAIL})
    if resp is None or resp.status_code != 200:
        return None
    try:
        data = resp.json()
    except ValueError:
        return None

    candidates: list[dict[str, Any]] = []
    best = data.get("best_oa_location")
    if isinstance(best, dict):
        candidates.append(best)
    locs = data.get("oa_locations") or []
    if isinstance(locs, list):
        candidates.extend(c for c in locs if isinstance(c, dict))

    # First pass: any direct ``url_for_pdf``.
    for loc in candidates:
        pdf_url = loc.get("url_for_pdf")
        if pdf_url:
            pdf_url = _rewrite_pmc_url(pdf_url)
            license_str = (loc.get("license") or "").strip().lower() or "unknown"
            return pdf_url, license_str

    # Second pass: if Unpaywall had no ``url_for_pdf`` but listed a PMC
    # repository ``url``, derive the EuropePMC render URL from its PMCID.
    for loc in candidates:
        u = loc.get("url") or ""
        pmcid = _extract_pmcid(u)
        if pmcid is not None:
            license_str = (
                (loc.get("license") or "").strip().lower() or "pmc-oa"
            )
            return PMC_PDF_FMT.format(pmcid=pmcid), license_str

    return None


# ---------------------------------------------------------------------------
# Tier 2: PMC
# ---------------------------------------------------------------------------


def _try_pmc(
    doi: str,
    session: _PoliteSession,
) -> tuple[str, str] | None:
    """Resolve DOI -> PMCID -> PMC PDF URL.

    Uses the NCBI ID Converter API to find the PMCID.  Returns
    ``(pdf_url, "pmc-oa")`` or ``None``.
    """
    resp = session.get(
        "pmc",
        f"{PMC_IDCONV_BASE}",
        params={
            "ids": doi,
            "idtype": "doi",
            "format": "json",
            "tool": "vaultlab",
            "email": UNPAYWALL_EMAIL,
        },
    )
    if resp is None or resp.status_code != 200:
        return None
    try:
        data = resp.json()
    except ValueError:
        return None
    records = data.get("records") or []
    if not records:
        return None
    pmcid = records[0].get("pmcid")
    if not pmcid:
        return None
    return PMC_PDF_FMT.format(pmcid=pmcid), "pmc-oa"


# ---------------------------------------------------------------------------
# Tier 3: bioRxiv / medRxiv
# ---------------------------------------------------------------------------


def _try_biorxiv(
    doi: str,
    session: _PoliteSession,
) -> tuple[str, str] | None:
    """Build a bioRxiv/medRxiv PDF URL for ``doi`` if it has the 10.1101 prefix.

    bioRxiv/medRxiv DOIs all share the ``10.1101`` registrant prefix.  We
    don't probe the URL here; the caller's downloader will check the
    response.
    """
    if not doi.startswith("10.1101/"):
        return None
    # We don't know preprint server choice from DOI; try bioRxiv first.
    return BIORXIV_PDF_FMT.format(doi=doi), "cc-by"


# ---------------------------------------------------------------------------
# Tier 4: Springer
# ---------------------------------------------------------------------------


def _try_springer(
    doi: str,
    session: _PoliteSession,
    api_key: str,
) -> tuple[str, str] | None:
    """Resolve DOI to a Springer PDF URL.

    1. Query the Springer Open Access API for an ``url[format=pdf]``.
    2. If the OA API has nothing, fall back to the direct
       ``link.springer.com/content/pdf/{doi}.pdf`` pattern (works for OA
       Springer/Nature DOIs even when the API record is sparse).
    """
    if api_key:
        resp = session.get(
            "springer",
            SPRINGER_OA_BASE,
            params={"q": f'doi:"{doi}"', "api_key": api_key},
        )
        if resp is not None and resp.status_code == 200:
            try:
                data = resp.json()
            except ValueError:
                data = {}
            for rec in data.get("records", []) or []:
                for u in rec.get("url", []) or []:
                    if isinstance(u, dict) and u.get("format", "").lower() == "pdf":
                        pdf_url = u.get("value", "")
                        if pdf_url:
                            return pdf_url, "subscription"

    # Direct pattern works for any Springer DOI even when OA API is empty.
    return SPRINGER_PDF_FMT.format(doi=doi), "subscription"


# ---------------------------------------------------------------------------
# Tier 5: Elsevier
# ---------------------------------------------------------------------------


def _try_elsevier(
    doi: str,
    api_key: str,
) -> tuple[str, dict[str, str], str] | None:
    """Return ``(url, headers, license)`` for an Elsevier API request."""
    if not api_key:
        return None
    return (
        f"{ELSEVIER_ARTICLE_BASE}{doi}",
        {"X-ELS-APIKey": api_key, "Accept": "application/pdf"},
        "subscription",
    )


# ---------------------------------------------------------------------------
# Generic PDF download with content-type guard
# ---------------------------------------------------------------------------


def _download_pdf(
    source: str,
    url: str,
    *,
    session: _PoliteSession,
    headers: dict[str, str] | None = None,
) -> bytes | None:
    """Fetch ``url`` and return its bytes if it's a PDF, else ``None``."""
    resp = session.get(source, url, headers=headers)
    if resp is None:
        return None
    if resp.status_code in (401, 403):
        logger.debug("%s denied access to %s (%d)", source, url, resp.status_code)
        return None
    if resp.status_code == 404:
        logger.debug("%s did not have %s (404)", source, url)
        return None
    if resp.status_code != 200:
        logger.debug("%s returned %d for %s", source, resp.status_code, url)
        return None
    if not _looks_like_pdf(resp.content, resp.headers.get("Content-Type", "")):
        logger.debug(
            "%s returned non-PDF content for %s (Content-Type=%s, size=%d)",
            source,
            url,
            resp.headers.get("Content-Type", ""),
            len(resp.content),
        )
        return None
    return resp.content


# ---------------------------------------------------------------------------
# Config helper
# ---------------------------------------------------------------------------


def _load_default_apis() -> dict[str, str]:
    """Load API keys from the standard config or fall back to empty dict.

    Used when the caller passes ``apis=None`` to :func:`acquire_pdf`.
    Failure is silent so missing-config doesn't break OA-only acquisition.
    """
    try:
        from vaultlab.research.config import get_config

        cfg = get_config()
    except Exception:
        return {}
    return {
        "springer_open_access_api_key": cfg.get("springer_open_access_api_key", ""),
        "elsevier_key": cfg.get("elsevier_key", ""),
    }


# ---------------------------------------------------------------------------
# Public API: single-DOI acquisition
# ---------------------------------------------------------------------------


def acquire_pdf(
    doi: str,
    *,
    cache_dir: Path,
    apis: dict[str, str] | None = None,
    skip_paywalled: bool = False,
    timeout: int = _DEFAULT_TIMEOUT,
    _session: _PoliteSession | None = None,
) -> AcquisitionResult:
    """Acquire a PDF for ``doi`` via the waterfall, return :class:`AcquisitionResult`.

    Args:
        doi: The DOI to acquire (case-insensitive; lower-cased internally).
        cache_dir: Directory where PDFs are stored.  Cache key is
            :func:`doi_slug`.
        apis: API key map.  Recognised keys:
            ``"springer_open_access_api_key"``, ``"elsevier_key"``.  When
            ``None`` (default), keys are loaded from
            :mod:`vaultlab.research.config`.
        skip_paywalled: If ``True``, skip Springer/Elsevier tiers (only
            OA sources are tried).
        timeout: Per-request HTTP timeout in seconds.
        _session: Internal — let the batch helper share a single
            :class:`_PoliteSession` across calls.

    Returns:
        :class:`AcquisitionResult` capturing tier, license, path or error.
    """
    doi = (doi or "").strip().lower()
    if not doi:
        return AcquisitionResult(
            doi=doi,
            pdf_path=None,
            source="failed",
            license=None,
            error="empty doi",
        )

    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    target = cache_path_for(doi, cache_dir)

    # ------------------------------------------------------------------
    # Cache hit
    # ------------------------------------------------------------------
    if target.exists() and target.stat().st_size > _MIN_PDF_BYTES:
        try:
            with open(target, "rb") as fh:
                head = fh.read(8)
        except OSError:
            head = b""
        if head[:5] == _PDF_MAGIC:
            return AcquisitionResult(
                doi=doi,
                pdf_path=target,
                source="cache",
                license=None,
            )

    apis = apis if apis is not None else _load_default_apis()
    session = _session or _PoliteSession(timeout=timeout)

    tried: list[str] = []
    last_error: str | None = None

    # ------------------------------------------------------------------
    # Tier 1: Unpaywall
    # ------------------------------------------------------------------
    tried.append("unpaywall")
    try:
        upw = _try_unpaywall(doi, session)
    except Exception as exc:  # pragma: no cover — defensive
        last_error = f"unpaywall lookup error: {exc}"
        upw = None
    if upw is not None:
        pdf_url, license_str = upw
        content = _download_pdf("unpaywall", pdf_url, session=session)
        if content is not None:
            _save_pdf(content, target)
            return AcquisitionResult(
                doi=doi,
                pdf_path=target,
                source="unpaywall",
                license=license_str,
            )

    # ------------------------------------------------------------------
    # Tier 2: PMC (via EuropePMC render endpoint, with NCBI fallback)
    # ------------------------------------------------------------------
    tried.append("pmc")
    try:
        pmc = _try_pmc(doi, session)
    except Exception as exc:  # pragma: no cover — defensive
        last_error = f"pmc lookup error: {exc}"
        pmc = None
    if pmc is not None:
        pdf_url, license_str = pmc
        content = _download_pdf("pmc", pdf_url, session=session)
        if content is None:
            # Some PMCIDs are missing from EuropePMC's render endpoint;
            # try NCBI's direct path as a sibling fallback.
            pmcid = pdf_url.split("/articles/")[-1].split("?")[0].split("/")[0]
            content = _download_pdf(
                "pmc",
                PMC_PDF_FMT_FALLBACK.format(pmcid=pmcid),
                session=session,
            )
        if content is not None:
            _save_pdf(content, target)
            return AcquisitionResult(
                doi=doi,
                pdf_path=target,
                source="pmc",
                license=license_str,
            )

    # ------------------------------------------------------------------
    # Tier 3: bioRxiv / medRxiv
    # ------------------------------------------------------------------
    tried.append("biorxiv")
    try:
        bio = _try_biorxiv(doi, session)
    except Exception as exc:  # pragma: no cover — defensive
        last_error = f"biorxiv lookup error: {exc}"
        bio = None
    if bio is not None:
        pdf_url, license_str = bio
        content = _download_pdf("biorxiv", pdf_url, session=session)
        if content is None:
            # Try medRxiv as a sibling.
            content = _download_pdf(
                "biorxiv", MEDRXIV_PDF_FMT.format(doi=doi), session=session
            )
        if content is not None:
            _save_pdf(content, target)
            return AcquisitionResult(
                doi=doi,
                pdf_path=target,
                source="biorxiv",
                license=license_str,
            )

    if skip_paywalled:
        return AcquisitionResult(
            doi=doi,
            pdf_path=None,
            source="failed",
            license=None,
            error=last_error or f"no OA source had pdf (tried {', '.join(tried)})",
        )

    # ------------------------------------------------------------------
    # Tier 4: Springer
    # ------------------------------------------------------------------
    tried.append("springer")
    springer_key = apis.get("springer_open_access_api_key", "")
    try:
        spr = _try_springer(doi, session, springer_key)
    except Exception as exc:  # pragma: no cover — defensive
        last_error = f"springer lookup error: {exc}"
        spr = None
    if spr is not None:
        pdf_url, license_str = spr
        content = _download_pdf("springer", pdf_url, session=session)
        if content is not None:
            _save_pdf(content, target)
            return AcquisitionResult(
                doi=doi,
                pdf_path=target,
                source="springer",
                license=license_str,
            )

    # ------------------------------------------------------------------
    # Tier 5: Elsevier
    # ------------------------------------------------------------------
    tried.append("elsevier")
    elsevier_key = apis.get("elsevier_key", "")
    el = _try_elsevier(doi, elsevier_key)
    if el is not None:
        pdf_url, headers, license_str = el
        content = _download_pdf(
            "elsevier", pdf_url, session=session, headers=headers
        )
        if content is not None:
            _save_pdf(content, target)
            return AcquisitionResult(
                doi=doi,
                pdf_path=target,
                source="elsevier",
                license=license_str,
            )

    return AcquisitionResult(
        doi=doi,
        pdf_path=None,
        source="failed",
        license=None,
        error=last_error or f"no source had pdf (tried {', '.join(tried)})",
    )


# ---------------------------------------------------------------------------
# Public API: corpus-wide acquisition
# ---------------------------------------------------------------------------


def acquire_pdfs_for_corpus(
    corpus: Corpus,
    cache_dir: Path,
    *,
    parallel: int = 4,
    apis: dict[str, str] | None = None,
    skip_paywalled: bool = False,
    timeout: int = _DEFAULT_TIMEOUT,
    progress: Callable[[str, int, int], None] | None = None,
) -> dict[str, AcquisitionResult]:
    """Acquire PDFs for every paper in ``corpus.papers`` in parallel.

    Args:
        corpus: A built :class:`Corpus`.  Only papers with non-empty DOIs
            are attempted.
        cache_dir: Directory where PDFs are stored.
        parallel: Worker count for the thread pool.  ``1`` is sequential.
        apis: API key map (forwarded to :func:`acquire_pdf`).
        skip_paywalled: If ``True``, only OA tiers are tried.
        timeout: Per-request HTTP timeout.
        progress: Optional callback ``progress(doi, done, total)``.

    Returns:
        Mapping ``doi -> AcquisitionResult``.
    """
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)

    apis = apis if apis is not None else _load_default_apis()
    dois = [d for d in corpus.papers if d]
    total = len(dois)
    results: dict[str, AcquisitionResult] = {}

    def _one(doi: str) -> AcquisitionResult:
        # Each worker uses its own session so per-source rate limits stay
        # local to the thread; otherwise ``_PoliteSession`` would funnel
        # all calls through one delay clock.
        return acquire_pdf(
            doi,
            cache_dir=cache_dir,
            apis=apis,
            skip_paywalled=skip_paywalled,
            timeout=timeout,
        )

    if parallel <= 1:
        for i, doi in enumerate(dois, 1):
            res = _one(doi)
            results[doi] = res
            if progress is not None:
                progress(doi, i, total)
        return results

    with ThreadPoolExecutor(max_workers=parallel) as pool:
        futures = {pool.submit(_one, doi): doi for doi in dois}
        done = 0
        for fut in futures:
            doi = futures[fut]
            try:
                res = fut.result()
            except Exception as exc:
                res = AcquisitionResult(
                    doi=doi,
                    pdf_path=None,
                    source="failed",
                    license=None,
                    error=f"worker exception: {exc}",
                )
            results[doi] = res
            done += 1
            if progress is not None:
                progress(doi, done, total)
    return results


__all__ = [
    "UNPAYWALL_EMAIL",
    "USER_AGENT",
    "AcquisitionResult",
    "acquire_pdf",
    "acquire_pdfs_for_corpus",
    "cache_path_for",
    "doi_slug",
]


# Internal helpers exported for tests.
__test_exports__ = [
    "_PoliteSession",
    "_download_pdf",
    "_load_default_apis",
    "_looks_like_pdf",
    "_try_biorxiv",
    "_try_elsevier",
    "_try_pmc",
    "_try_springer",
    "_try_unpaywall",
]


