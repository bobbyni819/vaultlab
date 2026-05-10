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
  polite-pool header (``vaultlab/<version> (mailto:<configured-email>)``;
  see :mod:`vaultlab.research._polite_pool` for resolution order).
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
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

import requests

from vaultlab.research.corpus import Corpus

if TYPE_CHECKING:
    from vaultlab.research.paper import Paper

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

from vaultlab.research._polite_pool import get_polite_pool_email, get_user_agent

USER_AGENT = get_user_agent("vaultlab-research")
"""Polite User-Agent header sent on every acquisition request.

Resolved at import-time from the user's
``VAULTLAB_POLITE_POOL_EMAIL`` env var or
``~/.config/vaultlab/config.json``. Falls back to the unconfigured
no-reply default if neither is set.
"""

UNPAYWALL_EMAIL = get_polite_pool_email()
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
        tried: Ordered list of tier names that were attempted (e.g.
            ``["unpaywall", "pmc", "biorxiv"]``). Empty for cache hits.
        tier_errors: Per-tier error string (only populated for tiers we
            actually called and that returned non-success). Keys are tier
            names; values are short strings like ``"404"``,
            ``"non-pdf content"``, or ``"key missing"``. Used by the
            decisions-log writer to surface "which sources we tried and
            why each one failed" without spelunking through logs.
        wall_time_ms: Wall-clock time of the entire :func:`acquire_pdf`
            call (rate-limit sleeps included). 0 for cache hits.
        publisher_url: Best-guess publisher URL (e.g.
            ``https://doi.org/<doi>``) for manual-fetch instructions
            when the API waterfall fails but the user has institutional
            browser access (Duke library proxy, etc.). Always ``None``
            on success.
        cache_target_path: Where the user should drop a manually-downloaded
            PDF so the next ``acquire_pdf`` call picks it up from cache
            (the canonical ``<cache_dir>/<doi-slug>.pdf``). Populated on
            failure so the orchestrator can render copy-paste manual
            fetch instructions.
    """

    doi: str
    pdf_path: Path | None
    source: str
    license: str | None
    error: str | None = None
    tried: tuple[str, ...] = ()
    tier_errors: dict[str, str] = field(default_factory=dict)
    wall_time_ms: int = 0
    publisher_url: str | None = None
    cache_target_path: Path | None = None

    # ---- Classified outcome (derived) ------------------------------------
    # Per design-doc Q4 (2026-05-02 paperclip integration), callers want a
    # richer outcome taxonomy than the raw ``source`` field for paywall-
    # transparency UX. Rather than mutate the constructor (11 call sites,
    # would break compat), we expose a derived property that classifies
    # the existing fields into the design-doc state machine.

    @property
    def outcome(self) -> str:
        """Classified outcome of this acquisition attempt.

        Returns one of these documented states:

        * ``cache_hit`` — already on disk; waterfall short-circuited.
        * ``paperclip_full_text`` — paperclip's pre-extracted sections +
          figures available (no PDF needed; consumer reads
          ``/papers/<id>/sections/`` directly).
        * ``oa_pdf`` — Open Access PDF acquired (Unpaywall / PMC /
          bioRxiv / medRxiv / Springer-OA).
        * ``gated_pdf_via_key`` — subscriber PDF acquired (Elsevier
          with key, or Springer paid API).
        * ``gated_metadata_only`` — abstract-only; PDF gated and we
          weren't able to fetch full text (Springer fallback when only
          metadata API is reachable).
        * ``failed_paywalled`` — known paywalled, every key path
          returned 401/403/subscription error; user needs manual fetch.
        * ``failed_not_indexed`` — DOI didn't resolve in any source.
        * ``failed`` — unspecified failure (legacy fallback).

        Use ``needs_manual_fetch`` for the paywall-transparency
        ``vaultlab fetch-list paywalled`` CLI report.
        """
        s = (self.source or "").lower()
        if s == "cache":
            return "cache_hit"
        if s == "paperclip":
            # Paperclip "success" means full text + figures pre-extracted.
            # Always treated as full-text outcome, regardless of pdf_path.
            return "paperclip_full_text"
        if s in ("unpaywall", "pmc", "biorxiv", "medrxiv"):
            return "oa_pdf"
        if s == "springer":
            # Springer succeeded with a PDF means OA pull worked.
            return "oa_pdf" if self.pdf_path else "gated_metadata_only"
        if s == "elsevier":
            return "gated_pdf_via_key"
        if s == "failed":
            # Distinguish paywalled (tried gated tiers with auth errors)
            # from not-indexed (no source had it). Heuristic in order:
            # 1. Any 401/403/subscription/forbidden string in tier_errors
            #    signals paywalled regardless of source.
            for err in self.tier_errors.values():
                e = str(err).lower()
                if "401" in e or "403" in e or "subscription" in e or "forbidden" in e:
                    return "failed_paywalled"
            # 2. If we tried Elsevier or Springer (gated tiers) and got
            #    a non-key-missing error (e.g., "non-pdf content",
            #    actually-tried-the-API failures), treat as paywalled.
            #    "key missing" is an unconfigured-source signal, not a
            #    paywall signal — fall through.
            for tier in ("elsevier", "springer"):
                err = str(self.tier_errors.get(tier, "")).lower()
                if err and "key missing" not in err and "no api key" not in err:
                    return "failed_paywalled"
            return "failed_not_indexed"
        return "failed"

    @property
    def needs_manual_fetch(self) -> bool:
        """True if the user should manually obtain this paper.

        Used by the planned ``vaultlab fetch-list paywalled`` CLI to
        emit the user-facing manual-fetch shopping list.
        """
        return self.outcome == "failed_paywalled"

    @property
    def is_full_text(self) -> bool:
        """True if a full-text source (PDF or paperclip sections) is
        available locally for downstream Tier-A reading."""
        return self.outcome in (
            "cache_hit",
            "paperclip_full_text",
            "oa_pdf",
            "gated_pdf_via_key",
        )

    @property
    def is_metadata_only(self) -> bool:
        """True when only abstract / metadata is available (Tier-B fallback)."""
        return self.outcome == "gated_metadata_only"


# ---------------------------------------------------------------------------
# Cache helpers
# ---------------------------------------------------------------------------


def doi_slug(doi: str) -> str:
    """Convert a DOI into a filesystem-safe slug.

    ``10.1126/science.1225829`` -> ``10.1126_science.1225829``.

    Delegates to :func:`vaultlab.kb.paths.slugify_doi` — the *one* source of
    truth for DOI slug formatting across the codebase. Pre-2026-04-30 this
    function used a dash-based variant
    (``10.1126/science.1225829`` -> ``10-1126_science-1225829``) which
    diverged from the ``slugify_doi`` dot-format; that mismatch caused
    summary-frontmatter ``source_pdf`` paths to 404.  See :func:`cache_path_for`
    for the back-compat resolver that still finds PDFs written under the
    legacy dash format.
    """
    from vaultlab.kb.paths import slugify_doi

    return slugify_doi(doi).lower()


def _legacy_doi_slug(doi: str) -> str:
    """Pre-2026-04-30 dash-format slug, kept only for back-compat lookups.

    ``10.1126/science.1225829`` -> ``10-1126_science-1225829``.

    Do **not** use for new writes — see :func:`doi_slug`.  Existing PDFs
    + extracted figures on disk under
    ``Sources/Papers/<dash-slug>/...`` are still discoverable through
    :func:`cache_path_for`'s fallback path.

    Strips a trailing ``.pdf`` (case-insensitive) before slugifying so a
    caller that passed ``Path(p).name`` instead of ``Path(p).stem`` still
    gets a clean slug. See Round-2 audit log Finding 3 (2026-04-30).
    """
    s = doi.strip().lower()
    if s.endswith(".pdf"):
        s = s[: -len(".pdf")]
    return s.replace("/", "_").replace(".", "-")


def cache_path_for(doi: str, cache_dir: Path) -> Path:
    """Return the canonical cache path for ``doi`` under ``cache_dir``.

    Resolution order:

    1. The canonical dot-format path
       (``cache_dir/<slugify_doi>.pdf``).  Returned unconditionally if the
       file exists OR if no legacy dash-format file exists either — i.e.
       this is *also* the path used for fresh writes.
    2. **Back-compat**: if the dot-format file is absent but the legacy
       dash-format file exists (399 PDFs + 3,771 figures landed under the
       old slug before 2026-04-30), return the dash-format path so reads
       still resolve.

    Future writes always land at the dot-format path.
    """
    cache_dir = Path(cache_dir)
    canonical = cache_dir / f"{doi_slug(doi)}.pdf"
    if canonical.exists():
        return canonical
    legacy = cache_dir / f"{_legacy_doi_slug(doi)}.pdf"
    if legacy.exists():
        return legacy
    return canonical


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
    paperclip_client=None,
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
        paperclip_client: Optional :class:`PaperclipClient` for the
            Tier-0 paperclip-corpus check. When given, we ask paperclip
            whether it has the paper before any HTTP download. On hit,
            return ``source="paperclip"`` immediately (the consumer
            reads sections from the paperclip virtual filesystem instead
            of a local PDF). On miss, the tier is recorded as
            ``not_in_paperclip_corpus`` in ``tier_errors`` and the
            existing waterfall (Unpaywall / PMC / bioRxiv / Springer /
            Elsevier) runs unchanged. ``None`` (default) skips the
            tier silently — Q5 graceful degrade.
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

    started = time.time()
    tried: list[str] = []
    tier_errors: dict[str, str] = {}
    last_error: str | None = None

    def _wall_ms() -> int:
        return int((time.time() - started) * 1000)

    # ------------------------------------------------------------------
    # Tier 0: Paperclip (8M-paper biomedical full-text corpus)
    #
    # Per the 2026-05-02 paperclip integration design (Q3+Q4): if
    # paperclip has the paper, return source="paperclip" immediately —
    # the downstream reader uses the pre-extracted sections + figures
    # from the paperclip virtual filesystem (/papers/<id>/) and skips
    # the PDF-download + pdftoppm step entirely. On miss, record
    # not_in_paperclip_corpus in tier_errors and continue (it's a
    # miss-with-explanation, not a failure). On any error (auth
    # missing, binary missing, timeout) — Q5 graceful degrade — skip
    # silently and continue.
    # ------------------------------------------------------------------
    if paperclip_client is not None:
        tried.append("paperclip")
        try:
            pc_paper = paperclip_client.lookup_doi(doi)
        except Exception as exc:  # noqa: BLE001 — Q5 graceful degrade
            tier_errors["paperclip"] = f"lookup error: {exc}"
            pc_paper = None
        if pc_paper is not None:
            return AcquisitionResult(
                doi=doi,
                pdf_path=None,  # paperclip serves text sections, not a PDF
                source="paperclip",
                license=None,
                tried=tuple(tried),
                tier_errors=dict(tier_errors),
                wall_time_ms=_wall_ms(),
            )
        tier_errors.setdefault("paperclip", "not_in_paperclip_corpus")

    # ------------------------------------------------------------------
    # Tier 1: Unpaywall
    # ------------------------------------------------------------------
    tried.append("unpaywall")
    try:
        upw = _try_unpaywall(doi, session)
    except Exception as exc:  # pragma: no cover — defensive
        last_error = f"unpaywall lookup error: {exc}"
        tier_errors["unpaywall"] = f"lookup error: {exc}"
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
                tried=tuple(tried),
                tier_errors=dict(tier_errors),
                wall_time_ms=_wall_ms(),
            )
        tier_errors["unpaywall"] = "non-pdf content or download failed"
    else:
        tier_errors.setdefault("unpaywall", "no OA location with url_for_pdf")

    # ------------------------------------------------------------------
    # Tier 2: PMC (via EuropePMC render endpoint, with NCBI fallback)
    # ------------------------------------------------------------------
    tried.append("pmc")
    try:
        pmc = _try_pmc(doi, session)
    except Exception as exc:  # pragma: no cover — defensive
        last_error = f"pmc lookup error: {exc}"
        tier_errors["pmc"] = f"lookup error: {exc}"
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
                tried=tuple(tried),
                tier_errors=dict(tier_errors),
                wall_time_ms=_wall_ms(),
            )
        tier_errors["pmc"] = "PMCID resolved but render endpoint had no PDF"
    else:
        tier_errors.setdefault("pmc", "no PMCID for DOI")

    # ------------------------------------------------------------------
    # Tier 3: bioRxiv / medRxiv
    # ------------------------------------------------------------------
    tried.append("biorxiv")
    try:
        bio = _try_biorxiv(doi, session)
    except Exception as exc:  # pragma: no cover — defensive
        last_error = f"biorxiv lookup error: {exc}"
        tier_errors["biorxiv"] = f"lookup error: {exc}"
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
                tried=tuple(tried),
                tier_errors=dict(tier_errors),
                wall_time_ms=_wall_ms(),
            )
        tier_errors["biorxiv"] = "preprint URL did not return a PDF"
    else:
        tier_errors.setdefault("biorxiv", "DOI not in 10.1101 prefix")

    if skip_paywalled:
        return AcquisitionResult(
            doi=doi,
            pdf_path=None,
            source="failed",
            license=None,
            error=last_error or f"no OA source had pdf (tried {', '.join(tried)})",
            tried=tuple(tried),
            tier_errors=dict(tier_errors),
            wall_time_ms=_wall_ms(),
            publisher_url=f"https://doi.org/{doi}",
            cache_target_path=target,
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
        tier_errors["springer"] = f"lookup error: {exc}"
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
                tried=tuple(tried),
                tier_errors=dict(tier_errors),
                wall_time_ms=_wall_ms(),
            )
        tier_errors["springer"] = "OA only at meta tier or 403"

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
                tried=tuple(tried),
                tier_errors=dict(tier_errors),
                wall_time_ms=_wall_ms(),
            )
        tier_errors["elsevier"] = "API returned non-pdf or 403"
    else:
        tier_errors.setdefault("elsevier", "key missing")

    return AcquisitionResult(
        doi=doi,
        pdf_path=None,
        source="failed",
        license=None,
        error=last_error or f"no source had pdf (tried {', '.join(tried)})",
        tried=tuple(tried),
        tier_errors=dict(tier_errors),
        wall_time_ms=_wall_ms(),
        publisher_url=f"https://doi.org/{doi}",
        cache_target_path=target,
    )


# ---------------------------------------------------------------------------
# Public API: manual-fetch fallback for paywalled papers
# ---------------------------------------------------------------------------


def render_manual_fetch_instructions(
    results: dict[str, AcquisitionResult],
    *,
    corpus_papers: dict[str, "Paper"] | None = None,
    title: str = "Papers needing manual download",
) -> str:
    """Render a markdown block telling the user which papers to fetch manually.

    Use after a corpus-wide ``acquire_pdfs_for_corpus`` call to surface
    papers the API waterfall couldn't reach but that the user has
    institutional browser access to (Springer-Nature paywalled, Wiley
    non-OA, etc.). For each failed DOI, emit:

    * The DOI as a clickable link to the publisher (``https://doi.org/<doi>``)
    * The canonical cache path where the user should drop the PDF
    * A one-line note on which API tiers were tried and why each failed

    On the user's *next* ``/lit-arc`` run, ``acquire_pdf`` will detect
    the file at ``cache_target_path`` and short-circuit the waterfall —
    no code change needed for the second-run pickup, the existing cache
    check handles it.

    Args:
        results: Mapping of DOI to :class:`AcquisitionResult` from
            ``acquire_pdfs_for_corpus``.
        corpus_papers: Optional ``corpus.papers`` dict, used to pull
            paper titles and journal names into the instructions.
        title: Heading for the markdown block.

    Returns:
        Markdown string. Empty when no papers need manual fetch.
    """
    failed = [
        (doi, r)
        for doi, r in results.items()
        if r.source == "failed" and r.cache_target_path is not None
    ]
    if not failed:
        return ""

    lines: list[str] = [
        f"# {title}",
        "",
        f"vaultlab couldn't get **{len(failed)} PDF(s)** via the API "
        f"waterfall. If you have institutional browser access (e.g. "
        f"Duke library proxy), download them from the publisher and "
        f"drop them at the indicated paths — vaultlab will pick them "
        f"up on the next `/lit-arc` run.",
        "",
        "## Per-paper instructions",
        "",
    ]
    for doi, r in failed:
        meta = corpus_papers.get(doi) if corpus_papers else None
        if meta is not None:
            title_s = (getattr(meta, "title", "") or "").strip() or doi
            journal_s = (getattr(meta, "journal", "") or "").strip()
        else:
            title_s = doi
            journal_s = ""
        tried = ", ".join(r.tried) if r.tried else "(none)"
        lines.append(f"### {title_s}")
        lines.append("")
        if journal_s:
            lines.append(f"- **Journal:** {journal_s}")
        lines.append(f"- **Publisher URL:** <{r.publisher_url}>")
        lines.append(f"- **Drop the PDF at:** `{r.cache_target_path}`")
        lines.append(f"- **Tried sources:** {tried}")
        if r.tier_errors:
            err_summary = "; ".join(
                f"{k}={v[:60]}" for k, v in r.tier_errors.items()
            )
            lines.append(f"- **Why each failed:** {err_summary}")
        lines.append("")

    lines.append("## How to fetch")
    lines.append("")
    lines.append(
        "1. Click the publisher URL above. If you're on Duke VPN or "
        "logged in via the Duke library proxy, the PDF download button "
        "should be available."
    )
    lines.append(
        "2. Save the PDF to the indicated path (the directory exists; "
        "you just need to write the file)."
    )
    lines.append(
        "3. Re-run `/lit-arc` for this topic. vaultlab will detect the "
        "file in cache and pick it up automatically — no code changes "
        "needed."
    )
    return "\n".join(lines) + "\n"


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
    aggressive_retry: bool = False,
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
        aggressive_retry: If ``True``, papers that came back ``failed`` in
            the first acquisition pass get a second chance through the full
            Springer/Elsevier waterfall — used by ``depth="complete"`` runs
            (see :func:`vaultlab.research.lineage.run_lit_arc`). Implies
            ``skip_paywalled=False`` for the retry pass regardless of the
            top-level ``skip_paywalled`` argument. Only takes effect after
            an initial pass has run, and only re-attempts DOIs whose first
            pass produced ``source="failed"``.
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

    def _one(doi: str, *, force_skip_paywalled: bool | None = None) -> AcquisitionResult:
        # Each worker uses its own session so per-source rate limits stay
        # local to the thread; otherwise ``_PoliteSession`` would funnel
        # all calls through one delay clock.
        return acquire_pdf(
            doi,
            cache_dir=cache_dir,
            apis=apis,
            skip_paywalled=(
                force_skip_paywalled
                if force_skip_paywalled is not None
                else skip_paywalled
            ),
            timeout=timeout,
        )

    if parallel <= 1:
        for i, doi in enumerate(dois, 1):
            res = _one(doi)
            results[doi] = res
            if progress is not None:
                progress(doi, i, total)
    else:
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

    # Aggressive retry: re-attempt the waterfall (with paywalled tiers
    # enabled) for any DOI whose first pass failed. This matches the
    # ``depth="complete"`` contract — read every PDF we can possibly get.
    if aggressive_retry:
        retry_dois = [
            d for d, r in results.items()
            if r.pdf_path is None and r.source == "failed"
        ]
        if retry_dois:
            logger.info(
                "acquire_pdfs_for_corpus: aggressive_retry on %d paywalled papers",
                len(retry_dois),
            )
            for d in retry_dois:
                # Force paywalled tiers ON for the retry, regardless of
                # the top-level skip_paywalled flag.
                results[d] = _one(d, force_skip_paywalled=False)

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


