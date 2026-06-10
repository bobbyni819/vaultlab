"""Per-paper summarization layer for vaultlab corpora.

Given an acquired PDF (or its ``Sources/Papers/<doi>.pdf`` path) and the
paper's metadata, this module produces a structured :class:`PaperSummary`
that maps directly onto the canonical ``Wiki/Summaries/<doi>.md`` format
documented in ``kb-output-conventions-2026-04-29.md``.

Two execution modes
-------------------
This module exposes **two parallel paths** for getting the LLM-generated
JSON into a :class:`PaperSummary`:

1. **SDK path** (:func:`summarize_paper`) — calls
   ``anthropic.Messages.create`` directly using an Anthropic API key.
   Use this when running from a plain Python script or service.

2. **Claude-Code-callable path** (:func:`prepare_summary_task` +
   :func:`render_summary_from_response`) — does NOT call any LLM. The
   slash command body, running inside a Claude Code session, has Claude
   itself read the PDF via the Read tool and call
   :func:`render_summary_from_response` with the JSON it produces. Use
   this from inside ``.claude/commands/<slash>.md`` bodies — Claude Code
   provides LLM access via the active session, so no API key is needed.

Both paths share :class:`PaperSummary`, :func:`build_summary_prompt`,
``_populate_citation_stats``, and ``_build_connections``. They differ
only in WHO runs the actual prompt → JSON step.

Design constraints (per the F.7 grill, decision D6)
---------------------------------------------------
* **Claude is the primary PDF reader.** No Grobid, no Marker, no PaperQA2
  dependency. The model reads the PDF bytes and emits structured JSON
  matching the :class:`PaperSummary` shape.
* **Tier C is a no-LLM stub.** When a PDF isn't available we still emit
  a summary file with the corpus metrics filled in, so the KB stays
  complete even for paywalled papers.
* **Page provenance is mandatory.** Every key finding must carry a
  ``[p<N>]`` marker; the prompt instructs Claude to omit findings it
  cannot ground in a specific page (or annotate them ``[unknown]``).
* **No fake references.** When CrossRef gives us references we trust
  them; only when ``crossref_refs_missing=True`` do we ask Claude to
  extract the references list from the PDF itself.

Authentication (SDK path only)
------------------------------
The Anthropic SDK path reads ``ANTHROPIC_API_KEY`` from the environment
by default. As a fallback we look for ``anthropic_api_key`` in the same
``research_apis.json`` config used by the rest of ``vaultlab.research``.
If neither is present the SDK path raises :class:`SummarizeAuthError`.
The Claude-Code-callable path needs no key.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

from vaultlab.kb.paths import ensure_parent, slugify_doi, summary_path
from vaultlab.research.paper import Paper

if TYPE_CHECKING:
    from vaultlab.research.corpus import Corpus
    from vaultlab.research.graph_metrics import CorpusMetrics

logger = logging.getLogger(__name__)

__all__ = [
    "PaperSummary",
    "SummarizationTask",
    "SummarizeAuthError",
    "SummaryReader",
    "build_summary_prompt",
    "load_anthropic_api_key",
    "prepare_summary_task",
    "render_summary_from_response",
    "render_summary_markdown",
    "summarize_corpus",
    "summarize_paper",
    "summary_response_schema",
    "write_summary_to_kb",
]


# Default model: Sonnet 4.6 is a good cost/quality target for paper
# summarization (we don't need Opus 4.7's reasoning for this task).
DEFAULT_MODEL = "claude-sonnet-4-6"

# Maximum tokens per response. The structured JSON we ask for typically
# runs 1-3 KB; 4096 leaves comfortable headroom.
DEFAULT_MAX_TOKENS = 4096


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class SummarizeAuthError(RuntimeError):
    """Raised when no Anthropic API key can be found.

    Message includes the search order so the caller knows where to put
    a key (env var ``ANTHROPIC_API_KEY`` or ``anthropic_api_key`` in the
    research-apis config).
    """


# ---------------------------------------------------------------------------
# Data class
# ---------------------------------------------------------------------------


@dataclass
class PaperSummary:
    """Structured per-paper summary destined for ``Wiki/Summaries/<doi>.md``.

    The fields are split into four groups:

    * Identity (DOI, title, authors, year, journal) — set from the search
      result before the LLM call.
    * Citation stats (counts, og_score, year_bucket, role_in_set, tier) —
      derived from :class:`CorpusMetrics` and acquisition state.
    * Provenance (extracted_via, extracted_at, source_pdf) — recorded by
      the summarizer at write time.
    * Content (TL;DR, why-it-matters, methods, key findings, references,
      connections) — written by Claude (Tier A/B) or empty (Tier C).
    """

    # Identity
    doi: str = ""
    title: str = ""
    authors: list[str] = field(default_factory=list)
    year: int = 0
    journal: str = ""

    # Citation stats (from CorpusMetrics + acquisition state)
    citation_count: int = 0
    influential_citations: int = 0
    og_score: float = 0.0
    forward_influence: int = 0
    year_bucket: str = "unknown"  # history / development / sota / unknown
    role_in_set: str = ""  # foundational / building-block / sota / etc.
    tier: str = "C"  # A=full-text, B=abstract+methods, C=abstract-only stub

    # Provenance
    extracted_via: str = "claude"
    extracted_at: str = ""  # ISO 8601 timestamp
    source_pdf: str = ""  # KB-relative path (e.g. "Sources/Papers/<slug>.pdf")
    source_pdf_sha256: str = ""  # content hash of the PDF this summary was read from;
    # the gate for idempotent re-summarization (re-read only when the PDF changes).
    acquisition_source: str = ""  # waterfall tier (unpaywall / pmc / ...)
    acquisition_license: str = ""  # license string from the waterfall

    # Content (LLM-written)
    tldr: str = ""
    why_it_matters: list[str] = field(default_factory=list)
    methods_summary: str = ""
    key_findings: list[str] = field(default_factory=list)
    extracted_references: list[str] = field(default_factory=list)
    connections_references: list[str] = field(default_factory=list)
    connections_cited_by_in_set: list[str] = field(default_factory=list)

    # Token usage (optional — populated when an LLM call ran)
    tokens_input: int = 0
    tokens_output: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# Response schema (shared by SDK + Claude-Code paths)
# ---------------------------------------------------------------------------


def summary_response_schema() -> dict[str, Any]:
    """Return a JSON schema describing the LLM response shape.

    Used by :class:`SummarizationTask` so the Claude-Code-callable path
    can validate inputs the same way the SDK path does. Matches the
    instructions baked into :func:`build_summary_prompt`.
    """
    return {
        "type": "object",
        "required": [
            "tldr",
            "why_it_matters",
            "methods_summary",
            "key_findings",
            "extracted_references",
        ],
        "properties": {
            "tldr": {
                "type": "string",
                "description": "Exactly 3 sentences summarizing the paper.",
            },
            "why_it_matters": {
                "type": "array",
                "items": {"type": "string"},
                "description": "2-5 bullets explaining novelty / impact.",
            },
            "methods_summary": {
                "type": "string",
                "description": "1-2 paragraphs on methodology.",
            },
            "key_findings": {
                "type": "array",
                "items": {"type": "string"},
                "minItems": 3,
                "description": (
                    "At least 3 (ideally 5-8) findings, each ending in a "
                    "[p<N>] page marker or [unknown]."
                ),
            },
            "extracted_references": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "DOIs from the paper's References section. Empty unless "
                    "crossref_refs_missing=True."
                ),
            },
        },
    }


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------


def load_anthropic_api_key(explicit: str | None = None) -> str:
    """Locate an Anthropic API key.

    Search order:
        1. ``explicit`` argument (passed by the caller)
        2. ``ANTHROPIC_API_KEY`` environment variable
        3. ``anthropic_api_key`` in the research-apis config

    Returns the first non-empty key found, or raises
    :class:`SummarizeAuthError` if none are configured.
    """
    if explicit:
        return explicit

    import os

    env_val = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if env_val:
        return env_val

    try:
        from vaultlab.research.config import get_config

        cfg = get_config()
    except Exception:
        cfg = {}
    cfg_val = (cfg.get("anthropic_api_key") or "").strip()
    if cfg_val:
        return cfg_val

    raise SummarizeAuthError(
        "No Anthropic API key found. Tried (in order):\n"
        "  1. explicit api_key= argument\n"
        "  2. ANTHROPIC_API_KEY environment variable\n"
        "  3. anthropic_api_key in research_apis.json config\n"
        "Set one of these and retry."
    )


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------


_SYSTEM_PROMPT = (
    "You are summarizing a scientific paper for a researcher's knowledge base. "
    "Be faithful — quote the paper, don't paraphrase claims you can't find. "
    "Every key finding MUST carry a [p<N>] page marker. If you cannot ground a "
    "finding in a specific page, mark it [unknown] or omit it entirely. "
    "Return ONLY valid JSON matching the schema given in the user message. "
    "Do not include any explanation, preamble, or markdown fencing around the JSON."
)


_OUTPUT_SCHEMA_DESCRIPTION = """\
Return a JSON object with exactly these keys:

{
  "tldr": "<3 sentences summarizing the paper's main contribution>",
  "why_it_matters": ["<bullet 1>", "<bullet 2>", ...],
  "methods_summary": "<1-2 paragraphs on methodology, extracted from the paper>",
  "key_findings": [
    "<finding 1 with [p<N>] page marker>",
    "<finding 2 with [p<N>]>",
    ...
  ],
  "extracted_references": [
    "<DOI 1>", "<DOI 2>", ...
  ]
}

Rules:
- key_findings: minimum 3, ideally 5-8. Each MUST end with a [p<N>] marker
  pointing to the page where the finding appears. If a page number cannot
  be determined, write [unknown] instead — do not guess.
- extracted_references: provide ONLY when the user asks for them
  (crossref_refs_missing=true in the metadata). Otherwise return [].
  When provided, list DOIs you can find in the paper's References section,
  one per array entry, with no commentary.
- tldr: exactly 3 sentences. State the central finding/contribution
  clearly enough that someone who hasn't read the paper would know what
  it does.
- why_it_matters: 2-5 bullets explaining what's novel or impactful.
- All quoted text inside JSON must use proper JSON escaping (\\\" for
  internal quotes, \\\\n for newlines, etc.).
"""


def build_summary_prompt(
    *,
    paper_metadata: dict[str, Any],
    crossref_refs_missing: bool = False,
    role_hint: str = "",
) -> str:
    """Build the user-message text for a summarization request.

    The prompt embeds identifying metadata (so Claude knows what paper it
    is even if the PDF's title page is sparse) and the strict JSON schema.
    A small example output is included so Claude has a concrete shape to
    match.
    """
    title = paper_metadata.get("title", "") or "<unknown>"
    authors = paper_metadata.get("authors") or []
    if isinstance(authors, list):
        authors_str = ", ".join(authors[:6])
        if len(authors) > 6:
            authors_str += ", ..."
    else:
        authors_str = str(authors)
    year = paper_metadata.get("year", 0) or "<unknown>"
    journal = paper_metadata.get("journal", "") or "<unknown>"
    doi = paper_metadata.get("doi", "") or "<unknown>"

    refs_clause = (
        "CrossRef did NOT provide a reference list for this paper. "
        "Please extract the references list from the PDF (References / Bibliography "
        "section) and return DOIs in the `extracted_references` array."
        if crossref_refs_missing
        else "CrossRef already provided this paper's reference list. "
        "Return an empty array for `extracted_references` (we don't need them again)."
    )

    role_clause = f"Role in the corpus (informational): {role_hint}\n" if role_hint else ""

    example_block = """\
Example of the expected JSON shape (DO NOT copy these contents — produce
content for the actual paper):

{
  "tldr": "This paper introduces base editing, a CRISPR-Cas9 derivative that converts cytidine to thymidine without inducing double-strand breaks. The system fuses a catalytically impaired Cas9 to a cytidine deaminase. It enables targeted single-nucleotide edits in mammalian cells with high efficiency.",
  "why_it_matters": [
    "First demonstration of CRISPR editing without DSB formation",
    "Founded the cytosine base editor (CBE) lineage"
  ],
  "methods_summary": "The authors fuse rAPOBEC1 to dCas9 (D10A nickase) and show C->T conversion at protospacers in HEK293T cells. Editing efficiency is measured by deep sequencing across multiple genomic targets.",
  "key_findings": [
    "C->T conversion efficiency reaches 37% at the BRCA1 locus [p4]",
    "Off-target editing is 10x lower than wild-type Cas9 [p6]",
    "Editing window is restricted to a 5nt protospacer region [p3]"
  ],
  "extracted_references": []
}
"""

    return f"""\
PAPER TO SUMMARIZE:

Title: {title}
Authors: {authors_str}
Year: {year}
Journal: {journal}
DOI: {doi}

{role_clause}{refs_clause}

OUTPUT FORMAT:
{_OUTPUT_SCHEMA_DESCRIPTION}

{example_block}

Now read the attached PDF and produce the JSON object for THIS paper.
Remember: ONLY the JSON object, no preamble, no markdown fencing.
"""


# ---------------------------------------------------------------------------
# JSON parsing
# ---------------------------------------------------------------------------


def _extract_json(text: str) -> dict[str, Any]:
    """Pull a JSON object out of an LLM response, tolerating preambles.

    Claude sometimes wraps JSON in ```json ... ``` fences despite our
    instructions. We strip those and parse the first ``{...}`` block.
    """
    s = text.strip()
    # Strip leading/trailing markdown fences.
    if s.startswith("```"):
        # Drop the opening fence line.
        first_newline = s.find("\n")
        if first_newline != -1:
            s = s[first_newline + 1 :]
        if s.endswith("```"):
            s = s[:-3].rstrip()
    # Locate the first balanced { ... } block.
    start = s.find("{")
    if start == -1:
        raise ValueError(f"no JSON object found in response: {s[:200]!r}")
    # Walk forward tracking depth so we ignore { inside strings.
    depth = 0
    in_str = False
    esc = False
    for i in range(start, len(s)):
        ch = s[i]
        if esc:
            esc = False
            continue
        if ch == "\\" and in_str:
            esc = True
            continue
        if ch == '"':
            in_str = not in_str
            continue
        if in_str:
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                blob = s[start : i + 1]
                return json.loads(blob)
    raise ValueError("unbalanced braces in response JSON")


# ---------------------------------------------------------------------------
# Anthropic API call
# ---------------------------------------------------------------------------


def _call_anthropic(
    *,
    pdf_bytes: bytes,
    prompt: str,
    api_key: str,
    model: str,
    max_tokens: int = DEFAULT_MAX_TOKENS,
) -> tuple[dict[str, Any], int, int]:
    """Send the PDF + prompt to Claude. Return ``(parsed_json, input_tok, output_tok)``."""
    import base64

    import anthropic

    client = anthropic.Anthropic(api_key=api_key)

    pdf_b64 = base64.standard_b64encode(pdf_bytes).decode("ascii")

    response = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=_SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "document",
                        "source": {
                            "type": "base64",
                            "media_type": "application/pdf",
                            "data": pdf_b64,
                        },
                    },
                    {"type": "text", "text": prompt},
                ],
            }
        ],
    )

    # Concatenate any text blocks.
    text_chunks: list[str] = []
    for block in response.content:
        if getattr(block, "type", "") == "text":
            text_chunks.append(block.text)
    full_text = "\n".join(text_chunks).strip()

    parsed = _extract_json(full_text)
    in_tok = getattr(response.usage, "input_tokens", 0) or 0
    out_tok = getattr(response.usage, "output_tokens", 0) or 0
    return parsed, in_tok, out_tok


# ---------------------------------------------------------------------------
# Tier C stub helpers (no LLM)
# ---------------------------------------------------------------------------


def _populate_citation_stats(
    summary: PaperSummary,
    *,
    doi: str,
    corpus_metrics: CorpusMetrics | None,
    corpus_papers: dict[str, Paper] | None = None,
    seed_dois: list[str] | None = None,
) -> None:
    """Fill the citation-stat fields on ``summary`` from corpus state.

    Mutates ``summary`` in place. Safe to call when ``corpus_metrics`` is
    ``None`` — the fields keep their dataclass defaults.
    """
    key = (doi or "").lower()

    if corpus_papers and key in corpus_papers:
        paper = corpus_papers[key]
        if not summary.title:
            summary.title = paper.title
        if not summary.authors:
            summary.authors = list(paper.authors)
        if not summary.year:
            summary.year = paper.year
        if not summary.journal:
            summary.journal = paper.journal
        if paper.citation_count:
            summary.citation_count = paper.citation_count

    if corpus_metrics is not None:
        summary.og_score = float(corpus_metrics.og_score.get(key, 0.0))
        summary.forward_influence = int(corpus_metrics.forward_influence.get(key, 0))
        summary.year_bucket = corpus_metrics.year_buckets.get(key, "unknown")

    if not summary.role_in_set:
        summary.role_in_set = _infer_role(summary, seed_dois=seed_dois, doi=key)


def _infer_role(
    summary: PaperSummary,
    *,
    seed_dois: list[str] | None,
    doi: str,
) -> str:
    """Heuristic role assignment.

    * ``foundational`` — high og_score (>=0.5) AND year_bucket == history
    * ``sota`` — year_bucket == sota
    * ``building-block`` — in seed set with non-zero forward_influence
    * ``seed`` — in seed set
    * ``cited`` — referenced by seeds but not a seed itself
    * ``""`` — unknown
    """
    if summary.og_score >= 0.5 and summary.year_bucket == "history":
        return "foundational"
    if summary.year_bucket == "sota":
        return "sota"
    in_seeds = bool(seed_dois) and doi in (seed_dois or [])
    if in_seeds and summary.forward_influence > 0:
        return "building-block"
    if in_seeds:
        return "seed"
    if summary.og_score > 0:
        return "cited"
    return ""


# ---------------------------------------------------------------------------
# Connections (wikilink builders)
# ---------------------------------------------------------------------------


def _build_connections(
    summary: PaperSummary,
    *,
    doi: str,
    corpus: Corpus | None,
    max_per_section: int = 5,
) -> None:
    """Populate ``connections_references`` and ``connections_cited_by_in_set``.

    These are filesystem-friendly DOI slugs (no leading ``[[``) — the
    markdown renderer wraps them as Obsidian wikilinks.
    """
    if corpus is None:
        return
    key = (doi or "").lower()

    # References this paper makes (corpus.references[key] -> list of cited DOIs)
    own_refs = corpus.references.get(key) or []
    seed_set = set(corpus.seed_dois)
    paper_set = set(corpus.papers.keys())

    # Connections -> References (foundational): DOIs cited by this paper
    # AND known to the corpus (so we can wikilink to them). Sort by
    # in-corpus prevalence (og_score) when metrics are present.
    refs_in_corpus = [r for r in own_refs if r in paper_set]
    if corpus.metrics is not None:
        refs_in_corpus.sort(
            key=lambda d: corpus.metrics.og_score.get(d, 0.0),  # type: ignore[union-attr]
            reverse=True,
        )
    summary.connections_references = [slugify_doi(d) for d in refs_in_corpus[:max_per_section]]

    # Connections -> Cited by in our set: papers IN the corpus whose
    # reference lists include this DOI.
    citers: list[str] = []
    for citing_doi, cited_list in corpus.references.items():
        if citing_doi == key:
            continue
        if not cited_list:
            continue
        if key in cited_list and citing_doi in seed_set:
            citers.append(citing_doi)
    # Sort citers by their forward_influence so the most prominent appear first.
    if corpus.metrics is not None:
        citers.sort(
            key=lambda d: corpus.metrics.forward_influence.get(d, 0),  # type: ignore[union-attr]
            reverse=True,
        )
    summary.connections_cited_by_in_set = [slugify_doi(d) for d in citers[:max_per_section]]


# ---------------------------------------------------------------------------
# Public API: Claude-Code-callable preparation + render
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SummarizationTask:
    """A prepared summarization task ready for a Claude Code session to execute.

    No LLM is called when this object is built — it's the structured
    "what to read + how to respond" envelope. The slash command body
    (running inside Claude Code) reads :attr:`pdf_path` itself and
    produces a JSON response matching :attr:`response_schema`, then
    feeds the response into :func:`render_summary_from_response`.

    Attributes:
        doi: Lower-cased DOI of the paper.
        pdf_path: Local path to the PDF Claude Code should read. May be
            absent on disk for Tier-C cases (caller decides via
            :attr:`tier`).
        paper_metadata: ``title``, ``authors``, ``year``, ``journal``,
            ``citation_count``, ``influential_citations`` from the
            search result.
        citation_stats: Pre-populated citation metrics (og_score,
            forward_influence, year_bucket, role_in_set, tier).
        crossref_refs_missing: When ``True``, the prompt asks Claude to
            also extract a references list from the PDF.
        output_path: Canonical destination for the summary markdown
            (i.e. ``Wiki/Summaries/<doi-slug>.md`` via
            :func:`vaultlab.kb.paths.summary_path`).
        prompt: The full user-message prompt Claude should respond to.
            The system prompt is :data:`_SYSTEM_PROMPT` (importable for
            advanced callers via the module attribute).
        system_prompt: The system message Claude should be given.
        response_schema: JSON schema describing the expected response
            shape.
        tier: Pre-computed tier letter ("A" if a PDF is available,
            otherwise "C"). Tier-C tasks should NOT be sent to the
            LLM — call :func:`render_summary_from_response` with an
            empty dict instead, or use the corpus orchestrator which
            short-circuits.
        acquisition_source: Tier label ("unpaywall", "pmc", ...) — flows
            into the rendered summary's provenance section.
        acquisition_license: License string — same.
    """

    doi: str
    pdf_path: Path
    paper_metadata: dict[str, Any]
    citation_stats: dict[str, Any]
    crossref_refs_missing: bool
    output_path: Path
    prompt: str
    system_prompt: str
    response_schema: dict[str, Any]
    tier: str = "A"
    acquisition_source: str = ""
    acquisition_license: str = ""
    text_path: Path | None = None
    """Optional path to a clean machine-extracted full-text file
    (typically Elsevier ``originalText`` written to ``<slug>.elsevier.txt``).
    When set, the reader can use this instead of parsing the PDF — faster
    and cleaner page-level provenance."""


# Type alias for the Claude-Code-side reader callback.
SummaryReader = Callable[["SummarizationTask"], dict[str, Any]]


def _build_base_summary(
    *,
    doi: str,
    paper_metadata: dict[str, Any],
    corpus_metrics: CorpusMetrics | None,
    corpus: Corpus | None,
    acquisition_source: str,
    acquisition_license: str,
) -> PaperSummary:
    """Build the PaperSummary with metadata, citation stats, and connections.

    Shared by the SDK path and the prepare/render path. Does NOT touch
    any LLM. The returned summary has empty content fields (tldr,
    key_findings, ...) — the caller fills them from the LLM response.
    """
    doi = (doi or "").strip().lower()
    summary = PaperSummary(
        doi=doi,
        title=paper_metadata.get("title", "") or "",
        authors=list(paper_metadata.get("authors") or []),
        year=int(paper_metadata.get("year") or 0),
        journal=paper_metadata.get("journal", "") or "",
        citation_count=int(paper_metadata.get("citation_count") or 0),
        influential_citations=int(paper_metadata.get("influential_citations") or 0),
        extracted_via="claude",
        extracted_at=datetime.now().isoformat(timespec="seconds"),
        acquisition_source=acquisition_source,
        acquisition_license=acquisition_license,
    )
    seed_dois = corpus.seed_dois if corpus is not None else None
    corpus_papers = corpus.papers if corpus is not None else None
    _populate_citation_stats(
        summary,
        doi=doi,
        corpus_metrics=corpus_metrics,
        corpus_papers=corpus_papers,
        seed_dois=seed_dois,
    )
    _build_connections(summary, doi=doi, corpus=corpus)
    return summary


def prepare_summary_task(
    *,
    doi: str,
    pdf_path: Path,
    paper_metadata: dict[str, Any],
    corpus_metrics: CorpusMetrics | None = None,
    corpus: Corpus | None = None,
    crossref_refs_missing: bool = False,
    kb_root: Path,
    acquisition_source: str = "",
    acquisition_license: str = "",
) -> SummarizationTask:
    """Prepare a summarization task. Does NOT call any LLM.

    Returns the structured task with prompt + expected response schema.
    The caller (the Claude Code session, or any custom orchestrator)
    is responsible for reading the PDF and producing JSON matching the
    schema, then feeding it into :func:`render_summary_from_response`.

    Use this from a slash command body (no Anthropic API key needed —
    Claude Code provides LLM access via the active session). For
    plain-Python callers with an API key, :func:`summarize_paper`
    bundles prepare + LLM call + render.

    Args:
        doi: DOI of the paper (case-insensitive; lower-cased internally).
        pdf_path: Local path Claude Code will read in-session. Should
            exist on disk; missing-file cases short-circuit to Tier C
            via the corpus orchestrator and don't go through this
            function.
        paper_metadata: ``title``, ``authors``, ``year``, ``journal``
            from the search result.
        corpus_metrics: Optional :class:`CorpusMetrics`; populates
            og_score / forward_influence / year_bucket on the eventual
            summary.
        corpus: Optional :class:`Corpus`; lets us build the
            ``connections_*`` wikilink lists from the citation graph.
        crossref_refs_missing: Forwarded to the prompt; when ``True``
            asks Claude to also extract the references list.
        kb_root: Vaultlab KB root (e.g.
            ``G:/My Drive/Knowledge/vaultlab``). Determines the
            canonical ``output_path``.
        acquisition_source: Tier label from
            :class:`AcquisitionResult` (e.g. ``unpaywall``).
        acquisition_license: License string from acquisition.

    Returns:
        A :class:`SummarizationTask` ready for the Claude Code reader.
    """
    base = _build_base_summary(
        doi=doi,
        paper_metadata=paper_metadata,
        corpus_metrics=corpus_metrics,
        corpus=corpus,
        acquisition_source=acquisition_source,
        acquisition_license=acquisition_license,
    )
    prompt = build_summary_prompt(
        paper_metadata={
            "title": base.title,
            "authors": base.authors,
            "year": base.year,
            "journal": base.journal,
            "doi": base.doi,
        },
        crossref_refs_missing=crossref_refs_missing,
        role_hint=base.role_in_set,
    )
    citation_stats = {
        "og_score": base.og_score,
        "forward_influence": base.forward_influence,
        "year_bucket": base.year_bucket,
        "role_in_set": base.role_in_set,
        "citation_count": base.citation_count,
        "influential_citations": base.influential_citations,
    }
    output_path = summary_path(Path(kb_root), base.doi)
    # Auto-detect a sibling text file (e.g. the Elsevier originalText
    # pre-fetch). The convention is "<pdf_stem>.elsevier.txt" sitting
    # next to the PDF. When present, the prompt nudges the reader to
    # prefer it for cleaner page-level provenance.
    text_path: Path | None = None
    pdf_path_obj = Path(pdf_path)
    elsevier_text = pdf_path_obj.with_suffix(".elsevier.txt")
    if elsevier_text.exists() and elsevier_text.stat().st_size > 0:
        text_path = elsevier_text
        # Append a hint to the prompt so the reader knows to use it.
        prompt = (
            prompt + "\n\n---\n\n" + "**A clean machine-extracted plain-text version of this "
            "article is available at:**\n\n"
            + f"    `{elsevier_text}`\n\n"
            + "Prefer reading this file instead of the PDF when both are "
            "present — it has cleaner text extraction with no page-break "
            "artifacts. The PDF remains available for figures and layout-"
            "sensitive checks."
        )

    return SummarizationTask(
        doi=base.doi,
        pdf_path=pdf_path_obj,
        paper_metadata={
            "title": base.title,
            "authors": list(base.authors),
            "year": base.year,
            "journal": base.journal,
            "doi": base.doi,
            "citation_count": base.citation_count,
            "influential_citations": base.influential_citations,
        },
        citation_stats=citation_stats,
        crossref_refs_missing=crossref_refs_missing,
        output_path=output_path,
        prompt=prompt,
        system_prompt=_SYSTEM_PROMPT,
        response_schema=summary_response_schema(),
        tier="A",
        acquisition_source=acquisition_source,
        acquisition_license=acquisition_license,
        text_path=text_path,
    )


def render_summary_from_response(
    task: SummarizationTask,
    response_json: dict[str, Any],
    *,
    corpus_metrics: CorpusMetrics | None = None,
    corpus: Corpus | None = None,
    tokens_input: int = 0,
    tokens_output: int = 0,
) -> PaperSummary:
    """Take Claude Code's JSON response and produce a populated PaperSummary.

    Reuses the same metadata / citation-stat / connections logic the SDK
    path uses. Does NOT call any LLM and does NOT write to disk — the
    caller decides whether to call :func:`write_summary_to_kb` next.

    Args:
        task: The :class:`SummarizationTask` produced by
            :func:`prepare_summary_task`.
        response_json: Parsed JSON dict matching ``task.response_schema``.
            For Tier-C / no-LLM cases, pass an empty dict — content
            fields will stay empty.
        corpus_metrics: Same :class:`CorpusMetrics` used in the
            prepare step (re-passed because it's not embedded in the
            frozen task to keep that object lightweight).
        corpus: Same :class:`Corpus` used in the prepare step.
        tokens_input: Optional input-token count from the LLM call (for
            provenance).
        tokens_output: Optional output-token count.

    Returns:
        A populated :class:`PaperSummary` with content from
        ``response_json`` plus the citation stats / connections already
        derived during preparation.
    """
    summary = _build_base_summary(
        doi=task.doi,
        paper_metadata=task.paper_metadata,
        corpus_metrics=corpus_metrics,
        corpus=corpus,
        acquisition_source=task.acquisition_source,
        acquisition_license=task.acquisition_license,
    )
    summary.tier = task.tier
    if task.tier == "A":
        summary.source_pdf = f"Sources/Papers/{slugify_doi(task.doi)}.pdf"
    summary.tldr = (response_json.get("tldr") or "").strip()
    summary.why_it_matters = list(response_json.get("why_it_matters") or [])
    summary.methods_summary = (response_json.get("methods_summary") or "").strip()
    summary.key_findings = list(response_json.get("key_findings") or [])
    summary.extracted_references = list(response_json.get("extracted_references") or [])
    summary.tokens_input = int(tokens_input or 0)
    summary.tokens_output = int(tokens_output or 0)
    return summary


# ---------------------------------------------------------------------------
# Public API: single-paper summarization (SDK path)
# ---------------------------------------------------------------------------


def summarize_paper(
    *,
    doi: str,
    pdf_path: Path | None,
    paper_metadata: dict[str, Any],
    corpus_metrics: CorpusMetrics | None = None,
    corpus: Corpus | None = None,
    crossref_refs_missing: bool = False,
    api_key: str | None = None,
    model: str = DEFAULT_MODEL,
    acquisition_source: str = "",
    acquisition_license: str = "",
    _llm: Callable[..., tuple[dict[str, Any], int, int]] | None = None,
) -> PaperSummary:
    """Build a :class:`PaperSummary` for a single paper using the Anthropic SDK.

    This is the **SDK path** — it makes a direct
    ``anthropic.Messages.create`` call using an API key from the
    environment / config. For the **Claude-Code-callable path** (no API
    key required, uses the active Claude Code session) see
    :func:`prepare_summary_task` + :func:`render_summary_from_response`.

    Args:
        doi: DOI of the paper (case-insensitive; lower-cased internally).
        pdf_path: Local PDF path. ``None`` (or a missing file) -> Tier C
            stub with citation stats only and no LLM call.
        paper_metadata: Dict carrying ``title``, ``authors``, ``year``,
            ``journal`` from the search result.
        corpus_metrics: Optional metrics dict; populates og_score etc.
        corpus: Optional :class:`Corpus`; lets us build the
            ``connections_*`` wikilink lists from the citation graph.
        crossref_refs_missing: When ``True``, asks Claude to also extract
            the paper's references list from the PDF.
        api_key: Override Anthropic API key (otherwise resolved via
            :func:`load_anthropic_api_key`).
        model: Anthropic model id. Defaults to Sonnet 4.6.
        acquisition_source: Tier label from
            :class:`AcquisitionResult` (e.g. ``unpaywall``); embedded in
            the provenance section.
        acquisition_license: License string from acquisition.
        _llm: Internal — injectable Claude caller for tests. The default
            is :func:`_call_anthropic`.

    Returns:
        A populated :class:`PaperSummary`. Tier is ``A`` if the PDF was
        read, ``C`` otherwise.
    """
    doi = (doi or "").strip().lower()

    summary = _build_base_summary(
        doi=doi,
        paper_metadata=paper_metadata,
        corpus_metrics=corpus_metrics,
        corpus=corpus,
        acquisition_source=acquisition_source,
        acquisition_license=acquisition_license,
    )

    # Tier C: no PDF -> stub.
    if pdf_path is None or not Path(pdf_path).exists():
        summary.tier = "C"
        summary.source_pdf = ""
        return summary

    summary.tier = "A"
    summary.source_pdf = f"Sources/Papers/{slugify_doi(doi)}.pdf"
    # Record the content hash of the PDF we are about to read. This is the gate that
    # makes corpus summarization idempotent: a later run skips the LLM read when the
    # on-disk PDF still hashes to this value. Mirrors papers_index.pdf_sha256 (chunked
    # SHA-256 of the same bytes), so the verdicts agree.
    summary.source_pdf_sha256 = hashlib.sha256(Path(pdf_path).read_bytes()).hexdigest()

    # Build the prompt and call Claude.
    prompt = build_summary_prompt(
        paper_metadata={
            "title": summary.title,
            "authors": summary.authors,
            "year": summary.year,
            "journal": summary.journal,
            "doi": summary.doi,
        },
        crossref_refs_missing=crossref_refs_missing,
        role_hint=summary.role_in_set,
    )

    pdf_bytes = Path(pdf_path).read_bytes()

    caller = _llm or _call_anthropic
    if _llm is None:
        # Real LLM call — resolve auth lazily so tests don't need a key.
        api_key = load_anthropic_api_key(api_key)
        parsed, in_tok, out_tok = caller(
            pdf_bytes=pdf_bytes,
            prompt=prompt,
            api_key=api_key,
            model=model,
        )
    else:
        parsed, in_tok, out_tok = caller(
            pdf_bytes=pdf_bytes,
            prompt=prompt,
            api_key=api_key or "test",
            model=model,
        )

    # Apply LLM output to the summary.
    summary.tldr = (parsed.get("tldr") or "").strip()
    summary.why_it_matters = list(parsed.get("why_it_matters") or [])
    summary.methods_summary = (parsed.get("methods_summary") or "").strip()
    summary.key_findings = list(parsed.get("key_findings") or [])
    summary.extracted_references = list(parsed.get("extracted_references") or [])
    summary.tokens_input = in_tok
    summary.tokens_output = out_tok

    return summary


# ---------------------------------------------------------------------------
# Markdown rendering
# ---------------------------------------------------------------------------


_INVISIBLE_FRONTMATTER_KEYS = (
    "tokens_input",
    "tokens_output",
    "acquisition_source",
    "acquisition_license",
    "connections_references",
    "connections_cited_by_in_set",
    "tldr",
    "why_it_matters",
    "methods_summary",
    "key_findings",
    "extracted_references",
)


def _frontmatter(summary: PaperSummary) -> str:
    """Return the YAML frontmatter block (without delimiters)."""
    data = summary.to_dict()
    # The frontmatter only carries identity, citation stats, and provenance —
    # the body of the markdown holds the prose / lists.
    fm = {k: v for k, v in data.items() if k not in _INVISIBLE_FRONTMATTER_KEYS}
    # Drop empty strings so the YAML is tidy.
    fm = {
        k: v
        for k, v in fm.items()
        if v not in ("", 0, 0.0)
        or k
        in (
            "year",
            "citation_count",
            "influential_citations",
            "og_score",
            "forward_influence",
        )
    }
    # yaml.safe_dump preserves insertion order in pyyaml >=6 only when
    # sort_keys=False. We keep our canonical order.
    return yaml.safe_dump(fm, sort_keys=False, allow_unicode=True).strip()


def _bullet_list(items: list[str]) -> str:
    if not items:
        return "- _(none)_\n"
    return "".join(f"- {item}\n" for item in items)


def _wikilink_list(slugs: list[str]) -> str:
    if not slugs:
        return "_(none)_"
    return ", ".join(f"[[{s}]]" for s in slugs)


def render_summary_markdown(summary: PaperSummary) -> str:
    """Render a :class:`PaperSummary` to canonical Wiki/Summaries markdown."""
    fm = _frontmatter(summary)

    if summary.tier == "C":
        body_intro = (
            "\n## TL;DR\n"
            "_No full-text PDF available; this is a Tier C stub built from "
            "corpus metrics only._\n"
        )
    else:
        body_intro = f"\n## TL;DR\n{summary.tldr or '_(empty)_'}\n"

    why = "\n## Why it matters in this lineage\n" + _bullet_list(summary.why_it_matters)
    methods = (
        "\n## Methods (extracted summary)\n"
        + (summary.methods_summary or "_(not extracted)_")
        + "\n"
    )
    findings = "\n## Key findings (with [page] provenance)\n" + _bullet_list(summary.key_findings)

    refs_line = ""
    if summary.connections_references or summary.connections_cited_by_in_set:
        refs_line = (
            "\n## Connections\n"
            f"- **References (foundational)**: "
            f"{_wikilink_list(summary.connections_references)}\n"
            f"- **Cited by in our set**: "
            f"{_wikilink_list(summary.connections_cited_by_in_set)}\n"
        )

    extra_refs_block = ""
    if summary.extracted_references:
        extra_refs_block = "\n## Extracted references (from PDF)\n" + _bullet_list(
            summary.extracted_references
        )

    provenance = (
        f"\n## Reading provenance\n- PDF acquired via: {summary.acquisition_source or 'n/a'}"
    )
    if summary.acquisition_license:
        provenance += f" ({summary.acquisition_license})"
    provenance += "\n"
    provenance += f"- Read at: {summary.extracted_at or 'n/a'}\n"
    if summary.tokens_input or summary.tokens_output:
        provenance += (
            f"- Tokens used: ~{summary.tokens_input} input, ~{summary.tokens_output} output\n"
        )

    return (
        "---\n"
        f"{fm}\n"
        "---\n" + body_intro + why + methods + findings + refs_line + extra_refs_block + provenance
    )


# ---------------------------------------------------------------------------
# Public API: write to KB
# ---------------------------------------------------------------------------


_REGEN_FOOTER_RE = re.compile(r"\n<!-- vaultlab regen attempt: [^>]+ -->\n*\Z", re.DOTALL)


def write_summary_to_kb(
    summary: PaperSummary,
    kb_root: Path,
    *,
    overwrite: bool = False,
) -> Path:
    """Write the rendered markdown to ``Wiki/Summaries/<doi-slug>.md``.

    If the target file already exists and ``overwrite=False``, the file is
    LEFT IN PLACE and a one-line regeneration-attempt comment is appended
    so the audit trail records that we considered re-running. This avoids
    silently clobbering hand-edits.

    Returns the path written (or kept).
    """
    path = ensure_parent(summary_path(Path(kb_root), summary.doi))

    if path.exists() and not overwrite:
        # Append a regen-attempt marker so the user can see we visited.
        existing = path.read_text(encoding="utf-8")
        existing = _REGEN_FOOTER_RE.sub("", existing)  # drop prior marker
        marker = (
            f"\n<!-- vaultlab regen attempt: {datetime.now().isoformat(timespec='seconds')} -->\n"
        )
        path.write_text(existing + marker, encoding="utf-8")
        logger.info("write_summary_to_kb: kept existing %s (overwrite=False)", path)
        return path

    md = render_summary_markdown(summary)
    path.write_text(md, encoding="utf-8")
    logger.info("write_summary_to_kb: wrote %s", path)
    return path


# ---------------------------------------------------------------------------
# Public API: corpus-wide summarization
# ---------------------------------------------------------------------------


def summarize_corpus(
    corpus: Corpus,
    *,
    pdf_cache_dir: Path,
    kb_root: Path,
    parallel: int = 2,  # API-rate-limit-friendly default
    api_key: str | None = None,
    model: str = DEFAULT_MODEL,
    overwrite: bool = False,
    idempotent: bool = True,
    progress: Callable[[str, int, int], None] | None = None,
    reader: SummaryReader | None = None,
    tier_a_dois: set[str] | frozenset[str] | None = None,
    _llm: Callable[..., tuple[dict[str, Any], int, int]] | None = None,
) -> dict[str, PaperSummary]:
    """Build summaries for every paper in ``corpus.papers`` and write them.

    Each paper is checked against ``pdf_cache_dir`` (the same
    ``acquire_pdf`` cache); papers with PDFs get full Tier-A reads,
    papers without get Tier-C stubs.

    Two modes:

    * **SDK mode (default)** — calls Claude via the Anthropic SDK using
      an API key (resolved per-paper from env / config).
    * **Reader mode** (``reader`` given) — for use inside Claude Code
      slash commands. The reader is invoked per Tier-A paper with the
      :class:`SummarizationTask` and returns a JSON dict matching
      :func:`summary_response_schema`. No Anthropic API key is needed
      because the slash command body itself is running inside a Claude
      Code session.

    Args:
        corpus: A built :class:`Corpus` (call ``compute_metrics`` first).
        pdf_cache_dir: Directory holding ``acquire_pdf``-style cached PDFs
            (``<doi-slug>.pdf`` / acquisition's ``doi_slug`` shape).
        kb_root: Vaultlab KB root (e.g. ``G:/My Drive/Knowledge/vaultlab``).
        parallel: Worker count for the thread pool. Default 2 keeps us
            inside Anthropic rate limits comfortably. Ignored in reader
            mode (reader is called sequentially because Claude Code
            sessions are single-threaded).
        api_key: Override key (SDK mode only).
        model: Anthropic model id (SDK mode only).
        overwrite: If False, existing summary files are kept (with a regen
            marker appended).
        idempotent: If True (default), a Tier-A paper whose summary already
            exists AND was read from the *same* PDF (matching SHA-256 in the
            summary's ``source_pdf_sha256`` frontmatter) is skipped WITHOUT an
            LLM read — the existing rich summary is left untouched and a
            metrics-only summary is returned for the in-memory corpus view.
            A paper is re-read only when it has no summary or its PDF changed.
            Set False (or ``overwrite=True``) to force a re-read of every
            Tier-A paper. This is the gate that makes multi-run fetching
            delta-only instead of re-spending tokens on already-read papers.
        progress: ``progress(doi, done, total)`` callback.
        reader: Optional Claude-Code-side callback. When given,
            replaces the SDK call. Receives a :class:`SummarizationTask`
            and must return a dict matching ``task.response_schema``.
        _llm: Test injection for the SDK path.

    Returns:
        ``doi -> PaperSummary``. Tier-C entries appear here too.
    """
    from concurrent.futures import ThreadPoolExecutor

    from vaultlab.research import papers_index as _pidx
    from vaultlab.research.acquisition import cache_path_for

    pdf_cache_dir = Path(pdf_cache_dir)
    kb_root = Path(kb_root)

    metrics = corpus.metrics
    dois = [d for d in corpus.papers if d]
    total = len(dois)
    results: dict[str, PaperSummary] = {}

    def _current_pdf_sha(doi: str, pdf_path: Path | None) -> str | None:
        """The PDF's hash when an up-to-date summary already exists; else ``None``.

        Returns the on-disk PDF SHA-256 only when idempotent mode is on, we are not
        force-overwriting, the PDF exists, and an existing summary records that exact
        same hash. A non-``None`` result means "the read can be skipped."
        """
        if not idempotent or overwrite:
            return None
        if pdf_path is None or not Path(pdf_path).exists():
            return None
        current = _pidx.pdf_sha256(Path(pdf_path))
        recorded = _pidx.existing_summary_pdf_sha(kb_root, doi)
        return current if (current and recorded == current) else None

    def _skip_read_summary(doi: str, paper, pdf_sha: str) -> PaperSummary:
        """A metrics-only Tier-A summary for a paper whose read we skipped (PDF unchanged).

        The rich existing ``Wiki/Summaries/<slug>.md`` is left in place; this object only
        feeds the in-memory corpus view (papers.md ranking, etc.)."""
        summary = _build_base_summary(
            doi=doi,
            paper_metadata={
                "title": paper.title,
                "authors": paper.authors,
                "year": paper.year,
                "journal": paper.journal,
                "doi": paper.doi,
                "citation_count": paper.citation_count,
            },
            corpus_metrics=metrics,
            corpus=corpus,
            acquisition_source="",
            acquisition_license="",
        )
        summary.tier = "A"
        summary.source_pdf = f"Sources/Papers/{slugify_doi(doi)}.pdf"
        summary.source_pdf_sha256 = pdf_sha
        return summary

    # Closes L4 audit bug #1: log the Tier-A budget so a silently-empty
    # set is easier to spot, and so the SDK path's enforcement (below)
    # is observable in run logs.
    if tier_a_dois is not None:
        logger.debug(
            "summarize_corpus: tier_a_dois budget = %d paper(s); "
            "all other papers fall through to Tier-C stubs",
            len(tier_a_dois),
        )

    def _one_reader(doi: str) -> tuple[str, PaperSummary]:
        """Reader-mode path — no SDK, no API key."""
        assert reader is not None
        paper = corpus.papers[doi]
        pdf_path = cache_path_for(doi, pdf_cache_dir)
        refs_missing = doi in corpus.references and not corpus.references.get(doi)
        # Closes L4-CODEX-discovered bug #1: respect tier_a_dois filter so
        # only papers selected for Tier-A reading invoke the reader. Other
        # papers with cached PDFs fall through to the Tier-C stub path so
        # we don't ask the reader to summarize 100+ peripheral papers.
        if tier_a_dois is not None and doi not in tier_a_dois:
            pdf_path = Path("/__force_tier_c__")  # nonexistent → Tier-C stub
        _gate_sha = _current_pdf_sha(doi, pdf_path)
        if _gate_sha is not None:
            logger.info("summarize_corpus: %s summary up-to-date (PDF unchanged) — skipped read", doi)
            return doi, _skip_read_summary(doi, paper, _gate_sha)
        if not pdf_path.exists():
            # Tier C: build a stub and skip the reader.
            summary = _build_base_summary(
                doi=doi,
                paper_metadata={
                    "title": paper.title,
                    "authors": paper.authors,
                    "year": paper.year,
                    "journal": paper.journal,
                    "doi": paper.doi,
                    "citation_count": paper.citation_count,
                },
                corpus_metrics=metrics,
                corpus=corpus,
                acquisition_source="",
                acquisition_license="",
            )
            summary.tier = "C"
            summary.source_pdf = ""
            write_summary_to_kb(summary, kb_root, overwrite=overwrite)
            return doi, summary

        task = prepare_summary_task(
            doi=doi,
            pdf_path=pdf_path,
            paper_metadata={
                "title": paper.title,
                "authors": paper.authors,
                "year": paper.year,
                "journal": paper.journal,
                "doi": paper.doi,
                "citation_count": paper.citation_count,
            },
            corpus_metrics=metrics,
            corpus=corpus,
            crossref_refs_missing=refs_missing,
            kb_root=kb_root,
        )
        response_json = reader(task) or {}
        summary = render_summary_from_response(
            task,
            response_json,
            corpus_metrics=metrics,
            corpus=corpus,
        )
        # Record which PDF this read was built from, so the next run can hash-gate it.
        summary.source_pdf_sha256 = _pidx.pdf_sha256(pdf_path)
        write_summary_to_kb(summary, kb_root, overwrite=overwrite)
        return doi, summary

    def _one_sdk(doi: str) -> tuple[str, PaperSummary]:
        paper = corpus.papers[doi]
        pdf_path = cache_path_for(doi, pdf_cache_dir)
        if not pdf_path.exists():
            pdf_path = None  # Tier C stub
        # Closes L4 audit bug #1: mirror the reader-mode tier_a_dois
        # enforcement in the SDK path. Without this guard, callers who
        # pass tier_a_dois with reader=None would silently get a Tier-A
        # summary for every paper that happens to have a cached PDF —
        # blowing the budget. Force pdf_path=None for non-budget papers
        # so they short-circuit to the Tier-C stub branch in
        # summarize_paper.
        if tier_a_dois is not None and doi not in tier_a_dois:
            pdf_path = None
        _gate_sha = _current_pdf_sha(doi, pdf_path)
        if _gate_sha is not None:
            logger.info("summarize_corpus: %s summary up-to-date (PDF unchanged) — skipped read", doi)
            return doi, _skip_read_summary(doi, paper, _gate_sha)
        # CrossRef gives us refs unless the entry exists with empty list.
        refs_missing = doi in corpus.references and not corpus.references.get(doi)
        summary = summarize_paper(
            doi=doi,
            pdf_path=pdf_path,
            paper_metadata={
                "title": paper.title,
                "authors": paper.authors,
                "year": paper.year,
                "journal": paper.journal,
                "doi": paper.doi,
                "citation_count": paper.citation_count,
            },
            corpus_metrics=metrics,
            corpus=corpus,
            crossref_refs_missing=refs_missing,
            api_key=api_key,
            model=model,
            _llm=_llm,
        )
        write_summary_to_kb(summary, kb_root, overwrite=overwrite)
        return doi, summary

    _one = _one_reader if reader is not None else _one_sdk

    # Reader mode is sequential because Claude Code sessions are single-threaded.
    if reader is not None or parallel <= 1:
        for i, doi in enumerate(dois, 1):
            try:
                _, summary = _one(doi)
            except Exception as exc:
                logger.warning("summarize_corpus: %s failed: %s", doi, exc)
                continue
            results[doi] = summary
            if progress is not None:
                progress(doi, i, total)
        return results

    with ThreadPoolExecutor(max_workers=parallel) as pool:
        futures = {pool.submit(_one, doi): doi for doi in dois}
        done = 0
        for fut in futures:
            doi = futures[fut]
            try:
                _, summary = fut.result()
            except Exception as exc:
                logger.warning("summarize_corpus: %s failed: %s", doi, exc)
                done += 1
                continue
            results[doi] = summary
            done += 1
            if progress is not None:
                progress(doi, done, total)
    return results
