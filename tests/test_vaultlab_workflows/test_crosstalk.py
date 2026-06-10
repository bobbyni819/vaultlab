"""Tests for vaultlab.workflows.crosstalk — adversarial meeting wrappers.

Covers the four public meeting builders + rigor_audit + the artifact
writer. Uses a synthetic stub runner_callback so no LLM is spun up; the
runner returns canned analyst/critic/synthesizer outputs and we verify
the wrapper extracts the synthesizer's structured JSON correctly.
"""

from __future__ import annotations

import json

import pytest

from vaultlab.research.picker import CandidatePaper
from vaultlab.research.summarize import PaperSummary
from vaultlab.workflows.crosstalk import (
    MAX_N_ROUNDS,
    CrosstalkResult,
    adversarial_arc_meeting,
    adversarial_deck_plan_meeting,
    adversarial_picker_meeting,
    append_decisions_log_entry,
    rigor_audit,
    write_crosstalk_artifacts,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_candidates() -> list[CandidatePaper]:
    return [
        CandidatePaper(
            doi="10.1/found-1990",
            title="Foundational",
            authors=["Smith J"],
            year=1990,
            journal="Nature",
            abstract="Foundational discovery in the field.",
            og_score=0.7,
            forward_influence=30,
            has_pdf=True,
        ),
        CandidatePaper(
            doi="10.1/method-2010",
            title="Methodological extension",
            authors=["Doe Q"],
            year=2010,
            journal="Cell",
            abstract="A new method to apply foundations.",
            og_score=0.4,
            forward_influence=15,
            has_pdf=True,
        ),
        CandidatePaper(
            doi="10.1/sota-2024",
            title="State-of-the-art system",
            authors=["Lee R"],
            year=2024,
            journal="Science",
            abstract="A modern application of the method.",
            og_score=0.2,
            forward_influence=4,
            has_pdf=False,
        ),
    ]


def _make_summaries() -> dict[str, PaperSummary]:
    return {
        "10.1/found-1990": PaperSummary(
            doi="10.1/found-1990",
            title="Foundational",
            authors=["Smith J"],
            year=1990,
            year_bucket="history",
            tier="A",
            og_score=0.7,
            forward_influence=30,
            tldr="Foundational discovery [p1].",
            key_findings=["X showed Y [p2]"],
        ),
        "10.1/method-2010": PaperSummary(
            doi="10.1/method-2010",
            title="Method",
            authors=["Doe Q"],
            year=2010,
            year_bucket="development",
            tier="A",
            og_score=0.4,
            forward_influence=15,
            tldr="New method [p1].",
            key_findings=["Method works [p3]"],
        ),
    }


def _stub_runner_for_picker(picks_dois: list[str]) -> object:
    """Return a runner_callback that emits picker-shaped synthesizer output."""

    def _runner(meeting, roles):
        # One canned response per role. The synthesizer's output is what
        # the wrapper extracts; the others are filler.
        outputs: list[dict[str, str]] = []
        for r in roles:
            if r.id == "synthesizer":
                payload = {
                    "picks": [
                        {"doi": d, "rank": i + 1, "rationale": f"Pick {i + 1}"}
                        for i, d in enumerate(picks_dois)
                    ]
                }
                outputs.append({"output": json.dumps(payload)})
            else:
                outputs.append({"output": f"[{r.id} canned commentary]"})
        return outputs

    return _runner


def _stub_runner_for_arc() -> object:
    def _runner(meeting, roles):
        outputs: list[dict[str, str]] = []
        for r in roles:
            if r.id == "synthesizer":
                payload = {
                    "history": "History prose with [[10.1_found-1990|Smith 1990]].",
                    "development": "Development with [[10.1_method-2010|Doe 2010]].",
                    "sota": "SOTA prose.",
                }
                outputs.append({"output": json.dumps(payload)})
            else:
                outputs.append({"output": f"[{r.id} commentary]"})
        return outputs

    return _runner


def _stub_runner_for_deck_plan() -> object:
    def _runner(meeting, roles):
        outputs: list[dict[str, str]] = []
        for r in roles:
            if r.id == "synthesizer":
                payload = {
                    "story_arc_summary": "history -> development -> SOTA",
                    "slides": [
                        {
                            "type": "title",
                            "title": "Trial deck",
                            "subtitle": "Trial",
                            "author": "Bobby",
                        },
                        {
                            "type": "section_divider",
                            "title": "Background",
                        },
                        {
                            "type": "text",
                            "title": "Foundational findings",
                            "bullets": [
                                "[[10.1_found-1990|Smith 1990]]: foundational",
                            ],
                            "citations": ["10.1/found-1990"],
                        },
                    ],
                }
                outputs.append({"output": json.dumps(payload)})
            else:
                outputs.append({"output": f"[{r.id} commentary]"})
        return outputs

    return _runner


# ---------------------------------------------------------------------------
# adversarial_picker_meeting
# ---------------------------------------------------------------------------


def test_adversarial_picker_meeting_with_stub_runner() -> None:
    """The wrapper extracts the synthesizer's picks JSON cleanly."""
    candidates = _make_candidates()
    runner = _stub_runner_for_picker(["10.1/found-1990", "10.1/method-2010"])

    result = adversarial_picker_meeting(
        topic="test topic",
        candidates=candidates,
        target_n=2,
        abstracts_md="abstracts here",
        n_rounds=2,
        runner_callback=runner,
    )

    assert isinstance(result, CrosstalkResult)
    assert result.crosstalk_status == "complete"
    assert "picks" in result.final_output
    assert len(result.final_output["picks"]) == 2
    assert result.final_output["picks"][0]["doi"] == "10.1/found-1990"
    # Rounds collected — n_rounds=2 with 4 roles per round = 8 turns.
    assert len(result.rounds) == 8
    assert result.purpose == "picker"


def test_adversarial_picker_meeting_no_callback_returns_fallback() -> None:
    """Without a runner_callback, status is fallback and final_output empty."""
    result = adversarial_picker_meeting(
        topic="t",
        candidates=_make_candidates(),
        target_n=2,
        abstracts_md="",
        n_rounds=1,
        runner_callback=None,
    )
    assert result.crosstalk_status == "fallback (callback failed)"
    assert result.final_output == {}


# ---------------------------------------------------------------------------
# adversarial_arc_meeting
# ---------------------------------------------------------------------------


def test_adversarial_arc_meeting_with_stub_runner() -> None:
    summaries = _make_summaries()
    runner = _stub_runner_for_arc()

    result = adversarial_arc_meeting(
        topic="test topic",
        summaries=summaries,
        n_rounds=2,
        runner_callback=runner,
    )

    assert result.crosstalk_status == "complete"
    assert result.final_output.get("history", "").startswith("History prose")
    assert "development" in result.final_output
    assert "sota" in result.final_output
    assert result.purpose == "arc"


def _capturing_arc_runner(seen: dict):
    """An arc runner that records the meeting's session_context then completes."""

    def _runner(meeting, roles):
        seen["ctx"] = meeting.session_context
        out = []
        for r in roles:
            if r.id == "synthesizer":
                out.append(
                    {"output": json.dumps({"history": "h", "development": "d", "sota": "s"})}
                )
            else:
                out.append({"output": "x"})
        return out

    return _runner


def test_arc_meeting_injects_kb_preamble_when_project_given(tmp_path) -> None:
    """Commitment #7: with project_slug, spawned roles see the project's KB context."""
    from vaultlab.kb.paths import project_state_path

    sh = project_state_path(tmp_path, "spatial-proj")
    sh.parent.mkdir(parents=True, exist_ok=True)
    sh.write_text("# START_HERE\n\nPrior work: built the CN pipeline.\n", encoding="utf-8")

    seen: dict = {}
    result = adversarial_arc_meeting(
        topic="spatial",
        summaries=_make_summaries(),
        n_rounds=1,
        runner_callback=_capturing_arc_runner(seen),
        project_slug="spatial-proj",
        kb_root=tmp_path,
    )
    assert "Prior work: built the CN pipeline." in seen["ctx"]  # preamble reached the meeting
    assert "Project context preamble" in seen["ctx"]
    assert result.crosstalk_status == "complete"


def test_arc_meeting_no_preamble_without_project_slug(tmp_path) -> None:
    """Default (no project_slug) is unchanged — no preamble, backward compatible."""
    seen: dict = {}
    adversarial_arc_meeting(
        topic="spatial",
        summaries=_make_summaries(),
        n_rounds=1,
        runner_callback=_capturing_arc_runner(seen),
    )
    assert "Project context preamble" not in seen["ctx"]


# ---------------------------------------------------------------------------
# adversarial_deck_plan_meeting
# ---------------------------------------------------------------------------


def test_adversarial_deck_plan_meeting_with_stub_runner(tmp_path) -> None:
    summaries = _make_summaries()
    fig_path = tmp_path / "fig.png"
    fig_path.write_bytes(b"\x89PNG\r\n\x1a\n")
    runner = _stub_runner_for_deck_plan()

    result = adversarial_deck_plan_meeting(
        topic="test topic",
        summaries=summaries,
        figure_assignments={"10.1/found-1990": fig_path},
        target_slide_count=3,
        n_rounds=2,
        runner_callback=runner,
    )

    assert result.crosstalk_status == "complete"
    assert "slides" in result.final_output
    assert len(result.final_output["slides"]) == 3
    assert result.final_output["slides"][0]["type"] == "title"
    assert result.purpose == "deck-plan"


def test_adversarial_deck_plan_meeting_loads_narrator_and_figure_lead(
    tmp_path,
) -> None:
    """G-1 regression: deck-plan meeting must instantiate the deck-pipeline
    roles (``narrator`` + ``figure_lead``), not the Mode.DATA_ANALYSIS
    default (``data_analyst`` + ``domain_expert``).

    The runner_callback receives ``(meeting, list(meeting.roles))`` —
    we capture that argument and assert on the role IDs directly.
    """
    summaries = _make_summaries()
    fig_path = tmp_path / "fig.png"
    fig_path.write_bytes(b"\x89PNG\r\n\x1a\n")

    captured_roles: list[list[str]] = []

    def _capturing_runner(meeting, roles):
        captured_roles.append([r.id for r in roles])
        # Mirror _stub_runner_for_deck_plan so the wrapper still
        # extracts a structured synthesizer payload.
        outputs: list[dict[str, str]] = []
        for r in roles:
            if r.id == "synthesizer":
                payload = {
                    "story_arc_summary": "h -> d -> s",
                    "slides": [
                        {"type": "title", "title": "T", "subtitle": "", "author": "B"},
                    ],
                }
                outputs.append({"output": json.dumps(payload)})
            else:
                outputs.append({"output": f"[{r.id} commentary]"})
        return outputs

    result = adversarial_deck_plan_meeting(
        topic="test topic",
        summaries=summaries,
        figure_assignments={"10.1/found-1990": fig_path},
        target_slide_count=1,
        n_rounds=1,
        runner_callback=_capturing_runner,
    )

    assert result.crosstalk_status == "complete"
    # Captured at least once (one round).
    assert captured_roles, "runner_callback was never invoked"
    role_ids = captured_roles[0]
    # The deck-pipeline roles MUST be instantiated.
    assert "narrator" in role_ids, f"deck-plan meeting did not load 'narrator' role; got {role_ids}"
    assert "figure_lead" in role_ids, (
        f"deck-plan meeting did not load 'figure_lead' role; got {role_ids}"
    )
    # And the wrong roles must NOT be present (this is the regression).
    assert "data_analyst" not in role_ids, (
        f"deck-plan meeting loaded 'data_analyst' (Mode.DATA_ANALYSIS "
        f"default) instead of 'narrator'; got {role_ids}"
    )
    assert "domain_expert" not in role_ids, (
        f"deck-plan meeting loaded 'domain_expert' (Mode.DATA_ANALYSIS "
        f"default) instead of 'figure_lead'; got {role_ids}"
    )
    # Critic + synthesizer round out the meeting.
    assert "methods_critic" in role_ids
    assert "synthesizer" in role_ids


# ---------------------------------------------------------------------------
# rigor_audit
# ---------------------------------------------------------------------------


def test_rigor_audit_catches_unverified_claim() -> None:
    """Auditor returns blocker issue for ungrounded [p3] claim."""

    def _runner(meeting, roles):
        # Auditor flags a fake page reference.
        payload = {
            "passed": False,
            "issues": [
                {
                    "loc": "Foundational findings slide",
                    "severity": "blocker",
                    "kind": "missing_page",
                    "fix": "[p3] does not resolve in the source summary.",
                }
            ],
        }
        return [{"output": json.dumps(payload)}]

    out = rigor_audit(
        document="Smith showed X [p3].",
        summaries=_make_summaries(),
        audit_kind="deck",
        runner_callback=_runner,
    )

    assert out["passed"] is False
    assert len(out["issues"]) == 1
    assert out["issues"][0]["severity"] == "blocker"
    assert out["issues"][0]["kind"] == "missing_page"


def test_rigor_audit_passes_clean_doc() -> None:
    """Auditor returns passed=True with no issues for a clean doc."""

    def _runner(meeting, roles):
        return [{"output": json.dumps({"passed": True, "issues": []})}]

    out = rigor_audit(
        document="Clean doc.",
        summaries=_make_summaries(),
        audit_kind="deck",
        runner_callback=_runner,
    )

    assert out["passed"] is True
    assert out["issues"] == []


def test_rigor_audit_no_callback_returns_skipped_minor_issue() -> None:
    out = rigor_audit(
        document="anything",
        summaries={},
        audit_kind="deck",
        runner_callback=None,
    )
    assert out["passed"] is True
    assert any("skipped" in i["fix"] for i in out["issues"])


def test_rigor_audit_invalid_audit_kind_raises() -> None:
    with pytest.raises(ValueError):
        rigor_audit(
            document="x",
            summaries={},
            audit_kind="bogus",
            runner_callback=None,
        )


def test_rigor_audit_methods_kind_accepted() -> None:
    """audit_kind='methods' is accepted and routes through a real audit path."""
    captured: dict = {}
    rigor_audit(
        document="methods paragraph",
        summaries={},
        audit_kind="methods",
        producer_kind="vaultlab.analysis.run_pipeline",
        runner_callback=_capture_context_runner(captured),
    )
    # No ValueError, and the meeting context is actually assembled for "methods".
    assert "AUDIT KIND: methods" in captured["context"]
    # A non-template producer_kind must NOT trigger the downgrade.
    assert "TEMPLATE-ONLY DOWNGRADE" not in captured["context"]


def _capture_context_runner(captured: dict) -> object:
    def _runner(meeting, roles):
        captured["context"] = meeting.session_context
        return [{"output": json.dumps({"passed": True, "issues": []})}]

    return _runner


def test_rigor_audit_reads_producer_from_sidecar(tmp_path) -> None:
    """rigor_audit populates producer_kind from the document's sidecar."""
    from vaultlab.provenance import ProvenanceRecord, write_receipts

    doc = tmp_path / "methods.md"
    doc.write_text("methods text", encoding="utf-8")
    write_receipts(
        doc,
        ProvenanceRecord(
            generated_by="vaultlab.analysis.run_pipeline",
            kind="methods_section",
            producer="template-only",
        ),
    )

    captured: dict = {}
    rigor_audit(
        document="methods text",
        document_path=str(doc),
        audit_kind="methods",
        runner_callback=_capture_context_runner(captured),
    )
    assert "PRODUCER KIND: template-only" in captured["context"]


def test_rigor_audit_explicit_producer_kind_wins(tmp_path) -> None:
    """An explicit producer_kind arg overrides the sidecar value."""
    from vaultlab.provenance import ProvenanceRecord, write_receipts

    doc = tmp_path / "methods.md"
    doc.write_text("methods text", encoding="utf-8")
    write_receipts(
        doc,
        ProvenanceRecord(generated_by="x", kind="methods_section", producer="template-only"),
    )

    captured: dict = {}
    rigor_audit(
        document="methods text",
        document_path=str(doc),
        audit_kind="methods",
        producer_kind="explicit-wins",
        runner_callback=_capture_context_runner(captured),
    )
    assert "PRODUCER KIND: explicit-wins" in captured["context"]
    assert "template-only" not in captured["context"]


def test_template_only_injects_downgrade_directive() -> None:
    """producer_kind='template-only' injects the Task-5 downgrade directive."""
    captured: dict = {}
    rigor_audit(
        document="`y` appears higher in `a` than `b`; recomputed p=0.01.",
        audit_kind="methods",
        producer_kind="template-only",
        runner_callback=_capture_context_runner(captured),
    )
    ctx = captured["context"]
    assert "TEMPLATE-ONLY DOWNGRADE" in ctx
    assert "skip Tasks 1-3" in ctx
    assert "Task 4" in ctx


def test_non_template_no_downgrade_directive() -> None:
    """Empty producer_kind keeps full grading — no downgrade injected."""
    captured: dict = {}
    rigor_audit(
        document="Smith showed X.",
        audit_kind="report",
        runner_callback=_capture_context_runner(captured),
    )
    ctx = captured["context"]
    assert "TEMPLATE-ONLY DOWNGRADE" not in ctx
    assert "PRODUCER KIND: (unspecified)" in ctx


def test_rigor_audit_overrides_passed_when_blockers_present() -> None:
    """If auditor incorrectly says passed=True but blockers exist, override."""

    def _runner(meeting, roles):
        payload = {
            "passed": True,
            "issues": [
                {
                    "loc": "x",
                    "severity": "blocker",
                    "kind": "ungrounded_claim",
                    "fix": "fix",
                }
            ],
        }
        return [{"output": json.dumps(payload)}]

    out = rigor_audit(
        document="x",
        summaries={},
        audit_kind="arc",
        runner_callback=_runner,
    )
    assert out["passed"] is False


# ---------------------------------------------------------------------------
# Hard caps + timeouts
# ---------------------------------------------------------------------------


def test_n_rounds_capped_at_max() -> None:
    with pytest.raises(ValueError) as excinfo:
        adversarial_picker_meeting(
            topic="t",
            candidates=_make_candidates(),
            target_n=2,
            abstracts_md="",
            n_rounds=MAX_N_ROUNDS + 1,
            runner_callback=_stub_runner_for_picker(["10.1/found-1990"]),
        )
    assert "MAX_N_ROUNDS" in str(excinfo.value)


def test_n_rounds_must_be_positive() -> None:
    with pytest.raises(ValueError):
        adversarial_picker_meeting(
            topic="t",
            candidates=_make_candidates(),
            target_n=2,
            abstracts_md="",
            n_rounds=0,
            runner_callback=_stub_runner_for_picker(["10.1/found-1990"]),
        )


def test_timeout_returns_partial_result() -> None:
    """A meeting that exceeds wall-clock budget reports incomplete status."""
    import time

    def _slow_runner(meeting, roles):
        time.sleep(0.1)
        return [{"output": "(too slow)"} for _ in roles]

    result = adversarial_picker_meeting(
        topic="t",
        candidates=_make_candidates(),
        target_n=2,
        abstracts_md="",
        n_rounds=3,
        timeout_seconds=0,  # immediate timeout
        runner_callback=_slow_runner,
    )
    # With timeout=0 the first round may complete but subsequent rounds
    # should be cut off; status must reflect incomplete OR fallback.
    assert result.crosstalk_status in {
        "incomplete (timeout)",
        "fallback (callback failed)",
    }


def test_runner_callback_exception_yields_fallback() -> None:
    def _bad_runner(meeting, roles):
        raise RuntimeError("boom")

    result = adversarial_picker_meeting(
        topic="t",
        candidates=_make_candidates(),
        target_n=2,
        abstracts_md="",
        n_rounds=2,
        runner_callback=_bad_runner,
    )
    assert result.crosstalk_status == "fallback (callback failed)"


def test_runner_callback_non_list_yields_fallback() -> None:
    def _bad_runner(meeting, roles):
        return "not a list"

    result = adversarial_picker_meeting(
        topic="t",
        candidates=_make_candidates(),
        target_n=2,
        abstracts_md="",
        n_rounds=2,
        runner_callback=_bad_runner,
    )
    assert result.crosstalk_status == "fallback (callback failed)"


# ---------------------------------------------------------------------------
# write_crosstalk_artifacts
# ---------------------------------------------------------------------------


def test_write_crosstalk_artifacts_writes_transcript_and_turns(tmp_path) -> None:
    candidates = _make_candidates()
    runner = _stub_runner_for_picker(["10.1/found-1990", "10.1/method-2010"])
    result = adversarial_picker_meeting(
        topic="t",
        candidates=candidates,
        target_n=2,
        abstracts_md="",
        n_rounds=1,
        runner_callback=runner,
    )

    paths = write_crosstalk_artifacts(result, run_dir=tmp_path)

    transcript = paths["transcript"]
    assert transcript.exists()
    text = transcript.read_text(encoding="utf-8")
    assert "Crosstalk meeting" in text
    assert "synthesizer" in text

    # Per-turn files are present and contain the role's output.
    turn_files = list(tmp_path.glob("meeting-picker-turn-*.md"))
    assert len(turn_files) == len(result.rounds)


def test_append_decisions_log_entry_creates_or_appends(tmp_path) -> None:
    log_path = tmp_path / "decisions-log.md"
    runner = _stub_runner_for_picker(["10.1/found-1990"])
    result = adversarial_picker_meeting(
        topic="t",
        candidates=_make_candidates(),
        target_n=1,
        abstracts_md="",
        n_rounds=1,
        runner_callback=runner,
    )

    p1 = append_decisions_log_entry(
        decisions_log_path=log_path,
        purpose="picker",
        n_rounds=1,
        result=result,
        summary_line="Final picks: 1",
        run_id="20260430T120000",
    )
    assert p1.exists()
    text1 = p1.read_text(encoding="utf-8")
    assert "picker meeting" in text1
    assert "Final picks: 1" in text1

    p2 = append_decisions_log_entry(
        decisions_log_path=log_path,
        purpose="arc",
        n_rounds=2,
        result=result,
        run_id="20260430T120000",
    )
    text2 = p2.read_text(encoding="utf-8")
    assert "picker meeting" in text2  # earlier entry preserved
    assert "arc meeting" in text2  # new entry added


# ---------------------------------------------------------------------------
# JSON extraction edge cases
# ---------------------------------------------------------------------------


def test_synthesizer_with_fenced_json_still_parsed() -> None:
    """If synthesizer wraps JSON in ```json ... ``` fences, we still parse."""

    def _runner(meeting, roles):
        outs = []
        for r in roles:
            if r.id == "synthesizer":
                wrapped = (
                    "```json\n"
                    + json.dumps(
                        {"picks": [{"doi": "10.1/found-1990", "rank": 1, "rationale": "x"}]}
                    )
                    + "\n```"
                )
                outs.append({"output": wrapped})
            else:
                outs.append({"output": "x"})
        return outs

    result = adversarial_picker_meeting(
        topic="t",
        candidates=_make_candidates(),
        target_n=1,
        abstracts_md="",
        n_rounds=1,
        runner_callback=_runner,
    )
    assert result.crosstalk_status == "complete"
    assert result.final_output["picks"][0]["doi"] == "10.1/found-1990"


def test_synthesizer_with_preamble_then_json_still_parsed() -> None:
    """If synthesizer prefaces JSON with prose, we still extract it."""

    def _runner(meeting, roles):
        outs = []
        for r in roles:
            if r.id == "synthesizer":
                payload = {"picks": [{"doi": "10.1/method-2010", "rank": 1, "rationale": "x"}]}
                outs.append({"output": "Sure, here is the result:\n" + json.dumps(payload)})
            else:
                outs.append({"output": "x"})
        return outs

    result = adversarial_picker_meeting(
        topic="t",
        candidates=_make_candidates(),
        target_n=1,
        abstracts_md="",
        n_rounds=1,
        runner_callback=_runner,
    )
    assert result.crosstalk_status == "complete"
    assert result.final_output["picks"][0]["doi"] == "10.1/method-2010"
