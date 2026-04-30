"""Per-paper summarization layer for vaultlab corpora.

Given an acquired PDF (or its ``Sources/Papers/<doi>.pdf`` path) and the
paper's metadata, this module produces a structured :class:`PaperSummary`
that maps directly onto the canonical ``Wiki/Summaries/<doi>.md`` format
documented in ``kb-output-conventions-2026-04-29.md``.

Design constraints (per the F.7 grill, decision D6)
---------------------------------------------------
* **Claude is the primary PDF reader.** No Grobid, no Marker, no PaperQA2
  dependency. We invoke the Anthropic Messages API with the PDF attached
  as a ``document`` content block — the model reads the bytes and emits
  structured JSON matching the :class:`PaperSummary` shape.
* **Tier C is a no-LLM stub.** When a PDF isn't available we still emit
  a summary file with the corpus metrics filled in, so the KB stays
  complete even for paywalled papers.
* **Page provenance is mandatory.** Every key finding must carry a
  ``[p<N>]`` marker; the prompt instructs Claude to omit findings it
  cannot ground in a specific page (or annotate them ``[unknown]``).
* **No fake references.** When CrossRef gives us references we trust
  them; only when ``crossref_refs_missing=True`` do we ask Claude to
  extract the references list from the PDF itself.

Authentication
--------------
The Anthropic SDK reads ``ANTHROPIC_API_KEY`` from the environment by
default. As a fallback we look for ``anthropic_api_key`` in the same
``research_apis.json`` config used by the rest of ``vaultlab.research``.
If neither is present the module raises :class:`SummarizeAuthError` so
callers know to set up credentials before retrying.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

import yaml

from vaultlab.kb.paths import ensure_parent, slugify_doi, summary_path
from vaultlab.research.paper import Paper

if TYPE_CHECKING:
    from vaultlab.research.corpus import Corpus
    from vaultlab.research.graph_metrics import CorpusMetrics

logger = logging.getLogger(__name__)

__all__ = [
    "PaperSummary",
    "SummarizeAuthError",
    "build_summary_prompt",
    "load_anthropic_api_key",
    "render_summary_markdown",
    "summarize_corpus",
    "summarize_paper",
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

    role_clause = (
        f"Role in the corpus (informational): {role_hint}\n"
        if role_hint
        else ""
    )

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
            s = s[: -3].rstrip()
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
    corpus_metrics: "CorpusMetrics | None",
    corpus_papers: "dict[str, Paper] | None" = None,
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
        summary.forward_influence = int(
            corpus_metrics.forward_influence.get(key, 0)
        )
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
    corpus: "Corpus | None",
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
    summary.connections_references = [
        slugify_doi(d) for d in refs_in_corpus[:max_per_section]
    ]

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
    summary.connections_cited_by_in_set = [
        slugify_doi(d) for d in citers[:max_per_section]
    ]


# ---------------------------------------------------------------------------
# Public API: single-paper summarization
# ---------------------------------------------------------------------------


def summarize_paper(
    *,
    doi: str,
    pdf_path: Path | None,
    paper_metadata: dict[str, Any],
    corpus_metrics: "CorpusMetrics | None" = None,
    corpus: "Corpus | None" = None,
    crossref_refs_missing: bool = False,
    api_key: str | None = None,
    model: str = DEFAULT_MODEL,
    acquisition_source: str = "",
    acquisition_license: str = "",
    _llm: Callable[..., tuple[dict[str, Any], int, int]] | None = None,
) -> PaperSummary:
    """Build a :class:`PaperSummary` for a single paper.

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

    summary = PaperSummary(
        doi=doi,
        title=paper_metadata.get("title", "") or "",
        authors=list(paper_metadata.get("authors") or []),
        year=int(paper_metadata.get("year") or 0),
        journal=paper_metadata.get("journal", "") or "",
        citation_count=int(paper_metadata.get("citation_count") or 0),
        influential_citations=int(
            paper_metadata.get("influential_citations") or 0
        ),
        extracted_via="claude",
        extracted_at=datetime.now().isoformat(timespec="seconds"),
        acquisition_source=acquisition_source,
        acquisition_license=acquisition_license,
    )

    # Citation stats (always available, no LLM needed).
    seed_dois = corpus.seed_dois if corpus is not None else None
    corpus_papers = corpus.papers if corpus is not None else None
    _populate_citation_stats(
        summary,
        doi=doi,
        corpus_metrics=corpus_metrics,
        corpus_papers=corpus_papers,
        seed_dois=seed_dois,
    )

    # Connections (wikilinks). Always derived from the corpus state, even
    # for Tier C — Obsidian's graph view should still show the edge.
    _build_connections(summary, doi=doi, corpus=corpus)

    # Tier C: no PDF -> stub.
    if pdf_path is None or not Path(pdf_path).exists():
        summary.tier = "C"
        summary.source_pdf = ""
        return summary

    summary.tier = "A"
    summary.source_pdf = f"Sources/Papers/{slugify_doi(doi)}.pdf"

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
    fm = {k: v for k, v in fm.items() if v not in ("", 0, 0.0) or k in (
        "year",
        "citation_count",
        "influential_citations",
        "og_score",
        "forward_influence",
    )}
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

    why = (
        "\n## Why it matters in this lineage\n"
        + _bullet_list(summary.why_it_matters)
    )
    methods = (
        "\n## Methods (extracted summary)\n"
        + (summary.methods_summary or "_(not extracted)_")
        + "\n"
    )
    findings = (
        "\n## Key findings (with [page] provenance)\n"
        + _bullet_list(summary.key_findings)
    )

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
        extra_refs_block = (
            "\n## Extracted references (from PDF)\n"
            + _bullet_list(summary.extracted_references)
        )

    provenance = (
        "\n## Reading provenance\n"
        f"- PDF acquired via: {summary.acquisition_source or 'n/a'}"
    )
    if summary.acquisition_license:
        provenance += f" ({summary.acquisition_license})"
    provenance += "\n"
    provenance += f"- Read at: {summary.extracted_at or 'n/a'}\n"
    if summary.tokens_input or summary.tokens_output:
        provenance += (
            f"- Tokens used: ~{summary.tokens_input} input, "
            f"~{summary.tokens_output} output\n"
        )

    return (
        "---\n"
        f"{fm}\n"
        "---\n"
        + body_intro
        + why
        + methods
        + findings
        + refs_line
        + extra_refs_block
        + provenance
    )


# ---------------------------------------------------------------------------
# Public API: write to KB
# ---------------------------------------------------------------------------


_REGEN_FOOTER_RE = re.compile(
    r"\n<!-- vaultlab regen attempt: [^>]+ -->\n*\Z", re.DOTALL
)


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
        marker = f"\n<!-- vaultlab regen attempt: {datetime.now().isoformat(timespec='seconds')} -->\n"
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
    corpus: "Corpus",
    *,
    pdf_cache_dir: Path,
    kb_root: Path,
    parallel: int = 2,  # API-rate-limit-friendly default
    api_key: str | None = None,
    model: str = DEFAULT_MODEL,
    overwrite: bool = False,
    progress: Callable[[str, int, int], None] | None = None,
    _llm: Callable[..., tuple[dict[str, Any], int, int]] | None = None,
) -> dict[str, PaperSummary]:
    """Build summaries for every paper in ``corpus.papers`` and write them.

    Each paper is checked against ``pdf_cache_dir`` (the same
    ``acquire_pdf`` cache); papers with PDFs get full Tier-A LLM reads,
    papers without get Tier-C stubs.

    Args:
        corpus: A built :class:`Corpus` (call ``compute_metrics`` first).
        pdf_cache_dir: Directory holding ``acquire_pdf``-style cached PDFs
            (``<doi-slug>.pdf`` / acquisition's ``doi_slug`` shape).
        kb_root: Vaultlab KB root (e.g. ``G:/My Drive/Knowledge/vaultlab``).
        parallel: Worker count for the thread pool. Default 2 keeps us
            inside Anthropic rate limits comfortably.
        api_key: Override key (otherwise resolved per-paper from env/config).
        model: Anthropic model id.
        overwrite: If False, existing summary files are kept (with a regen
            marker appended).
        progress: ``progress(doi, done, total)`` callback.
        _llm: Test injection.

    Returns:
        ``doi -> PaperSummary``. Tier-C entries appear here too.
    """
    from concurrent.futures import ThreadPoolExecutor

    from vaultlab.research.acquisition import cache_path_for

    pdf_cache_dir = Path(pdf_cache_dir)
    kb_root = Path(kb_root)

    metrics = corpus.metrics
    dois = [d for d in corpus.papers if d]
    total = len(dois)
    results: dict[str, PaperSummary] = {}

    def _one(doi: str) -> tuple[str, PaperSummary]:
        paper = corpus.papers[doi]
        pdf_path = cache_path_for(doi, pdf_cache_dir)
        if not pdf_path.exists():
            pdf_path = None  # Tier C stub
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

    if parallel <= 1:
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
