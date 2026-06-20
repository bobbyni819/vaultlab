"""Tests for vaultlab.manuscript.figure_text_consistency."""

from __future__ import annotations

from pathlib import Path

from vaultlab.figures.publication.coverage import CoverageManifest
from vaultlab.manuscript.claim_ledger import ClaimLedger
from vaultlab.manuscript.figure_text_consistency import (
    check_figure_text_consistency,
    find_figure_callouts,
)


def test_find_figure_callouts_parses_tags_and_prose_refs():
    text = """
    [CLAIM:c1] Signal was localized. [FIG:5]
    Figure 5C reports the lipid image.
    The validation cohort is summarized in Fig. 6.
    """

    callouts = find_figure_callouts(text)

    observed = [(callout.figure_id, callout.panel, callout.line_number) for callout in callouts]
    assert ("5", None, 2) in observed
    assert ("5", "C", 3) in observed
    assert ("6", None, 4) in observed


def test_missing_figure_callout_reports_missing_figure(tmp_path: Path):
    report = check_figure_text_consistency(
        "The result is shown in Figure 5C.",
        figures_dir=tmp_path,
        coverage_dir=tmp_path,
    )

    assert not report.ok
    assert any(problem.kind == "missing_figure" and problem.figure_id == "5" for problem in report.problems)


def test_identity_contradiction_flags_553_sulfatide_vs_pi(tmp_path: Path):
    CoverageManifest(
        figure_id="5",
        script_path="make_fig5.py",
        footer="m/z 553.28 sulfatide",
        params={"caption": "m/z 553.28 annotated as sulfatide"},
    ).to_json(tmp_path / "5.coverage.json")

    report = check_figure_text_consistency(
        "Figure 5C labels m/z 553.28 as PI in the epithelial region.",
        coverage_dir=tmp_path,
    )

    assert not report.ok
    contradictions = [problem for problem in report.problems if problem.kind == "identity_contradiction"]
    assert len(contradictions) == 1
    assert contradictions[0].figure_id == "5"
    assert "553.28" in contradictions[0].message


def test_number_mismatch_flags_contradicting_numeric_link():
    manuscript = """
    [CLAIM:c1] The association was rho=0.42 in Figure 5. [STAT:rho=0.31 src=stats.csv] [FIG:5]
    """

    report = check_figure_text_consistency(manuscript)

    assert not report.ok
    mismatches = [problem for problem in report.problems if problem.kind == "number_mismatch"]
    assert len(mismatches) == 1
    assert mismatches[0].claim_id == "c1"
    assert "rho" in mismatches[0].message


def test_fully_consistent_snippet_is_ok(tmp_path: Path):
    (tmp_path / "5.png").write_bytes(b"png")
    CoverageManifest(
        figure_id="5",
        script_path="make_fig5.py",
        footer="m/z 553.28 PI",
        params={"caption": "rho=0.31; m/z 553.28 PI"},
    ).to_json(tmp_path / "5.coverage.json")

    ledger = ClaimLedger()
    ledger.add_claim("c1", "The association was rho=0.31 in Figure 5C.")
    ledger.link_numeric("c1", "rho=0.31", "stats.csv")
    ledger.link_figure("c1", "5", panel="C")

    report = check_figure_text_consistency(
        "[CLAIM:c1] The association was rho=0.31 and m/z 553.28 PI in Figure 5C.",
        ledger=ledger,
        figures_dir=tmp_path,
        coverage_dir=tmp_path,
    )

    assert report.ok
    assert report.problems == []
