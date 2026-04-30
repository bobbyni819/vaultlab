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
from typing import Optional

from vaultlab.runner import ClaudeCodeRunner, build_meeting
from vaultlab.runner.meetings import ROLE_TEMPLATES
from vaultlab.runner.models import Agenda, InvestigationMode, Mode

from vaultlab.workflows._models import DeepThinkEnsembleBundle, WorkflowPlan
from vaultlab.workflows._provenance import Provenance
from vaultlab.workflows._runner import run_workflow
from vaultlab.workflows._utils import (
    _inject_prior_context,
    _session_summary_if_exists,
)
from vaultlab.workflows.ensemble import plan_ensemble_critic
from vaultlab.workflows.synthesis import plan_synthesis


def _get_role(role_id: str):
    """Look up a role by id from the vaultlab role catalog.

    TODO(roles-lift): replace this with ``vaultlab.roles.load_role`` once
    that loader returns ``vaultlab.runner.models.Role`` (currently it
    returns a frozen, structurally-different ``Role`` from
    :mod:`vaultlab.roles._loader`). For now we go through
    :mod:`vaultlab.runner.meetings` ``ROLE_TEMPLATES`` which already re-
    packs bobby_ailab roles into the runner-compatible shape.
    """
    return ROLE_TEMPLATES[role_id]


# ---------------------------------------------------------------------------
# Classic single-round deep-think
# ---------------------------------------------------------------------------


def plan_deep_think_round(
    cfg,
    topic: str,
    round_num: int = 1,
    mode: Mode = Mode.DATA_ANALYSIS,
    investigation_mode: InvestigationMode = InvestigationMode.DIRECTED,
    agenda: Optional[Agenda] = None,
    date_str: Optional[str] = None,
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
    meeting = build_meeting(
        topic=topic,
        meeting_type="deep_think",
        session_context=ctx,
        mode=mode,
        round_num=round_num,
        agenda=agenda,
    )
    runner = ClaudeCodeRunner(
        kb_path=cfg.kb_path, command_name="deep-think", date_str=date_str,
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
    return WorkflowPlan(meeting=meeting, plan=plan, provenance=prov)


def plan_round_from_critic_tests(
    cfg,
    critic_output: str,
    topic: str,
    round_num: int = 2,
    mode: Mode = Mode.DATA_ANALYSIS,
    priority_filter: Optional[list[str]] = None,
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
    # TODO(parsers-lift): replace bobby_ailab._parsers.parse_next_round_tests
    # with a vaultlab-native parser. Today the helper still lives in
    # bobby_ailab — small (220 LOC) and stable, deferred.
    from bobby_ailab._parsers import parse_next_round_tests

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
        cfg=cfg, topic=topic, round_num=round_num, mode=mode,
        investigation_mode=InvestigationMode.DIRECTED,
        agenda=agenda,
    )
    # Record in provenance that this round was auto-seeded from prior Critic
    wp.provenance.tags = list(wp.provenance.tags) + ["round-from-critic"]
    wp.provenance.notes = (
        f"Auto-seeded from Round {round_num - 1} Critic output: "
        f"{len(tests)} priority tests"
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
    agenda: Optional[Agenda] = None,
    date_str: Optional[str] = None,
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
    # Build a reasoning meeting (Analyst + Expert + Critic) but drop the Critic
    # role to isolate the pre-critic outputs as a self-contained phase
    pre_meeting = build_meeting(
        topic=topic, meeting_type="reasoning", session_context=ctx,
        mode=mode, round_num=round_num, agenda=pre_agenda,
    )
    pre_meeting.roles = [_get_role(analyst_id), _get_role("domain_expert")]
    pre_runner = ClaudeCodeRunner(
        kb_path=cfg.kb_path, command_name="deep-think-ensemble",
        date_str=f"{base_date}-precritic",
    )
    pre_plan = pre_runner.plan(pre_meeting, task=pre_agenda)
    pre_prov = Provenance(
        generated_by="deep-think-ensemble",
        project=cfg.name,
        meeting_mode=pre_meeting.mode.value,
        investigation_mode=investigation_mode.value,
        topic=topic, round=round_num, kind="deep_think_pre_critic",
        tags=["deep-think", "ensemble", "pre-critic"],
    )
    pre_wp = WorkflowPlan(meeting=pre_meeting, plan=pre_plan, provenance=pre_prov)

    # ── Phase 2: N critic plans (stubs — prior_outputs filled at run time) ──
    # prior_outputs is empty here because pre-critic hasn't run yet; the
    # runner helper fills it in before dispatching critics.
    critic_wps, meta_wp = plan_ensemble_critic(
        cfg, topic=topic, prior_outputs="(pre-critic outputs go here)",
        n_critics=n_critics, round_num=round_num,
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
        questions=pre_agenda_questions + [
            "What concerns did the critic ensemble raise, and how were they resolved?",
            "Which findings are robust, needing-validation, or contested?",
        ],
        rules=pre_agenda_rules + [
            "Every integrated claim traces to a specific pre-critic or meta-review source",
            "Preserve minority objections — do not average them away",
        ],
        investigation_mode=investigation_mode,
    )
    synth_wp = plan_synthesis(
        cfg, topic=topic, investigation_mode=investigation_mode,
        agenda=synth_agenda,
        date_str=f"{base_date}-ensemble-synth",
        canonical_suffix="ensemble",
    )
    synth_wp.provenance.tags = list(synth_wp.provenance.tags) + [
        "ensemble-synthesis", f"n_critics={n_critics}",
    ]
    synth_wp.provenance.kind = "deep_think_ensemble_synthesis"

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
    """
    # Phase 1
    run_workflow(bundle.pre_critic, agent_fn=agent_fn, resume=resume)
    pre_critic_outputs = "\n\n".join(
        f"### {step.role_name}\n{turn.output.strip()}"
        for step, turn in zip(bundle.pre_critic.plan.steps, bundle.pre_critic.plan.turns)
        if turn.output.strip()
    )

    # Phase 2 — each critic sees the pre-critic outputs
    for critic_wp in bundle.critic_plans:
        _inject_prior_context(critic_wp, pre_critic_outputs)
        run_workflow(critic_wp, agent_fn=agent_fn, resume=resume)
    critic_outputs = [
        critic_wp.plan.turns[-1].output for critic_wp in bundle.critic_plans
    ]

    # Phase 3 — meta-reviewer sees all N critic outputs
    meta_prior = "\n\n".join(
        f"### Review {i + 1}\n{out.strip()}"
        for i, out in enumerate(critic_outputs)
        if out.strip()
    )
    _inject_prior_context(bundle.meta_review, meta_prior)
    run_workflow(bundle.meta_review, agent_fn=agent_fn, resume=resume)
    meta_output = bundle.meta_review.plan.turns[-1].output

    # Phase 4 — synthesizer sees pre-critic + meta-review
    synth_prior = (
        pre_critic_outputs
        + "\n\n### Meta-review\n"
        + meta_output.strip()
    )
    _inject_prior_context(bundle.synthesis, synth_prior)
    run_workflow(bundle.synthesis, agent_fn=agent_fn, resume=resume)

    return bundle


__all__ = [
    "plan_deep_think_round",
    "plan_round_from_critic_tests",
    "plan_deep_think_with_ensemble_critic",
    "run_deep_think_with_ensemble_critic",
]
