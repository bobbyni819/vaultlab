from __future__ import annotations

from vaultlab.projects.analysis_planning import (
    AnalysisOpportunity,
    AnalysisOpportunityAudit,
    AnalysisOpportunityProblem,
    find_coverage_gaps,
)
from vaultlab.projects.data_inventory import AccessStatus, DataInventory, DatasetRecord
from vaultlab.projects.figure_plan import FigurePlan, SubpanelPlan, SupplementPlan, SupportRole


def _dataset(dataset_id: str, access: AccessStatus = AccessStatus.AVAILABLE) -> DatasetRecord:
    return DatasetRecord(
        dataset_id=dataset_id,
        modality="synthetic-imaging",
        scale="region",
        unit_coverage=["D1", "D2", "R1", "R2"],
        replication_unit="donor",
        location=f"datasets/{dataset_id}.csv",
        fmt="csv",
        size_bytes=256,
        processing_stage="normalized",
        access=access,
        caveats=[],
    )


def _subpanel(subpanel_id: str, letter: str, source_result: str) -> SubpanelPlan:
    return SubpanelPlan(
        subpanel_id=subpanel_id,
        figure_id="Fig1",
        letter=letter,
        concept=f"synthetic concept {letter}",
        plot_type="heatmap",
        source_result=source_result,
        analysis_script=f"analysis/{letter}.py",
        plot_script=f"plots/{letter}.py",
        output_figure=f"figures/{letter}.png",
        manifest_path=f"figures/{letter}.coverage.json",
        layout_sidecar_path=f"figures/{letter}.png.layout.json",
        visual_qa_path=f"figures/{letter}.visual-qa.json",
        provenance_path=f"figures/{letter}.method.md",
        panel_slot_id=letter,
        claim_id=f"claim-{letter}",
        supplement_ids=[],
    )


def _plan() -> FigurePlan:
    return FigurePlan(
        figure_id="Fig1",
        purpose="Synthetic figure plan for tests.",
        reading_order=["A", "B"],
        subpanel_ids=["fig1-a", "fig1-b"],
        supplement_ids=[],
        required_analyses=["analysis-A", "analysis-B"],
        open_decisions=[],
    )


def test_find_coverage_gaps_emits_negative_control_donor_support_and_missing_data() -> None:
    inventory = DataInventory(datasets=[_dataset("DS1")])
    opportunities = find_coverage_gaps(
        _plan(),
        [_subpanel("fig1-a", "A", "DS1"), _subpanel("fig1-b", "B", "DS2")],
        [],
        inventory,
    )

    ids = [opportunity.opportunity_id for opportunity in opportunities]

    assert ids == [
        "missing-dataset-ds2",
        "fig1-negative-control",
        "fig1-a-donor-aware-support",
        "fig1-b-donor-aware-support",
    ]
    missing_dataset = opportunities[0]
    negative_control = opportunities[1]
    donor_b = opportunities[3]
    assert missing_dataset.data_needed == ["DS2"]
    assert missing_dataset.data_status == "needs_collection"
    assert negative_control.supplement_destination == "negative_control"
    assert negative_control.data_status == "needs_collection"
    assert donor_b.figure_destination == "Fig1/B"
    assert donor_b.data_needed == ["DS2"]
    assert donor_b.data_status == "needs_collection"


def test_find_coverage_gaps_success_path_with_controls_and_inventory() -> None:
    subpanels = [_subpanel("fig1-a", "A", "DS1")]
    supplements = [
        SupplementPlan(
            supplement_id="S-neg",
            archive_role="negative_control",
            support_role=SupportRole.NEGATIVE_CONTROL,
            output_figure="supp/S-neg.png",
            manifest_path="supp/S-neg.coverage.json",
        ),
        SupplementPlan(
            supplement_id="S-donor",
            parent_subpanel_id="fig1-a",
            support_role=SupportRole.ROBUSTNESS,
            output_figure="supp/S-donor.png",
            manifest_path="supp/S-donor.coverage.json",
        ),
    ]

    opportunities = find_coverage_gaps(
        FigurePlan(
            figure_id="Fig1",
            purpose="Synthetic figure plan for tests.",
            reading_order=["A"],
            subpanel_ids=["fig1-a"],
            supplement_ids=["S-neg", "S-donor"],
            required_analyses=["analysis-A"],
            open_decisions=[],
        ),
        subpanels,
        supplements,
        DataInventory(datasets=[_dataset("DS1")]),
    )

    assert opportunities == []


def test_analysis_opportunity_validate_and_round_trip() -> None:
    opportunity = AnalysisOpportunity(
        opportunity_id="fig1-a-donor-aware-support",
        question="Add donor-aware robustness support for Fig1/A.",
        claim_supported="claim-A",
        data_needed=["DS1"],
        data_status="available",
        method="stratify by donor",
        rigor_note="Controls donor-level replication.",
        failure_mode_controlled="donor_confounding",
        figure_destination="Fig1/A",
        supplement_destination="donor_aware_support",
        compute_estimate="local",
        risk="medium",
        priority=30,
    )
    problem = AnalysisOpportunityProblem("warn", "synthetic warning", field="priority")
    audit = AnalysisOpportunityAudit("warn", [problem])

    assert opportunity.validate() == []
    assert AnalysisOpportunity.from_dict(opportunity.to_dict()) == opportunity
    assert AnalysisOpportunityProblem.from_dict(problem.to_dict()) == problem
    assert AnalysisOpportunityAudit.from_dict(audit.to_dict()) == audit


def test_analysis_opportunity_validate_flags_required_fields_and_priority() -> None:
    opportunity = AnalysisOpportunity(
        opportunity_id="",
        question="",
        claim_supported=None,
        data_needed=[],
        data_status="",
        method="",
        rigor_note="",
        failure_mode_controlled="",
        figure_destination=None,
        supplement_destination=None,
        compute_estimate=None,
        risk="",
        priority=-1,
    )

    messages = opportunity.validate()

    assert "analysis opportunity <missing> missing required field: opportunity_id" in messages
    assert "analysis opportunity <missing> missing required field: question" in messages
    assert "analysis opportunity <missing> missing required field: data_status" in messages
    assert "analysis opportunity <missing> missing required field: method" in messages
    assert "analysis opportunity <missing> missing required field: rigor_note" in messages
    assert "analysis opportunity <missing> missing required field: failure_mode_controlled" in messages
    assert "analysis opportunity <missing> missing required field: risk" in messages
    assert "analysis opportunity <missing> priority must be non-negative" in messages
    assert "analysis opportunity <missing> needs figure_destination or supplement_destination" in messages

