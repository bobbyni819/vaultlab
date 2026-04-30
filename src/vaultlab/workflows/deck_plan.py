"""Content-aware deck-plan generator.

This module is the bobby_slides differentiator that the L4 audit said was
missing: instead of mechanical synthesis from corpus metadata
(history-bucket leader / dev-bucket leader / sota-bucket leader, hard-coded
7-slide structure — see :func:`vaultlab.slides.deck._plan_from_lineage`),
the LLM reasons about the story arc and produces a typed plan that the
deterministic renderer (:func:`vaultlab.slides.build_from_plan`) executes.

Design
------

Two execution modes, mirroring :mod:`vaultlab.research.lineage`:

1. **Mechanical fallback** — when no ``plan_callback`` is provided, route
   through :func:`vaultlab.slides.build_deck_from_lineage_result`'s
   existing bucket-leader synthesis. This is the v0.1 fast path; it
   keeps backwards compat and works without an LLM.

2. **Content-aware path** — :func:`prepare_deck_plan_task` builds a
   typed :class:`DeckPlanTask` (no LLM call). The slash command body
   inside Claude Code reads ``task.corpus_summaries`` +
   ``task.corpus_metrics`` + ``task.figure_assignments`` and produces a
   JSON response per ``task.response_schema``.
   :func:`render_plan_from_response` validates the response, fills in
   missing fields, drops invalid slides, and emits a dict-plan that
   :func:`vaultlab.slides.build_from_plan` consumes.

The dict-plan is the **same shape** :func:`build_from_plan` already
understands (``title / section_divider / figure / multi_figure / text /
references``). The ``references`` slide is auto-generated from the DOIs
cited across the LLM's slides — the LLM never picks references directly.

Public API
----------

- :class:`DeckPlanTask` — frozen dataclass with the prepared prompt /
  schema / inputs.
- :func:`prepare_deck_plan_task` — build a :class:`DeckPlanTask`.
- :func:`render_plan_from_response` — Claude's JSON -> dict-plan.
- :func:`generate_deck_plan` — top-level orchestrator.
- :func:`deck_plan_response_schema` — the JSON schema.
- :data:`PlanGeneratorCallback` — callback type alias.

Out of scope (for this module): the actual LLM call. The
``plan_callback`` *is* the LLM (Claude Code itself); the SDK path lives
in :mod:`vaultlab.research.lineage` for legacy reasons.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date as _date
from pathlib import Path
from typing import TYPE_CHECKING, Any

from vaultlab.kb.paths import slugify_doi

if TYPE_CHECKING:
    from vaultlab.research.corpus import Corpus
    from vaultlab.research.summarize import PaperSummary

logger = logging.getLogger(__name__)


__all__ = [
    "DeckPlanTask",
    "PlanGeneratorCallback",
    "deck_plan_response_schema",
    "generate_deck_plan",
    "prepare_deck_plan_task",
    "render_plan_from_response",
]


# Slide types the response schema supports. ``references`` is excluded —
# the renderer auto-appends a references slide from cited DOIs.
SUPPORTED_LLM_SLIDE_TYPES: frozenset[str] = frozenset({
    "title",
    "section_divider",
    "figure",
    "multi_figure",
    "text",
})


# ---------------------------------------------------------------------------
# Dataclass + callback type
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DeckPlanTask:
    """Prepared deck-plan-generation task ready for a Claude Code session.

    Attributes
    ----------
    topic
        The user-supplied topic (raw, not slugified).
    corpus_summaries
        List of per-paper dicts (``doi``, ``title``, ``authors``, ``year``,
        ``journal``, ``year_bucket``, ``tier``, ``og_score``,
        ``forward_influence``, ``tldr``, ``key_findings``). Restricted to
        Tier-A papers — the corpus papers we have full-text content for.
    corpus_metrics
        Dict of ``{"top_og": [(doi, score), ...], "top_co_citation":
        [(doi_a, doi_b, count), ...], "year_buckets": {bucket -> count},
        "n_total_papers": int, "n_tier_a": int}``.
    figure_assignments
        Mapping ``doi -> on-disk figure path`` for figures the LLM may
        choose to drop into ``figure`` slides.
    speaker
        Speaker name (title slide).
    affiliation
        Affiliation string (title slide).
    target_slide_count
        Target number of slides the LLM should produce. Default 7.
    audience
        Audience tag — ``"journal-club"`` / ``"lab-meeting"`` /
        ``"conference"`` — feeds the prompt's tone instructions.
    prompt
        The full user-message prompt for the LLM.
    system_prompt
        The system message guiding the LLM's behavior.
    response_schema
        JSON schema describing the expected response shape.
    """

    topic: str
    corpus_summaries: list[dict[str, Any]]
    corpus_metrics: dict[str, Any]
    figure_assignments: dict[str, Path]
    speaker: str
    affiliation: str
    target_slide_count: int
    audience: str
    prompt: str
    system_prompt: str
    response_schema: dict[str, Any]


PlanGeneratorCallback = Callable[[DeckPlanTask], dict[str, Any]]


# ---------------------------------------------------------------------------
# System prompt (tone + faithfulness rules)
# ---------------------------------------------------------------------------


_DECK_PLAN_SYSTEM_PROMPT = (
    "You are a literature-savvy slide-deck author. Your job is to produce a "
    "TYPED JSON plan for a slide deck describing a research topic. "
    "RULES:\n"
    "1. Read EVERY Tier-A paper summary (TL;DR + key_findings) before you "
    "decide the story arc. Do not skim — every paper's findings should "
    "influence which slides you pick.\n"
    "2. Identify a 3-5 beat narrative through the corpus. Common arcs: "
    "history -> development -> SOTA, chronological evolution, "
    "methodological progression, by-application, problem -> approach -> result. "
    "Let the corpus's actual content shape the arc — do not force a template.\n"
    "3. Every bullet on every content slide MUST come from a real paper's "
    "TL;DR or key_findings. Cite each claim with a wikilink in the form "
    "[[<doi-slug>|Author Year]] using the slugs provided. Do NOT invent "
    "claims.\n"
    "4. When a slide makes a claim about paper X but the most relevant figure "
    "is from paper Y, you MAY use Y's figure — set ``claim_paper_doi`` to X "
    "and ``figure_paper_doi`` to Y, and the renderer will compose a "
    "'Substituted figure from <Y>' caption.\n"
    "5. Pick figures ONLY from the available figure_assignments — never "
    "fabricate an image_path.\n"
    "6. Write speaker_notes for every slide using the dual-format pattern: "
    "``mental_map`` (hook / key_claim / evidence / key_terms / click / "
    "transition) and ``detailed_script`` (200-400 word first-person "
    "monologue).\n"
    "7. Hit the target_slide_count exactly — do not sprawl. Title slide + "
    "section dividers count toward the total.\n"
    "Return ONLY a JSON object matching the response_schema. No markdown "
    "fencing, no commentary."
)


# ---------------------------------------------------------------------------
# Prompt builder
# ---------------------------------------------------------------------------


def _author_year_label_from_dict(s: dict[str, Any]) -> str:
    """Vancouver-style ``Last Year`` from a summary dict.

    Mirrors :func:`vaultlab.research.lineage._author_year_label` but
    operates on the dict shape we feed into the prompt.
    """
    authors = s.get("authors") or []
    last = ""
    if authors:
        first = authors[0]
        # NCBI-style "Smith J" -> last name is the first whitespace token.
        last = (first.split()[0] if first else "") or ""
    if not last:
        last = "Anon"
    year = s.get("year")
    year_str = str(year) if year else "n.d."
    return f"{last} {year_str}"


def _summary_to_prompt_dict(s: PaperSummary) -> dict[str, Any]:
    """Project a :class:`PaperSummary` to the dict shape used in the prompt + task.

    We restrict to the fields the LLM should reason over (no token usage,
    no provenance, no source paths). This shape is what
    :attr:`DeckPlanTask.corpus_summaries` carries.
    """
    return {
        "doi": s.doi,
        "doi_slug": slugify_doi(s.doi) if s.doi else "",
        "title": s.title,
        "authors": list(s.authors or []),
        "year": s.year,
        "journal": s.journal,
        "year_bucket": s.year_bucket,
        "tier": s.tier,
        "og_score": float(s.og_score),
        "forward_influence": int(s.forward_influence),
        "tldr": s.tldr,
        "key_findings": list(s.key_findings or []),
    }


def _bucket_summaries_for_prompt(
    summaries: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    """Group prompt-shape summary dicts by ``year_bucket``."""
    buckets: dict[str, list[dict[str, Any]]] = {
        "history": [],
        "development": [],
        "sota": [],
        "unknown": [],
    }
    for s in summaries:
        bucket = s.get("year_bucket", "unknown") or "unknown"
        buckets.setdefault(bucket, []).append(s)
    for k in buckets:
        buckets[k].sort(key=lambda d: d.get("year", 0) or 0)
    return buckets


def _render_summary_block(name: str, items: list[dict[str, Any]]) -> str:
    """Render one bucketed summary block (history / development / sota)."""
    if not items:
        return f"### {name} bucket: (no Tier-A papers in this bucket)\n"
    lines = [f"### {name} bucket ({len(items)} papers)"]
    for s in items[:25]:  # cap to keep prompt manageable
        slug = s.get("doi_slug") or (slugify_doi(s.get("doi", "")) if s.get("doi") else "?")
        label = _author_year_label_from_dict(s)
        tldr = (s.get("tldr") or "_(no TL;DR — Tier-C stub)_").strip()
        findings = "; ".join((s.get("key_findings") or [])[:3]) or "_(no findings)_"
        og = s.get("og_score", 0.0) or 0.0
        fi = s.get("forward_influence", 0) or 0
        lines.append(
            f"- [[{slug}|{label}]] ({s.get('year')}) "
            f"og={og:.2f} fi={fi} — {tldr} "
            f"Findings: {findings}"
        )
    return "\n".join(lines)


def _render_figure_assignments(
    figure_assignments: dict[str, Path],
    summaries_by_doi: dict[str, dict[str, Any]],
) -> str:
    """Render the available-figures block for the prompt."""
    if not figure_assignments:
        return "(no figures available — all slides must be ``text`` or ``section_divider``)\n"
    lines = ["Available figures (use these EXACT image_path values):"]
    for doi, path in figure_assignments.items():
        s = summaries_by_doi.get(doi.lower()) or summaries_by_doi.get(doi)
        slug = slugify_doi(doi) if doi else ""
        label = _author_year_label_from_dict(s) if s else doi
        lines.append(
            f"- doi=[[{slug}|{label}]] image_path={Path(path).as_posix()}"
        )
    return "\n".join(lines) + "\n"


def _render_co_citation_block(
    co_citation: list[tuple[str, str, int]],
    summaries_by_doi: dict[str, dict[str, Any]],
) -> str:
    if not co_citation:
        return "(none)"
    lines = []
    for a, b, n in co_citation[:5]:
        sa = summaries_by_doi.get(a.lower()) or summaries_by_doi.get(a)
        sb = summaries_by_doi.get(b.lower()) or summaries_by_doi.get(b)
        la = _author_year_label_from_dict(sa) if sa else a
        lb = _author_year_label_from_dict(sb) if sb else b
        lines.append(
            f"- [[{slugify_doi(a)}|{la}]] + [[{slugify_doi(b)}|{lb}]] "
            f"— co-cited by {n} papers"
        )
    return "\n".join(lines)


def _render_top_og_block(
    top_og: list[tuple[str, float]],
    summaries_by_doi: dict[str, dict[str, Any]],
) -> str:
    if not top_og:
        return "(none)"
    lines = []
    for doi, score in top_og[:8]:
        s = summaries_by_doi.get(doi.lower()) or summaries_by_doi.get(doi)
        label = _author_year_label_from_dict(s) if s else doi
        lines.append(f"- [[{slugify_doi(doi)}|{label}]] — og_score={score:.2f}")
    return "\n".join(lines)


def _build_deck_plan_prompt(
    *,
    topic: str,
    audience: str,
    target_slide_count: int,
    speaker: str,
    affiliation: str,
    corpus_summaries: list[dict[str, Any]],
    corpus_metrics: dict[str, Any],
    figure_assignments: dict[str, Path],
) -> str:
    """Build the user-message prompt for the deck-plan LLM call."""
    summaries_by_doi: dict[str, dict[str, Any]] = {}
    for s in corpus_summaries:
        doi = (s.get("doi") or "").strip().lower()
        if doi:
            summaries_by_doi[doi] = s

    buckets = _bucket_summaries_for_prompt(corpus_summaries)
    history_block = _render_summary_block("history", buckets.get("history", []))
    development_block = _render_summary_block(
        "development", buckets.get("development", [])
    )
    sota_block = _render_summary_block("sota", buckets.get("sota", []))

    fig_block = _render_figure_assignments(figure_assignments, summaries_by_doi)
    cocite_block = _render_co_citation_block(
        list(corpus_metrics.get("top_co_citation") or []),
        summaries_by_doi,
    )
    og_block = _render_top_og_block(
        list(corpus_metrics.get("top_og") or []),
        summaries_by_doi,
    )

    n_tier_a = corpus_metrics.get("n_tier_a", len(corpus_summaries))
    n_total = corpus_metrics.get("n_total_papers", n_tier_a)

    return f"""\
TOPIC: {topic}
AUDIENCE: {audience}
TARGET_SLIDE_COUNT: {target_slide_count}
SPEAKER: {speaker}
AFFILIATION: {affiliation}

CORPUS SHAPE:
- {n_total} total papers in the corpus
- {n_tier_a} Tier-A (full-text) papers — these are what you'll cite
- The corpus is bucketed by publication-year quartile (history /
  development / sota)

PER-PAPER SUMMARIES (Tier-A only, bucketed by year):

{history_block}

{development_block}

{sota_block}

TOP OG PAPERS (highest fraction of corpus citing them):
{og_block}

TOP CO-CITATION PAIRS (papers often cited together — useful for slide
claims like "X and Y together established Z"):
{cocite_block}

AVAILABLE FIGURES:
{fig_block}

OUTPUT FORMAT:
Return ONLY a JSON object matching this shape:

{{
  "story_arc_summary": "<1-2 sentence description of the arc you chose>",
  "slides": [
    {{"type": "title", "title": "...", "subtitle": "...", "author": "..."}},
    {{"type": "section_divider", "title": "..."}},
    {{
      "type": "figure",
      "title": "...",
      "image_path": "<EXACT path from figure_assignments>",
      "claim_paper_doi": "<doi the slide is about>",
      "figure_paper_doi": "<doi whose figure is used; same as claim if not substituted>",
      "caption": "<1-2 sentences>",
      "bullets": ["claim from paper [[<slug>|Author Year]] ...", ...],
      "speaker_notes": {{
        "mental_map": {{"hook": "...", "key_claim": "...", "evidence": "...",
                        "key_terms": [...], "click": "...", "transition": "..."}},
        "detailed_script": "<200-400 word monologue>"
      }}
    }},
    {{"type": "multi_figure", "title": "...", "figures": [
        {{"path": "...", "label": "A", "caption": "..."}}, ...]}},
    {{"type": "text", "title": "...", "bullets": [...],
      "speaker_notes": {{...}} }}
  ]
}}

Pick exactly {target_slide_count} slides. The renderer will auto-append
a references slide so don't include one. Now write the JSON.
"""


# ---------------------------------------------------------------------------
# Response schema
# ---------------------------------------------------------------------------


def deck_plan_response_schema() -> dict[str, Any]:
    """JSON schema for the deck-plan LLM response.

    The schema is intentionally permissive on per-slide content fields —
    :func:`render_plan_from_response` fills in defaults and validates
    required fields. We use ``oneOf`` over ``type`` discriminator so each
    slide kind has its own field expectations.
    """
    speaker_notes_schema = {
        "type": "object",
        "properties": {
            "mental_map": {
                "type": "object",
                "properties": {
                    "hook": {"type": "string"},
                    "key_claim": {"type": "string"},
                    "evidence": {"type": "string"},
                    "key_terms": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "click": {"type": "string"},
                    "transition": {"type": "string"},
                },
            },
            "detailed_script": {"type": "string"},
        },
    }

    return {
        "type": "object",
        "required": ["slides"],
        "properties": {
            "story_arc_summary": {"type": "string"},
            "slides": {
                "type": "array",
                "minItems": 1,
                "items": {
                    "oneOf": [
                        {
                            "type": "object",
                            "required": ["type", "title"],
                            "properties": {
                                "type": {"const": "title"},
                                "title": {"type": "string"},
                                "subtitle": {"type": "string"},
                                "author": {"type": "string"},
                                "speaker_notes": speaker_notes_schema,
                            },
                        },
                        {
                            "type": "object",
                            "required": ["type", "title"],
                            "properties": {
                                "type": {"const": "section_divider"},
                                "title": {"type": "string"},
                                "speaker_notes": speaker_notes_schema,
                            },
                        },
                        {
                            "type": "object",
                            "required": ["type", "title", "image_path"],
                            "properties": {
                                "type": {"const": "figure"},
                                "title": {"type": "string"},
                                "image_path": {"type": "string"},
                                "claim_paper_doi": {"type": "string"},
                                "figure_paper_doi": {"type": "string"},
                                "caption": {"type": "string"},
                                "bullets": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                },
                                "citation_source": {"type": "string"},
                                "speaker_notes": speaker_notes_schema,
                            },
                        },
                        {
                            "type": "object",
                            "required": ["type", "title", "figures"],
                            "properties": {
                                "type": {"const": "multi_figure"},
                                "title": {"type": "string"},
                                "figures": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "required": ["path"],
                                        "properties": {
                                            "path": {"type": "string"},
                                            "label": {"type": "string"},
                                            "caption": {"type": "string"},
                                            "claim_paper_doi": {"type": "string"},
                                            "figure_paper_doi": {"type": "string"},
                                        },
                                    },
                                },
                                "speaker_notes": speaker_notes_schema,
                            },
                        },
                        {
                            "type": "object",
                            "required": ["type", "title"],
                            "properties": {
                                "type": {"const": "text"},
                                "title": {"type": "string"},
                                "bullets": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                },
                                "citations": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                },
                                "speaker_notes": speaker_notes_schema,
                            },
                        },
                    ],
                },
            },
        },
    }


# ---------------------------------------------------------------------------
# Task preparation
# ---------------------------------------------------------------------------


def prepare_deck_plan_task(
    *,
    topic: str,
    corpus: Corpus,
    summaries: dict[str, PaperSummary],
    figure_assignments: dict[str, Path] | None = None,
    speaker: str = "",
    affiliation: str = "",
    audience: str = "journal-club",
    target_slide_count: int = 7,
    kb_root: Path,
) -> DeckPlanTask:
    """Prepare a :class:`DeckPlanTask`. Does NOT call any LLM.

    The slash-command body or other caller invokes the LLM and feeds the
    response back through :func:`render_plan_from_response`.

    Args:
        topic: User-supplied topic (raw, not slugified).
        corpus: Built :class:`vaultlab.research.corpus.Corpus` with
            ``compute_metrics`` already run.
        summaries: ``doi -> PaperSummary``. Restricted to Tier-A papers
            internally — Tier-C stubs (no TL;DR / key_findings) are
            dropped from the prompt.
        figure_assignments: Optional ``doi -> figure path`` map. When
            ``None``, the prompt still works but the LLM will be
            instructed to use ``text`` / ``section_divider`` slides only.
        speaker: Speaker name (title slide).
        affiliation: Affiliation string (title slide).
        audience: Audience tag — ``"journal-club"`` / ``"lab-meeting"`` /
            ``"conference"``.
        target_slide_count: Number of slides the LLM should produce.
        kb_root: Vaultlab KB root (currently unused inside the task but
            kept in the signature for parity with
            :func:`vaultlab.research.lineage.prepare_arc_task`; future
            iterations may inject KB-specific context).

    Returns:
        A :class:`DeckPlanTask` ready for the Claude Code session.
    """
    del kb_root  # reserved for future KB-context injection

    # Restrict to Tier-A papers — Tier-C stubs without TL;DR/findings
    # would leak generic phrasing into slide bullets.
    tier_a_summaries: list[PaperSummary] = [
        s for s in summaries.values()
        if (s.tier or "").upper() == "A" or s.tldr or s.key_findings
    ]
    corpus_summaries = [_summary_to_prompt_dict(s) for s in tier_a_summaries]

    metrics = corpus.metrics
    top_og: list[tuple[str, float]] = (
        sorted(metrics.og_score.items(), key=lambda kv: kv[1], reverse=True)[:10]
        if metrics is not None
        else []
    )
    top_co: list[tuple[str, str, int]] = (
        list(metrics.co_citation_pairs[:10]) if metrics is not None else []
    )
    year_buckets_count: dict[str, int] = {}
    if metrics is not None:
        for bucket in metrics.year_buckets.values():
            year_buckets_count[bucket] = year_buckets_count.get(bucket, 0) + 1

    corpus_metrics = {
        "top_og": top_og,
        "top_co_citation": top_co,
        "year_buckets": year_buckets_count,
        "n_total_papers": len(corpus.papers),
        "n_tier_a": len(tier_a_summaries),
    }

    figure_assignments = dict(figure_assignments or {})

    prompt = _build_deck_plan_prompt(
        topic=topic,
        audience=audience,
        target_slide_count=target_slide_count,
        speaker=speaker,
        affiliation=affiliation,
        corpus_summaries=corpus_summaries,
        corpus_metrics=corpus_metrics,
        figure_assignments=figure_assignments,
    )

    return DeckPlanTask(
        topic=topic,
        corpus_summaries=corpus_summaries,
        corpus_metrics=corpus_metrics,
        figure_assignments=figure_assignments,
        speaker=speaker,
        affiliation=affiliation,
        target_slide_count=target_slide_count,
        audience=audience,
        prompt=prompt,
        system_prompt=_DECK_PLAN_SYSTEM_PROMPT,
        response_schema=deck_plan_response_schema(),
    )


# ---------------------------------------------------------------------------
# Render LLM response -> dict-plan
# ---------------------------------------------------------------------------


def _coerce_speaker_notes(notes: Any) -> dict[str, Any] | None:
    """Coerce notes into the dict shape :func:`build_from_plan` expects.

    The renderer accepts a dict (``{"hook": ..., "key_claim": ...}``) OR
    a dict with explicit ``mental_map`` + ``detailed_script`` keys. We
    flatten the latter into the former when needed because
    :func:`vaultlab.slides.notes.attach_to_slide` reads either form.
    """
    if not notes:
        return None
    if not isinstance(notes, dict):
        return None
    # If notes has 'mental_map' or 'detailed_script', return as-is —
    # attach_to_slide handles dual-format dicts already (via dual_format).
    if "mental_map" in notes or "detailed_script" in notes:
        out: dict[str, Any] = {}
        mm = notes.get("mental_map") or {}
        if isinstance(mm, dict):
            out.update(mm)
        if notes.get("detailed_script"):
            out["detailed_script"] = notes["detailed_script"]
        return out
    return notes


def _author_year_for_doi(
    doi: str,
    summaries_by_doi: dict[str, dict[str, Any]],
) -> str:
    s = summaries_by_doi.get((doi or "").lower()) or summaries_by_doi.get(doi or "")
    if not s:
        return doi or ""
    return _author_year_label_from_dict(s)


def _build_references_from_cited_dois(
    cited_dois: list[str],
    summaries_by_doi: dict[str, dict[str, Any]],
) -> list[str]:
    """Build a list of Vancouver-style reference strings.

    The reference slide (added deterministically by
    :func:`render_plan_from_response`) consumes plain strings — see
    :func:`vaultlab.slides.layouts.add_references_slide`'s contract.
    """
    refs: list[str] = []
    seen: set[str] = set()
    for doi in cited_dois:
        if not doi:
            continue
        key = doi.lower()
        if key in seen:
            continue
        seen.add(key)
        s = summaries_by_doi.get(key) or summaries_by_doi.get(doi)
        if not s:
            refs.append(f"DOI: {doi}")
            continue
        authors = s.get("authors") or []
        if authors:
            if len(authors) > 3:
                authors_part = ", ".join(authors[:3]) + ", et al."
            else:
                authors_part = ", ".join(authors)
        else:
            authors_part = "Anon."
        title = s.get("title") or "(no title)"
        year = s.get("year") or ""
        journal = s.get("journal") or ""
        ref = f"{authors_part} {title}. {journal} {year}."
        refs.append(ref.strip())
    return refs


def _normalize_title_slide(slide: dict[str, Any], task: DeckPlanTask) -> dict[str, Any]:
    return {
        "type": "title",
        "title": slide.get("title") or task.topic,
        "subtitle": slide.get("subtitle", ""),
        "author": slide.get("author") or task.speaker,
        "speaker_notes": _coerce_speaker_notes(slide.get("speaker_notes")),
    }


def _normalize_section_divider_slide(slide: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "section_divider",
        "title": slide.get("title", ""),
        "speaker_notes": _coerce_speaker_notes(slide.get("speaker_notes")),
    }


def _normalize_figure_slide(
    slide: dict[str, Any],
    *,
    figure_assignments: dict[str, Path],
    summaries_by_doi: dict[str, dict[str, Any]],
    cited_dois: list[str],
) -> dict[str, Any] | None:
    image_path = slide.get("image_path", "")
    if not image_path:
        # Drop figure slides without a usable path.
        return None
    # Validate image_path is one we offered (or at least exists on disk).
    image_path = str(image_path)
    valid_paths = {Path(p).as_posix() for p in figure_assignments.values()}
    if image_path and Path(image_path).as_posix() not in valid_paths:
        # Permissive: keep the slide IF the file exists on disk; otherwise drop.
        if not Path(image_path).exists():
            logger.warning(
                "deck plan: dropping figure slide '%s' — image_path %r not in "
                "figure_assignments and not on disk",
                slide.get("title", "(untitled)"),
                image_path,
            )
            return None

    claim_doi = (slide.get("claim_paper_doi") or "").strip()
    figure_doi = (slide.get("figure_paper_doi") or claim_doi or "").strip()
    if claim_doi:
        cited_dois.append(claim_doi)
    if figure_doi and figure_doi != claim_doi:
        cited_dois.append(figure_doi)

    caption = slide.get("caption", "")
    if not caption and figure_doi:
        # Provide a sensible default caption.
        label = _author_year_for_doi(figure_doi, summaries_by_doi)
        caption = f"Figure from {label}"

    # Closes L4 audit bug #2: when the LLM picks a figure from a paper
    # other than the slide's claim source, the audience needs a visible
    # attribution flag that the figure is substituted. Mirror the
    # ``_compose_substitution_caption`` convention from
    # :mod:`vaultlab.slides.deck` so adversarial / plan-callback decks
    # carry the same prefix as the mechanical decks. We don't reuse the
    # helper directly because deck_plan.py works with summary dicts and
    # builds simpler "Author Year" labels rather than the one-line
    # "Author Year — Title" labels deck.py prefers.
    if claim_doi and figure_doi and claim_doi != figure_doi:
        fig_label = _author_year_for_doi(figure_doi, summaries_by_doi)
        fig_slug = slugify_doi(figure_doi)
        prefix = f"Substituted figure from [[{fig_slug}|{fig_label}]]"
        if caption:
            caption = f"{prefix}: {caption}"
        else:
            caption = prefix

    citation_source = slide.get("citation_source") or _author_year_for_doi(
        claim_doi or figure_doi, summaries_by_doi
    )

    bullets = list(slide.get("bullets") or [])

    return {
        "type": "figure",
        "title": slide.get("title", ""),
        "image_path": image_path,
        "caption": caption,
        "bullets": bullets,
        "citation_source": citation_source,
        "speaker_notes": _coerce_speaker_notes(slide.get("speaker_notes")),
        # Preserve the claim/figure DOI tracking for downstream consumers
        # that want to tell substituted figures from non-substituted.
        "claim_paper_doi": claim_doi,
        "figure_paper_doi": figure_doi,
    }


def _normalize_multi_figure_slide(
    slide: dict[str, Any],
    *,
    figure_assignments: dict[str, Path],
    cited_dois: list[str],
) -> dict[str, Any] | None:
    raw_figs = slide.get("figures") or []
    valid_paths = {Path(p).as_posix() for p in figure_assignments.values()}
    figs: list[dict[str, Any]] = []
    for f in raw_figs:
        if not isinstance(f, dict):
            continue
        path = str(f.get("path", ""))
        if not path:
            continue
        if path and Path(path).as_posix() not in valid_paths:
            if not Path(path).exists():
                logger.warning(
                    "deck plan: dropping figure '%s' from multi_figure — "
                    "path not in figure_assignments and not on disk",
                    path,
                )
                continue
        figs.append({
            "path": path,
            "label": f.get("label", ""),
            "caption": f.get("caption", ""),
            "citation_source": f.get("citation_source", ""),
        })
        for k in ("claim_paper_doi", "figure_paper_doi"):
            v = (f.get(k) or "").strip()
            if v:
                cited_dois.append(v)
    if not figs:
        return None
    return {
        "type": "multi_figure",
        "title": slide.get("title", ""),
        "figures": figs,
        "speaker_notes": _coerce_speaker_notes(slide.get("speaker_notes")),
    }


def _normalize_text_slide(
    slide: dict[str, Any],
    *,
    cited_dois: list[str],
) -> dict[str, Any]:
    bullets = [str(b) for b in (slide.get("bullets") or [])]
    citations = [str(d) for d in (slide.get("citations") or []) if d]
    cited_dois.extend(citations)
    return {
        "type": "text",
        "title": slide.get("title", ""),
        "bullets": bullets,
        "speaker_notes": _coerce_speaker_notes(slide.get("speaker_notes")),
    }


def render_plan_from_response(
    task: DeckPlanTask,
    response_json: dict[str, Any],
) -> dict[str, Any]:
    """Take Claude Code's JSON response and produce the typed dict plan
    that :func:`vaultlab.slides.build_from_plan` consumes.

    Validates slide types, fills missing fields with sensible defaults,
    drops invalid slides, and appends a deterministic ``references``
    slide built from the DOIs cited across the LLM's slides.

    Args:
        task: The :class:`DeckPlanTask` produced by
            :func:`prepare_deck_plan_task`.
        response_json: Parsed JSON dict matching ``task.response_schema``.

    Returns:
        A dict-plan with ``title`` / ``author`` / ``slides`` keys ready
        for :func:`build_from_plan`.
    """
    summaries_by_doi: dict[str, dict[str, Any]] = {}
    for s in task.corpus_summaries:
        doi = (s.get("doi") or "").strip().lower()
        if doi:
            summaries_by_doi[doi] = s

    raw_slides = list((response_json or {}).get("slides") or [])
    cited_dois: list[str] = []
    out_slides: list[dict[str, Any]] = []

    for raw in raw_slides:
        if not isinstance(raw, dict):
            continue
        stype = raw.get("type")
        if stype not in SUPPORTED_LLM_SLIDE_TYPES:
            logger.warning(
                "deck plan: dropping slide with unsupported type %r", stype
            )
            continue
        if stype == "title":
            out_slides.append(_normalize_title_slide(raw, task))
        elif stype == "section_divider":
            out_slides.append(_normalize_section_divider_slide(raw))
        elif stype == "figure":
            normalized = _normalize_figure_slide(
                raw,
                figure_assignments=task.figure_assignments,
                summaries_by_doi=summaries_by_doi,
                cited_dois=cited_dois,
            )
            if normalized is not None:
                out_slides.append(normalized)
        elif stype == "multi_figure":
            normalized = _normalize_multi_figure_slide(
                raw,
                figure_assignments=task.figure_assignments,
                cited_dois=cited_dois,
            )
            if normalized is not None:
                out_slides.append(normalized)
        elif stype == "text":
            out_slides.append(_normalize_text_slide(raw, cited_dois=cited_dois))

    # Ensure a title slide exists at position 0 — keep the deck legal.
    has_title = bool(out_slides) and out_slides[0].get("type") == "title"
    if not has_title:
        out_slides.insert(
            0,
            _normalize_title_slide(
                {
                    "title": task.topic,
                    "subtitle": f"{task.audience.replace('-', ' ').title()} deck",
                    "author": task.speaker,
                },
                task,
            ),
        )

    # Auto-append the references slide.
    refs = _build_references_from_cited_dois(cited_dois, summaries_by_doi)
    if refs:
        out_slides.append(
            {
                "type": "references",
                "title": "References",
                "references": refs,
            }
        )

    return {
        "title": task.topic,
        "author": task.speaker,
        "subtitle": f"{task.audience.replace('-', ' ').title()} deck",
        "topic": task.topic,
        "story_arc_summary": (response_json or {}).get("story_arc_summary", ""),
        "slides": out_slides,
    }


# ---------------------------------------------------------------------------
# Top-level orchestrator
# ---------------------------------------------------------------------------


def generate_deck_plan(
    topic: str,
    corpus: Corpus,
    summaries: dict[str, PaperSummary],
    *,
    figure_assignments: dict[str, Path] | None = None,
    speaker: str = "",
    affiliation: str = "",
    audience: str = "journal-club",
    target_slide_count: int = 7,
    kb_root: Path,
    plan_callback: PlanGeneratorCallback | None = None,
    fallback_to_mechanical: bool = True,
) -> dict[str, Any]:
    """Run the content-aware deck-plan generator.

    With ``plan_callback`` set: prepare task -> callback -> render plan.
    With ``None``: fall back to the mechanical synthesis from
    :func:`vaultlab.slides.deck.build_deck_from_lineage_result` — but
    return the resulting :class:`DeckPlan` projected into the dict-plan
    shape so downstream renderers can use either path uniformly.

    Args:
        topic: User-supplied topic.
        corpus: The corpus dataclass.
        summaries: ``doi -> PaperSummary`` map.
        figure_assignments: Optional ``doi -> figure path`` map.
        speaker: Speaker name.
        affiliation: Affiliation string.
        audience: Audience tag.
        target_slide_count: Number of slides for the LLM path.
        kb_root: KB root.
        plan_callback: Optional callable that receives a
            :class:`DeckPlanTask` and returns the JSON response. When
            None, the mechanical fallback is used (subject to
            ``fallback_to_mechanical``).
        fallback_to_mechanical: If True (default) and ``plan_callback``
            is None, fall back to the mechanical synthesis. If False,
            raise ValueError.

    Returns:
        A dict-plan ready for :func:`build_from_plan`.
    """
    if plan_callback is not None:
        task = prepare_deck_plan_task(
            topic=topic,
            corpus=corpus,
            summaries=summaries,
            figure_assignments=figure_assignments,
            speaker=speaker,
            affiliation=affiliation,
            audience=audience,
            target_slide_count=target_slide_count,
            kb_root=kb_root,
        )
        response = plan_callback(task) or {}
        return render_plan_from_response(task, response)

    if not fallback_to_mechanical:
        raise ValueError(
            "generate_deck_plan called without plan_callback and "
            "fallback_to_mechanical=False"
        )

    return _mechanical_fallback_plan(
        topic=topic,
        summaries=summaries,
        figure_assignments=figure_assignments or {},
        speaker=speaker,
        affiliation=affiliation,
    )


# ---------------------------------------------------------------------------
# Mechanical fallback (no LLM)
# ---------------------------------------------------------------------------


def _mechanical_fallback_plan(
    *,
    topic: str,
    summaries: dict[str, PaperSummary],
    figure_assignments: dict[str, Path],
    speaker: str,
    affiliation: str,
) -> dict[str, Any]:
    """Build a dict-plan via the legacy bucket-leader synthesis.

    Mirrors the structure of
    :func:`vaultlab.slides.deck._plan_from_lineage` but emits the
    dict-plan shape rather than the typed :class:`DeckPlan`. Used as the
    fallback path when no plan_callback is supplied.
    """
    summaries_by_doi: dict[str, dict[str, Any]] = {}
    for s in summaries.values():
        d = _summary_to_prompt_dict(s)
        if d.get("doi"):
            summaries_by_doi[d["doi"].lower()] = d

    buckets = _bucket_summaries_for_prompt(list(summaries_by_doi.values()))
    cited_dois: list[str] = []
    slides: list[dict[str, Any]] = [
        {
            "type": "title",
            "title": f"Lineage: {topic}",
            "subtitle": "Journal-club deck",
            "author": speaker,
            "speaker_notes": {
                "hook": f"Today we trace the lineage of {topic}.",
                "key_claim": (
                    f"This corpus has {len(summaries)} papers; "
                    "we'll walk through history, development, and the SOTA."
                ),
            },
        },
        {"type": "section_divider", "title": "Background"},
    ]

    history = buckets.get("history", [])[:3]
    if history:
        bullets = []
        for s in history:
            slug = s.get("doi_slug") or ""
            label = _author_year_label_from_dict(s)
            tldr = (s.get("tldr") or "").strip().split("\n")[0][:200]
            bullets.append(
                f"[[{slug}|{label}]]: {tldr}" if tldr else f"[[{slug}|{label}]]"
            )
            if s.get("doi"):
                cited_dois.append(s["doi"])
        slides.append({
            "type": "text",
            "title": "Foundational findings",
            "bullets": bullets,
        })

    slides.append({"type": "section_divider", "title": "Development"})

    development = buckets.get("development", [])[:3]
    if development:
        bullets = []
        for s in development:
            slug = s.get("doi_slug") or ""
            label = _author_year_label_from_dict(s)
            tldr = (s.get("tldr") or "").strip().split("\n")[0][:200]
            bullets.append(
                f"[[{slug}|{label}]]: {tldr}" if tldr else f"[[{slug}|{label}]]"
            )
            if s.get("doi"):
                cited_dois.append(s["doi"])
        slides.append({
            "type": "text",
            "title": "How the field evolved",
            "bullets": bullets,
        })

    sota = buckets.get("sota", [])[:5]
    if sota:
        bullets = []
        for s in sota:
            slug = s.get("doi_slug") or ""
            label = _author_year_label_from_dict(s)
            findings = s.get("key_findings") or []
            first = (findings[0] if findings else (s.get("tldr") or ""))
            bullets.append(
                f"[[{slug}|{label}]]: {str(first)[:200]}"
            )
            if s.get("doi"):
                cited_dois.append(s["doi"])
        slides.append({
            "type": "text",
            "title": "State of the art",
            "bullets": bullets,
        })

    refs = _build_references_from_cited_dois(cited_dois, summaries_by_doi)
    if refs:
        slides.append({
            "type": "references",
            "title": "References",
            "references": refs,
        })

    del figure_assignments  # Mechanical fallback skips figures (text-only).
    del affiliation  # Carried in DeckPlan but unused by build_from_plan.

    return {
        "title": f"Lineage: {topic}",
        "subtitle": "Journal-club deck",
        "author": speaker,
        "topic": topic,
        "story_arc_summary": (
            "Mechanical bucket-leader synthesis "
            "(no plan_callback supplied)."
        ),
        "slides": slides,
    }
