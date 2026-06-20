"""Tests for the manuscript verification ladder."""

from __future__ import annotations

import json
from pathlib import Path

from vaultlab.manuscript.verification_ladder import (
    LadderRung,
    assess_verification_ladder,
)


def test_claim_ladder_tracks_strict_mixed_claim_rungs(tmp_path: Path) -> None:
    coverage_dir = tmp_path / "coverage"
    coverage_dir.mkdir()
    (coverage_dir / "figR1.coverage.json").write_text(
        json.dumps({"figure_id": "figR1", "script_path": "scripts/figR1.py"}),
        encoding="utf-8",
    )
    manuscript = """
    [CLAIM:c1 kind=quantitative section=Results] Tier-one evidence exists.
    [CITE:smith2020 tier=1]

    [CLAIM:c2 kind=quantitative section=Results] Full-text quote exists.
    [CITE:lee2021 tier=3]

    [CLAIM:c3 kind=quantitative section=Results] Full-text quote and rendered figure exist.
    [CITE:nguyen2022 tier=3]
    [FIG:figR1]
    """

    report = assess_verification_ladder(manuscript, coverage_dir=coverage_dir)

    by_claim = {item.claim_id: item for item in report.claim_rungs}
    assert by_claim["c1"].rung is LadderRung.SOURCE_SEARCHED
    assert by_claim["c1"].next_blocker is not None
    assert "Tier-3" in by_claim["c1"].next_blocker
    assert by_claim["c2"].rung is LadderRung.QUOTE_BACKED
    assert by_claim["c2"].next_blocker is not None
    assert "figure" in by_claim["c2"].next_blocker
    assert by_claim["c3"].rung is LadderRung.RENDERED
    assert report.min_claim_rung is LadderRung.SOURCE_SEARCHED
    assert report.summary == {
        "PROPOSED": 0,
        "SOURCE_SEARCHED": 1,
        "QUOTE_BACKED": 1,
        "RENDERED": 1,
        "PIXEL_AUDITED": 0,
        "REVIEWER_APPROVED": 0,
    }


def test_to_markdown_renders_weakest_claim_dashboard(tmp_path: Path) -> None:
    coverage_dir = tmp_path / "coverage"
    coverage_dir.mkdir()
    (coverage_dir / "figR1.coverage.json").write_text("{}", encoding="utf-8")
    manuscript = """
    [CLAIM:c1 kind=quantitative] Needs full-text quote.
    [CITE:smith2020 tier=1]

    [CLAIM:c2 kind=quantitative] Rendered figure supports this claim.
    [CITE:lee2021 tier=3] [FIG:figR1]
    """

    report = assess_verification_ladder(manuscript, coverage_dir=coverage_dir)
    rendered = report.to_markdown()

    assert "# Verification Ladder Dashboard" in rendered
    assert "weakest claim" in rendered
    assert "`SOURCE_SEARCHED`" in rendered
    assert "| c1 | SOURCE_SEARCHED |" in rendered
    assert "| figR1 | RENDERED |" in rendered


def test_missing_inputs_never_crash_and_cap_claim_at_quote_backed() -> None:
    manuscript = """
    [CLAIM:c1 kind=quantitative] This claim has a quote but no figure file.
    [CITE:lee2021 tier=3] [FIG:figMissing]
    """

    report = assess_verification_ladder(manuscript)

    assert report.claim_rungs[0].rung is LadderRung.QUOTE_BACKED
    assert report.figure_rungs[0].rung is LadderRung.PROPOSED
    assert report.figure_rungs[0].next_blocker is not None
