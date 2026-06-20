"""Capstone integration tests for the figure-to-manuscript pipeline."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from vaultlab.figures.contract import FigureContract
from vaultlab.figures.publication.bundle import save_publication_figure
from vaultlab.figures.publication.coverage import CoverageManifest
from vaultlab.figures.understand.visual_qa import visual_qa_figure
from vaultlab.manuscript.citation_gate import run_citation_gate
from vaultlab.manuscript.claim_ledger import ClaimLedger
from vaultlab.manuscript.data_availability import data_sources_from_coverage
from vaultlab.manuscript.figure_text_consistency import check_figure_text_consistency
from vaultlab.manuscript.preflight import run_manuscript_preflight
from vaultlab.manuscript.state import ManuscriptStage, assess_manuscript
from vaultlab.manuscript.verification_ladder import LadderRung, assess_verification_ladder


def _render_publication_bundle(tmp_path: Path) -> tuple[Path, Path, Path]:
    matplotlib = pytest.importorskip("matplotlib")
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from PIL import Image

    source_data = tmp_path / "source-data" / "fig1-values.csv"
    source_data.parent.mkdir()
    source_data.write_text("group,value\nbaseline,0.12\ntreated,0.82\n", encoding="utf-8")

    coverage = CoverageManifest(
        figure_id="1",
        script_path="tests/test_vaultlab_pipeline_e2e.py",
        timestamp="2026-06-20T12:00:00Z",
        panel_role="main",
        regions_included=["synthetic-region"],
        donors_included=["d1", "d2", "d3"],
        cell_types_included=["synthetic-cell"],
        source_data=[str(source_data)],
        source_data_sha256={str(source_data): "0" * 64},
        params={"caption": "rho=0.82; synthetic-region"},
    )
    contract = FigureContract(
        conclusion="The synthetic treatment condition has the expected higher value.",
        evidence_chain={"A": "Panel A reports the synthetic treatment statistic."},
        width_mm=89.0,
        height_mm=70.0,
        dpi=300,
        source_data_path=source_data,
        stats_block="Spearman rho=0.82 from deterministic synthetic data.",
    )

    fig, ax = plt.subplots(figsize=(3.2, 2.4), constrained_layout=True)
    ax.bar(["baseline", "treated"], [0.12, 0.82], color=["#4C78A8", "#59A14F"])
    ax.set_ylim(0, 1)
    ax.set_ylabel("association")
    ax.set_title("Synthetic association")

    bundle_dir = tmp_path / "bundle"
    result = save_publication_figure(
        fig,
        bundle_dir / "1",
        contract=contract,
        coverage=coverage,
        recipe_id="pipeline-e2e",
    )

    assert result.png.exists()
    assert result.svg.exists()
    assert result.pdf.exists()
    assert result.coverage_json is not None and result.coverage_json.exists()
    assert result.provenance_json is not None and result.provenance_json.exists()
    assert result.method_md is not None and result.method_md.exists()
    assert result.coverage_audit is not None and result.coverage_audit.ok
    with Image.open(result.png) as rendered:
        rendered.verify()

    figures_dir = tmp_path / "figures"
    coverage_dir = tmp_path / "coverage"
    figures_dir.mkdir()
    coverage_dir.mkdir()
    shutil.copyfile(result.png, figures_dir / "1.png")
    shutil.copyfile(result.coverage_json, coverage_dir / "1.coverage.json")
    return figures_dir, coverage_dir, source_data


def _happy_manuscript(source_data: Path) -> str:
    return f"""
    # Synthetic manuscript

    [CLAIM:c1 kind=quantitative section=Results] The synthetic treatment association was
    rho=0.82 in Figure 1, consistent with the source table.
    [FIG:1] [STAT:rho=0.82 src="{source_data}" method=spearman]
    [CITE:smith2026 tier=3 status=verified_fulltext]

    Figure 1 reports the deterministic synthetic association.
    """


def _blocked_manuscript(source_data: Path) -> str:
    return f"""
    # Synthetic manuscript

    [CLAIM:c1 kind=quantitative section=Results] The synthetic treatment association was
    rho=0.82 in Figure 1 without a ledger figure link.
    [STAT:rho=0.82 src="{source_data}" method=spearman]
    [CITE:smith2026 tier=1 status=api_confirmed]
    """


def test_full_pipeline_happy_path(tmp_path: Path) -> None:
    figures_dir, coverage_dir, source_data = _render_publication_bundle(tmp_path)
    manuscript_md = _happy_manuscript(source_data)
    ledger = ClaimLedger.from_markdown(manuscript_md)

    consistency = check_figure_text_consistency(
        manuscript_md,
        ledger=ledger,
        figures_dir=figures_dir,
        coverage_dir=coverage_dir,
    )
    visual_qa = visual_qa_figure(figures_dir / "1.png", run_vision=False, write_sidecar=False)
    citation_gate = run_citation_gate(ledger=ledger)
    preflight = run_manuscript_preflight(
        manuscript_md,
        ledger=ledger,
        figures_dir=figures_dir,
        coverage_dir=coverage_dir,
        roles=[],
        run_visual_qa=True,
    )
    state = assess_manuscript(
        manuscript_md,
        ledger=ledger,
        figures_dir=figures_dir,
        coverage_dir=coverage_dir,
        roles=[],
        run_visual_qa=True,
    )
    ladder = assess_verification_ladder(
        manuscript_md,
        ledger=ledger,
        figures_dir=figures_dir,
        coverage_dir=coverage_dir,
        run_visual_qa=False,
    )
    sources = data_sources_from_coverage(coverage_dir)
    das_draft = sources.to_das_draft()

    assert consistency.ok
    assert visual_qa.verdict != "FAIL"
    assert citation_gate.ok
    assert preflight.ok
    assert state.current_stage.rank >= ManuscriptStage.CITATION_TIERED.rank
    assert ladder.min_claim_rung is not None
    assert ladder.min_claim_rung.rank >= LadderRung.RENDERED.rank
    assert source_data.name in das_draft
    assert "Figure(s) 1" in das_draft


def test_full_pipeline_blocked_path(tmp_path: Path) -> None:
    figures_dir, coverage_dir, source_data = _render_publication_bundle(tmp_path)
    manuscript_md = _blocked_manuscript(source_data)
    ledger = ClaimLedger.from_markdown(manuscript_md)

    consistency = check_figure_text_consistency(
        manuscript_md,
        ledger=ledger,
        figures_dir=figures_dir,
        coverage_dir=coverage_dir,
    )
    visual_qa = visual_qa_figure(figures_dir / "1.png", run_vision=False, write_sidecar=False)
    citation_gate = run_citation_gate(ledger=ledger)
    preflight = run_manuscript_preflight(
        manuscript_md,
        ledger=ledger,
        figures_dir=figures_dir,
        coverage_dir=coverage_dir,
        roles=[],
        run_visual_qa=True,
    )
    state = assess_manuscript(
        manuscript_md,
        ledger=ledger,
        figures_dir=figures_dir,
        coverage_dir=coverage_dir,
        roles=[],
        run_visual_qa=True,
    )
    ladder = assess_verification_ladder(
        manuscript_md,
        ledger=ledger,
        figures_dir=figures_dir,
        coverage_dir=coverage_dir,
        run_visual_qa=False,
    )
    sources = data_sources_from_coverage(coverage_dir)

    assert consistency.ok
    assert visual_qa.verdict != "FAIL"
    assert not citation_gate.ok
    assert citation_gate.promotion_queue
    assert any("fetch the abstract" in item.action for item in citation_gate.promotion_queue)
    assert not preflight.ok
    assert state.current_stage.rank <= ManuscriptStage.EVIDENCE_LINKED.rank
    assert state.fix_queue
    assert any("missing figure link" in item.message for item in state.fix_queue)
    assert any("needs Tier-3" in item.message for item in state.fix_queue)
    assert ladder.min_claim_rung is not None
    assert ladder.min_claim_rung.rank == LadderRung.SOURCE_SEARCHED.rank
    assert ladder.claim_rungs[0].next_blocker is not None
    assert "Tier-3" in ladder.claim_rungs[0].next_blocker
    assert sources.n_manifests == 1
