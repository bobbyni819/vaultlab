"""Batched PDF summarization — read multiple papers in one LLM call.

Background
----------
Today the Tier-A summarizer reads ONE PDF per LLM call. With Anthropic's
1M-context Claude Opus models, this is wasteful: 5-15 PDFs fit comfortably
in one request, and batching delivers three benefits:

1. **Cost + latency reduction** — fewer round-trips, less API overhead.
2. **Cross-paper synthesis** — the LLM sees related papers together,
   so cross-references (e.g., "Paper A's CODEX panel was extended by
   Paper B") can be detected during summarization rather than only in
   the narrator stage.
3. **Better TL;DR coherence** — papers in the same lineage get
   summarized with consistent terminology when the model sees them
   together.

The downsides — risk of cross-contamination (LLM mixing facts between
papers), output-token pressure, ordering sensitivity — are controllable
via the task structure: each paper gets a numbered slot in the prompt,
the LLM is required to return a top-level dict keyed by DOI, and the
response parser validates schema per DOI before applying.

Architecture
------------
:func:`prepare_batch_task` builds a :class:`BatchSummarizationTask` from
a list of (doi, pdf_path, metadata) tuples. The task carries:

* The composite prompt with each paper as a numbered "PAPER N" block
* The system prompt with batch-specific guard rails
* The response schema (top-level ``summaries: {<doi>: <per-paper-schema>}``)

:func:`apply_batch_response` parses the LLM response and applies each
per-paper summary to its corresponding :class:`PaperSummary` instance.

The function is gated by :func:`should_batch`: only batches when ≥2
papers all have PDFs and total estimated PDF size is under the model's
context window. Single papers fall through to the existing per-paper
:func:`summarize.summarize_paper` path.

Usage
-----
::

    from vaultlab.research.batched_reader import (
        prepare_batch_task, apply_batch_response, should_batch,
    )

    pdf_specs = [
        (doi, pdf_path, paper_metadata) for doi, pdf_path, paper_metadata in batch
    ]
    if should_batch(pdf_specs):
        task = prepare_batch_task(pdf_specs)
        response = reader_callback(task)  # YOUR Claude Code reader
        apply_batch_response(summaries, response)

Defaults
--------
- ``DEFAULT_BATCH_SIZE = 8`` — middle of the safe range (5-12).
- ``MAX_BATCH_PDF_BYTES = 100MB`` — defensive cap on total PDF size
  per request.
- ``MIN_BATCH_SIZE = 2`` — single papers go through the existing
  per-paper path (no point batching one).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


DEFAULT_BATCH_SIZE = 8
MIN_BATCH_SIZE = 2
MAX_BATCH_PDF_BYTES = 100 * 1024 * 1024  # 100 MB total per call


# ---------------------------------------------------------------------------
# Gate: when to batch
# ---------------------------------------------------------------------------


def should_batch(
    pdf_specs: list[tuple[str, Path, dict[str, Any]]],
    *,
    max_total_bytes: int = MAX_BATCH_PDF_BYTES,
) -> bool:
    """Return True if a batch of PDFs qualifies for batched summarization.

    Args:
        pdf_specs: List of (doi, pdf_path, metadata) tuples.
        max_total_bytes: Defensive cap on total PDF size.

    Returns:
        True if all of the following:
        * ≥ MIN_BATCH_SIZE papers
        * Every PDF path exists
        * Total size under ``max_total_bytes``
    """
    if len(pdf_specs) < MIN_BATCH_SIZE:
        return False

    total_bytes = 0
    for _, pdf_path, _ in pdf_specs:
        if pdf_path is None or not Path(pdf_path).exists():
            return False
        try:
            total_bytes += Path(pdf_path).stat().st_size
        except OSError:
            return False
    return total_bytes <= max_total_bytes


# ---------------------------------------------------------------------------
# Task envelope
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BatchSummarizationTask:
    """A prepared multi-paper summarization task.

    Attributes:
        dois: Lower-cased DOIs in batch order.
        pdf_paths: Paths to PDFs in batch order (parallel to ``dois``).
        paper_metadata: Per-paper metadata dicts (parallel to ``dois``).
        prompt: Composite user-message prompt with all papers numbered.
        system_prompt: Batch-specific system message.
        response_schema: JSON schema for the response.
    """

    dois: list[str]
    pdf_paths: list[Path]
    paper_metadata: list[dict[str, Any]]
    prompt: str
    system_prompt: str
    response_schema: dict[str, Any]


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------


_BATCH_SYSTEM_PROMPT = """\
You are summarizing MULTIPLE research papers in a single response.
Each paper is provided as a separate PDF document attached to this
message, and labeled "PAPER 1", "PAPER 2", etc. in the user prompt.

CRITICAL ANTI-CONTAMINATION GUARDRAILS:
- Each summary MUST be based ONLY on its corresponding PDF. Do NOT
  let facts from PAPER 1 leak into PAPER 2's summary.
- If you reference one paper from inside another's summary (e.g., in
  the "Connections" section), use ONLY information that paper itself
  states — do NOT use facts from PAPER 2 to enrich PAPER 1's claims.
- When a claim could plausibly come from multiple papers, attribute
  it to the specific PDF that contains it.
- [pN] page anchors must be the actual page in THAT paper's PDF, not
  a cross-paper reference.

PER-PAPER REQUIREMENTS (same as single-paper summarization):
- TL;DR: exactly 3 sentences. First names the paper's central
  contribution.
- why_it_matters: 2-5 bullets explaining novelty / impact.
- methods_summary: 1-2 paragraphs of methodological detail.
- key_findings: 3-7 numbered findings, each ending [pN] page anchor.
- extracted_references: empty unless the prompt explicitly requests
  references for that paper.

OUTPUT FORMAT:
Return ONLY a JSON object of the form:

{
  "summaries": {
    "<DOI of PAPER 1 in lowercase>": { ...per-paper fields... },
    "<DOI of PAPER 2 in lowercase>": { ...per-paper fields... },
    ...
  }
}

NO markdown fencing. NO commentary outside the JSON. Every DOI in
the user prompt must appear as a key in "summaries"; missing DOIs
will be treated as failed and re-summarized individually.
"""


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------


def build_batch_prompt(
    *,
    pdf_specs: list[tuple[str, Path, dict[str, Any]]],
    role_hints: dict[str, str] | None = None,
) -> str:
    """Build the user-message prompt for a batched summarization call.

    Args:
        pdf_specs: List of (doi, pdf_path, metadata) tuples.
        role_hints: Optional per-DOI role context strings.

    Returns:
        Complete user-message prompt with each paper as a numbered
        "PAPER N" block.
    """
    role_hints = role_hints or {}
    lines = [
        f"You are summarizing {len(pdf_specs)} papers in this batch. "
        "Each paper's PDF is attached above; the order matches the "
        "PAPER N labels below.",
        "",
    ]
    for i, (doi, _path, metadata) in enumerate(pdf_specs, start=1):
        title = metadata.get("title", "(unknown title)")
        authors_list = metadata.get("authors", [])
        if isinstance(authors_list, list):
            authors = ", ".join(str(a) for a in authors_list[:5])
            if len(authors_list) > 5:
                authors += f" + {len(authors_list) - 5} others"
        else:
            authors = str(authors_list)
        year = metadata.get("year", "?")
        journal = metadata.get("journal", "?")

        block = [
            f"=== PAPER {i} ===",
            f"DOI: {doi}",
            f"Title: {title}",
            f"Authors: {authors}",
            f"Year: {year}",
            f"Journal: {journal}",
        ]
        role = role_hints.get(doi.lower(), "")
        if role:
            block.append(f"Role hint: {role}")
        lines.extend(block)
        lines.append("")

    lines.extend([
        "Produce a JSON object of the form:",
        "",
        "{",
        '  "summaries": {',
    ])
    for doi, _path, _md in pdf_specs:
        lines.append(f'    "{doi.lower()}": {{ ...per-paper fields... }},')
    lines.extend([
        "  }",
        "}",
        "",
        "Each per-paper field set must include tldr (3 sentences),",
        "why_it_matters (2-5 bullets), methods_summary (1-2 paragraphs),",
        "key_findings (3-7 entries with [pN] page anchors), and",
        "extracted_references (typically empty unless requested).",
    ])
    return "\n".join(lines)


def batch_response_schema(
    dois: list[str],
) -> dict[str, Any]:
    """JSON schema for a batched-summarization response.

    The response must have a top-level ``summaries`` object keyed by
    DOI; each per-DOI value matches the per-paper response schema.
    """
    per_paper_schema = {
        "type": "object",
        "required": [
            "tldr", "why_it_matters", "methods_summary",
            "key_findings", "extracted_references",
        ],
        "properties": {
            "tldr": {"type": "string"},
            "why_it_matters": {"type": "array", "items": {"type": "string"}},
            "methods_summary": {"type": "string"},
            "key_findings": {"type": "array", "items": {"type": "string"}},
            "extracted_references": {
                "type": "array", "items": {"type": "string"},
            },
        },
    }
    return {
        "type": "object",
        "required": ["summaries"],
        "properties": {
            "summaries": {
                "type": "object",
                "properties": {doi.lower(): per_paper_schema for doi in dois},
                "required": [doi.lower() for doi in dois],
            },
        },
    }


def prepare_batch_task(
    *,
    pdf_specs: list[tuple[str, Path, dict[str, Any]]],
    role_hints: dict[str, str] | None = None,
) -> BatchSummarizationTask:
    """Build a :class:`BatchSummarizationTask` from a list of paper specs.

    Args:
        pdf_specs: List of (doi, pdf_path, metadata) tuples.
        role_hints: Optional per-DOI role-context strings.

    Returns:
        A :class:`BatchSummarizationTask`.
    """
    dois = [doi.lower() for doi, _, _ in pdf_specs]
    pdf_paths = [Path(p) for _, p, _ in pdf_specs]
    metas = [m for _, _, m in pdf_specs]
    prompt = build_batch_prompt(pdf_specs=pdf_specs, role_hints=role_hints)
    return BatchSummarizationTask(
        dois=dois,
        pdf_paths=pdf_paths,
        paper_metadata=metas,
        prompt=prompt,
        system_prompt=_BATCH_SYSTEM_PROMPT,
        response_schema=batch_response_schema(dois),
    )


# ---------------------------------------------------------------------------
# Response → per-paper summaries
# ---------------------------------------------------------------------------


def parse_batch_response(
    *,
    response: dict[str, Any],
    dois: list[str],
) -> dict[str, dict[str, Any]]:
    """Extract per-DOI summaries from a batched LLM response.

    Args:
        response: The full LLM response dict.
        dois: DOIs we expected to find (in batch order).

    Returns:
        Dict mapping lower-cased DOI → per-paper summary dict. DOIs
        missing from the response (i.e., the LLM dropped one) are
        omitted; the caller should re-summarize them individually.
    """
    summaries_obj = response.get("summaries") if isinstance(response, dict) else None
    if not isinstance(summaries_obj, dict):
        logger.warning(
            "batch response missing 'summaries' key; got keys: %s",
            list(response.keys()) if isinstance(response, dict) else "(non-dict)",
        )
        return {}

    result: dict[str, dict[str, Any]] = {}
    requested = {d.lower() for d in dois}
    for key, value in summaries_obj.items():
        key_lower = key.lower()
        if key_lower not in requested:
            logger.warning(
                "batch response includes unexpected DOI %s; skipping",
                key_lower,
            )
            continue
        if not isinstance(value, dict):
            logger.warning(
                "batch response for %s is not a dict; skipping", key_lower,
            )
            continue
        result[key_lower] = value

    missing = requested - set(result.keys())
    if missing:
        logger.warning(
            "batch response missing %d DOIs: %s",
            len(missing), ", ".join(sorted(missing)),
        )
    return result


def apply_batch_response_to_summary(
    *,
    summary,  # PaperSummary; not type-imported to avoid circular dep
    per_paper_response: dict[str, Any],
    pdf_path: Path | None = None,
) -> None:
    """Apply one DOI's per-paper response from a batch to its summary.

    Sets ``tier="A"`` (since batch path requires PDFs), populates all
    content fields, and stamps provenance with ``extracted_via`` =
    ``"claude-batch"`` so post-hoc audits can tell batched summaries
    apart from per-paper ones.

    Args:
        summary: The :class:`PaperSummary` to mutate.
        per_paper_response: One paper's slice of the batch response.
        pdf_path: Optional PDF path for provenance.
    """
    summary.tier = "A"
    summary.tldr = (per_paper_response.get("tldr") or "").strip()
    summary.why_it_matters = list(per_paper_response.get("why_it_matters") or [])
    summary.methods_summary = (
        (per_paper_response.get("methods_summary") or "").strip()
    )
    summary.key_findings = list(per_paper_response.get("key_findings") or [])
    summary.extracted_references = list(
        per_paper_response.get("extracted_references") or []
    )
    summary.extracted_at = datetime.now(timezone.utc).isoformat()
    summary.extracted_via = "claude-batch"
    if pdf_path is not None:
        summary.source_pdf = str(pdf_path)


__all__ = [
    "BatchSummarizationTask",
    "DEFAULT_BATCH_SIZE",
    "MAX_BATCH_PDF_BYTES",
    "MIN_BATCH_SIZE",
    "apply_batch_response_to_summary",
    "batch_response_schema",
    "build_batch_prompt",
    "parse_batch_response",
    "prepare_batch_task",
    "should_batch",
]
