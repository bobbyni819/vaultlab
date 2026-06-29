from __future__ import annotations

from pathlib import Path

from vaultlab.projects.figure_plan import (
    FigurePlan,
    SubpanelPlan,
    SubpanelReadiness,
    SupplementPlan,
    SupportRole,
    dump_plan,
    load_plan,
    validate_figure_plan,
)


def _subpanel(
    subpanel_id: str,
    letter: str,
    *,
    claim_id: str | None = None,
    supplement_ids: list[str] | None = None,
) -> SubpanelPlan:
    return SubpanelPlan(
        subpanel_id=subpanel_id,
        figure_id="Fig1",
        letter=letter,
        concept=f"synthetic concept {letter}",
        plot_type="heatmap",
        source_result=f"results/{letter}.csv",
        analysis_script=f"analysis/{letter}.py",
        plot_script=f"plots/{letter}.py",
        output_figure=f"figures/{letter}.png",
        manifest_path=f"figures/{letter}.coverage.json",
        layout_sidecar_path=f"figures/{letter}.png.layout.json",
        visual_qa_path=f"figures/{letter}.visual-qa.json",
        provenance_path=f"figures/{letter}.method.md",
        panel_slot_id=letter,
        claim_id=claim_id or f"claim-{letter}",
        supplement_ids=list(supplement_ids or []),
        readiness=SubpanelReadiness.DISPLAY_EXISTS,
    )


def _valid_fixture() -> tuple[FigurePlan, list[SubpanelPlan], list[SupplementPlan]]:
    subpanels = [
        _subpanel("fig1-a", "A", supplement_ids=["SA"]),
        _subpanel("fig1-b", "B"),
        _subpanel("fig1-c", "C"),
    ]
    supplements = [
        SupplementPlan(
            supplement_id="SA",
            parent_subpanel_id="fig1-a",
            support_role=SupportRole.PARAMETER_SWEEP,
            output_figure="supp/SA.png",
            manifest_path="supp/SA.coverage.json",
            notes="Synthetic parameter sweep.",
        ),
        SupplementPlan(
            supplement_id="archive-1",
            archive_role="exploratory_archive",
            support_role=SupportRole.EXPLORATORY_ARCHIVE,
            output_figure="supp/archive-1.png",
            manifest_path="supp/archive-1.coverage.json",
            notes="Synthetic archived exploratory view.",
        ),
    ]
    plan = FigurePlan(
        figure_id="Fig1",
        purpose="Synthetic figure plan for tests.",
        reading_order=["A", "B", "C"],
        subpanel_ids=["fig1-a", "fig1-b", "fig1-c"],
        supplement_ids=["SA", "archive-1"],
        required_analyses=["analysis-A", "analysis-B"],
        open_decisions=[],
    )
    return plan, subpanels, supplements


def test_figure_plan_round_trips_json_bundle(tmp_path: Path) -> None:
    plan, subpanels, supplements = _valid_fixture()

    audit = validate_figure_plan(plan, subpanels, supplements)
    assert audit.ok() is True
    assert audit.overall_severity == "pass"

    out = dump_plan(plan, subpanels, supplements, tmp_path / "fig1.plan.json")
    loaded_plan, loaded_subpanels, loaded_supplements = load_plan(out)

    assert loaded_plan == plan
    assert loaded_subpanels == subpanels
    assert loaded_supplements == supplements


def test_load_plan_rejects_mismatched_schema(tmp_path: Path) -> None:
    import json

    import pytest

    plan, subpanels, supplements = _valid_fixture()
    path = dump_plan(plan, subpanels, supplements, tmp_path / "fig1.plan.json")
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["schema"] = "vaultlab-figure-plan/v0"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="unsupported figure plan schema"):
        load_plan(path)


def test_figure_plan_audit_flags_missing_refs_orphans_duplicates_and_bad_ids() -> None:
    plan, subpanels, supplements = _valid_fixture()
    broken_plan = FigurePlan(
        figure_id=plan.figure_id,
        purpose=plan.purpose,
        reading_order=["A", "D"],
        subpanel_ids=["fig1-a", "fig1-missing"],
        supplement_ids=["SA", "missing-supp"],
        required_analyses=plan.required_analyses,
        open_decisions=plan.open_decisions,
    )
    broken_subpanels = [
        subpanels[0],
        SubpanelPlan.from_dict({**subpanels[1].to_dict(), "letter": "A", "panel_slot_id": "slot A"}),
        SubpanelPlan.from_dict({**subpanels[2].to_dict(), "claim_id": "claim C with spaces"}),
    ]
    broken_supplements = [
        supplements[0],
        SupplementPlan(
            supplement_id="orphan",
            support_role=SupportRole.ROBUSTNESS,
            output_figure="supp/orphan.png",
            manifest_path="supp/orphan.coverage.json",
        ),
    ]

    audit = validate_figure_plan(broken_plan, broken_subpanels, broken_supplements)

    assert audit.ok() is False
    assert audit.overall_severity == "fail"
    messages = [problem.message for problem in audit.problems]
    assert "figure plan references missing subpanel_id: fig1-missing" in messages
    assert "reading_order letter not present in referenced subpanels: D" in messages
    assert "duplicate subpanel figure/letter pair: Fig1/A" in messages
    assert "figure plan references missing supplement_id: missing-supp" in messages
    assert "supplement orphan is orphaned: set parent_subpanel_id or archive_role" in messages
    assert "subpanel fig1-b has malformed panel_slot_id: slot A" in messages
    assert "subpanel fig1-c has malformed claim_id: claim C with spaces" in messages


def test_figure_plan_audit_flags_subpanel_referencing_missing_supplement() -> None:
    subpanels = [_subpanel("fig1-a", "A", supplement_ids=["nonexistent-supp"])]
    plan = FigurePlan(
        figure_id="Fig1",
        purpose="Synthetic figure plan for tests.",
        reading_order=["A"],
        subpanel_ids=["fig1-a"],
        supplement_ids=[],
        required_analyses=[],
        open_decisions=[],
    )

    audit = validate_figure_plan(plan, subpanels, [])

    assert audit.ok() is False
    messages = [problem.message for problem in audit.problems]
    assert "subpanel fig1-a references missing supplement_id: nonexistent-supp" in messages
