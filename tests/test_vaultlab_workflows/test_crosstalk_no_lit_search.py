"""Tests for crosstalk operating WITHOUT a prior literature-search context.

Task #117: verify the multi-agent crosstalk path (analyst → critics →
synthesizer) fires correctly when invoked without a prior
``lineage_result`` / lit-arc backing it. This is the no-arc invocation
pattern needed for:

* journal-club discussion crosstalk (a topic + agenda, no corpus)
* deep-think on a single concept (no upstream corpus needed)
* response-letter argument synthesis (a single reviewer block, no corpus)

The tests cover five things:

1. The crosstalk-invocation policy returns ``True`` for the no-arc
   ``deep_think`` case (``CrosstalkContext(task_kind="deep_think",
   n_evidence_sources=0)``).
2. The deep-think planner (:func:`plan_deep_think_round`) builds a valid
   plan with no upstream lit-arc passed in.
3. The classic deep-think round runs end-to-end with no upstream
   context, writing per-step outputs + canonical synthesis with the
   expected provenance frontmatter.
4. The provenance records the no-arc state via the existing
   ``crosstalk_*`` tag + notes stamping (the ensemble bundle reflects
   ``n_evidence_sources=max(n_critics, 1)`` at runtime, so for a hand-
   built no-arc bundle we verify the plan-time ``crosstalk_invoked=true``
   tag persists and a synthesizer-only path also gets stamped on demand).
5. The crosstalk output composes with the manuscript primitives
   (:func:`vaultlab.manuscript.polish.write_polish_report`,
   :func:`vaultlab.manuscript.respond.write_response_letter`) without
   any lit-arc / lineage_result detour.

Tests use a deterministic mock runner-callback / agent so they run in CI
without an LLM. See task-117 context in
``.claude/goals/test-crosstalk-no-lit-search.md``.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

import pytest

from vaultlab.config import ProjectConfig
from vaultlab.manuscript.polish import write_polish_report
from vaultlab.manuscript.respond import (
    ActionType,
    CommentKind,
    ReviewerComment,
    ResponseLetter,
    write_response_letter,
)
from vaultlab.workflows import (
    CrosstalkContext,
    CrosstalkResult,
    adversarial_arc_meeting,
    plan_deep_think_round,
    plan_deep_think_with_ensemble_critic,
    plan_synthesis,
    read_provenance,
    run_deep_think_with_ensemble_critic,
    run_workflow,
    should_invoke,
    skip_reason,
)


# ---------------------------------------------------------------------------
# Fixtures + mock runner
# ---------------------------------------------------------------------------


@pytest.fixture
def cfg():
    """A minimal ProjectConfig with a temp KB. No lit-arc, no findings."""
    with tempfile.TemporaryDirectory() as d:
        kb = os.path.join(d, "kb")
        os.makedirs(os.path.join(kb, "Output"))
        os.makedirs(os.path.join(kb, "Sources", "Notes"))
        os.makedirs(os.path.join(kb, "Wiki", "Concepts"))
        yield ProjectConfig(
            name="no-arc-test",
            kb_path=kb,
            domain="testing",
            domain_context="No upstream lit-arc; pure no-arc invocation.",
        )


def _mock_agent(prefix: str = "MOCK"):
    """Deterministic stand-in for the LLM agent function.

    The workflow runner expects ``agent_fn(prompt, tools) -> str``. The
    return text deliberately tags itself with the prefix so per-step
    assertions can verify the runner wrote real output.
    """

    def fn(prompt: str, tools: list[str]) -> str:
        return f"{prefix}: deterministic response ({len(prompt)} chars)"

    return fn


def _mock_runner_callback():
    """Deterministic runner_callback for crosstalk-meeting wrappers.

    Returns one dict per role. Analyst + critic outputs are filler; the
    synthesizer emits arc-shaped JSON so the wrapper's
    ``_extract_json_blob`` finds a usable ``final_output``. The function
    signature matches :data:`vaultlab.workflows.crosstalk.RunnerCallback`.
    """

    def runner(meeting, roles):
        outputs: list[dict[str, str]] = []
        for r in roles:
            if r.id == "synthesizer":
                payload = {
                    "history": "Mocked history paragraph.",
                    "development": "Mocked development paragraph.",
                    "sota": "Mocked state-of-the-art paragraph.",
                }
                outputs.append({"output": json.dumps(payload)})
            elif "critic" in r.id:
                outputs.append({"output": "Critic output: mocked critique."})
            else:
                # data_analyst, domain_expert, literature_surveyor, etc.
                outputs.append({"output": f"{r.id} output: mocked observations."})
        return outputs

    return runner


# ---------------------------------------------------------------------------
# (1) Policy fires for no-arc deep_think
# ---------------------------------------------------------------------------


def test_policy_fires_for_no_arc_deep_think():
    """``CrosstalkContext(task_kind='deep_think', n_evidence_sources=0)``
    fires by default per the policy's FIRE_KINDS rule.

    This is the canonical no-arc invocation: an agent is asked to deep-
    think about a topic without any prior literature search seeding the
    corpus. The policy must fire so the round-table runs.
    """
    ctx = CrosstalkContext(task_kind="deep_think", n_evidence_sources=0)
    assert should_invoke(ctx) is True
    assert skip_reason(ctx) is None


def test_policy_fires_for_no_arc_journal_club():
    """Journal-club discussion is the other primary no-arc use case."""
    ctx = CrosstalkContext(task_kind="journal_club", n_evidence_sources=0)
    assert should_invoke(ctx) is True


def test_policy_fires_for_no_arc_synthesis():
    """Single-concept synthesis (no arc) — fires by default."""
    ctx = CrosstalkContext(task_kind="synthesis", n_evidence_sources=0)
    assert should_invoke(ctx) is True


# ---------------------------------------------------------------------------
# (2) Planner builds a valid plan without prior lit-arc
# ---------------------------------------------------------------------------


def test_plan_deep_think_round_works_without_lineage_result(cfg):
    """``plan_deep_think_round`` accepts a topic + agenda with no
    ``lineage_result`` argument at all — the signature has none, which
    is the whole point of this test. We assert the plan came back well-
    formed: meeting with roles, run plan with steps, and the canonical
    provenance stub stamped with the crosstalk decision."""
    wp = plan_deep_think_round(cfg, topic="single-concept exploration")

    # Plan shape: at least 4 roles (Analyst/Expert/Critic/Synthesizer)
    assert wp.meeting is not None
    assert len(wp.meeting.roles) >= 4
    assert len(wp.plan.steps) == len(wp.plan.turns)
    assert len(wp.plan.steps) >= 4

    # Provenance is filled and the no-arc deep-think fired the policy
    assert wp.provenance.generated_by == "deep-think"
    assert wp.provenance.kind == "deep_think_round"
    assert "crosstalk_invoked=true" in wp.provenance.tags
    assert "crosstalk_task_kind=deep_think" in wp.provenance.tags


def test_plan_deep_think_ensemble_works_without_lineage_result(cfg):
    """The ensemble-critic bundle planner also has no ``lineage_result``
    argument. Build a bundle with no prior arc and assert every phase is
    in place with provenance stamped."""
    bundle = plan_deep_think_with_ensemble_critic(
        cfg,
        topic="no-arc deep think",
        n_critics=2,
    )

    assert bundle.pre_critic is not None
    assert len(bundle.critic_plans) == 2
    assert bundle.meta_review is not None
    assert bundle.synthesis is not None

    # Every phase stamped (plan-time)
    for phase_wp in bundle.all_plans:
        assert "crosstalk_invoked=true" in phase_wp.provenance.tags
        assert "crosstalk_task_kind=deep_think" in phase_wp.provenance.tags


# ---------------------------------------------------------------------------
# (3) End-to-end execution with no upstream context
# ---------------------------------------------------------------------------


def test_deep_think_round_executes_end_to_end_without_lit_arc(cfg):
    """A classic single-round deep-think runs end-to-end with no prior
    arc seeded. Every step writes its output file with provenance
    frontmatter."""
    wp = plan_deep_think_round(cfg, topic="no-arc topic")
    result = run_workflow(wp, agent_fn=_mock_agent("NOARC"))

    # All turns filled
    assert all(t.output.startswith("NOARC") for t in result.plan.turns)

    # Per-step output files written with provenance frontmatter
    for step in wp.plan.steps:
        assert os.path.isfile(step.output_path), (
            f"step {step.role_id} did not write {step.output_path}"
        )
        prov = read_provenance(step.output_path)
        assert prov is not None
        assert prov.generated_by == "deep-think"
        assert "crosstalk_invoked=true" in prov.tags
        assert "crosstalk_task_kind=deep_think" in prov.tags


def test_ensemble_bundle_executes_end_to_end_without_lit_arc(cfg):
    """A full ensemble-critic bundle runs end-to-end with no upstream
    arc. The canonical synthesis output is the final integration."""
    bundle = plan_deep_think_with_ensemble_critic(
        cfg,
        topic="no-arc ensemble",
        n_critics=2,
    )
    run_deep_think_with_ensemble_critic(bundle, agent_fn=_mock_agent("ENS"))

    # Canonical synthesis path was written
    canonical = bundle.synthesis.canonical_output_path
    assert canonical is not None
    assert os.path.isfile(canonical)

    prov = read_provenance(canonical)
    assert prov is not None
    assert "crosstalk_invoked=true" in prov.tags
    assert "crosstalk_task_kind=deep_think" in prov.tags


def test_synthesis_only_executes_without_findings_or_arc(cfg):
    """A Synthesizer-only plan also has no ``lineage_result`` argument.
    With an empty KB (no findings, no branch summaries), it still runs
    end-to-end and writes the canonical ``synthesis-<date>.md``."""
    wp = plan_synthesis(cfg, topic="no-arc synthesis")
    run_workflow(wp, agent_fn=_mock_agent("SYN"))

    assert wp.canonical_output_path is not None
    assert os.path.isfile(wp.canonical_output_path)
    prov = read_provenance(wp.canonical_output_path)
    assert prov is not None
    assert prov.generated_by == "synthesize"


# ---------------------------------------------------------------------------
# (4) Provenance records the no-arc state
# ---------------------------------------------------------------------------


def test_deep_think_round_records_no_arc_state_in_provenance(cfg):
    """Notes record the policy decision; the plan-time call is seeded
    from the no-arc context (``n_evidence_sources=`` len(agenda
    questions), not from an upstream corpus). The decision must land in
    the workflow's Provenance so an audit can reconstruct it."""
    wp = plan_deep_think_round(cfg, topic="no-arc-decision")
    notes = wp.provenance.notes
    # The decision summary string is in notes
    assert "crosstalk_invoked=True" in notes
    assert "crosstalk_task_kind=deep_think" in notes
    # deep_think fires by default → no skip reason
    assert "crosstalk_skip_reason" not in notes


def test_crosstalk_meeting_wrapper_fires_without_arc(cfg):
    """The adversarial-meeting wrapper :func:`adversarial_arc_meeting`
    works without a ``lineage_result``: we hand it a ``summaries`` dict
    (which can be empty) and a runner callback. With NO prior arc and
    NO summaries, the meeting still runs and yields a CrosstalkResult.

    This covers the "agent invokes crosstalk on a freshly-instantiated
    topic with nothing seeded" case — the wrapper does not require
    upstream lit-arc state to fire.
    """
    result = adversarial_arc_meeting(
        topic="no-arc topic",
        summaries={},  # ← the no-arc state: zero papers seeded
        n_rounds=1,
        runner_callback=_mock_runner_callback(),
    )

    assert isinstance(result, CrosstalkResult)
    # Synthesizer emitted parseable JSON, so the wrapper reports complete.
    assert result.crosstalk_status == "complete"
    assert result.final_output.get("history", "").startswith("Mocked history")
    # purpose stamp present — feeds the audit log
    assert result.purpose == "arc"


# ---------------------------------------------------------------------------
# (5) Composes with manuscript primitives without a lit-arc detour
# ---------------------------------------------------------------------------


def test_crosstalk_synthesis_composes_with_manuscript_polish(cfg, tmp_path):
    """A crosstalk synthesis output can feed manuscript.polish directly.

    The polish primitive takes raw text and writes a polish report — no
    lit-arc, no lineage_result, no corpus needed. We run a no-arc
    deep-think, take its canonical synthesis text, and run the polish
    checker over it.
    """
    wp = plan_synthesis(cfg, topic="no-arc polishable text")
    run_workflow(wp, agent_fn=_mock_agent("POLISH-IN"))

    canonical = Path(wp.canonical_output_path)
    body = canonical.read_text(encoding="utf-8")

    # Polish primitive accepts the synthesis body directly
    report_path = tmp_path / "polish-report.md"
    out = write_polish_report(
        report_path,
        body,
        source_path=str(canonical),
    )
    assert out.exists()
    assert out.read_text(encoding="utf-8").startswith("# Polish report")


def test_crosstalk_synthesis_composes_with_manuscript_respond(tmp_path):
    """A crosstalk argument-synthesis output can be wrapped as a response-
    letter without needing an arc.

    The response-letter primitive takes a ``ResponseLetter`` and writes
    markdown + receipts. There is no dependency on lineage_result. The
    no-arc deep-think pattern most relevant here: a single reviewer
    comment + a one-paragraph argument the crosstalk synthesizer drafted.
    """
    # Imagine the crosstalk synthesizer produced this response paragraph:
    synth_response = (
        "We thank the reviewer. The CLR transformation does in fact "
        "preserve the relative ordering — see Methods §2.3 of the revision."
    )
    letter = ResponseLetter(
        reviewer=1,
        comments=[
            ReviewerComment(
                stable_id="R1-C1",
                reviewer=1,
                quote="Why CLR?",
                kind=CommentKind.METHOD_QUESTION,
                action=ActionType.ACCEPT_TEXT,
                response_text=synth_response,
                evidence_ref="§Methods, p.4",
            )
        ],
        opening="We thank the reviewer for their thoughtful comments.",
        closing="We hope these revisions are satisfactory.",
    )
    out_path = tmp_path / "response-to-R1.md"
    written = write_response_letter(out_path, letter)
    assert written.exists()
    text = written.read_text(encoding="utf-8")
    # The crosstalk-drafted prose lands in the response letter directly
    assert synth_response in text
    # And the receipts sidecar was emitted (red line #2)
    assert (tmp_path / "response-to-R1.md.provenance.json").exists()
