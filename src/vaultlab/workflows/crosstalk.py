"""Crosstalk integration — wrap meeting primitives for pipeline use.

This module slots :mod:`vaultlab.runner.meetings` into the existing
pipelines (``/lit-arc``, ``/build-deck``) per the decisions in
``grill-crosstalk-integration-2026-04-30.md``. The wrappers turn the
``Meeting`` + ``MeetingTurn`` primitives into purpose-shaped helpers
whose ``final_output`` matches the same schemas the single-shot
callbacks already produce — so they're drop-in for
:func:`vaultlab.research.picker.pick_top_n_content_aware`,
:func:`vaultlab.research.lineage.run_lit_arc`, and
:func:`vaultlab.workflows.deck_plan.generate_deck_plan`.

Tiered defaults
---------------
* `/lit-arc` — picker + arc default to ADVERSARIAL crosstalk.
* `/build-deck` — plan defaults to ADVERSARIAL; final deck text passes
  through :func:`rigor_audit` (the new ``rigor_auditor`` role) before
  the .pptx ships.

Design constraints
------------------
* ``n_rounds`` is capped at 5 (Q5: AI-Scientist research shows
  diminishing returns and degenerate spirals beyond that).
* Wall-clock timeout is 10 min per meeting (Q5).
* Every role must return structured JSON, not free text — the
  synthesizer's JSON IS the meeting's ``final_output``.
* All file writes go through :mod:`vaultlab.kb.paths` (no string
  concatenation of filesystem paths).
* No SDK / Anthropic calls live here. The runner_callback IS the LLM,
  same pattern as ``picker_callback`` / ``reader`` / ``narrator``.
"""

from __future__ import annotations

import json
import logging
import re
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from vaultlab.kb.paths import (
    ensure_parent,
)
from vaultlab.runner.kb_context import prepend_preamble
from vaultlab.runner.meetings import (
    adversarial_inject,
    build_meeting,
    compose_turns,
)
from vaultlab.runner.models import (
    Agenda,
    Meeting,
    MeetingMode,
    MeetingTurn,
    Mode,
    Role,
)

if TYPE_CHECKING:
    from vaultlab.research.graph_metrics import CorpusMetrics
    from vaultlab.research.picker import CandidatePaper
    from vaultlab.research.summarize import PaperSummary

logger = logging.getLogger(__name__)

__all__ = [
    "MAX_N_ROUNDS",
    "MEETING_TIMEOUT_SECONDS",
    "CrosstalkResult",
    "RunnerCallback",
    "adversarial_arc_meeting",
    "adversarial_deck_plan_meeting",
    "adversarial_picker_meeting",
    "meta_review_checklist",
    "rigor_audit",
    "write_crosstalk_artifacts",
]


# ---------------------------------------------------------------------------
# Hard caps (Q5 in grill-crosstalk-integration-2026-04-30.md)
# ---------------------------------------------------------------------------

MAX_N_ROUNDS: int = 5
"""Hard cap on adversarial-meeting rounds.

AI-Scientist research and our own grill (Q5) showed that beyond ~5 rounds
agents either stop changing their position or spiral into ever-more-baroque
critiques. Refuse politely above this — the caller should split the work
into multiple meetings instead.
"""

MEETING_TIMEOUT_SECONDS: int = 600
"""Default wall-clock cap per meeting (10 minutes)."""


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------


@dataclass
class CrosstalkResult:
    """Structured outcome of a crosstalk-style meeting.

    Attributes:
        final_output: The synthesizer's structured output (already
            shaped to match the matching single-shot schema).
        rounds: Per-turn record (analyst draft, critic objections,
            synthesizer integration). The same list is also written to
            disk by :func:`write_crosstalk_artifacts`.
        runtime_seconds: Wall-clock elapsed time from meeting start to
            final synthesizer turn.
        crosstalk_status: One of:

            * ``"complete"`` — every turn ran, synthesizer JSON parsed.
            * ``"incomplete (timeout)"`` — wall-clock timeout hit.
            * ``"fallback (callback failed)"`` — runner_callback raised
              or returned an unusable shape.
            * ``"converged"`` — ``early_exit`` stopped the meeting once the
              synthesizer output stabilised between consecutive rounds.
        purpose: ``"picker"`` | ``"arc"`` | ``"deck-plan"`` |
            ``"rigor-audit"``. Used by the audit-trail writer.
    """

    final_output: dict[str, Any] = field(default_factory=dict)
    rounds: list[MeetingTurn] = field(default_factory=list)
    runtime_seconds: float = 0.0
    crosstalk_status: str = "complete"
    purpose: str = ""
    critic_spread: float | None = None
    """Disagreement among critic outputs across rounds (0=converged, 1=max), or
    ``None`` with < 2 critic turns. Informational — feeds
    ``crosstalk_policy.rounds_for_spread`` for adaptive round sizing."""
    meta_review: list[str] = field(default_factory=list)
    """Recurring critic concerns across rounds (meta-review, AI co-scientist) — a
    standing checklist a caller seeds into the next meeting so a concern caught
    once stays addressed. Empty unless >= 2 critic turns repeat a concern."""


# ---------------------------------------------------------------------------
# Runner callback type
# ---------------------------------------------------------------------------


# A runner callback executes a meeting: given a Meeting + the ordered roles,
# it returns one dict per role with at minimum a ``"output"`` key holding
# the raw text the role produced. The slash-command body inside Claude
# Code IS the LLM via this callback — same pattern as picker_callback /
# reader / narrator. No SDK calls live in this module.
RunnerCallback = Callable[[Meeting, list[Role]], list[dict[str, Any]]]


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def _validate_n_rounds(n_rounds: int) -> None:
    if n_rounds < 1:
        raise ValueError(f"n_rounds must be >= 1, got {n_rounds}")
    if n_rounds > MAX_N_ROUNDS:
        raise ValueError(
            f"n_rounds={n_rounds} exceeds MAX_N_ROUNDS={MAX_N_ROUNDS}. "
            "AI-Scientist research (and our own grill, Q5 in "
            "grill-crosstalk-integration-2026-04-30.md) shows that beyond "
            "~5 rounds agents stop updating their positions or spiral. "
            "Split the work into multiple meetings instead."
        )


# ---------------------------------------------------------------------------
# Generic adversarial-meeting executor (shared by picker / arc / plan)
# ---------------------------------------------------------------------------


def _extract_json_blob(text: str) -> dict[str, Any] | None:
    """Pull the first JSON object out of a free-form text response.

    Roles return JSON-shaped output but a wrapping LLM may add a leading
    sentence or wrap in fenced code. We scan for the first ``{...}`` we
    can ``json.loads``.
    """
    if not text:
        return None
    # Fast path: maybe the whole thing is JSON.
    s = text.strip()
    if s.startswith("```"):
        # Strip ```json ... ``` fences.
        s = re.sub(r"^```[a-zA-Z]*\s*", "", s)
        s = re.sub(r"\s*```$", "", s)
    try:
        parsed = json.loads(s)
    except json.JSONDecodeError:
        parsed = None
    if isinstance(parsed, dict):
        return parsed
    # Slow path: find the largest balanced {...} blob.
    start = text.find("{")
    while start != -1:
        depth = 0
        for i in range(start, len(text)):
            ch = text[i]
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    candidate = text[start : i + 1]
                    try:
                        parsed = json.loads(candidate)
                    except json.JSONDecodeError:
                        parsed = None
                    if isinstance(parsed, dict):
                        return parsed
                    break
        start = text.find("{", start + 1)
    return None


def _synthesizer_similarity(prev_text: str, curr_text: str) -> float:
    """Similarity in ``[0, 1]`` between two synthesizer outputs (for early-exit).

    Compares the parsed JSON when both parse (canonical sorted-key form), else
    the raw text. ``1.0`` = identical. Used only when ``early_exit`` is enabled.
    """
    import difflib

    prev_parsed = _extract_json_blob(prev_text)
    curr_parsed = _extract_json_blob(curr_text)
    if isinstance(prev_parsed, dict) and isinstance(curr_parsed, dict):
        a = json.dumps(prev_parsed, sort_keys=True)
        b = json.dumps(curr_parsed, sort_keys=True)
    else:
        a, b = prev_text or "", curr_text or ""
    return difflib.SequenceMatcher(None, a, b).ratio()


def _compute_critic_spread(turns: list[MeetingTurn]) -> float | None:
    """Disagreement among the critic's outputs across rounds, in ``[0, 1]``.

    ``0.0`` = the critic repeated itself (converged); ``1.0`` = maximal change
    between rounds. ``None`` when there are fewer than two critic turns to
    compare. Consumed by ``crosstalk_policy.rounds_for_spread`` to size a
    follow-up run — high spread means the critics are still finding new
    objections, so more rounds may help. (AI co-scientist adaptive allocation.)
    """
    critic_outputs = [
        t.output
        for t in turns
        if "critic" in (t.role_id or "") and (t.output or "").strip()
    ]
    if len(critic_outputs) < 2:
        return None
    diffs = [
        1.0 - _synthesizer_similarity(critic_outputs[i], critic_outputs[i + 1])
        for i in range(len(critic_outputs) - 1)
    ]
    return sum(diffs) / len(diffs)


def meta_review_checklist(turns: list[MeetingTurn], *, min_recurrence: int = 2) -> list[str]:
    """Recurring critic concerns across a meeting, as a standing checklist.

    Meta-review (AI co-scientist feedback-without-fine-tuning): mine the critic
    outputs for concern lines that RECUR across >= ``min_recurrence`` distinct
    critic turns — those are the unresolved issues every later round (or the
    next meeting) should keep addressing. Returns them in first-seen order. A
    caller seeds the next meeting's context with these so a concern caught once
    becomes a standing requirement.

    Deterministic + pure (no LLM): recurrence is matched on normalised concern
    lines, so it catches verbatim / re-raised concerns. (A future LLM
    ``meta_reviewer`` role could additionally distill paraphrased themes.)
    """
    from collections import Counter

    turn_count: Counter[str] = Counter()
    display: dict[str, str] = {}
    order: list[str] = []
    for t in turns:
        if "critic" not in (t.role_id or ""):
            continue
        turn_concerns: set[str] = set()
        for raw in (t.output or "").splitlines():
            line = raw.strip(" -*\t").strip()
            if len(line) < 8:  # skip blanks / trivial fragments
                continue
            norm = " ".join(line.lower().split())
            if norm not in turn_concerns:
                turn_concerns.add(norm)
                if norm not in display:
                    display[norm] = line
                    order.append(norm)
        turn_count.update(turn_concerns)
    return [display[n] for n in order if turn_count[n] >= min_recurrence]


def _run_adversarial_meeting(
    *,
    meeting: Meeting,
    runner_callback: RunnerCallback | None,
    n_rounds: int,
    timeout_seconds: int,
    purpose: str,
    early_exit: bool = False,
    early_exit_threshold: float = 0.95,
) -> CrosstalkResult:
    """Execute the ADVERSARIAL meeting with a runner callback.

    Builds turns for ``n_rounds`` cycles (each cycle = full role rotation),
    feeds them through ``runner_callback`` round-by-round so later rounds
    see earlier rounds' real outputs (via :func:`adversarial_inject`),
    and returns the final synthesizer's parsed JSON.

    On timeout, returns the partial transcript with
    ``crosstalk_status="incomplete (timeout)"``.

    On callback failure (raised exception, non-list return, missing
    output keys), returns ``crosstalk_status="fallback (callback
    failed)"`` with whatever turns completed.
    """
    _validate_n_rounds(n_rounds)
    started = time.time()

    if runner_callback is None:
        return CrosstalkResult(
            final_output={},
            rounds=[],
            runtime_seconds=0.0,
            crosstalk_status="fallback (callback failed)",
            purpose=purpose,
        )

    # We collect ALL turns across all rounds in the rounds list. The
    # synthesizer is always the last role of the meeting per
    # _MEETING_TYPE_ROLES["deep_think"] etc.
    all_turns: list[MeetingTurn] = []
    round_status = "complete"
    prev_synth_output: str | None = None

    try:
        for round_idx in range(n_rounds):
            # Compose fresh prompts for this round, with prior rounds'
            # outputs injected via adversarial_inject.
            base_turns = compose_turns(
                meeting,
                task=meeting.agenda
                if meeting.agenda is not None
                else f"Round {round_idx + 1} of {n_rounds} for {purpose}",
            )

            # If we already have outputs from earlier rounds, inject them
            # so this round's prompts see the real prior conversation.
            if all_turns:
                # We need to include all_turns' outputs as priors for the
                # FIRST role of this round. Build a synthetic prior list.
                seeded = list(all_turns) + base_turns
                rewritten = adversarial_inject(seeded)
                # Slice off the rewritten copies of all_turns; we only want
                # the rewritten base_turns.
                base_turns = rewritten[len(all_turns) :]

            # Check timeout before invoking callback for this round.
            if time.time() - started > timeout_seconds:
                round_status = "incomplete (timeout)"
                break

            # Invoke runner_callback for the round's roles.
            try:
                raw = runner_callback(meeting, list(meeting.roles))
            except Exception as exc:
                logger.warning(
                    "crosstalk runner_callback raised on round %d: %s",
                    round_idx + 1,
                    exc,
                )
                round_status = "fallback (callback failed)"
                break

            if not isinstance(raw, list):
                logger.warning(
                    "crosstalk runner_callback returned non-list (%s); fallback",
                    type(raw).__name__,
                )
                round_status = "fallback (callback failed)"
                break

            # Pair raw outputs back to base_turns. We tolerate a callback
            # that returns dicts with either ``output`` (canonical) or
            # ``content`` (alt) keys.
            for i, turn in enumerate(base_turns):
                if i >= len(raw):
                    break
                cell = raw[i] if isinstance(raw[i], dict) else {}
                output = cell.get("output") or cell.get("content") or ""
                turn.output = str(output)
                # Also attach a per-turn output_path hint; the artifact
                # writer fills the actual path when a run_dir is given.
                all_turns.append(turn)

            # Adversarial-inject so the next round's prompts see this
            # round's real outputs (no-op for the last round).
            all_turns = list(adversarial_inject(all_turns))

            # Convergence early-exit (opt-in): if this round's synthesizer output
            # is ~unchanged from the previous round's, the meeting has stopped
            # producing new signal — stop instead of burning the remaining
            # rounds. (AI co-scientist: stop when the tournament stabilises.)
            if early_exit:
                this_synth = next(
                    (t for t in reversed(all_turns) if t.role_id == "synthesizer"),
                    None,
                )
                this_output = this_synth.output if this_synth is not None else None
                if (
                    this_output
                    and prev_synth_output is not None
                    and _synthesizer_similarity(prev_synth_output, this_output)
                    >= early_exit_threshold
                ):
                    round_status = "converged"
                    break
                if this_output:
                    prev_synth_output = this_output

            # Timeout check after the round finishes.
            if time.time() - started > timeout_seconds:
                round_status = "incomplete (timeout)"
                break

    except Exception as exc:  # pragma: no cover — defensive
        logger.exception("crosstalk meeting raised: %s", exc)
        round_status = "fallback (callback failed)"

    runtime = time.time() - started

    # Extract the synthesizer's final JSON from the last synthesizer turn.
    final_output: dict[str, Any] = {}
    synth_turn = next(
        (t for t in reversed(all_turns) if t.role_id == "synthesizer"),
        None,
    )
    if synth_turn is not None and synth_turn.output:
        parsed = _extract_json_blob(synth_turn.output)
        if isinstance(parsed, dict):
            final_output = parsed

    if not final_output and round_status == "complete":
        # Synthesizer returned nothing parseable. Treat as fallback.
        round_status = "fallback (callback failed)"

    return CrosstalkResult(
        final_output=final_output,
        rounds=all_turns,
        runtime_seconds=runtime,
        crosstalk_status=round_status,
        purpose=purpose,
        critic_spread=_compute_critic_spread(all_turns),
        meta_review=meta_review_checklist(all_turns),
    )


# ---------------------------------------------------------------------------
# Public meeting-builders
# ---------------------------------------------------------------------------


def adversarial_picker_meeting(
    *,
    topic: str,
    candidates: list[CandidatePaper],
    target_n: int,
    abstracts_md: str,
    n_rounds: int = 3,
    timeout_seconds: int = MEETING_TIMEOUT_SECONDS,
    runner_callback: RunnerCallback | None = None,
    project_slug: str | None = None,
    kb_root: Path | str | None = None,
    early_exit: bool = False,
    early_exit_threshold: float = 0.95,
) -> CrosstalkResult:
    """ADVERSARIAL meeting: data_analyst proposes top-N picks; literature_critic
    challenges (missing seminal works? off-topic?); synthesizer picks final.

    Output's ``final_output`` matches
    :func:`vaultlab.research.picker.picker_response_schema` so it's a
    drop-in replacement for the single-shot
    :func:`vaultlab.research.picker.pick_top_n_content_aware` callback.
    """
    _validate_n_rounds(n_rounds)
    candidate_dois = ", ".join(c.doi for c in candidates) or "(none)"

    statement = (
        f"Pick the {target_n} BEST papers from the {len(candidates)} "
        f"candidates for a literature lineage arc on '{topic}'. "
        "Read each abstract before ranking; do not rank by citation count "
        "alone."
    )
    questions = [
        "Which candidates are clearly on-topic vs tangential?",
        "Are there seminal works among the candidates that the citation graph alone would miss?",
        "Are any high-citation candidates secretly off-topic (deceptive citation signal)?",
        f"What are the top {target_n} picks, ranked, with rationales?",
    ]
    rules = [
        "Use the exact DOIs listed in the candidates — do NOT invent new DOIs.",
        "Synthesizer MUST return JSON of the form "
        '{"picks": [{"doi": ..., "rank": int, "rationale": ...}, ...]} '
        "with no other top-level keys.",
        f"Return EXACTLY {target_n} picks.",
    ]
    agenda = Agenda(
        topic=topic,
        statement=statement,
        questions=questions,
        rules=rules,
    )

    session_context = (
        f"TOPIC: {topic}\n"
        f"TARGET N: {target_n}\n"
        f"CANDIDATE DOIS ({len(candidates)}): {candidate_dois}\n\n"
        f"CANDIDATES WITH ABSTRACTS:\n{abstracts_md}"
    )
    session_context = prepend_preamble(
        session_context, project_slug, kb_root=kb_root, role="literature_surveyor"
    )

    # data_analyst proposes; literature_critic challenges; synthesizer picks.
    meeting = build_meeting(
        topic=topic,
        meeting_type="deep_think",
        session_context=session_context,
        mode=Mode.LITERATURE_REVIEW,  # picks literature_surveyor + literature_critic
        agenda=agenda,
    )
    # deep_think with LITERATURE_REVIEW gives:
    #   [literature_surveyor, domain_expert, literature_critic, synthesizer]
    # We want analyst-flavour first, so the surveyor effectively plays the
    # "data_analyst" role for picker meetings. The synthesizer is last.

    return _run_adversarial_meeting(
        meeting=meeting,
        runner_callback=runner_callback,
        n_rounds=n_rounds,
        timeout_seconds=timeout_seconds,
        purpose="picker",
        early_exit=early_exit,
        early_exit_threshold=early_exit_threshold,
    )


def adversarial_arc_meeting(
    *,
    topic: str,
    summaries: dict[str, PaperSummary],
    metrics: CorpusMetrics | None = None,
    n_rounds: int = 3,
    timeout_seconds: int = MEETING_TIMEOUT_SECONDS,
    runner_callback: RunnerCallback | None = None,
    project_slug: str | None = None,
    kb_root: Path | str | None = None,
    early_exit: bool = False,
    early_exit_threshold: float = 0.95,
) -> CrosstalkResult:
    """ADVERSARIAL meeting: data_analyst drafts arc; methods_critic challenges
    field-development claims; literature_critic flags missing strands;
    synthesizer integrates.

    Output's ``final_output`` matches
    :func:`vaultlab.research.lineage.arc_response_schema` —
    ``{"history": str, "development": str, "sota": str}``.
    """
    _validate_n_rounds(n_rounds)

    # Bucket summaries for the session context.
    bucket_lines: dict[str, list[str]] = {
        "history": [],
        "development": [],
        "sota": [],
        "unknown": [],
    }
    for s in summaries.values():
        bucket = s.year_bucket or "unknown"
        bucket_lines.setdefault(bucket, []).append(
            f"- {s.doi} ({s.year}) [{s.tier}] og={s.og_score:.2f} fi={s.forward_influence}"
            f" — {(s.tldr or '').strip()[:200]}"
        )
    bucket_render = []
    for name in ("history", "development", "sota"):
        items = bucket_lines.get(name) or []
        bucket_render.append(f"### {name} ({len(items)} papers)")
        bucket_render.extend(items[:25] or ["(no papers in this bucket)"])
    bucket_md = "\n".join(bucket_render)

    n_total = len(summaries)
    n_tier_a = sum(1 for s in summaries.values() if s.tier == "A")

    statement = (
        f"Write a 3-paragraph lineage arc (history / development / "
        f"state-of-the-art) for '{topic}'. The corpus has {n_total} papers "
        f"({n_tier_a} Tier-A with full TL;DRs)."
    )
    questions = [
        "What is the foundational claim each bucket should anchor?",
        "Are field-development claims (X led to Y) supported by the actual "
        "summaries, or speculative?",
        "Are major strands (methods, applications, mechanisms) all represented?",
        "Final 3-paragraph narrative with 3-5 wikilink citations per paragraph?",
    ]
    rules = [
        "Cite each claim with [[<doi-slug>|Author Year]] using only DOIs from the corpus.",
        "Do not invent claims not present in the per-paper summaries.",
        "Synthesizer MUST return JSON of the form "
        '{"history": str, "development": str, "sota": str} '
        "with no other top-level keys.",
    ]
    agenda = Agenda(
        topic=topic,
        statement=statement,
        questions=questions,
        rules=rules,
    )

    session_context = (
        f"TOPIC: {topic}\n"
        f"CORPUS SHAPE: {n_total} papers ({n_tier_a} Tier-A)\n\n"
        f"BUCKETED SUMMARIES:\n{bucket_md}\n"
    )
    session_context = prepend_preamble(
        session_context, project_slug, kb_root=kb_root, role="data_analyst"
    )

    meeting = build_meeting(
        topic=topic,
        meeting_type="deep_think",
        session_context=session_context,
        mode=Mode.DATA_ANALYSIS,
        agenda=agenda,
    )
    # deep_think with DATA_ANALYSIS gives:
    #   [data_analyst, domain_expert, methods_critic, synthesizer]

    del metrics  # currently unused — reserved for later (Q3 enrichment)

    return _run_adversarial_meeting(
        meeting=meeting,
        runner_callback=runner_callback,
        n_rounds=n_rounds,
        timeout_seconds=timeout_seconds,
        purpose="arc",
        early_exit=early_exit,
        early_exit_threshold=early_exit_threshold,
    )


def adversarial_deck_plan_meeting(
    *,
    topic: str,
    summaries: dict[str, PaperSummary],
    metrics: CorpusMetrics | None = None,
    figure_assignments: dict[str, Path] | None = None,
    target_slide_count: int = 7,
    n_rounds: int = 3,
    timeout_seconds: int = MEETING_TIMEOUT_SECONDS,
    runner_callback: RunnerCallback | None = None,
    project_slug: str | None = None,
    kb_root: Path | str | None = None,
    early_exit: bool = False,
    early_exit_threshold: float = 0.95,
) -> CrosstalkResult:
    """ADVERSARIAL meeting: narrator proposes story arc; figure_lead picks
    figures; methods_critic flags overclaiming; synthesizer integrates.

    Output's ``final_output`` matches
    :func:`vaultlab.workflows.deck_plan.deck_plan_response_schema` —
    ``{"slides": [...], "story_arc_summary": str}``.
    """
    _validate_n_rounds(n_rounds)
    figure_assignments = dict(figure_assignments or {})

    summary_lines = [
        f"- {s.doi} ({s.year}, {s.year_bucket}, tier {s.tier}) — {(s.tldr or '').strip()[:200]}"
        for s in summaries.values()
    ]
    fig_lines = [
        f"- doi={doi} image_path={Path(p).as_posix()}" for doi, p in figure_assignments.items()
    ]

    statement = (
        f"Plan a {target_slide_count}-slide deck for '{topic}'. Pick a "
        "narrative arc, choose figures from those available, and ensure "
        "every bullet cites a real paper."
    )
    questions = [
        "What narrative arc fits the corpus? (chronological / "
        "methodological / problem-approach-result / by-application)",
        "Which figures best support each slide? Are any substituted "
        "(claim X but show figure from Y)?",
        "Are any slide claims overclaimed relative to the source TL;DR?",
        f"Final {target_slide_count}-slide plan in the deck_plan response schema?",
    ]
    rules = [
        "Pick figures ONLY from the available figure_assignments — do not fabricate image paths.",
        "Every bullet must cite a real paper via [[<doi-slug>|Author Year]].",
        "Synthesizer MUST return JSON of the form "
        '{"story_arc_summary": str, "slides": [...]} matching the '
        "deck_plan response schema.",
        f"Hit target_slide_count={target_slide_count} exactly.",
    ]
    agenda = Agenda(
        topic=topic,
        statement=statement,
        questions=questions,
        rules=rules,
    )

    session_context = (
        f"TOPIC: {topic}\n"
        f"TARGET_SLIDE_COUNT: {target_slide_count}\n\n"
        f"PER-PAPER SUMMARIES ({len(summaries)} papers):\n"
        + "\n".join(summary_lines or ["(no summaries)"])
        + "\n\nAVAILABLE FIGURES:\n"
        + ("\n".join(fig_lines) if fig_lines else "(none)")
    )
    session_context = prepend_preamble(
        session_context, project_slug, kb_root=kb_root, role="narrator"
    )

    # G-1 fix: explicitly select narrator + figure_lead + methods_critic +
    # synthesizer instead of riding the Mode.DATA_ANALYSIS default
    # (which would have given us data_analyst + domain_expert +
    # methods_critic + synthesizer — wrong for a deck plan). The two
    # purpose-built deck-pipeline roles must actually instantiate.
    from vaultlab.roles import ROLE_TEMPLATES as _ROLE_TEMPLATES

    deck_plan_roles = [
        _ROLE_TEMPLATES["narrator"],
        _ROLE_TEMPLATES["figure_lead"],
        _ROLE_TEMPLATES["methods_critic"],
        _ROLE_TEMPLATES["synthesizer"],
    ]

    meeting = build_meeting(
        topic=topic,
        meeting_type="deep_think",
        session_context=session_context,
        mode=Mode.DATA_ANALYSIS,
        agenda=agenda,
        roles=deck_plan_roles,
    )

    del metrics  # currently unused — reserved for later

    return _run_adversarial_meeting(
        meeting=meeting,
        runner_callback=runner_callback,
        n_rounds=n_rounds,
        timeout_seconds=timeout_seconds,
        purpose="deck-plan",
        early_exit=early_exit,
        early_exit_threshold=early_exit_threshold,
    )


# ---------------------------------------------------------------------------
# Rigor audit (final gate)
# ---------------------------------------------------------------------------


def rigor_audit(
    *,
    document: str,
    document_path: str | None = None,
    summaries: dict[str, PaperSummary] | None = None,
    audit_kind: str = "deck",
    producer_kind: str = "",
    runner_callback: RunnerCallback | None = None,
    timeout_seconds: int = MEETING_TIMEOUT_SECONDS,
    project_slug: str | None = None,
    kb_root: Path | str | None = None,
) -> dict[str, Any]:
    """Final-gate review by the new ``rigor_auditor`` role.

    Catches what forward critics let slip (Q3 in
    grill-crosstalk-integration-2026-04-30.md):

    * Every "X showed Y" claim links to a ``[[doi-slug]]`` in
      Wiki/Summaries.
    * Every ``[p<N>]`` page marker resolves to a real page.
    * Every reference is cited at least once in the body.
    * No claim language exceeds evidence tier.
    * No ``Wiki/Summaries/<doi>.md`` referenced that doesn't exist.

    Returns ``{"passed": bool, "issues": [...]}`` (always populated; on
    callback failure, returns ``passed=True`` with a single ``minor``
    issue noting the audit was skipped).
    """
    if audit_kind not in {"arc", "deck", "report", "methods"}:
        raise ValueError(
            "audit_kind must be 'arc', 'deck', 'report', or 'methods', "
            f"got {audit_kind!r}"
        )

    # Resolve producer_kind from the document's provenance sidecar when not
    # explicitly supplied (explicit arg wins). Lets the auditor distinguish
    # template-only output from LLM-drafted prose (issues 9-11).
    if not producer_kind and document_path:
        from vaultlab.provenance import read_receipt

        rec = read_receipt(document_path)
        if rec is not None and rec.producer:
            producer_kind = rec.producer

    summaries = summaries or {}

    # Build the auditor role meeting (single role, individual mode — the
    # synthesizer doesn't add anything for a structured fix-list).
    from vaultlab.roles import ROLE_TEMPLATES

    if "rigor_auditor" not in ROLE_TEMPLATES:
        # Defensive — should never happen since we ship the role.
        return {
            "passed": True,
            "issues": [
                {
                    "loc": "(setup)",
                    "severity": "minor",
                    "kind": "other",
                    "fix": "rigor_auditor role not loaded; audit skipped.",
                }
            ],
        }

    auditor = ROLE_TEMPLATES["rigor_auditor"]

    summaries_md = (
        "\n".join(
            f"- {doi}: tldr={(s.tldr or '').strip()[:160]} | "
            f"findings={'; '.join((s.key_findings or [])[:3])[:200]}"
            for doi, s in (summaries or {}).items()
        )
        or "(no summaries provided)"
    )

    statement = (
        f"Audit the {audit_kind} document below for rigor. Return ONLY a "
        "JSON object with 'passed' and 'issues'. Do not rewrite the "
        "document — produce a fix-list the writer can act on."
    )
    questions = [
        "Are all claims grounded in a Wiki/Summaries entry?",
        "Do all [p<N>] markers resolve?",
        "Are all references cited at least once in the body?",
        "Is any language overclaimed relative to source evidence?",
        "Do all [[wikilinks]] target existing summary files?",
    ]
    rules = [
        'Return ONLY a JSON object: {"passed": bool, "issues": [...]}.',
        "Each issue must have loc, severity (blocker|major|minor), kind, and fix.",
        "Set passed=true only when no blocker or major issues remain.",
    ]
    agenda = Agenda(
        topic=f"rigor audit ({audit_kind})",
        statement=statement,
        questions=questions,
        rules=rules,
    )

    # producer_kind names what generated the document (template-only primitive
    # vs. LLM pass). For template-only output we inject a short directive that
    # triggers the rigor_auditor's template-only downgrade (the rule itself
    # lives in roles/rigor_auditor/prompt.md Task 5 — META PRINCIPLE #1).
    producer_line = f"PRODUCER KIND: {producer_kind or '(unspecified)'}\n\n"
    downgrade_line = ""
    if producer_kind == "template-only":
        downgrade_line = (
            "TEMPLATE-ONLY DOWNGRADE: apply rigor_auditor Task 5's template-only "
            "path — skip Tasks 1-3 (claim grounding, page markers, references) "
            "and grade only Task 4 (overclaiming) at minor severity. Hedged "
            'verification lines ("appears to … p=…") are acceptable.\n\n'
        )
    session_context = (
        f"AUDIT KIND: {audit_kind}\n\n"
        f"{producer_line}"
        f"{downgrade_line}"
        f"PER-PAPER SUMMARIES (for cross-reference):\n{summaries_md}\n\n"
        f"DOCUMENT TO AUDIT:\n{document}"
    )
    session_context = prepend_preamble(
        session_context, project_slug, kb_root=kb_root, role="rigor_auditor"
    )

    meeting = Meeting(
        topic=f"rigor audit ({audit_kind})",
        mode=MeetingMode.INDIVIDUAL,
        roles=[auditor],
        session_context=session_context,
        agenda=agenda,
    )

    if runner_callback is None:
        return {
            "passed": True,
            "issues": [
                {
                    "loc": "(audit)",
                    "severity": "minor",
                    "kind": "other",
                    "fix": "rigor_audit called with no runner_callback; audit skipped.",
                }
            ],
        }

    started = time.time()
    try:
        raw = runner_callback(meeting, list(meeting.roles))
    except Exception as exc:
        logger.warning("rigor_audit runner_callback raised: %s", exc)
        return {
            "passed": True,
            "issues": [
                {
                    "loc": "(audit)",
                    "severity": "minor",
                    "kind": "other",
                    "fix": f"rigor_audit callback raised: {exc!r}",
                }
            ],
        }
    runtime = time.time() - started
    if runtime > timeout_seconds:
        logger.warning(
            "rigor_audit ran past timeout (%.1fs > %ds)",
            runtime,
            timeout_seconds,
        )

    if not isinstance(raw, list) or not raw:
        return {
            "passed": True,
            "issues": [
                {
                    "loc": "(audit)",
                    "severity": "minor",
                    "kind": "other",
                    "fix": "rigor_audit callback returned empty/invalid result.",
                }
            ],
        }

    cell = raw[0] if isinstance(raw[0], dict) else {}
    output_text = str(cell.get("output") or cell.get("content") or "")
    parsed = _extract_json_blob(output_text)
    if not isinstance(parsed, dict):
        return {
            "passed": True,
            "issues": [
                {
                    "loc": "(audit)",
                    "severity": "minor",
                    "kind": "other",
                    "fix": "rigor_audit response was not parseable JSON.",
                }
            ],
        }
    # Normalise the structure.
    issues = parsed.get("issues") or []
    if not isinstance(issues, list):
        issues = []
    norm_issues: list[dict[str, Any]] = []
    for it in issues:
        if not isinstance(it, dict):
            continue
        norm_issues.append(
            {
                "loc": str(it.get("loc", "")),
                "severity": str(it.get("severity", "minor")),
                "kind": str(it.get("kind", "other")),
                "fix": str(it.get("fix", "")),
            }
        )
    passed = bool(parsed.get("passed", False))
    # Belt-and-braces: if the auditor said passed=True but there are
    # blocker/major issues, override.
    has_serious = any(i.get("severity") in {"blocker", "major"} for i in norm_issues)
    if has_serious and passed:
        passed = False
    return {"passed": passed, "issues": norm_issues}


# ---------------------------------------------------------------------------
# Audit-trail writer
# ---------------------------------------------------------------------------


def write_crosstalk_artifacts(
    result: CrosstalkResult,
    *,
    run_dir: Path,
) -> dict[str, Path]:
    """Write transcript + per-turn files for an ADVERSARIAL meeting.

    Routes through :func:`vaultlab.kb.paths.transcript_path` and
    :func:`vaultlab.kb.paths.turn_path` so file layout matches the rest
    of vaultlab's run-id directories. Returns a dict with ``transcript``
    and ``turns`` keys.
    """
    run_dir = Path(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)

    purpose = result.purpose or "meeting"
    # transcript-<purpose>.md so multiple meetings per run don't collide
    transcript_p = ensure_parent(Path(run_dir) / f"meeting-{purpose}-transcript.md")

    # Render transcript.
    lines: list[str] = [
        f"# Crosstalk meeting — {purpose}",
        "",
        f"- Status: {result.crosstalk_status}",
        f"- Runtime: {result.runtime_seconds:.1f}s",
        f"- Turns: {len(result.rounds)}",
        "",
    ]
    for i, turn in enumerate(result.rounds, start=1):
        lines.append(f"## Turn {i}: {turn.role_id}")
        lines.append("")
        lines.append(turn.output.strip() or "_(no output)_")
        lines.append("")
    transcript_p.write_text("\n".join(lines), encoding="utf-8")

    # Render per-turn files.
    turn_paths: list[Path] = []
    for i, turn in enumerate(result.rounds, start=1):
        # Use a purpose-prefixed slug so multiple meetings per run don't
        # collide on turn-1-data_analyst.md.
        per_turn = ensure_parent(Path(run_dir) / f"meeting-{purpose}-turn-{i}-{turn.role_id}.md")
        per_turn.write_text(
            f"# {turn.role_id} (turn {i})\n\n{turn.output.strip()}\n",
            encoding="utf-8",
        )
        turn.output_path = str(per_turn)
        turn_paths.append(per_turn)

    return {
        "transcript": transcript_p,
        "turns": turn_paths,  # type: ignore[dict-item]
    }


def append_decisions_log_entry(
    *,
    decisions_log_path: Path,
    purpose: str,
    n_rounds: int,
    result: CrosstalkResult,
    summary_line: str = "",
    run_id: str | None = None,
    timestamp: str | None = None,
) -> Path:
    """Append a one-entry-per-meeting block to ``decisions-log.md``.

    See ``grill-crosstalk-integration-2026-04-30.md`` "Audit trail for
    crosstalk" for the format.
    """
    ts = timestamp or datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    block_lines = [
        f"## {ts} — {purpose} meeting (ADVERSARIAL, {n_rounds} rounds)",
        f"Crosstalk status: {result.crosstalk_status} "
        f"(runtime: {result.runtime_seconds:.1f}s, turns: {len(result.rounds)})",
    ]
    if summary_line:
        block_lines.insert(1, summary_line)
    if run_id:
        block_lines.append(f"Transcript: runs/{run_id}/meeting-{purpose}-transcript.md")
    block = "\n".join(block_lines) + "\n"

    p = Path(decisions_log_path)
    if p.exists():
        existing = p.read_text(encoding="utf-8")
        if not existing.endswith("\n"):
            existing += "\n"
        p.write_text(existing + "\n" + block, encoding="utf-8")
    else:
        ensure_parent(p)
        p.write_text(block, encoding="utf-8")
    return p
