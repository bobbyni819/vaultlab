"""Section-aware reader — dispatch text extraction by acquisition source.

Per the 2026-05-02 paperclip integration design (Q3), Tier-A reading
should use paperclip's pre-extracted sections when available
(higher-quality semantic boundaries than ``pdftoppm`` page-1-10) and
fall back to the existing PDF text-extraction path otherwise.

This module is the dispatcher. Callers pass an
:class:`AcquisitionResult` and (optionally) a
:class:`PaperclipClient`; we route based on the result's classified
``outcome``:

* ``paperclip_full_text``  →  read sections via PaperclipClient
* ``cache_hit | oa_pdf | gated_pdf_via_key``  →  pdf.extract_text
* ``gated_metadata_only``  →  Tier-B: return abstract from the corpus
                              (caller passes that in via ``abstract=...``)
* anything else            →  empty string

The function returns a single string suitable for an LLM read. For
callers that need structured sections (e.g. to extract Methods alone),
use :func:`read_paper_sections`.
"""

from __future__ import annotations

import logging
from pathlib import Path

from vaultlab.research.acquisition import AcquisitionResult

logger = logging.getLogger(__name__)


def read_paper_text(
    result: AcquisitionResult,
    *,
    paperclip_client=None,
    paperclip_paper_id: str | None = None,
    abstract_fallback: str = "",
) -> str:
    """Return the readable body text for a paper.

    Args:
        result: The :class:`AcquisitionResult` from ``acquire_pdf``.
        paperclip_client: Required when
            ``result.outcome == "paperclip_full_text"``. Skipped
            otherwise.
        paperclip_paper_id: Required when reading from paperclip — the
            corpus-internal ID like ``arx_2107.07953``. The orchestrator
            keeps the ID alongside the DOI in the picks list.
        abstract_fallback: When ``result.outcome == "gated_metadata_only"``
            the caller can pass the abstract text from the corpus
            metadata as a Tier-B fallback. Empty string disables.

    Returns:
        Body text suitable for LLM ingestion. Empty string when no
        readable source is available.
    """
    outcome = result.outcome
    if outcome == "paperclip_full_text":
        if paperclip_client is None or not paperclip_paper_id:
            logger.warning(
                "read_paper_text: paperclip outcome but no client/paper_id "
                "for doi=%s — falling back to empty",
                result.doi,
            )
            return ""
        return paperclip_client.get_paper_text(paperclip_paper_id)

    if outcome in ("cache_hit", "oa_pdf", "gated_pdf_via_key"):
        if result.pdf_path is None:
            return ""
        from vaultlab.research.pdf import extract_text
        return extract_text(str(result.pdf_path))

    if outcome == "gated_metadata_only":
        return abstract_fallback or ""

    # failed_paywalled / failed_not_indexed / failed
    return ""


def read_paper_sections(
    result: AcquisitionResult,
    *,
    paperclip_client=None,
    paperclip_paper_id: str | None = None,
    abstract_fallback: str = "",
) -> dict[str, str]:
    """Return structured sections for a paper.

    For paperclip-sourced papers, returns a real section map
    (``{"Abstract": ..., "Introduction": ..., "Methods": ..., ...}``).
    For PDF-sourced papers, returns a single ``{"all": text}`` entry
    (we don't currently attempt semantic-section extraction from PDFs).
    For metadata-only outcomes, returns ``{"Abstract": abstract_fallback}``
    when the fallback is non-empty.

    Args:
        result: The :class:`AcquisitionResult` from ``acquire_pdf``.
        paperclip_client: Required for paperclip outcome.
        paperclip_paper_id: Required for paperclip outcome.
        abstract_fallback: Used for ``gated_metadata_only`` outcome.

    Returns:
        Mapping of section name → section text. May be empty.
    """
    outcome = result.outcome

    if outcome == "paperclip_full_text":
        if paperclip_client is None or not paperclip_paper_id:
            return {}
        out: dict[str, str] = {}
        for name in paperclip_client.list_sections(paperclip_paper_id):
            text = paperclip_client.get_section(paperclip_paper_id, name)
            if text:
                out[name] = text
        return out

    if outcome in ("cache_hit", "oa_pdf", "gated_pdf_via_key"):
        if result.pdf_path is None:
            return {}
        from vaultlab.research.pdf import extract_text
        text = extract_text(str(result.pdf_path))
        return {"all": text} if text else {}

    if outcome == "gated_metadata_only":
        if abstract_fallback:
            return {"Abstract": abstract_fallback}
        return {}

    return {}


def list_paper_figures(
    result: AcquisitionResult,
    *,
    paperclip_client=None,
    paperclip_paper_id: str | None = None,
    pdf_extract_dir: Path | None = None,
) -> list[str]:
    """List figure filenames available for a paper.

    For paperclip-sourced papers, returns the pre-extracted figure
    filenames from ``/papers/<id>/figures/`` (no extraction step).
    For PDF-sourced papers, returns the filenames inside
    ``pdf_extract_dir`` if a prior figure-extraction run produced them
    (see :mod:`vaultlab.research.figures`); otherwise empty.

    Args:
        result: The :class:`AcquisitionResult`.
        paperclip_client: Required for paperclip outcome.
        paperclip_paper_id: Required for paperclip outcome.
        pdf_extract_dir: Directory where ``vaultlab.research.figures.
            extract_figures`` writes its PNG outputs for the PDF case.

    Returns:
        List of filenames (no path). Empty list when no figures
        available.
    """
    outcome = result.outcome

    if outcome == "paperclip_full_text":
        if paperclip_client is None or not paperclip_paper_id:
            return []
        return paperclip_client.list_figures(paperclip_paper_id)

    if outcome in ("cache_hit", "oa_pdf", "gated_pdf_via_key"):
        if pdf_extract_dir is None or not pdf_extract_dir.exists():
            return []
        return [
            p.name for p in pdf_extract_dir.iterdir()
            if p.is_file() and p.suffix.lower() in (".png", ".jpg", ".jpeg")
        ]

    return []


__all__ = [
    "read_paper_text",
    "read_paper_sections",
    "list_paper_figures",
]
