"""Deep-think workflow builders + ensemble-critic variant.

The classic deep-think round is the four-role adversarial cycle::

    Analyst → Domain Expert → Methods Critic → Synthesizer

Each step sees the prior steps' outputs (real outputs after
``inject_prior_outputs``). One round produces four output files plus a
canonical synthesis path.

The ensemble-critic variant fans the Methods Critic out to N independent
critics and adds an Area Chair meta-reviewer between the critics and the
final synthesis. This is the AI-Scientist reviewer-ensemble pattern
wrapped around the existing deep-think shape.

Public surface
--------------

* :func:`plan_deep_think_round` — one classic round
* :func:`plan_round_from_critic_tests` — auto-build round N+1 agenda from
  prior round's Critic priorities
* :func:`plan_deep_think_with_ensemble_critic` — pre-critic + N critics +
  meta-review + synthesis bundle
* :func:`run_deep_think_with_ensemble_critic` — execute the bundle
"""

from __future__ import annotations

from datetime import date

from vaultlab.roles import load_role
from vaultlab.runner import ClaudeCodeRunner, build_meeting
from vaultlab.runner.kb_context import prepend_preamble
from vaultlab.runner.models import Agenda, InvestigationMode, Mode
from vaultlab.workflows._models import DeepThinkEnsembleBundle, WorkflowPlan
from vaultlab.workflows._provenance import Provenance
from vaultlab.workflows._runner import run_workflow
from vaultlab.workflows._utils import (
    _inject_prior_context,
    _session_summary_if_exists,
)
from vaultlab.workflows.crosstalk_policy import (
    CrosstalkContext,
    should_invoke,
    skip_reason,
)
from vaultlab.workflows.ensemble import plan_ensemble_critic
from vaultlab.workflows.synthesis import plan_synthesis


def _get_role(role_id: str):
    """Look up a role by id from the vaultlab role catalog.

    Thin wrapper around :func:`vaultlab.roles.load_role` so the workflow
    code reads the markdown+YAML role definitions directly — no
    intermediate cache, no bobby_ailab lookup.
    """
    return load_role(role_id)


def _record_crosstalk_decision(
    prov: Provenance,
    ctx: CrosstalkContext,
) -> tuple[bool, str | None]:
    """Stamp a Provenance with the crosstalk-policy decision and return it.

    SPEC-E sub-goal 2.4: every crosstalk-firing site records ``invoked`` /
    ``skip_reason`` / ``task_kind`` so audits can reconstruct why a given
    deep-think run did or didn't fire crosstalk. The decision is folded
    into the WorkflowPlan's provenance via:

    * ``params`` — typed structured receipt (``crosstalk_invoked``,
      ``crosstalk_task_kind``, ``crosstalk_skip_reason``). This is the
      canonical home post-2026-05-15: the workflow ``Provenance``
      dataclass now carries a ``params`` dict mirroring
      :class:`vaultlab.provenance.ProvenanceRecord`.
    * ``tags`` — short machine-greppable markers (``crosstalk_invoked=true``,
      ``crosstalk_task_kind=deep_think``). Kept for back-compat with audit
      tooling that greps tags.
    * ``notes`` — appended human-readable summary (preserves any existing
      note text); includes the skip reason when applicable. Also kept for
      back-compat.

    The triple-write is intentional: ``params`` is the right home for
    structured decisions, but old indexes / scripts read tags + notes so
    we keep emitting both while the rest of the codebase migrates.
    """
    invoked = should_invoke(ctx)
    reason = skip_reason(ctx)

    # Structured params (canonical post-unification home)
    prov.params["crosstalk_invoked"] = invoked
    prov.params["crosstalk_task_kind"] = ctx.task_kind
    prov.params["crosstalk_skip_reason"] = reason

    invoked_tag = f"crosstalk_invoked={str(invoked).lower()}"
    kind_tag = f"crosstalk_task_kind={ctx.task_kind}"
    # Idempotent stamp: dedupe so plan-time + runtime calls don't pile up
    # duplicate tags. The same dataclass instance flows through both
    # ``plan_deep_think_with_ensemble_critic`` and
    # ``run_deep_think_with_ensemble_critic`` — second call should be a
    # no-op when the decision hasn't changed.
    existing = set(prov.tags)
    new_tags = [t for t in (invoked_tag, kind_tag) if t not in existing]
    if new_tags:
        prov.tags = list(prov.tags) + new_tags
    note_bits = [
        f"crosstalk_invoked={invoked}",
        f"crosstalk_task_kind={ctx.task_kind}",
    ]
    if reason:
        note_bits.append(f"crosstalk_skip_reason={reason!r}")
    summary = "; ".join(note_bits)
    if summary not in (prov.notes or ""):
        if prov.notes:
            prov.notes = f"{prov.notes}\n{summary}"
        else:
            prov.notes = summary
    return invoked, reason


# ---------------------------------------------------------------------------
# Classic single-round deep-think
# ---------------------------------------------------------------------------


def plan_deep_think_round(
    cfg,
    topic: str,
    round_num: int = 1,
    mode: Mode = Mode.DATA_ANALYSIS,
    investigation_mode: InvestigationMode = InvestigationMode.DIRECTED,
    agenda: Agenda | None = None,
    date_str: str | None = None,
) -> WorkflowPlan:
    """Build a single round of the deep-think workflow.

    The returned ``RunPlan`` has one step per role (Analyst + Expert +
    Critic + Synthesizer). The slash command executes them in order,
    injecting real outputs into later prompts via
    ``plan.inject_prior_outputs``.
    """
    if agenda is None:
        agenda = Agenda(
            topic=topic,
            statement=f"Assess and integrate findings on {topic}",
            questions=[
                "What does the data show (exact values)?",
                "Does evidence meet the project's significance thresholds?",
                "What is the domain interpretation and proposed mechanism?",
                "Is there literature support (paperclip primary, bobby_research fallback)?",
                "How does this connect to existing findings in the session?",
            ],
            rules=[
                "Cite exact data-file paths and query strings",
                "Compare every numerical claim to a null baseline",
                "Never cite papers from memory — verify via paperclip or bobby_research",
            ],
            investigation_mode=investigation_mode,
        )
    else:
        # respect the caller's agenda but override investigation_mode if they
        # passed a different default
        agenda.investigation_mode = investigation_mode or agenda.investigation_mode

    ctx = cfg.context_summary() + "\n\n" + _session_summary_if_exists(cfg)
    # Commitment #7: spawned analyst/critic/synthesizer sub-agents get the project's
    # KB context (no-op when the project isn't onboarded; uses the cfg already in hand).
    ctx = prepend_preamble(ctx, getattr(cfg, "name", None), kb_root=getattr(cfg, "kb_path", None))
    meeting = build_meeting(
        topic=topic,
        meeting_type="deep_think",
        session_context=ctx,
        mode=mode,
        round_num=round_num,
        agenda=agenda,
    )
    runner = ClaudeCodeRunner(
        kb_path=cfg.kb_path,
        command_name="deep-think",
        date_str=date_str,
    )
    plan = runner.plan(meeting, task=agenda)
    prov = Provenance(
        generated_by="deep-think",
        project=cfg.name,
        meeting_mode=meeting.mode.value,
        investigation_mode=agenda.investigation_mode.value,
        topic=topic,
        round=round_num,
        kind="deep_think_round",
        tags=["deep-think", agenda.investigation_mode.value],
    )
    # SPEC-E sub-goal 2.4: gate crosstalk via the invocation policy and
    # record the decision on the workflow's provenance. The classic
    # adversarial cycle (Analyst → Expert → Critic → Synthesizer) is a
    # cross-evidence reasoning task → 'deep_think'.
    _record_crosstalk_decision(
        prov,
        CrosstalkContext(
            task_kind="deep_think",
            n_evidence_sources=len(agenda.questions),
        ),
    )
    return WorkflowPlan(meeting=meeting, plan=plan, provenance=prov)


def plan_round_from_critic_tests(
    cfg,
    critic_output: str,
    topic: str,
    round_num: int = 2,
    mode: Mode = Mode.DATA_ANALYSIS,
    priority_filter: list[str] | None = None,
) -> WorkflowPlan:
    """Build a Round N deep-think plan from the prior round's Critic tests.

    Parses priority-tagged ``[CRITICAL]`` / ``[HIGH]`` / ``[MEDIUM]`` /
    ``[LOW]`` items from ``critic_output`` and turns each into an agenda
    question. Agenda is automatically DIRECTED (we're building on
    committed Round N-1 findings).

    ``priority_filter`` restricts to a subset of priorities — e.g.
    ``["CRITICAL", "HIGH"]`` skips the lower-priority tests.

    Raises :class:`ValueError` if no priority tests parse from
    ``critic_output``.
    """
    from vaultlab.parsers import parse_next_round_tests

    tests = parse_next_round_tests(critic_output)
    if priority_filter:
        tests = [t for t in tests if t["priority"] in priority_filter]
    if not tests:
        raise ValueError(
            "No priority-tagged tests parsed from critic output. "
            "Expected lines like '1. [CRITICAL] Recompute ...'"
        )

    questions = [f"[{t['priority']}] {t['description']}" for t in tests]
    rules = [
        "Address CRITICAL tests first — they gate the round's conclusion",
        "Cite exact data values and queries for each check",
        "Use paperclip lookup/grep to verify any literature claims (bobby_research fallback)",
        "Report results in the same priority order as the agenda",
    ]
    agenda = Agenda(
        topic=topic,
        statement=(
            f"Address the Round {round_num - 1} Critic's next-round tests for {topic}. "
            f"Each agenda question IS a test; answer whether it passes, "
            f"what the evidence shows, and how it changes the finding's rating."
        ),
        questions=questions,
        rules=rules,
        investigation_mode=InvestigationMode.DIRECTED,
    )
    wp = plan_deep_think_round(
        cfg=cfg,
        topic=topic,
        round_num=round_num,
        mode=mode,
        investigation_mode=InvestigationMode.DIRECTED,
        agenda=agenda,
    )
    # Record in provenance that this round was auto-seeded from prior Critic
    wp.provenance.tags = list(wp.provenance.tags) + ["round-from-critic"]
    wp.provenance.notes = (
        f"Auto-seeded from Round {round_num - 1} Critic output: {len(tests)} priority tests"
    )
    return wp


# ---------------------------------------------------------------------------
# Ensemble-critic deep-think (4-phase bundle)
# ---------------------------------------------------------------------------


def plan_deep_think_with_ensemble_critic(
    cfg,
    topic: str,
    n_critics: int = 3,
    round_num: int = 1,
    mode: Mode = Mode.DATA_ANALYSIS,
    investigation_mode: InvestigationMode = InvestigationMode.DIRECTED,
    agenda: Agenda | None = None,
    date_str: str | None = None,
) -> DeepThinkEnsembleBundle:
    """Deep-think where the Critic phase is replaced by N critics + meta-review.

    The workflow is the same as a standard deep-think round (Analyst →
    Expert → Critic → Synthesizer), but the single Critic step becomes an
    ensemble: N critics run independently at ENSEMBLE_TEMPERATURE, then
    an Area Chair meta-reviewer aggregates their ratings using strictest-
    wins aggregation.

    Minority concerns that a single critic might let slide surface
    reliably — this is the AI-Scientist reviewer-ensemble pattern
    wrapped around the existing deep-think shape.

    Returns a :class:`DeepThinkEnsembleBundle` with 4 phases. The bundled
    :func:`run_deep_think_with_ensemble_critic` helper executes them in
    the right order with correct output injection between phases.
    """
    if n_critics < 2:
        raise ValueError("plan_deep_think_with_ensemble_critic requires n_critics >= 2")

    base_date = date_str or date.today().isoformat()

    # ── Phase 1: pre-critic (Analyst + Expert, 2-step adversarial) ──────
    pre_agenda_questions = [
        "What does the data show (exact values)?",
        "Does evidence meet the project's significance thresholds?",
        "What is the domain interpretation and proposed mechanism?",
        "Is there literature support (paperclip primary)?",
        "How does this connect to existing findings in the session?",
    ]
    pre_agenda_rules = [
        "Cite exact data-file paths and query strings",
        "Compare every numerical claim to a null baseline",
        "Never cite papers from memory — verify via paperclip or bobby_research",
    ]
    pre_agenda = agenda or Agenda(
        topic=topic,
        statement=f"Assess findings on {topic} (pre-critic phase)",
        questions=pre_agenda_questions,
        rules=pre_agenda_rules,
        investigation_mode=investigation_mode,
    )
    analyst_id = "data_analyst" if mode == Mode.DATA_ANALYSIS else "literature_surveyor"
    ctx = cfg.context_summary() + "\n\n" + _session_summary_if_exists(cfg)
    # Commitment #7: spawned analyst/critic/synthesizer sub-agents get the project's
    # KB context (no-op when the project isn't onboarded; uses the cfg already in hand).
    ctx = prepend_preamble(ctx, getattr(cfg, "name", None), kb_root=getattr(cfg, "kb_path", None))
    # Build a reasoning meeting (Analyst + Expert + Critic) but drop the Critic
    # role to isolate the pre-critic outputs as a self-contained phase
    pre_meeting = build_meeting(
        topic=topic,
        meeting_type="reasoning",
        session_context=ctx,
        mode=mode,
        round_num=round_num,
        agenda=pre_agenda,
    )
    pre_meeting.roles = [_get_role(analyst_id), _get_role("domain_expert")]
    pre_runner = ClaudeCodeRunner(
        kb_path=cfg.kb_path,
        command_name="deep-think-ensemble",
        date_str=f"{base_date}-precritic",
    )
    pre_plan = pre_runner.plan(pre_meeting, task=pre_agenda)
    pre_prov = Provenance(
        generated_by="deep-think-ensemble",
        project=cfg.name,
        meeting_mode=pre_meeting.mode.value,
        investigation_mode=investigation_mode.value,
        topic=topic,
        round=round_num,
        kind="deep_think_pre_critic",
        tags=["deep-think", "ensemble", "pre-critic"],
    )
    pre_wp = WorkflowPlan(meeting=pre_meeting, plan=pre_plan, provenance=pre_prov)

    # ── Phase 2: N critic plans (stubs — prior_outputs filled at run time) ──
    # prior_outputs is empty here because pre-critic hasn't run yet; the
    # runner helper fills it in before dispatching critics.
    critic_wps, meta_wp = plan_ensemble_critic(
        cfg,
        topic=topic,
        prior_outputs="(pre-critic outputs go here)",
        n_critics=n_critics,
        round_num=round_num,
        date_str=f"{base_date}-ensemble",
    )

    # ── Phase 4: synthesis ──────────────────────────────────────────────
    synth_agenda = Agenda(
        topic=topic,
        statement=(
            f"Integrate the pre-critic outputs and the meta-review into one "
            f"narrative for {topic}. Name the disagreements the critics "
            f"surfaced and say how they were resolved."
        ),
        questions=pre_agenda_questions
        + [
            "What concerns did the critic ensemble raise, and how were they resolved?",
            "Which findings are robust, needing-validation, or contested?",
        ],
        rules=pre_agenda_rules
        + [
            "Every integrated claim traces to a specific pre-critic or meta-review source",
            "Preserve minority objections — do not average them away",
        ],
        investigation_mode=investigation_mode,
    )
    synth_wp = plan_synthesis(
        cfg,
        topic=topic,
        investigation_mode=investigation_mode,
        agenda=synth_agenda,
        date_str=f"{base_date}-ensemble-synth",
        canonical_suffix="ensemble",
    )
    synth_wp.provenance.tags = list(synth_wp.provenance.tags) + [
        "ensemble-synthesis",
        f"n_critics={n_critics}",
    ]
    synth_wp.provenance.kind = "deep_think_ensemble_synthesis"

    # SPEC-E sub-goal 2.4: gate crosstalk via the invocation policy.
    # The ensemble-critic deep-think is the canonical "fire the round-
    # table" workflow → 'deep_think'. Stamp the decision on every phase's
    # provenance so each phase output records why crosstalk fired
    # (or didn't); the synthesis phase gets the canonical final record.
    bundle_ctx = CrosstalkContext(
        task_kind="deep_think",
        n_evidence_sources=len(pre_agenda_questions),
    )
    for phase_wp in (pre_wp, *critic_wps, meta_wp, synth_wp):
        _record_crosstalk_decision(phase_wp.provenance, bundle_ctx)

    return DeepThinkEnsembleBundle(
        pre_critic=pre_wp,
        critic_plans=critic_wps,
        meta_review=meta_wp,
        synthesis=synth_wp,
    )


def run_deep_think_with_ensemble_critic(
    bundle: DeepThinkEnsembleBundle,
    agent_fn,
    resume: bool = False,
) -> DeepThinkEnsembleBundle:
    """Execute an ensemble-critic deep-think bundle end-to-end.

    Runs the 4 phases in order, wiring each phase's output into the next:

      1. ``pre_critic``   — Analyst + Expert run adversarially
      2. ``critic_plans`` — N critics receive pre-critic outputs as prior
         context
      3. ``meta_review``  — meta-reviewer receives all N critic outputs
      4. ``synthesis``    — synthesizer receives pre-critic + meta-review
         outputs

    ``agent_fn`` has the same signature as :func:`run_workflow`'s.
    ``resume=True`` respects existing output files (see
    :func:`run_workflow` docs).

    Returns the same bundle with every plan's turns filled and outputs
    written.

    SPEC-E sub-goal 2.4 — The ensemble-critic bundle is the runtime
    firing point for deep-think crosstalk. We re-stamp each phase's
    provenance with the policy decision here so hand-built bundles (that
    skipped ``plan_deep_think_with_ensemble_critic``) still record the
    decision in their output files. The bundle always executes —
    matching the lineage / deck-plan pattern, where the gate is
    instrumentation, not flow-control — but the decision lives in every
    phase output's provenance frontmatter for audits to reconstruct.
    """
    n_critics_in_bundle = len(bundle.critic_plans)
    runtime_ctx = CrosstalkContext(
        task_kind="deep_think",
        n_evidence_sources=max(n_critics_in_bundle, 1),
    )
    for phase_wp in bundle.all_plans:
        _record_crosstalk_decision(phase_wp.provenance, runtime_ctx)

    # Phase 1
    run_workflow(bundle.pre_critic, agent_fn=agent_fn, resume=resume)
    pre_critic_outputs = "\n\n".join(
        f"### {step.role_name}\n{turn.output.strip()}"
        for step, turn in zip(
            bundle.pre_critic.plan.steps, bundle.pre_critic.plan.turns, strict=False
        )
        if turn.output.strip()
    )

    # Phase 2 — each critic sees the pre-critic outputs
    for critic_wp in bundle.critic_plans:
        _inject_prior_context(critic_wp, pre_critic_outputs)
        run_workflow(critic_wp, agent_fn=agent_fn, resume=resume)
    critic_outputs = [critic_wp.plan.turns[-1].output for critic_wp in bundle.critic_plans]

    # Phase 3 — meta-reviewer sees all N critic outputs
    meta_prior = "\n\n".join(
        f"### Review {i + 1}\n{out.strip()}" for i, out in enumerate(critic_outputs) if out.strip()
    )
    _inject_prior_context(bundle.meta_review, meta_prior)
    run_workflow(bundle.meta_review, agent_fn=agent_fn, resume=resume)
    meta_output = bundle.meta_review.plan.turns[-1].output

    # Phase 4 — synthesizer sees pre-critic + meta-review
    synth_prior = pre_critic_outputs + "\n\n### Meta-review\n" + meta_output.strip()
    _inject_prior_context(bundle.synthesis, synth_prior)
    run_workflow(bundle.synthesis, agent_fn=agent_fn, resume=resume)

    return bundle


__all__ = [
    "plan_deep_think_round",
    "plan_deep_think_with_ensemble_critic",
    "plan_round_from_critic_tests",
    "run_deep_think_with_ensemble_critic",
]
