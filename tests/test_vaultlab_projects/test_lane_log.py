from __future__ import annotations

from vaultlab.projects.lane_log import (
    Lane,
    LaneHandoff,
    LaneLogAudit,
    LaneLogProblem,
    LanePairStatus,
    LaneStatusReport,
    ReadReceipt,
    merge_handoffs,
    validate_handoff,
)


def _receipt(file_path: str = "Wiki/Projects/Fig1/START_HERE.md") -> ReadReceipt:
    return ReadReceipt(
        file_path=file_path,
        role="reviewer",
        sections_read=["Overview", "Lineage runs"],
        key_facts=["Synthetic fact from Fig1 planning state."],
        timestamp="2026-06-29T10:00:00Z",
    )


def _handoff(status: str = "ready") -> LaneHandoff:
    return LaneHandoff(
        source=Lane.FIGURES,
        target=Lane.REVIEW,
        status=status,
        artifacts=["figures/Fig1.png"],
        verification=["pytest tests/test_vaultlab_projects/ -q"],
        downstream_request="Review synthetic Fig1 layout.",
        open_decisions=[],
        read_receipts=[_receipt()],
    )


def test_validate_handoff_success_and_merge_by_lane_pair() -> None:
    handoff = _handoff()

    messages = validate_handoff(handoff, required_reads=["Wiki/Projects/Fig1/START_HERE.md"])
    report = merge_handoffs([handoff, _handoff(status="accepted")])
    key = (Lane.FIGURES, Lane.REVIEW)

    assert messages == []
    assert key in report.lane_pairs
    assert report.lane_pairs[key].handoff_count == 2
    assert report.lane_pairs[key].latest_status == "accepted"
    assert report.lane_pairs[key].artifacts == ["figures/Fig1.png"]
    assert LaneHandoff.from_dict(handoff.to_dict()) == handoff
    assert LaneStatusReport.from_dict(report.to_dict()) == report


def test_validate_handoff_flags_missing_required_read_and_non_draft_verification() -> None:
    handoff = LaneHandoff(
        source=Lane.COMPUTE,
        target=Lane.FIGURES,
        status="ready",
        artifacts=["Output/Fig1/result.csv"],
        verification=[],
        downstream_request="Render synthetic Fig1 panel.",
        open_decisions=[],
        read_receipts=[_receipt("Wiki/Projects/Fig1/papers.md")],
    )

    messages = validate_handoff(handoff, required_reads=["Wiki/Projects/Fig1/START_HERE.md"])

    assert "handoff compute->figures missing verification for non-draft status: ready" in messages
    assert "handoff compute->figures missing required read receipt: Wiki/Projects/Fig1/START_HERE.md" in messages
    assert handoff.audit().ok() is False


def test_read_receipt_validate_flags_missing_sections_and_facts() -> None:
    receipt = ReadReceipt(
        file_path="Wiki/Projects/Fig1/START_HERE.md",
        role="reviewer",
        sections_read=[],
        key_facts=[],
        timestamp="2026-06-29T10:00:00Z",
    )

    problems = receipt.validate()

    assert "read receipt Wiki/Projects/Fig1/START_HERE.md missing sections_read" in problems
    assert "read receipt Wiki/Projects/Fig1/START_HERE.md missing key_facts" in problems
    assert receipt.audit().ok() is False


def test_validate_handoff_allows_draft_without_verification() -> None:
    handoff = LaneHandoff(
        source=Lane.SANDBOX,
        target=Lane.STORYLINE,
        status="draft",
        artifacts=[],
        verification=[],
        downstream_request="Draft synthetic storyline options.",
        open_decisions=["Choose synthetic storyline order."],
        read_receipts=[],
    )

    assert validate_handoff(handoff) == []


def test_lane_log_records_and_audits_round_trip() -> None:
    receipt = _receipt()
    pair = LanePairStatus(
        source=Lane.FIGURES,
        target=Lane.REVIEW,
        handoff_count=1,
        latest_status="ready",
        artifacts=["figures/Fig1.png"],
        verification=["pytest tests/test_vaultlab_projects/ -q"],
        open_decisions=[],
    )
    problem = LaneLogProblem("warn", "synthetic warning", field="status")
    audit = LaneLogAudit("warn", [problem])

    assert ReadReceipt.from_dict(receipt.to_dict()) == receipt
    assert LanePairStatus.from_dict(pair.to_dict()) == pair
    assert LaneLogProblem.from_dict(problem.to_dict()) == problem
    assert LaneLogAudit.from_dict(audit.to_dict()) == audit

