"""Figure-acquisition layer for vaultlab corpora (API-only, no PDF mining).

For each DOI we try to obtain native-resolution figure files plus their
captions / labels via APIs that publish them as machine-readable assets:

    1. **PMC OA tar package** — the primary path.  The OA service at
       ``https://www.ncbi.nlm.nih.gov/pmc/utils/oa/oa.fcgi?id=PMC<id>``
       returns a record with an FTP/HTTP link to a ``.tar.gz`` containing
       both the article XML (``<stem>.nxml``) and the figure files
       (``.jpg``/``.png``/``.tif``/``.gif``) at native resolution.  We
       parse the ``<fig>`` elements in the NXML to recover labels and
       captions, then match each ``<graphic xlink:href="...">`` to a
       file extracted from the tar.
    2. **Elsevier ScienceDirect Article Retrieval (XML)** — the secondary
       path for paywalled Cell Press / Elsevier titles when an institutional
       ``elsevier_key`` is configured.  The XML response contains
       ``<ce:figure>`` elements with labels, captions, and ``<ce:link
       locator="grN"/>`` references.  We resolve each locator to the
       Elsevier object-retrieval endpoint
       (``/content/object/eid/1-s2.0-<PII>-<locator>_lrg.jpg``) which
       returns the high-resolution JPEG bytes.  Confirmed empirically
       2026-04-30 against ``cell.2018.07.010`` (Goltsev CODEX, 15 figures),
       ``immuni.2018.12.018`` (7 figures), ``cell.2020.07.005`` (14
       figures) — the institutional key on file unlocks ~100 paywalled
       Elsevier DOIs in the existing CODEX corpus.
    3. **Springer Open Access JSON** — the tertiary path for non-PMC
       Springer papers.  The OA API does NOT advertise figure URLs
       (verified empirically 2026-04-30 — top-level keys are
       ``contentType, identifier, language, url, title, creators,
       publicationName, doi, publisher, ..., abstract, subjects,
       disciplines``; no ``figures``/``graphics``/``images`` field).
       The probe code is retained so future schema changes can be
       handled by widening the field probe.  The Springer Meta API v2
       (which DOES expose figures) requires a separate
       ``springer_meta_api_key`` that is not currently provisioned.

Anything that cannot be resolved by these paths is returned with
``source = "unavailable"``.  We never fall back to extracting images
from PDFs — the user has explicitly opted out of that path.

Cache layout::

    cache_dir / <doi-slug> / <fig-id>.<ext>
    cache_dir / <doi-slug> / .nxml          (PMC only — the article XML)
    cache_dir / <doi-slug> / .figures.json  (manifest of FigureAcquisitionResult)

DOI slugs use the same convention as :mod:`vaultlab.research.acquisition`
(``10.1126/science.1225829`` -> ``10-1126_science-1225829``).
"""

from __future__ import annotations

import io
import json
import logging
import re
import tarfile
import xml.etree.ElementTree as ET
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from vaultlab.research.acquisition import (
    PMC_IDCONV_BASE,
    USER_AGENT,
    _PoliteSession,
    doi_slug,
)
from vaultlab.research.corpus import Corpus

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PMC_OA_BASE = "https://www.ncbi.nlm.nih.gov/pmc/utils/oa/oa.fcgi"
"""PMC Open Access service — issues tar/PDF links keyed by PMCID."""

SPRINGER_OA_BASE = "http://api.springernature.com/openaccess/json"
"""Springer Open Access JSON API; queried by DOI."""

ELSEVIER_ARTICLE_BASE = "https://api.elsevier.com/content/article/doi"
"""Elsevier ScienceDirect Article Retrieval API; XML by DOI."""

ELSEVIER_OBJECT_BASE = "https://api.elsevier.com/content/object/eid"
"""Elsevier object retrieval — fetches figure binaries by EID."""

_DEFAULT_TIMEOUT = 60
_FIGURE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".tif", ".tiff", ".gif")
"""File extensions in the PMC OA tar package that we treat as figures."""

# JATS XML namespaces — the OA NXML files use the standard JATS schema.
_NS = {
    "xlink": "http://www.w3.org/1999/xlink",
}

# Elsevier full-text-retrieval-response namespaces.
_ELS_NS = {
    "ce": "http://www.elsevier.com/xml/common/dtd",
    "xlink": "http://www.w3.org/1999/xlink",
    "xocs": "http://www.elsevier.com/xml/xocs/dtd",
    "prism": "http://prismstandard.org/namespaces/basic/2.0/",
    "dc": "http://purl.org/dc/elements/1.1/",
}


# ---------------------------------------------------------------------------
# Public dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Figure:
    """A single extracted figure with metadata.

    Attributes:
        figure_id: Stable identifier (usually from the NXML ``<fig id=...>``
            attribute, e.g. ``"fig1"`` or ``"fig-S2"``; falls back to the
            graphic filename stem).
        file_path: Local path to the cached figure file.
        caption: Caption text extracted from the NXML; empty for non-PMC
            sources.
        label: Display label (e.g. ``"Figure 1"``, ``"Fig 2A"``); empty
            when the source has no label field.
        panels: Panel letters (``["A", "B", "C"]``) when detectable from
            the caption; empty otherwise.
    """

    figure_id: str
    file_path: Path
    caption: str = ""
    label: str = ""
    panels: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class FigureAcquisitionResult:
    """Outcome of a single :func:`acquire_figures` call.

    Attributes:
        doi: The lower-cased DOI we attempted to acquire figures for.
        figures: List of :class:`Figure`; empty when ``source ==
            "unavailable"``.
        source: Tier that succeeded:
            ``"pmc-tar" | "springer-api" | "cache" | "unavailable"``.
        error: Free-text reason populated when ``source == "unavailable"``.
    """

    doi: str
    figures: list[Figure]
    source: str
    error: str | None = None


# ---------------------------------------------------------------------------
# Cache helpers
# ---------------------------------------------------------------------------


def figure_cache_dir(doi: str, cache_dir: Path) -> Path:
    """Return the per-paper cache directory for ``doi`` under ``cache_dir``."""
    return Path(cache_dir) / doi_slug(doi)


def _manifest_path(paper_dir: Path) -> Path:
    return paper_dir / ".figures.json"


def _save_manifest(result: FigureAcquisitionResult, paper_dir: Path) -> None:
    """Persist a manifest of the result so we can short-circuit on re-runs."""
    paper_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "doi": result.doi,
        "source": result.source,
        "error": result.error,
        "figures": [
            {
                "figure_id": f.figure_id,
                "file_path": str(f.file_path),
                "caption": f.caption,
                "label": f.label,
                "panels": list(f.panels),
            }
            for f in result.figures
        ],
    }
    with open(_manifest_path(paper_dir), "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2)


def _load_manifest(paper_dir: Path) -> FigureAcquisitionResult | None:
    """Load a saved manifest if every referenced file still exists."""
    p = _manifest_path(paper_dir)
    if not p.exists():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    figures = []
    for f in data.get("figures", []):
        path = Path(f.get("file_path", ""))
        if not path.exists():
            return None  # cache stale — re-acquire
        figures.append(
            Figure(
                figure_id=f.get("figure_id", ""),
                file_path=path,
                caption=f.get("caption", ""),
                label=f.get("label", ""),
                panels=list(f.get("panels", [])),
            )
        )
    return FigureAcquisitionResult(
        doi=data.get("doi", ""),
        figures=figures,
        source="cache",
        error=data.get("error"),
    )


# ---------------------------------------------------------------------------
# Tier 1: PMC OA tar
# ---------------------------------------------------------------------------


def _doi_to_pmcid(doi: str, session: _PoliteSession) -> str | None:
    """Resolve a DOI to a PMCID via the NCBI ID Converter API."""
    resp = session.get(
        "pmc",
        PMC_IDCONV_BASE,
        params={
            "ids": doi,
            "idtype": "doi",
            "format": "json",
            "tool": "vaultlab",
            "email": "bobby.ni@duke.edu",
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
    return pmcid or None


def _resolve_pmc_tar_url(pmcid: str, session: _PoliteSession) -> str | None:
    """Query the PMC OA service for a ``format=tgz`` link for ``pmcid``.

    Response shape::

        <OA>
          <records>
            <record id="PMC..." citation="..." license="...">
              <link format="tgz" updated="..." href="ftp://..."/>
            </record>
          </records>
        </OA>

    Returns the ``href`` of the ``tgz`` link or ``None`` if the paper
    isn't in the OA subset.  FTP URLs are rewritten to HTTPS because
    NCBI's FTP front-end has been retired in many regions.
    """
    resp = session.get(
        "pmc",
        PMC_OA_BASE,
        params={"id": pmcid, "format": "tgz"},
    )
    if resp is None or resp.status_code != 200:
        return None
    try:
        root = ET.fromstring(resp.content)
    except ET.ParseError:
        return None
    # If the paper is not OA the response carries an <error code="..."/>
    err = root.find(".//error")
    if err is not None:
        logger.debug("PMC OA error for %s: %s", pmcid, err.attrib)
        return None
    link = root.find(".//link[@format='tgz']")
    if link is None:
        return None
    href = link.get("href", "")
    if not href:
        return None
    # NCBI emits ftp:// links but the FTP front-end has been retired.
    # The same paths serve over HTTPS, but the OA bulk directories were
    # moved under /pub/pmc/deprecated/ in 2026.  Rewrite both quirks.
    if href.startswith("ftp://"):
        href = "https://" + href[len("ftp://") :]
    for old, new in (
        ("/pub/pmc/oa_package/", "/pub/pmc/deprecated/oa_package/"),
        ("/pub/pmc/oa_pdf/", "/pub/pmc/deprecated/oa_pdf/"),
        ("/pub/pmc/oa_bulk/", "/pub/pmc/deprecated/oa_bulk/"),
    ):
        if old in href and "/deprecated/" not in href:
            href = href.replace(old, new)
    return href


def _download_tar_bytes(
    url: str,
    session: _PoliteSession,
) -> bytes | None:
    """Fetch ``url`` and return its bytes (no PDF/format guards needed)."""
    resp = session.get("pmc", url)
    if resp is None or resp.status_code != 200:
        return None
    if not resp.content:
        return None
    return resp.content


def _extract_panels_from_caption(caption: str) -> list[str]:
    """Best-effort panel-letter detection from a caption string.

    Handles ``(A)``, ``(a, b)``, ``A.``, etc.  Only single-letter labels
    A-Z are kept (case-insensitive, returned upper-cased).  Duplicates
    are removed in first-seen order.
    """
    if not caption:
        return []
    # Patterns of the form "(A)", "(A, B)", " A. ", "(a–c)" etc.
    found: list[str] = []
    seen: set[str] = set()
    for match in re.finditer(
        r"\(([a-zA-Z](?:\s*[,–—\-]\s*[a-zA-Z])*)\)",
        caption,
    ):
        group = match.group(1)
        # Split on commas, hyphens, en/em dashes.
        parts = re.split(r"[,–—\-]", group)
        for raw in parts:
            letter = raw.strip().upper()
            if len(letter) == 1 and "A" <= letter <= "Z" and letter not in seen:
                seen.add(letter)
                found.append(letter)
    return found


def _parse_nxml_figures(nxml_bytes: bytes) -> dict[str, dict[str, str]]:
    """Parse an NXML article and return ``{href -> {"id","label","caption"}}``.

    The keys are the basenames referenced by ``<graphic xlink:href="...">``
    inside ``<fig>`` elements.  The basename match lets the caller pair
    each figure file extracted from the tar with its metadata.

    The NXML schema looks like::

        <fig id="fig1">
          <label>Figure 1</label>
          <caption><p>...</p></caption>
          <graphic xlink:href="fig1"/>
        </fig>
    """
    try:
        root = ET.fromstring(nxml_bytes)
    except ET.ParseError as exc:
        logger.warning("NXML parse error: %s", exc)
        return {}

    out: dict[str, dict[str, str]] = {}
    # JATS uses unprefixed tag names; iterate by tag.
    for fig in root.iter("fig"):
        fig_id = fig.get("id", "") or ""
        label_el = fig.find("label")
        label_text = _all_text(label_el) if label_el is not None else ""
        caption_el = fig.find("caption")
        caption_text = _all_text(caption_el) if caption_el is not None else ""
        # Find every <graphic> under this fig (some figs have multiple panels
        # as separate graphics).
        for graphic in fig.iter("graphic"):
            href = graphic.get(f"{{{_NS['xlink']}}}href") or graphic.get("href")
            if not href:
                continue
            # Strip directory parts; figures live alongside the NXML in
            # the tar, so the basename is the lookup key.
            basename = href.rsplit("/", 1)[-1]
            out[basename] = {
                "id": fig_id or basename,
                "label": label_text,
                "caption": caption_text,
            }
    return out


def _all_text(element: ET.Element | None) -> str:
    """Concatenate every text node under ``element`` (XML mixed content)."""
    if element is None:
        return ""
    parts: list[str] = []
    if element.text:
        parts.append(element.text)
    for child in element:
        parts.append(_all_text(child))
        if child.tail:
            parts.append(child.tail)
    return re.sub(r"\s+", " ", "".join(parts)).strip()


def _extract_tar_to_dir(tar_bytes: bytes, target_dir: Path) -> tuple[list[Path], bytes | None]:
    """Extract figure files (and capture the NXML bytes) from a PMC tar package.

    Returns ``(figure_paths, nxml_bytes)``.  ``nxml_bytes`` is ``None`` if
    the package doesn't contain an article XML (unusual but tolerated —
    we still salvage the figures and return them with empty captions).

    All paths returned are inside ``target_dir`` and have been hardened
    against tar traversal (any entry whose resolved path escapes
    ``target_dir`` is silently dropped).
    """
    target_dir.mkdir(parents=True, exist_ok=True)
    figure_paths: list[Path] = []
    nxml_bytes: bytes | None = None

    with tarfile.open(fileobj=io.BytesIO(tar_bytes), mode="r:gz") as tar:
        for member in tar.getmembers():
            if not member.isfile():
                continue
            name = member.name
            base = name.rsplit("/", 1)[-1]
            ext = ("." + base.rsplit(".", 1)[-1].lower()) if "." in base else ""

            # Defensive: ignore any entry that escapes the target dir.
            target_path = (target_dir / base).resolve()
            if not str(target_path).startswith(str(target_dir.resolve())):
                logger.warning("Refusing to extract suspect tar entry: %s", name)
                continue

            try:
                fh = tar.extractfile(member)
                if fh is None:
                    continue
                data = fh.read()
            except (OSError, tarfile.TarError) as exc:
                logger.debug("Failed to read tar entry %s: %s", name, exc)
                continue

            if ext == ".nxml" and nxml_bytes is None:
                nxml_bytes = data
                continue

            if ext in _FIGURE_EXTENSIONS:
                with open(target_path, "wb") as out:
                    out.write(data)
                figure_paths.append(target_path)

    return figure_paths, nxml_bytes


def _try_pmc_tar(
    doi: str,
    paper_dir: Path,
    session: _PoliteSession,
) -> FigureAcquisitionResult | None:
    """Attempt the PMC OA tar path.  Returns ``None`` if the paper isn't
    in PMC OA; otherwise a populated result (possibly with zero figures
    when the package was empty)."""
    pmcid = _doi_to_pmcid(doi, session)
    if pmcid is None:
        return None
    tar_url = _resolve_pmc_tar_url(pmcid, session)
    if tar_url is None:
        return None
    tar_bytes = _download_tar_bytes(tar_url, session)
    if tar_bytes is None:
        return None

    figure_paths, nxml_bytes = _extract_tar_to_dir(tar_bytes, paper_dir)
    if not figure_paths:
        return FigureAcquisitionResult(
            doi=doi,
            figures=[],
            source="unavailable",
            error="PMC OA tar contained no figure files",
        )

    href_meta = _parse_nxml_figures(nxml_bytes) if nxml_bytes else {}

    figures: list[Figure] = []
    for path in figure_paths:
        # NXML <graphic href="..."> often omits the file extension; try
        # the bare stem first and then the full basename.
        stem = path.stem
        meta = href_meta.get(stem) or href_meta.get(path.name) or {}
        fig_id = meta.get("id", "") or stem
        caption = meta.get("caption", "")
        label = meta.get("label", "")
        figures.append(
            Figure(
                figure_id=fig_id,
                file_path=path,
                caption=caption,
                label=label,
                panels=_extract_panels_from_caption(caption),
            )
        )

    return FigureAcquisitionResult(
        doi=doi,
        figures=figures,
        source="pmc-tar",
    )


# ---------------------------------------------------------------------------
# Tier 2: Elsevier ScienceDirect Article Retrieval (paywalled Cell Press, etc.)
# ---------------------------------------------------------------------------


def _parse_elsevier_figures(xml_bytes: bytes) -> tuple[str, list[dict[str, str]]]:
    """Parse an Elsevier full-text-retrieval-response XML.

    Returns ``(pii, figures)`` where ``pii`` is the article PII (used to
    construct figure object EIDs) and ``figures`` is a list of dicts with
    keys ``id, label, caption, locator``.  ``locator`` is the figure key
    inside the article (e.g. ``"gr1"`` for main figures, ``"figs1"`` for
    supplementary) referenced by ``<ce:link locator="...">`` inside each
    ``<ce:figure>`` block.
    """
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as exc:
        logger.warning("Elsevier XML parse error: %s", exc)
        return "", []

    # PII: appears as <xocs:pii-unformatted>, <prism:pii>, or
    # <dc:identifier>PII:...</dc:identifier> depending on the article.
    pii = ""
    for tag in (
        f"{{{_ELS_NS['xocs']}}}pii-unformatted",
        f"{{{_ELS_NS['prism']}}}pii",
    ):
        el = root.find(f".//{tag}")
        if el is not None and el.text:
            pii = el.text.strip()
            break
    if not pii:
        # dc:identifier has the form "PII:S0..."
        for el in root.iter(f"{{{_ELS_NS['dc']}}}identifier"):
            if el.text and el.text.startswith("PII:"):
                pii = el.text[len("PII:"):].strip()
                break

    figures: list[dict[str, str]] = []
    for fig in root.iter(f"{{{_ELS_NS['ce']}}}figure"):
        fig_id = fig.get("id", "")
        label_el = fig.find(f"{{{_ELS_NS['ce']}}}label")
        label = _all_text(label_el) if label_el is not None else ""
        # Caption text lives inside <ce:caption><ce:simple-para>...
        cap_el = fig.find(f".//{{{_ELS_NS['ce']}}}simple-para")
        caption = _all_text(cap_el) if cap_el is not None else ""
        link_el = fig.find(f".//{{{_ELS_NS['ce']}}}link")
        locator = link_el.get("locator", "") if link_el is not None else ""
        if not locator:
            # Fallback: pull from xlink:href like "pii:<PII>/gr1"
            href = link_el.get(f"{{{_ELS_NS['xlink']}}}href", "") if link_el is not None else ""
            if "/" in href:
                locator = href.rsplit("/", 1)[-1]
        if not locator:
            continue
        figures.append(
            {
                "id": fig_id or locator,
                "label": label,
                "caption": caption,
                "locator": locator,
            }
        )
    return pii, figures


def _try_elsevier_api(
    doi: str,
    paper_dir: Path,
    session: _PoliteSession,
    api_key: str,
) -> FigureAcquisitionResult | None:
    """Attempt the Elsevier ScienceDirect Article Retrieval path.

    Returns ``None`` when the key is missing, the article isn't on
    ScienceDirect (404), or the XML carries no ``<ce:figure>`` blocks.
    Returns a populated result when at least one figure binary was
    successfully fetched from the object-retrieval endpoint.
    """
    if not api_key:
        return None
    url = f"{ELSEVIER_ARTICLE_BASE}/{doi}"
    resp = session.get(
        "elsevier",
        url,
        headers={"X-ELS-APIKey": api_key, "Accept": "text/xml"},
    )
    if resp is None or resp.status_code != 200 or not resp.content:
        return None

    pii, fig_meta = _parse_elsevier_figures(resp.content)
    if not pii or not fig_meta:
        return None

    paper_dir.mkdir(parents=True, exist_ok=True)
    figures: list[Figure] = []
    for entry in fig_meta:
        locator = entry["locator"]
        # Try high-res first, then fall back to standard, then small.
        # EID format: 1-s2.0-<PII>-<locator>_lrg.jpg
        eid_candidates = [
            f"1-s2.0-{pii}-{locator}_lrg.jpg",
            f"1-s2.0-{pii}-{locator}.jpg",
        ]
        fetched: tuple[bytes, str] | None = None
        for eid in eid_candidates:
            obj_url = f"{ELSEVIER_OBJECT_BASE}/{eid}"
            obj_resp = session.get(
                "elsevier",
                obj_url,
                headers={"X-ELS-APIKey": api_key},
            )
            if obj_resp is None or obj_resp.status_code != 200:
                continue
            ct = (obj_resp.headers or {}).get("Content-Type", "") if obj_resp.headers else ""
            if not obj_resp.content or "image" not in ct.lower():
                continue
            fetched = (obj_resp.content, ct)
            break
        if fetched is None:
            continue

        content, content_type = fetched
        ext = _guess_extension(content_type, eid_candidates[0])
        # Cache file name uses locator (e.g. "gr1.jpg") to mirror the
        # filenames PMC tars use; figure_id keeps the original ce:figure id.
        target = paper_dir / f"{locator}{ext}"
        with open(target, "wb") as fh:
            fh.write(content)

        caption = entry["caption"]
        figures.append(
            Figure(
                figure_id=entry["id"],
                file_path=target,
                caption=caption,
                label=entry["label"],
                panels=_extract_panels_from_caption(caption),
            )
        )

    if not figures:
        return None
    return FigureAcquisitionResult(
        doi=doi,
        figures=figures,
        source="elsevier-api",
    )


# ---------------------------------------------------------------------------
# Tier 3: Springer Open Access JSON
# ---------------------------------------------------------------------------


def _try_springer_api(
    doi: str,
    paper_dir: Path,
    session: _PoliteSession,
    api_key: str,
) -> FigureAcquisitionResult | None:
    """Attempt the Springer OA JSON path.

    Behaviour was checked empirically against the live API: the JSON
    response carries the article record but does **not** expose figure
    image URLs as standalone fields.  When that's the case (or no key is
    configured) we return ``None`` so the caller can mark the paper
    ``unavailable``.  We still ship the lookup logic so future Springer
    schema changes can be handled by widening the field probe below.
    """
    if not api_key:
        return None
    resp = session.get(
        "springer",
        SPRINGER_OA_BASE,
        params={"q": f'doi:"{doi}"', "api_key": api_key},
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

    # Probe for any field that looks like a list of figures with image
    # URLs.  Springer's OA schema does not currently advertise figures
    # but we look anyway so this code remains future-proof.
    figures_field: list[dict[str, Any]] = []
    for rec in records:
        for key in ("figures", "figure", "graphics", "images"):
            value = rec.get(key)
            if isinstance(value, list) and value:
                figures_field = value
                break
        if figures_field:
            break

    if not figures_field:
        return None

    figures: list[Figure] = []
    paper_dir.mkdir(parents=True, exist_ok=True)
    for i, entry in enumerate(figures_field, 1):
        if not isinstance(entry, dict):
            continue
        # Try several common field names for image URL.
        url = ""
        for key in ("url", "value", "imageUrl", "href", "src"):
            v = entry.get(key)
            if isinstance(v, str) and v.startswith(("http://", "https://")):
                url = v
                break
        if not url:
            continue
        try:
            fig_resp = session.get("springer", url)
        except Exception as exc:  # pragma: no cover — defensive
            logger.debug("Springer figure fetch failed for %s: %s", url, exc)
            continue
        if fig_resp is None or fig_resp.status_code != 200 or not fig_resp.content:
            continue
        ext = _guess_extension(fig_resp.headers.get("Content-Type", ""), url)
        target = paper_dir / f"fig{i}{ext}"
        with open(target, "wb") as fh:
            fh.write(fig_resp.content)
        caption = entry.get("caption") or entry.get("title") or ""
        label = entry.get("label") or ""
        figures.append(
            Figure(
                figure_id=entry.get("id", "") or f"fig{i}",
                file_path=target,
                caption=str(caption),
                label=str(label),
                panels=_extract_panels_from_caption(str(caption)),
            )
        )

    if not figures:
        return None
    return FigureAcquisitionResult(
        doi=doi,
        figures=figures,
        source="springer-api",
    )


def _guess_extension(content_type: str, url: str) -> str:
    """Pick a sensible extension from a content type / URL."""
    ct = (content_type or "").lower()
    if "jpeg" in ct or "jpg" in ct:
        return ".jpg"
    if "png" in ct:
        return ".png"
    if "tiff" in ct:
        return ".tif"
    if "gif" in ct:
        return ".gif"
    lower = url.lower()
    for ext in _FIGURE_EXTENSIONS:
        if lower.endswith(ext):
            return ext
    return ".bin"


# ---------------------------------------------------------------------------
# Config helper
# ---------------------------------------------------------------------------


def _load_default_apis() -> dict[str, str]:
    """Best-effort load of API keys from the standard config."""
    try:
        from vaultlab.research.config import get_config

        cfg = get_config()
    except Exception:
        return {}
    return {
        "springer_open_access_api_key": cfg.get("springer_open_access_api_key", ""),
        "ncbi_api_key": cfg.get("ncbi_api_key", ""),
        "elsevier_key": cfg.get("elsevier_key", ""),
    }


# ---------------------------------------------------------------------------
# Public API: single-DOI figure acquisition
# ---------------------------------------------------------------------------


def acquire_figures(
    doi: str,
    *,
    cache_dir: Path,
    apis: dict[str, str] | None = None,
    timeout: int = _DEFAULT_TIMEOUT,
    _session: _PoliteSession | None = None,
) -> FigureAcquisitionResult:
    """Acquire figures for ``doi`` via the API waterfall.

    Tries PMC OA tar first, then Springer OA JSON.  Returns
    ``source="unavailable"`` (never raises) when no API path yields
    figures.  PDF figure extraction is intentionally never attempted.

    Args:
        doi: The DOI of the paper.  Lower-cased internally.
        cache_dir: Root directory under which per-paper subfolders live.
        apis: API key map (forwarded from
            :data:`research.config`).  When ``None`` the config is
            queried for ``springer_open_access_api_key``.
        timeout: HTTP timeout per request.
        _session: Internal — share a polite session across calls in a
            corpus-wide acquisition.

    Returns:
        :class:`FigureAcquisitionResult` describing the outcome.
    """
    doi = (doi or "").strip().lower()
    if not doi:
        return FigureAcquisitionResult(
            doi=doi,
            figures=[],
            source="unavailable",
            error="empty doi",
        )

    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    paper_dir = figure_cache_dir(doi, cache_dir)

    # Cache hit — manifest validates that referenced files still exist.
    cached = _load_manifest(paper_dir)
    if cached is not None and cached.figures:
        return cached

    apis = apis if apis is not None else _load_default_apis()
    session = _session or _PoliteSession(timeout=timeout)

    # Tier 1: PMC OA tar
    try:
        result = _try_pmc_tar(doi, paper_dir, session)
    except Exception as exc:  # pragma: no cover — defensive
        logger.warning("PMC OA tar failed for %s: %s", doi, exc)
        result = None
    if result is not None and result.source == "pmc-tar" and result.figures:
        _save_manifest(result, paper_dir)
        return result

    # Tier 2: Elsevier ScienceDirect Article Retrieval (paywalled Cell Press, etc.)
    elsevier_key = apis.get("elsevier_key", "")
    try:
        result = _try_elsevier_api(doi, paper_dir, session, elsevier_key)
    except Exception as exc:  # pragma: no cover — defensive
        logger.warning("Elsevier figure API failed for %s: %s", doi, exc)
        result = None
    if result is not None and result.figures:
        _save_manifest(result, paper_dir)
        return result

    # Tier 3: Springer OA JSON (probe-only — empirically no figures field)
    springer_key = apis.get("springer_open_access_api_key", "")
    try:
        result = _try_springer_api(doi, paper_dir, session, springer_key)
    except Exception as exc:  # pragma: no cover — defensive
        logger.warning("Springer figure API failed for %s: %s", doi, exc)
        result = None
    if result is not None and result.figures:
        _save_manifest(result, paper_dir)
        return result

    final = FigureAcquisitionResult(
        doi=doi,
        figures=[],
        source="unavailable",
        error="no API source provided figures (tried pmc-tar, elsevier-api, springer-api)",
    )
    # Persist the unavailable verdict so the next run doesn't re-query.
    _save_manifest(final, paper_dir)
    return final


# ---------------------------------------------------------------------------
# Public API: corpus-wide figure acquisition
# ---------------------------------------------------------------------------


def acquire_figures_for_corpus(
    corpus: Corpus,
    cache_dir: Path,
    *,
    parallel: int = 2,
    apis: dict[str, str] | None = None,
    timeout: int = _DEFAULT_TIMEOUT,
    progress: Callable[[str, int, int], None] | None = None,
) -> dict[str, FigureAcquisitionResult]:
    """Run :func:`acquire_figures` for every paper in ``corpus.papers``.

    Args:
        corpus: A built :class:`Corpus`.  Only papers with non-empty DOIs
            are attempted.
        cache_dir: Root directory for per-paper figure caches.
        parallel: Worker count for the thread pool.  Default ``2`` to
            keep within NCBI's polite-pool rate limit (3 req/s without
            an API key).
        apis: API key map (forwarded to :func:`acquire_figures`).
        timeout: Per-request HTTP timeout.
        progress: Optional callback ``progress(doi, done, total)``.

    Returns:
        Mapping ``doi -> FigureAcquisitionResult``.
    """
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)

    apis = apis if apis is not None else _load_default_apis()
    dois = [d for d in corpus.papers if d]
    total = len(dois)
    results: dict[str, FigureAcquisitionResult] = {}

    def _one(doi: str) -> FigureAcquisitionResult:
        # Each worker gets its own session so per-source delays remain
        # local to the thread (mirrors research.acquisition).
        return acquire_figures(
            doi,
            cache_dir=cache_dir,
            apis=apis,
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
                res = FigureAcquisitionResult(
                    doi=doi,
                    figures=[],
                    source="unavailable",
                    error=f"worker exception: {exc}",
                )
            results[doi] = res
            done += 1
            if progress is not None:
                progress(doi, done, total)
    return results


# ---------------------------------------------------------------------------
# Helpers re-exported for tests
# ---------------------------------------------------------------------------


__all__ = [
    "ELSEVIER_ARTICLE_BASE",
    "ELSEVIER_OBJECT_BASE",
    "Figure",
    "FigureAcquisitionResult",
    "PMC_OA_BASE",
    "SPRINGER_OA_BASE",
    "USER_AGENT",
    "acquire_figures",
    "acquire_figures_for_corpus",
    "figure_cache_dir",
]


# Internal helpers exported for tests.
__test_exports__ = [
    "_doi_to_pmcid",
    "_extract_panels_from_caption",
    "_extract_tar_to_dir",
    "_load_manifest",
    "_parse_elsevier_figures",
    "_parse_nxml_figures",
    "_resolve_pmc_tar_url",
    "_save_manifest",
    "_try_elsevier_api",
    "_try_pmc_tar",
    "_try_springer_api",
]
