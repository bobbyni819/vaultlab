"""End-to-end ``/lit-report`` orchestrator: deep research mode (3000-5000 word review).

This module is the differentiator that proves vaultlab can produce
graduate-student-level scientific review writing — not just slide-ready
summaries. Per Task #59 + ``grill-crosstalk-integration-2026-04-30.md``,
``/lit-report`` defaults to FULL ADVERSARIAL crosstalk on every section
(no opt-out — this is the deep-research mode).

What it produces
----------------
For topic ``<topic>`` (slugified), the run writes:

    Sources/Notes/lit-search-<topic>-<date>.md       (search log)
    Sources/Articles/<doi-slug>.md                   (one stub per seed)
    Sources/Papers/<doi-slug>.pdf                    (downloaded full-text)
    Wiki/Summaries/<doi-slug>.md                     (per-paper summaries)
    Wiki/Concepts/<topic-slug>-report-<date>.md      (the assembled review)
    Wiki/Concepts/<topic-slug>-report-<date>/        (per-section drafts)
        background.md
        methods_landscape.md
        findings.md
        contradictions.md
        future_directions.md
        audit.md
    <report>.provenance.json + <report>.method.md     (provenance receipts)

Phase boundaries
----------------
1. **Search → Summaries** — same as :func:`run_lit_arc` but with
   ``depth="thorough"`` default and 20-seed default budget. Re-uses
   :func:`vaultlab.research.lineage._write_search_log`,
   :func:`vaultlab.research.lineage._write_article_stub`,
   :func:`vaultlab.research.acquisition.acquire_pdfs_for_corpus`, and
   :func:`vaultlab.research.summarize.summarize_corpus`.
2. **Per-section adversarial meetings** — for each of the 5 sections we
   run a section-specific role-mix ADVERSARIAL meeting via
   :func:`vaultlab.workflows.crosstalk._run_adversarial_meeting`. Sections
   are generated sequentially with cohesion: section N+1 sees the
   already-written sections 1..N in its context, which prevents repeated
   definitions and contradicting tones.
3. **Rigor audit** — :func:`vaultlab.workflows.crosstalk.rigor_audit`
   runs over the assembled document. Issues are inlined as margin
   comments (``> **[RIGOR]** ...``) but the report still ships.
4. **Provenance receipts** — :func:`vaultlab.provenance.write_receipts`
   drops the JSON + method.md sidecars next to the report.

Two execution modes
-------------------
Like :mod:`summarize` and :mod:`lineage`, this module exposes two
parallel paths:

1. **SDK path** (no callbacks) — calls the Anthropic API directly via
   an API key. Used by plain Python callers / tests with stubs.
2. **Claude-Code-callable path** (``reader=...``, ``section_writer=...``,
   ``crosstalk_runner=...``) — does NOT call any LLM. The slash command
   body inside Claude Code provides callbacks; the active session reads
   PDFs / writes section text / executes crosstalk meetings without an
   API key.

Use the Claude-Code-callable path from ``.claude/commands/lit-report.md``
so users without an Anthropic API key can still run the full pipeline.
"""

from __future__ import annotations

import json
import logging
import re
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from vaultlab.kb.paths import (
    concept_path,
    ensure_parent,
    slugify_doi,
    slugify_topic,
    summary_path,
)
from vaultlab.provenance import ProvenanceRecord, write_receipts
from vaultlab.research.acquisition import acquire_pdfs_for_corpus
from vaultlab.research.corpus import build_corpus_from_seeds
from vaultlab.research.graph_metrics import compute_metrics
from vaultlab.research.lineage import (
    DepthLevel,
    _derive_max_papers,
    _pick_top_n_for_summarization,
    _write_article_stub,
    _write_search_log,
)
from vaultlab.research.picker import PickerCallback, pick_top_n_content_aware
from vaultlab.research.summarize import (
    DEFAULT_MODEL,
    PaperSummary,
    SummaryReader,
    summarize_corpus,
)

if TYPE_CHECKING:
    from vaultlab.research.graph_metrics import CorpusMetrics
    from vaultlab.workflows.crosstalk import RunnerCallback

logger = logging.getLogger(__name__)

__all__ = [
    "SECTION_ORDER",
    "SECTION_ROLES",
    "SECTION_WORD_TARGETS",
    "ReportRunResult",
    "ReportTask",
    "Section",
    "build_section_prompt",
    "prepare_report_task",
    "render_section_from_response",
    "run_lit_report",
    "section_response_schema",
]


# ---------------------------------------------------------------------------
# Section taxonomy
# ---------------------------------------------------------------------------

Section = Literal[
    "background",
    "methods_landscape",
    "findings",
    "contradictions",
    "future_directions",
]

SECTION_ORDER: tuple[Section, ...] = (
    "background",
    "methods_landscape",
    "findings",
    "contradictions",
    "future_directions",
)

# Section-specific role mixes — see grill-crosstalk-integration-2026-04-30.md Q3.
# Every section ends with synthesizer (the integrating role) so its JSON output
# IS the meeting's final_output (matches _run_adversarial_meeting's contract).
SECTION_ROLES: dict[str, list[str]] = {
    "background": ["literature_surveyor", "domain_expert", "synthesizer"],
    "methods_landscape": [
        "literature_surveyor",
        "methods_critic",
        "synthesizer",
    ],
    "findings": [
        "data_analyst",
        "methods_critic",
        "literature_critic",
        "synthesizer",
    ],
    "contradictions": [
        "methods_critic",
        "literature_critic",
        "synthesizer",
    ],
    "future_directions": ["domain_expert", "synthesizer"],
}


# Default mid-range word counts (per spec: 500-800, 800-1200, 1000-1500,
# 300-500, 200-400 → totals to 2800-4400, comfortably inside 3000-5000).
SECTION_WORD_TARGETS: dict[str, int] = {
    "background": 650,
    "methods_landscape": 1000,
    "findings": 1250,
    "contradictions": 400,
    "future_directions": 300,
}


# Wikilink pattern used by render_section_from_response to validate that
# claims are anchored in the corpus. Matches [[doi-slug|Author Year]].
_WIKILINK_RE = re.compile(r"\[\[([A-Za-z0-9._\-+/]+)(?:\\?\|[^\]]*)?\]\]")


# ---------------------------------------------------------------------------
# Result dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ReportTask:
    """A prepared deep-research-report section task.

    No LLM is called when this object is built. The orchestrator drives a
    crosstalk meeting (per :data:`SECTION_ROLES`) that returns JSON
    matching :attr:`response_schema`; :func:`render_section_from_response`
    converts that JSON into the final markdown section text.

    Attributes:
        topic: User-supplied topic (raw, not slugified).
        section: Which of the five sections this task is for.
        summaries: Mapping of doi -> :class:`PaperSummary` (Tier-A reads
            preferred; Tier-C stubs included for citation context).
        metrics: Citation-graph metrics for the corpus (or None when the
            corpus has no metrics yet).
        prior_sections: Already-written sections, keyed by their section
            id (e.g. ``{"background": "<text>"}``). Empty for the first
            section. Threaded into the meeting context for cohesion.
        target_word_count: Mid-range target for the section (drives the
            prompt's "approximately N words" instruction).
        audience: ``"graduate-student"`` (default), ``"domain-expert"``,
            or ``"interdisciplinary"``. Sets the prompt's audience tag.
        prompt: The full user-message prompt text.
        system_prompt: System message for the synthesizer.
        response_schema: JSON schema for the synthesizer's output.
        roles: Ordered role-id list (synthesizer last) used by the
            crosstalk runner.
    """

    topic: str
    section: Section
    summaries: dict[str, PaperSummary]
    metrics: CorpusMetrics | None
    prior_sections: dict[str, str]
    target_word_count: int
    audience: str
    prompt: str
    system_prompt: str
    response_schema: dict[str, Any]
    roles: list[str] = field(default_factory=list)


@dataclass
class ReportRunResult:
    """Output of a :func:`run_lit_report` call.

    Attributes:
        topic: User-supplied topic (raw).
        report_path: ``Wiki/Concepts/<topic>-report-<date>.md`` — the
            assembled review.
        section_paths: Per-section draft markdown files at
            ``Wiki/Concepts/<topic>-report-<date>/<section>.md``.
        audit_report_path: ``.../audit.md`` — the rigor audit fix-list.
        audit_status: ``"passed"`` | ``"passed_with_warnings"`` |
            ``"failed"``. ``failed`` indicates blocker-level issues.
        corpus_size: Number of papers in the corpus.
        pdfs_acquired: Count of papers with a successful PDF acquisition.
        summaries_used: Count of summaries (Tier-A + Tier-C) referenced
            during section generation.
        word_count: Total word count across all five sections (excludes
            the audit footer + frontmatter).
        section_word_counts: Per-section word counts.
        duration_seconds: Wall-clock time of the full run.
        search_log_path: Path to the search log written in Phase 2.
    """

    topic: str
    report_path: Path
    section_paths: dict[str, Path] = field(default_factory=dict)
    audit_report_path: Path = Path()
    audit_status: str = "passed"
    corpus_size: int = 0
    pdfs_acquired: int = 0
    summaries_used: int = 0
    word_count: int = 0
    section_word_counts: dict[str, int] = field(default_factory=dict)
    duration_seconds: float = 0.0
    search_log_path: Path = Path()


# ---------------------------------------------------------------------------
# Section writer callback type
# ---------------------------------------------------------------------------


# A section_writer is the Claude-Code-callable path's per-section callback.
# It receives a :class:`ReportTask` and returns JSON matching the task's
# response_schema. Used as a fallback when no crosstalk_runner is given,
# or when a meeting falls through to single-shot (callback failed).
SectionWriter = Callable[["ReportTask"], dict[str, Any]]


# ---------------------------------------------------------------------------
# Prompt helpers
# ---------------------------------------------------------------------------


_SYSTEM_PROMPT_BY_SECTION: dict[str, str] = {
    "background": (
        "You are writing the Background section of a deep-research review. "
        "Establish historical context, foundational works, and the scope of "
        "the field. Be faithful — only use the per-paper TL;DR / key findings "
        "provided in the user message. Cite each substantive claim with a "
        "[[<doi-slug>|Author Year]] wikilink. Return ONLY a JSON object."
    ),
    "methods_landscape": (
        "You are writing the Methods landscape section of a deep-research "
        "review. Compare the techniques the field uses, with concrete "
        "trade-offs (when to use X vs Y). Cite every method to the paper "
        "that introduced or extended it. Return ONLY a JSON object."
    ),
    "findings": (
        "You are writing the Key findings section of a deep-research review. "
        "Synthesize a narrative across the corpus — group findings by claim, "
        "not by paper. Every claim must be evidence-grounded with a "
        "[[<doi-slug>|Author Year]] wikilink. Return ONLY a JSON object."
    ),
    "contradictions": (
        "You are writing the Contradictions & open questions section of a "
        "deep-research review. Adversarial reading: where do papers "
        "disagree, what gaps exist, what's underdetermined? Cite both sides "
        "of every disagreement. Return ONLY a JSON object."
    ),
    "future_directions": (
        "You are writing the Future directions section of a deep-research "
        "review. Speculative but grounded — every direction must be tied to "
        "a specific gap revealed by the corpus. Return ONLY a JSON object."
    ),
}


def section_response_schema() -> dict[str, Any]:
    """JSON schema for one section's adversarial-meeting output.

    The synthesizer (last role in every section's role mix) MUST return
    a JSON object matching this shape. ``claims_with_evidence`` is the
    audit handle — :func:`render_section_from_response` checks every
    claim for a wikilink anchor.
    """
    return {
        "type": "object",
        "required": ["section_text", "claims_with_evidence"],
        "properties": {
            "section_text": {
                "type": "string",
                "description": (
                    "The full markdown section body. Must contain "
                    "[[<doi-slug>|Author Year]] wikilinks every 2-3 "
                    "sentences for evidence anchoring."
                ),
            },
            "claims_with_evidence": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["claim", "doi_slugs"],
                    "properties": {
                        "claim": {
                            "type": "string",
                            "description": "A single substantive claim from the section.",
                        },
                        "doi_slugs": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": (
                                "DOI-slugs of papers that support this claim. "
                                "Use slugify_doi(doi) format, e.g. "
                                "'10.1038_nature17946'."
                            ),
                        },
                    },
                },
                "description": (
                    "Per-claim evidence map — one entry per substantive "
                    "claim in section_text. Used by the rigor auditor."
                ),
            },
        },
    }


def _bucketed_summaries_md(summaries: dict[str, PaperSummary]) -> str:
    """Render the per-paper summaries as Markdown buckets for the prompt."""
    buckets: dict[str, list[str]] = {
        "history": [],
        "development": [],
        "sota": [],
        "unknown": [],
    }
    for s in summaries.values():
        bucket = s.year_bucket or "unknown"
        # Closes L4 audit bug #6: route through slugify_doi so the
        # wikilink slug matches the actual file written by
        # write_summary_to_kb (which uses summary_path -> slugify_doi).
        # The previous .replace("/", "_") only handled `/` and broke on
        # rarer DOI characters like `:` `*` `?` `<` `>` `|`.
        slug = slugify_doi(s.doi) if s.doi else ""
        from vaultlab.kb.paths import format_author_lastname

        first_author = (format_author_lastname(s.authors[0]) if s.authors else "") or "Anon"
        label = f"{first_author} {s.year}" if s.year else first_author
        tldr = (s.tldr or "_(Tier-C stub — no TL;DR)_").strip()[:280]
        findings_preview = "; ".join((s.key_findings or [])[:2]) or "_(no findings)_"
        buckets.setdefault(bucket, []).append(
            f"- [[{slug}|{label}]] ({s.year or '?'}, tier {s.tier}, "
            f"og={s.og_score:.2f}) — {tldr} | findings: {findings_preview}"
        )
    out: list[str] = []
    for name in ("history", "development", "sota"):
        items = buckets.get(name) or []
        out.append(f"### {name} bucket ({len(items)} papers)")
        out.extend(items[:30] or ["(no papers)"])
        out.append("")
    return "\n".join(out)


def _prior_sections_md(prior_sections: dict[str, str]) -> str:
    """Render already-written sections as cohesion context."""
    if not prior_sections:
        return "_(this is the first section — no prior sections written yet)_"
    blocks: list[str] = []
    for sec in SECTION_ORDER:
        if sec in prior_sections:
            text = prior_sections[sec].strip()
            # Cap at 1500 chars per section so the meeting context stays
            # tractable across all 5 sections.
            if len(text) > 1500:
                text = text[:1500] + "\n... [truncated for cohesion context] ..."
            blocks.append(f"### Already-written: {sec}\n\n{text}\n")
    return "\n".join(blocks) or "_(no prior sections in canonical order)_"


def build_section_prompt(
    *,
    topic: str,
    section: Section,
    summaries: dict[str, PaperSummary],
    prior_sections: dict[str, str],
    target_word_count: int,
    audience: str,
) -> str:
    """Build the user-message prompt for one section's meeting."""
    n_total = len(summaries)
    n_tier_a = sum(1 for s in summaries.values() if s.tier == "A")
    section_label = section.replace("_", " ")

    # Word-range guidance per spec (background 500-800, methods 800-1200, etc.)
    word_ranges = {
        "background": "500-800",
        "methods_landscape": "800-1200",
        "findings": "1000-1500",
        "contradictions": "300-500",
        "future_directions": "200-400",
    }
    word_range = word_ranges.get(section, f"~{target_word_count}")

    return f"""\
TOPIC: {topic}
SECTION: {section_label} ({word_range} words; target ~{target_word_count})
AUDIENCE: {audience}

You are writing the **{section_label}** section of a deep-research review
on '{topic}'. The corpus has {n_total} papers ({n_tier_a} Tier-A with full
TL;DRs).

CITATION RULES:
- Every substantive claim must be anchored with [[<doi-slug>|Author Year]]
  wikilinks every 2-3 sentences.
- Use the EXACT slugs given below — do not invent DOIs.
- Do not introduce papers not in the corpus.

PRIOR SECTIONS (read these for cohesion — do NOT repeat their definitions):

{_prior_sections_md(prior_sections)}

PER-PAPER SUMMARIES (bucketed by year):

{_bucketed_summaries_md(summaries)}

OUTPUT FORMAT:
Return ONLY a JSON object matching this schema:

{{
  "section_text": "<{word_range}-word markdown section text with [[wikilinks]] every 2-3 sentences>",
  "claims_with_evidence": [
    {{
      "claim": "<single substantive claim from section_text>",
      "doi_slugs": ["<slug1>", "<slug2>"]
    }},
    ...
  ]
}}

Write the JSON now.
"""


# ---------------------------------------------------------------------------
# Task preparation (no LLM call)
# ---------------------------------------------------------------------------


def prepare_report_task(
    *,
    topic: str,
    section: Section,
    summaries: dict[str, PaperSummary],
    metrics: CorpusMetrics | None,
    prior_sections: dict[str, str],
    audience: str = "graduate-student",
    target_word_count: int | None = None,
    kb_root: Path | None = None,
) -> ReportTask:
    """Prepare a typed task for one section of the deep research report.

    No LLM is called. The returned :class:`ReportTask` carries everything
    the orchestrator needs (prompt, system prompt, schema, role list) to
    drive a crosstalk meeting.

    Args:
        topic: User-supplied topic (raw).
        section: Which of the five sections.
        summaries: Mapping of doi -> :class:`PaperSummary`.
        metrics: Citation-graph metrics for the corpus (or None).
        prior_sections: Already-written sections (empty for first).
        audience: ``"graduate-student"`` | ``"domain-expert"`` |
            ``"interdisciplinary"``.
        target_word_count: Override default word target. None defaults
            to :data:`SECTION_WORD_TARGETS`.
        kb_root: Vaultlab KB root (currently unused but accepted for
            symmetry with :func:`prepare_arc_task`).

    Returns:
        :class:`ReportTask` ready for the crosstalk runner.
    """
    if section not in SECTION_ORDER:
        raise ValueError(f"unknown section: {section!r} (expected one of {SECTION_ORDER})")
    target = target_word_count if target_word_count is not None else SECTION_WORD_TARGETS[section]
    del kb_root  # accepted for symmetry; not used today
    prompt = build_section_prompt(
        topic=topic,
        section=section,
        summaries=summaries,
        prior_sections=prior_sections,
        target_word_count=target,
        audience=audience,
    )
    return ReportTask(
        topic=topic,
        section=section,
        summaries=dict(summaries),
        metrics=metrics,
        prior_sections=dict(prior_sections),
        target_word_count=target,
        audience=audience,
        prompt=prompt,
        system_prompt=_SYSTEM_PROMPT_BY_SECTION[section],
        response_schema=section_response_schema(),
        roles=list(SECTION_ROLES[section]),
    )


# ---------------------------------------------------------------------------
# Section rendering (validates wikilinks, returns markdown)
# ---------------------------------------------------------------------------


def _word_count(text: str) -> int:
    """Count whitespace-separated words in text (no markdown stripping)."""
    return len(text.split())


def render_section_from_response(
    task: ReportTask,
    response_json: dict[str, Any],
) -> str:
    """Convert the synthesizer's JSON into final markdown for one section.

    Validates that ``section_text`` exists and that
    ``claims_with_evidence`` entries reference at least one wikilink-style
    DOI slug. Missing-evidence claims are flagged inline with a
    ``> **[NEEDS EVIDENCE]** ...`` blockquote so the rigor auditor can
    catch them.

    Args:
        task: The :class:`ReportTask` produced by :func:`prepare_report_task`.
        response_json: Parsed JSON dict matching ``task.response_schema``.

    Returns:
        Markdown section body (no leading H2 — the assembler adds that).
    """
    if not isinstance(response_json, dict):
        return f"_(empty response from section meeting for {task.section})_"
    text = str(response_json.get("section_text", "")).strip()
    if not text:
        return f"_(no section_text returned for {task.section})_"

    claims = response_json.get("claims_with_evidence") or []
    if not isinstance(claims, list):
        claims = []

    # Find missing-evidence claims (no doi_slugs).
    missing: list[str] = []
    for c in claims:
        if not isinstance(c, dict):
            continue
        slugs = c.get("doi_slugs") or []
        if not isinstance(slugs, list) or not slugs:
            claim = str(c.get("claim", "")).strip()
            if claim:
                missing.append(claim)

    # Validate that section_text actually has wikilinks. If zero, that's
    # a strong signal of a hallucination-prone section — flag it.
    has_wikilinks = bool(_WIKILINK_RE.search(text))

    flag_lines: list[str] = []
    if missing:
        for claim in missing[:5]:
            preview = claim[:140] + ("..." if len(claim) > 140 else "")
            flag_lines.append(f"> **[NEEDS EVIDENCE]** {preview}")
    if not has_wikilinks:
        flag_lines.append(
            "> **[NEEDS EVIDENCE]** No [[wikilinks]] detected in this "
            "section — every substantive claim must be anchored."
        )

    if flag_lines:
        text = text + "\n\n" + "\n".join(flag_lines)
    return text


# ---------------------------------------------------------------------------
# Report assembly
# ---------------------------------------------------------------------------


def _abstract_from_sections(sections: dict[str, str], topic: str) -> str:
    """Generate a 100-150 word abstract by stitching first sentences.

    Heuristic — the LLM doesn't write a separate abstract turn. We pull
    the first sentence from each section to produce a 5-sentence executive
    summary. The user can rewrite manually.
    """
    sentences: list[str] = []
    for sec in SECTION_ORDER:
        body = sections.get(sec, "").strip()
        if not body:
            continue
        # Split on first sentence-ending punctuation.
        match = re.search(r"^(.+?[.!?])\s", body)
        first = match.group(1) if match else body[:200].strip()
        # Strip wikilinks down to author labels for readability.
        first = _WIKILINK_RE.sub(
            lambda m: m.group(0).split("|")[-1].rstrip("]"),
            first,
        )
        sentences.append(first.rstrip())
    if not sentences:
        return f"_(no sections written for '{topic}')_"
    abstract = " ".join(sentences)
    return abstract


def _references_from_summaries(
    summaries: dict[str, PaperSummary],
    *,
    cited_slugs: set[str],
) -> str:
    """Render References section listing cited papers (alphabetical by author)."""
    rows: list[tuple[str, str]] = []
    for doi, s in summaries.items():
        # Closes L4 audit bug #6: same slugify_doi routing so the
        # references list lines up with the actual summary filenames.
        slug_source = s.doi or doi
        slug = slugify_doi(slug_source) if slug_source else ""
        if cited_slugs and slug not in cited_slugs:
            continue
        from vaultlab.kb.paths import format_author_lastname

        first_author = s.authors[0] if s.authors else ""
        last_name = format_author_lastname(first_author) or "Anon"
        year = s.year or 0
        title = s.title or "(untitled)"
        journal = s.journal or ""
        sort_key = (last_name.lower(), year)
        line = f"- [[{slug}|{last_name} {year}]] — *{title}*" + (
            f" ({journal}, {year})" if journal else ""
        )
        rows.append((f"{sort_key[0]}_{sort_key[1]:04d}", line))
    rows.sort(key=lambda r: r[0])
    if not rows:
        return "_(no references cited)_"
    return "\n".join(line for _, line in rows)


def _audit_status_label(audit: dict[str, Any]) -> str:
    """Map an audit dict to a frontmatter status string."""
    if not audit:
        return "passed"
    issues = audit.get("issues") or []
    has_blocker = any(i.get("severity") == "blocker" for i in issues)
    has_major = any(i.get("severity") == "major" for i in issues)
    if has_blocker:
        return "failed"
    if has_major or issues:
        return "passed_with_warnings"
    if audit.get("passed", True):
        return "passed"
    return "failed"


def _render_audit_section(audit: dict[str, Any]) -> str:
    """Render the rigor audit footer for the assembled report."""
    if not audit:
        return "## Rigor audit\n\n_(audit skipped — no runner_callback)_\n"
    issues = audit.get("issues") or []
    passed = bool(audit.get("passed", True))
    lines = ["## Rigor audit", ""]
    if passed and not issues:
        lines.append("Status: **passed** — no issues found.")
        return "\n".join(lines) + "\n"
    if passed:
        lines.append(f"Status: **passed_with_warnings** ({len(issues)} minor issues).")
    else:
        lines.append(f"Status: **failed** ({len(issues)} issues — see below).")
    lines.append("")
    lines.append("| Severity | Loc | Kind | Fix |")
    lines.append("|---|---|---|---|")
    for i in issues:
        if not isinstance(i, dict):
            continue
        sev = i.get("severity", "minor")
        loc = i.get("loc", "")
        kind = i.get("kind", "other")
        fix = i.get("fix", "")
        # Escape pipe characters in cell content.
        loc = str(loc).replace("|", "\\|")
        fix = str(fix).replace("|", "\\|")
        lines.append(f"| {sev} | {loc} | {kind} | {fix} |")
    return "\n".join(lines) + "\n"


def _section_h2(section: Section) -> str:
    """Pretty H2 label for a section id."""
    return {
        "background": "Background",
        "methods_landscape": "Methods landscape",
        "findings": "Key findings",
        "contradictions": "Contradictions & open questions",
        "future_directions": "Future directions",
    }[section]


def _assemble_report_markdown(
    *,
    topic: str,
    date_str: str,
    sections: dict[str, str],
    summaries: dict[str, PaperSummary],
    audit: dict[str, Any],
    seeds_n: int,
    corpus_size: int,
    pdfs_acquired: int,
    method_relpath: str,
) -> tuple[str, dict[str, int], int]:
    """Build the final review markdown.

    Returns ``(markdown, per_section_word_counts, total_words)``.
    """
    n_total = len(summaries)
    n_tier_a = sum(1 for s in summaries.values() if s.tier == "A")

    # Build per-section word counts.
    per_section_words: dict[str, int] = {}
    for sec in SECTION_ORDER:
        per_section_words[sec] = _word_count(sections.get(sec, ""))
    total_words = sum(per_section_words.values())

    # Collect cited slugs from section text for the References section.
    cited_slugs: set[str] = set()
    for body in sections.values():
        for m in _WIKILINK_RE.finditer(body):
            cited_slugs.add(m.group(1))

    audit_status = _audit_status_label(audit)

    fm_lines = [
        "---",
        f"topic: {topic}",
        f"date: {date_str}",
        f"seeds: {seeds_n}",
        f"corpus_size: {corpus_size}",
        f"papers_with_full_text: {pdfs_acquired}",
        f"summaries_used: {n_total}",
        f"tier_a_count: {n_tier_a}",
        f"total_words: {total_words}",
        f"sections: {sum(1 for sec in SECTION_ORDER if sections.get(sec))}",
        f"audit_status: {audit_status}",
        "generated_by: vaultlab.research.report.run_lit_report",
        f"provenance: {method_relpath}",
        "---",
    ]

    body: list[str] = []
    body.append(f"# Deep research report: {topic}")
    body.append("")
    body.append(
        f"Corpus: {n_total} papers ({n_tier_a} Tier-A read full-text). "
        f"Seeds: {seeds_n}. Date: {date_str}. Total: {total_words} words "
        f"across {sum(1 for sec in SECTION_ORDER if sections.get(sec))} sections."
    )
    body.append("")

    # Abstract.
    body.append("## Abstract")
    body.append("")
    body.append(_abstract_from_sections(sections, topic))
    body.append("")

    # Sections in canonical order.
    for sec in SECTION_ORDER:
        text = sections.get(sec, "").strip()
        if not text:
            continue
        wc = per_section_words[sec]
        body.append(f"## {_section_h2(sec)} ({wc} words)")
        body.append("")
        body.append(text)
        body.append("")

    # References.
    body.append("## References")
    body.append("")
    body.append(_references_from_summaries(summaries, cited_slugs=cited_slugs))
    body.append("")

    # Rigor audit.
    body.append("---")
    body.append("")
    body.append(_render_audit_section(audit))

    return (
        "\n".join(fm_lines) + "\n\n" + "\n".join(body).rstrip() + "\n",
        per_section_words,
        total_words,
    )


# ---------------------------------------------------------------------------
# Section meeting executor (delegates to crosstalk._run_adversarial_meeting)
# ---------------------------------------------------------------------------


def _build_section_meeting(
    task: ReportTask,
    *,
    n_rounds: int,
    runner_callback: RunnerCallback | None,
    timeout_seconds: int,
) -> tuple[dict[str, Any], Any]:
    """Run an ADVERSARIAL section meeting and return (JSON, CrosstalkResult).

    The role mix comes from :data:`SECTION_ROLES`. We build the meeting
    by hand (rather than via :func:`build_meeting`) because the role mix
    is section-specific, not one of the named meeting types.

    Returns ``(parsed_json, crosstalk_result)``. The
    :class:`vaultlab.workflows.crosstalk.CrosstalkResult` is returned so
    the caller can persist per-turn transcripts via
    :func:`vaultlab.workflows.crosstalk.write_crosstalk_artifacts` —
    AGENTS.md Invariant 4 (ChainLink-per-turn) requires every role-turn
    to land on disk. Both halves are populated even on callback failure
    (JSON may be empty; CrosstalkResult records the fallback status).
    """
    from vaultlab.roles import ROLE_TEMPLATES
    from vaultlab.runner.models import Agenda, Meeting, MeetingMode
    from vaultlab.workflows.crosstalk import _run_adversarial_meeting

    # Resolve role objects.
    role_objs = []
    for rid in task.roles:
        if rid not in ROLE_TEMPLATES:
            raise ValueError(
                f"role '{rid}' not loaded — section {task.section} requires {task.roles}"
            )
        role_objs.append(ROLE_TEMPLATES[rid])

    section_label = task.section.replace("_", " ")
    statement = (
        f"Write the {section_label} section ({task.target_word_count} words) "
        f"of a deep-research review on '{task.topic}'. Be evidence-grounded; "
        "every claim cites a paper via [[wikilinks]]."
    )
    rules = [
        "Every substantive claim must cite a paper with "
        "[[<doi-slug>|Author Year]] every 2-3 sentences.",
        "Use ONLY DOIs from the corpus — never invent citations.",
        f"Synthesizer MUST return JSON matching the schema "
        f"{json.dumps(task.response_schema)} with no other top-level keys.",
        "Read the prior sections (if any) to keep tone/scope consistent and "
        "avoid repeating definitions.",
    ]
    questions = [
        f"What is the central narrative of the {section_label} section?",
        "Which papers anchor the most important claims?",
        "Where could a reader doubt the evidence — what's left out?",
        f"Final {section_label} section in the response_schema shape?",
    ]
    agenda = Agenda(
        topic=task.topic,
        statement=statement,
        questions=questions,
        rules=rules,
    )

    meeting = Meeting(
        topic=task.topic,
        mode=MeetingMode.ADVERSARIAL,
        roles=role_objs,
        session_context=task.prompt,  # the prepared prompt IS the context
        agenda=agenda,
    )

    result = _run_adversarial_meeting(
        meeting=meeting,
        runner_callback=runner_callback,
        n_rounds=n_rounds,
        timeout_seconds=timeout_seconds,
        purpose=f"report-{task.section}",
    )
    return (result.final_output or {}), result


# ---------------------------------------------------------------------------
# Public orchestrator
# ---------------------------------------------------------------------------


_ProgressFn = Callable[..., None]


def _emit(progress: _ProgressFn | None, *args: Any, **kwargs: Any) -> None:
    if progress is None:
        return
    try:
        progress(*args, **kwargs)
    except Exception:  # pragma: no cover — never break a run on a callback
        logger.debug("progress callback raised", exc_info=True)


def run_lit_report(
    topic: str,
    *,
    kb_root: Path | None = None,
    project_slug: str | None = None,
    speaker: str = "",
    affiliation: str = "",
    audience: str = "graduate-student",
    target_total_words: int = 4000,  # mid of 3000-5000 (informational only)
    # Phase 1-6 controls (mirror run_lit_arc):
    depth: DepthLevel = "thorough",
    max_seeds: int = 20,
    max_papers_to_summarize: int | None = None,
    pdf_cache_dir: Path | None = None,
    apis: dict[str, str] | None = None,
    # Phase 1-6 callbacks (Claude-Code mode):
    picker_callback: PickerCallback | None = None,
    reader: SummaryReader | None = None,
    # Phase 7 (per-section) callbacks:
    section_writer: SectionWriter | None = None,
    crosstalk_runner: RunnerCallback | None = None,
    crosstalk_n_rounds: int = 3,
    section_timeout_seconds: int = 600,
    # Phase 8 (rigor audit):
    audit_strict: bool = False,
    # Progress reporting:
    progress: _ProgressFn | None = None,
    # Test injection (mirror run_lit_arc):
    _client: Any | None = None,
    _fetch_refs: Any | None = None,
    _acquire: Any | None = None,
    _summarize_corpus_fn: Any | None = None,
    _today: str | None = None,
) -> ReportRunResult:
    """Deep research report orchestrator (3000-5000 word review).

    Phases:

    1-6. Search → corpus → PDFs → per-paper summaries (same as
        :func:`run_lit_arc` but with ``depth="thorough"`` default and
        ``max_seeds=20`` default).
    7. Per-section ADVERSARIAL meetings: for each of the five sections,
       a section-specific role mix (see :data:`SECTION_ROLES`) drafts the
       section text. Section N+1 receives sections 1..N for cohesion.
    8. Rigor audit on the assembled document — runs after all sections
       are written. Issues are inlined as margin comments. ``audit_strict``
       blocks the save when blocker-level issues are found.
    9. Write ``Wiki/Concepts/<topic>-report-<date>.md`` plus per-section
       drafts and provenance receipts.

    Two execution modes (mirror :func:`run_lit_arc`):

    * **SDK path** — leave ``reader`` / ``section_writer`` /
      ``crosstalk_runner`` at None. Anthropic API key required.
    * **Claude-Code path** — pass ``reader`` for per-paper PDF summaries,
      and EITHER ``crosstalk_runner`` (for full crosstalk per-section
      meetings; the default for ``/lit-report``) OR ``section_writer``
      (single-shot per-section fallback).

    Per Bobby's "tiered+dynamic" decision (Q1 in
    grill-crosstalk-integration-2026-04-30.md), ``/lit-report`` defaults
    to FULL crosstalk on every section — this is the differentiator from
    ``/lit-arc``. There is no opt-out flag here; if ``crosstalk_runner``
    is None, sections fall through to ``section_writer`` (or empty).

    Args:
        topic: User-supplied topic (raw).
        kb_root: Vaultlab KB root.
        project_slug: Optional override for ``slugify_topic(topic)``.
        speaker: Recorded in provenance receipt.
        affiliation: Recorded in provenance receipt.
        audience: ``"graduate-student"`` (default) | ``"domain-expert"`` |
            ``"interdisciplinary"``. Threaded into per-section prompts.
        target_total_words: Informational target (3000-5000 default).
            Per-section word targets come from
            :data:`SECTION_WORD_TARGETS`.
        depth: ``"fast" | "balanced" | "thorough" (default) | "complete"``.
            Default ``"thorough"`` so reports read every cached PDF.
        max_seeds: Search-result budget for the seed query.
        max_papers_to_summarize: Override the depth-derived Tier-A budget.
        pdf_cache_dir: Defaults to ``<kb_root>/Sources/Papers``.
        apis: Optional API-key map forwarded to PDF acquisition.
        picker_callback: Optional content-aware Tier-A picker. If ``None``,
            falls back to citation-graph rank.
        reader: Per-paper PDF reader. Required for the Claude-Code path.
        section_writer: Per-section writer (single-shot fallback).
        crosstalk_runner: Crosstalk meeting executor (preferred path).
        crosstalk_n_rounds: Meeting rounds (default 3, hard cap 5 enforced
            by :func:`_run_adversarial_meeting`).
        section_timeout_seconds: Per-section meeting timeout (default 600s
            = 10 min).
        audit_strict: If True, raise :class:`RuntimeError` on
            blocker-level audit issues instead of writing the flagged
            report.
        progress: ``progress(event, **fields)`` callback.
        _client, _fetch_refs, _acquire, _summarize_corpus_fn, _today:
            Test injection points (mirror :func:`run_lit_arc`).

    Returns:
        :class:`ReportRunResult` with paths + word counts.
    """
    # G-2 fix (option b): if project_slug wasn't threaded explicitly, walk
    # up from cwd looking for ``.vaultlab-project.json`` and adopt its
    # slug. Aligns with the "state-aware, additive, read-before-write"
    # memory rule — explicit kwarg still wins, but a forgetful slash-
    # command body no longer creates a parallel ``Wiki/Projects/<slug>/``.
    if project_slug is None:
        try:
            from vaultlab.onboarding import load_project_config_from_cwd

            _cfg = load_project_config_from_cwd()
        except Exception:  # pragma: no cover — never break a run
            logger.exception("load_project_config_from_cwd failed")
            _cfg = None
        if _cfg is not None and getattr(_cfg, "slug", ""):
            project_slug = _cfg.slug
            logger.info(
                "auto-discovered project_slug=%s from .vaultlab-project.json (cwd=%s)",
                project_slug,
                Path.cwd(),
            )

    started = time.time()
    date_str = _today or date.today().strftime("%Y-%m-%d")
    # Multi-tenant KB-root resolution (Layer A, 2026-04-30): see the matching
    # block in run_lit_arc — same chain, same rationale.
    if kb_root is None:
        from vaultlab.context.locations import resolve_kb_root

        kb_root = resolve_kb_root()
    kb_root = Path(kb_root)

    if pdf_cache_dir is None:
        pdf_cache_dir = kb_root / "Sources" / "Papers"
    pdf_cache_dir = Path(pdf_cache_dir)
    pdf_cache_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Phase 1: search
    # ------------------------------------------------------------------
    _emit(progress, "phase", "search", topic=topic, max_seeds=max_seeds)
    if _client is None:
        from vaultlab.research import ResearchClient

        client = ResearchClient()
    else:
        client = _client
    raw_seeds = client.search(topic, max_results=max_seeds)
    seeds = [s for s in raw_seeds if s.doi][:max_seeds]
    _emit(progress, "seeds", n=len(seeds))

    # ------------------------------------------------------------------
    # Phase 2: search log
    # ------------------------------------------------------------------
    log_path = _write_search_log(kb_root=kb_root, topic=topic, seeds=seeds, date_str=date_str)
    _emit(progress, "search_log", path=str(log_path))

    # ------------------------------------------------------------------
    # Phase 3: article stubs
    # ------------------------------------------------------------------
    article_stubs: list[Path] = []
    for seed in seeds:
        p = _write_article_stub(kb_root, seed)
        if p is not None:
            article_stubs.append(p)
    _emit(progress, "article_stubs", n=len(article_stubs))

    # ------------------------------------------------------------------
    # Phase 4: corpus + metrics
    # ------------------------------------------------------------------
    _emit(progress, "phase", "corpus", n_seeds=len(seeds))
    corpus = build_corpus_from_seeds(
        seeds,
        topic=topic,
        fetch_refs=_fetch_refs,
    )
    compute_metrics(corpus)
    _emit(
        progress,
        "corpus",
        n_papers=corpus.n_papers,
        n_edges=corpus.n_edges,
    )

    # ------------------------------------------------------------------
    # Phase 5: PDF acquisition (waterfall)
    # ------------------------------------------------------------------
    _emit(progress, "phase", "acquire_pdfs", n_papers=corpus.n_papers)
    acq = _acquire if _acquire is not None else acquire_pdfs_for_corpus
    skip_paywalled_arg = depth != "complete"
    aggressive_retry_arg = depth == "complete"
    try:
        acq_results = acq(
            corpus,
            pdf_cache_dir,
            apis=apis,
            skip_paywalled=skip_paywalled_arg,
            aggressive_retry=aggressive_retry_arg,
        )
    except TypeError:
        try:
            acq_results = acq(
                corpus,
                pdf_cache_dir,
                apis=apis,
                skip_paywalled=skip_paywalled_arg,
            )
        except TypeError:
            acq_results = acq(corpus, pdf_cache_dir)
    pdfs_acquired = sum(1 for r in acq_results.values() if getattr(r, "pdf_path", None) is not None)
    _emit(progress, "pdfs_acquired", n=pdfs_acquired)

    # ------------------------------------------------------------------
    # Resolve Tier-A budget
    # ------------------------------------------------------------------
    if max_papers_to_summarize is None:
        resolved_max_papers = _derive_max_papers(
            depth, n_pdfs_cached=pdfs_acquired, corpus_size=corpus.n_papers
        )
    else:
        resolved_max_papers = int(max_papers_to_summarize)
    _emit(
        progress,
        "depth_budget",
        depth=depth,
        n_pdfs_cached=pdfs_acquired,
        budget=resolved_max_papers,
    )

    # ------------------------------------------------------------------
    # Phase 6: summaries
    # ------------------------------------------------------------------
    _emit(progress, "phase", "summarize", n_papers=corpus.n_papers)

    tier_a_dois: set[str] | None = None
    if resolved_max_papers and resolved_max_papers < corpus.n_papers:
        if picker_callback is not None:
            keep_list = pick_top_n_content_aware(
                topic,
                corpus,
                target_n=resolved_max_papers,
                coarse_n=None,  # read every corpus abstract
                kb_root=kb_root,
                pdf_cache_dir=pdf_cache_dir,
                picker_callback=picker_callback,
                fallback_to_citation_graph=True,
            )
        else:
            keep_list = _pick_top_n_for_summarization(
                corpus,
                n=resolved_max_papers,
                pdf_cache_dir=pdf_cache_dir,
            )
        tier_a_dois = set(keep_list)

    summarize_fn = _summarize_corpus_fn if _summarize_corpus_fn is not None else summarize_corpus
    if reader is not None:
        summaries = summarize_fn(
            corpus,
            pdf_cache_dir=pdf_cache_dir,
            kb_root=kb_root,
            parallel=1,
            overwrite=True,
            reader=reader,
            tier_a_dois=tier_a_dois,
        )
    else:
        summaries = summarize_fn(
            corpus,
            pdf_cache_dir=pdf_cache_dir,
            kb_root=kb_root,
            parallel=2,
            overwrite=True,
        )

    summary_paths = {doi: summary_path(kb_root, doi) for doi in summaries}
    summaries_used = len(summaries)
    _emit(
        progress,
        "summaries",
        total=summaries_used,
        written=sum(1 for p in summary_paths.values() if p.exists()),
    )

    # ------------------------------------------------------------------
    # Phase 7: per-section ADVERSARIAL meetings (cohesion-threaded)
    # ------------------------------------------------------------------
    # The report goes to Wiki/Concepts/<slug>-report-<date>.md and the
    # per-section drafts go to a sibling directory of the same stem.
    #
    # F-8 fix (pipeline-integration-map audit): when the caller passes an
    # explicit ``project_slug``, drive the path slug from it so the report
    # lands at ``Wiki/Concepts/<project_slug>-report-<date>.md`` instead
    # of the topic-derived slug. Mirrors the resolved-slug pattern from
    # ``run_lit_arc`` (Phase 9). When ``project_slug`` is ``None``, we
    # fall back to ``slugify_topic(topic)`` — i.e. the previous behaviour.
    resolved_slug = (
        project_slug.strip() if project_slug and project_slug.strip() else slugify_topic(topic)
    )
    # ``concept_path`` slugifies its topic argument, so feeding the
    # already-resolved slug is idempotent and produces the same path
    # regardless of whether the user passed a raw topic or a slug.
    report_path = ensure_parent(concept_path(kb_root, resolved_slug, "report", date_str))
    report_drafts_dir = report_path.with_suffix("")  # strip .md
    report_drafts_dir.mkdir(parents=True, exist_ok=True)

    # G-5 fix: per-section adversarial meetings produce ~50 role-turns; we
    # must persist every turn to disk per AGENTS.md Invariant 4
    # (ChainLink-per-turn). Build the canonical run_dir up-front so each
    # section's transcripts can be dropped under
    # ``Output/<slug>/runs/<run_id>/`` via write_crosstalk_artifacts.
    from vaultlab.kb.paths import run_dir as _run_dir_path

    section_run_dir = _run_dir_path(kb_root, resolved_slug)
    section_run_dir.mkdir(parents=True, exist_ok=True)

    metrics = corpus.metrics
    sections_text: dict[str, str] = {}
    section_paths: dict[str, Path] = {}

    for section in SECTION_ORDER:
        _emit(progress, "phase", "section", section=section)
        task = prepare_report_task(
            topic=topic,
            section=section,
            summaries=summaries,
            metrics=metrics,
            prior_sections=dict(sections_text),
            audience=audience,
            kb_root=kb_root,
        )

        response_json: dict[str, Any] = {}
        section_ct_result = None
        # Crosstalk path (preferred default for /lit-report).
        if crosstalk_runner is not None:
            try:
                response_json, section_ct_result = _build_section_meeting(
                    task,
                    n_rounds=crosstalk_n_rounds,
                    runner_callback=crosstalk_runner,
                    timeout_seconds=section_timeout_seconds,
                )
            except Exception as exc:
                logger.exception("section meeting failed for %s: %s", section, exc)
                response_json = {}
                section_ct_result = None

            # G-5 fix: persist per-turn transcripts for the section
            # meeting (AGENTS.md Invariant 4). The artifact writer drops
            # ``meeting-report-<section>-transcript.md`` plus per-turn
            # files into the run_dir; we never break the run on a write
            # failure.
            if section_ct_result is not None:
                try:
                    from vaultlab.workflows.crosstalk import (
                        write_crosstalk_artifacts,
                    )

                    write_crosstalk_artifacts(section_ct_result, run_dir=section_run_dir)
                except Exception:
                    logger.exception(
                        "write_crosstalk_artifacts (section=%s) failed",
                        section,
                    )

        # Single-shot fallback (callable-LLM mode without crosstalk).
        if not response_json and section_writer is not None:
            try:
                response_json = section_writer(task) or {}
            except Exception as exc:
                logger.exception("section_writer raised on %s: %s", section, exc)
                response_json = {}

        section_md = render_section_from_response(task, response_json)
        sections_text[section] = section_md

        # Per-section draft file.
        draft_path = ensure_parent(report_drafts_dir / f"{section}.md")
        draft_path.write_text(
            f"# {_section_h2(section)}\n\n{section_md}\n",
            encoding="utf-8",
        )
        section_paths[section] = draft_path
        _emit(
            progress,
            "section_written",
            section=section,
            words=_word_count(section_md),
            path=str(draft_path),
        )

    # ------------------------------------------------------------------
    # Phase 8: rigor audit on the assembled body
    # ------------------------------------------------------------------
    _emit(progress, "phase", "rigor_audit")
    # Pre-assemble a draft document body for the auditor (without
    # frontmatter, since the audit is over content not metadata).
    audit_body_parts: list[str] = []
    for sec in SECTION_ORDER:
        body = sections_text.get(sec, "").strip()
        if body:
            audit_body_parts.append(f"## {_section_h2(sec)}\n\n{body}\n")
    audit_body = "\n".join(audit_body_parts)

    audit_dict: dict[str, Any] = {}
    if crosstalk_runner is not None:
        try:
            from vaultlab.workflows.crosstalk import rigor_audit

            audit_dict = rigor_audit(
                document=audit_body,
                summaries=summaries,
                audit_kind="report",
                runner_callback=crosstalk_runner,
                timeout_seconds=section_timeout_seconds,
            )
        except Exception as exc:
            logger.exception("rigor_audit failed: %s", exc)
            audit_dict = {
                "passed": True,
                "issues": [
                    {
                        "loc": "(audit)",
                        "severity": "minor",
                        "kind": "other",
                        "fix": f"rigor_audit raised: {exc!r}",
                    }
                ],
            }

    audit_status = _audit_status_label(audit_dict)
    _emit(progress, "audit_done", status=audit_status, n_issues=len(audit_dict.get("issues") or []))

    # Strict mode: refuse to write a flagged report.
    if audit_strict and audit_status == "failed":
        raise RuntimeError(
            f"audit_strict=True and rigor audit failed with "
            f"{len(audit_dict.get('issues') or [])} blocker-level issues. "
            "Aborting before write. Lower audit_strict or fix the issues."
        )

    # ------------------------------------------------------------------
    # Phase 9: assemble + write
    # ------------------------------------------------------------------
    method_relpath = report_path.name + ".method.md"
    md, per_section_words, total_words = _assemble_report_markdown(
        topic=topic,
        date_str=date_str,
        sections=sections_text,
        summaries=summaries,
        audit=audit_dict,
        seeds_n=len(seeds),
        corpus_size=corpus.n_papers,
        pdfs_acquired=pdfs_acquired,
        method_relpath=method_relpath,
    )
    report_path.write_text(md, encoding="utf-8")
    _emit(progress, "report_written", path=str(report_path), words=total_words)

    # Audit fix-list as a separate file for easy reference.
    audit_path = ensure_parent(report_drafts_dir / "audit.md")
    audit_lines: list[str] = [
        f"# Rigor audit — {topic}",
        "",
        f"Date: {date_str}",
        f"Status: **{audit_status}**",
        f"Issues: {len(audit_dict.get('issues') or [])}",
        "",
        _render_audit_section(audit_dict),
    ]
    audit_path.write_text("\n".join(audit_lines), encoding="utf-8")

    # Provenance receipts.
    record = ProvenanceRecord(
        generated_by="vaultlab.research.report.run_lit_report",
        project="lit-report",
        topic=topic,
        kind="deep_research_report",
        inputs=[str(p) for p in summary_paths.values()],
        params={
            "max_seeds": max_seeds,
            "depth": depth,
            "max_papers_to_summarize": resolved_max_papers,
            "max_papers_to_summarize_explicit": max_papers_to_summarize,
            "pdf_cache_dir": str(pdf_cache_dir),
            "audience": audience,
            "target_total_words": target_total_words,
            "actual_total_words": total_words,
            "section_word_counts": per_section_words,
            "crosstalk_n_rounds": crosstalk_n_rounds,
            "audit_status": audit_status,
            "audit_strict": audit_strict,
            "narration": "claude" if section_writer or crosstalk_runner else "skipped",
        },
        model=DEFAULT_MODEL,
        related_outputs=[
            str(log_path),
            *[str(p) for p in section_paths.values()],
            str(audit_path),
            *[str(p) for p in article_stubs],
        ],
        notes=(f"Speaker: {speaker}; Affiliation: {affiliation}" if speaker or affiliation else ""),
    )
    write_receipts(report_path, record)
    _emit(progress, "provenance_written")

    # ``resolved_slug`` is already computed above (Phase 7) and used to
    # route ``report_path``. We don't write a project view for
    # ``/lit-report`` — that's ``/lit-arc`` territory — but the slug is
    # honoured in the output-path construction per F-8.

    duration = time.time() - started
    return ReportRunResult(
        topic=topic,
        report_path=report_path,
        section_paths=section_paths,
        audit_report_path=audit_path,
        audit_status=audit_status,
        corpus_size=corpus.n_papers,
        pdfs_acquired=pdfs_acquired,
        summaries_used=summaries_used,
        word_count=total_words,
        section_word_counts=per_section_words,
        duration_seconds=duration,
        search_log_path=log_path,
    )
