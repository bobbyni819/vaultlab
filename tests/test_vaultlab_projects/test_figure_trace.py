from __future__ import annotations

from pathlib import Path

from vaultlab.figures.layout_sidecar import build_matplotlib_layout_sidecar, write_layout_sidecar
from vaultlab.figures.publication.coverage import CoverageManifest
from vaultlab.projects.figure_plan import SubpanelPlan, SubpanelReadiness
from vaultlab.projects.figure_trace import link_panel_slot_to_subpanel, trace_subpanel
from vaultlab.slides.panel_contract import (
    PanelLayoutContract,
    PanelSlot,
    audit_panel_layout_contract,
)


def _subpanel(
    subpanel_id: str,
    letter: str,
    *,
    provenance_path: str,
    layout_sidecar_path: str,
    readiness: SubpanelReadiness,
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
        layout_sidecar_path=layout_sidecar_path,
        visual_qa_path=f"figures/{letter}.visual-qa.json",
        provenance_path=provenance_path,
        panel_slot_id=letter,
        claim_id=f"claim-{letter}",
        supplement_ids=[],
        readiness=readiness,
    )


def _render_heatmap(path: Path, *, pushed_colorbar_label: bool, target_width_in: float) -> Path:
    import matplotlib

    # Reset rcParams to defaults so this render is deterministic regardless of
    # any global matplotlib state (e.g. font.size) left behind by earlier tests
    # in the full suite -- the effective-font check depends on those sizes.
    matplotlib.rcdefaults()
    matplotlib.use("Agg", force=True)
    import matplotlib.pyplot as plt
    import numpy as np

    fig, ax = plt.subplots(figsize=(3.4, 2.4), dpi=120)
    data = np.arange(9, dtype=float).reshape(3, 3)
    image = ax.imshow(data, cmap="viridis")
    ax.set_title("Synthetic")
    ax.set_xlabel("Region")
    ax.set_ylabel("Donor")
    colorbar = fig.colorbar(image, ax=ax)
    colorbar.set_label("Synthetic colorbar label", labelpad=70 if pushed_colorbar_label else 4)
    if not pushed_colorbar_label:
        fig.tight_layout()
    fig.savefig(path, dpi=120)
    sidecar = build_matplotlib_layout_sidecar(
        fig,
        figure_path=path,
        target_width_in=target_width_in,
        target_height_in=1.0,
    )
    plt.close(fig)
    return write_layout_sidecar(sidecar)


def _write_coverage(path: Path, *, letter: str) -> None:
    CoverageManifest(
        figure_id="Fig1",
        script_path=f"plots/{letter}.py",
        regions_included=["R1", "R2"],
        donors_included=["D1", "D2"],
        source_data=[f"results/{letter}.csv"],
    ).to_json(path)


def test_trace_subpanel_loads_sidecars_and_computes_readiness(tmp_path: Path) -> None:
    figures = tmp_path / "figures"
    figures.mkdir()
    clean_sidecar = _render_heatmap(
        figures / "A.png",
        pushed_colorbar_label=False,
        target_width_in=3.4,
    )
    bad_sidecar = _render_heatmap(
        figures / "B.png",
        pushed_colorbar_label=True,
        target_width_in=0.5,
    )
    _write_coverage(figures / "A.coverage.json", letter="A")
    _write_coverage(figures / "B.coverage.json", letter="B")
    (figures / "A.method.md").write_text(
        "Rendered from D1/D2 and R1/R2 with recorded parameters.\n",
        encoding="utf-8",
    )
    (figures / "B.method.md").write_text(
        "TODO: record what was rendered for this panel.\n",
        encoding="utf-8",
    )

    clean = _subpanel(
        "fig1-a",
        "A",
        provenance_path="figures/A.method.md",
        layout_sidecar_path=str(clean_sidecar.relative_to(tmp_path)),
        readiness=SubpanelReadiness.GEOMETRY_QA_PASSED,
    )
    bad = _subpanel(
        "fig1-b",
        "B",
        provenance_path="figures/B.method.md",
        layout_sidecar_path=str(bad_sidecar.relative_to(tmp_path)),
        readiness=SubpanelReadiness.GEOMETRY_QA_PASSED,
    )

    clean_trace = trace_subpanel(clean, base_dir=tmp_path)
    bad_trace = trace_subpanel(bad, base_dir=tmp_path)

    assert clean_trace.computed_readiness is SubpanelReadiness.GEOMETRY_QA_PASSED
    assert clean_trace.promotion_gate.passed is True
    assert clean_trace.problems == []
    assert clean_trace.coverage_severity == "pass"
    assert clean_trace.layout_severity == "pass"
    assert clean_trace.panel_severity == "pass"
    assert clean_trace.overall_severity == "pass"

    assert bad_trace.computed_readiness is SubpanelReadiness.DISPLAY_EXISTS
    assert bad_trace.promotion_gate.passed is False
    assert bad_trace.problems == []
    assert "provenance_placeholder: todo" in bad_trace.promotion_gate.blockers
    assert bad_trace.layout_severity == "fail"


def test_link_panel_slot_to_subpanel_maps_contract_letters() -> None:
    subpanels = [
        _subpanel(
            "fig1-a",
            "A",
            provenance_path="figures/A.method.md",
            layout_sidecar_path="figures/A.png.layout.json",
            readiness=SubpanelReadiness.DISPLAY_EXISTS,
        ),
        _subpanel(
            "fig1-b",
            "B",
            provenance_path="figures/B.method.md",
            layout_sidecar_path="figures/B.png.layout.json",
            readiness=SubpanelReadiness.DISPLAY_EXISTS,
        ),
    ]
    contract = PanelLayoutContract(
        figure_id="Fig1",
        slide_width_in=7.5,
        slide_height_in=5.0,
        panels=[
            PanelSlot(letter="A", image_path="figures/A.png", slot_in=[0.3, 0.4, 2.0, 1.5]),
            PanelSlot(letter="B", image_path="figures/B.png", slot_in=[2.6, 0.4, 2.0, 1.5]),
            PanelSlot(letter="C", image_path="figures/C.png", slot_in=[4.9, 0.4, 2.0, 1.5]),
        ],
    )

    assert link_panel_slot_to_subpanel(contract, subpanels) == {
        "A": "fig1-a",
        "B": "fig1-b",
        "C": None,
    }


def test_trace_subpanel_reaches_deck_ready_only_with_passing_panel_audit(tmp_path: Path) -> None:
    figures = tmp_path / "figures"
    figures.mkdir()
    clean_sidecar = _render_heatmap(
        figures / "A.png",
        pushed_colorbar_label=False,
        target_width_in=3.4,
    )
    _write_coverage(figures / "A.coverage.json", letter="A")
    (figures / "A.method.md").write_text(
        "Rendered from D1/D2 and R1/R2 with recorded parameters.\n",
        encoding="utf-8",
    )

    subpanel = _subpanel(
        "fig1-a",
        "A",
        provenance_path="figures/A.method.md",
        layout_sidecar_path=str(clean_sidecar.relative_to(tmp_path)),
        readiness=SubpanelReadiness.DECK_READY,
    )

    contract = PanelLayoutContract(
        figure_id="Fig1",
        slide_width_in=7.5,
        slide_height_in=5.0,
        panels=[PanelSlot(letter="A", image_path="figures/A.png", slot_in=[0.3, 0.4, 2.0, 1.5])],
    )
    panel_audit = audit_panel_layout_contract(contract)
    assert panel_audit.ok()

    # Without a panel audit the bridge refuses to confirm DECK_READY.
    capped = trace_subpanel(subpanel, base_dir=tmp_path)
    assert capped.computed_readiness is SubpanelReadiness.GEOMETRY_QA_PASSED
    assert capped.promotion_gate.passed is False
    assert "panel_audit_missing" in capped.promotion_gate.blockers

    # With a passing panel audit the same subpanel reaches DECK_READY.
    ready = trace_subpanel(subpanel, base_dir=tmp_path, panel_audit=panel_audit)
    assert ready.computed_readiness is SubpanelReadiness.DECK_READY
    assert ready.promotion_gate.passed is True
    assert ready.promotion_gate.blockers == []
    assert ready.panel_severity == "pass"
    assert ready.problems == []


def test_trace_subpanel_reports_missing_files_as_named_problems(tmp_path: Path) -> None:
    subpanel = _subpanel(
        "fig1-c",
        "C",
        provenance_path="figures/C.method.md",
        layout_sidecar_path="figures/C.png.layout.json",
        readiness=SubpanelReadiness.GEOMETRY_QA_PASSED,
    )

    trace = trace_subpanel(subpanel, base_dir=tmp_path)

    assert trace.computed_readiness is SubpanelReadiness.DISPLAY_EXISTS
    assert "missing manifest_path: figures/C.coverage.json" in trace.problems
    assert "missing layout_sidecar_path: figures/C.png.layout.json" in trace.problems
    assert "missing provenance_path: figures/C.method.md" in trace.problems
