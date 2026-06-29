"""End-to-end capstone: the whole vaultlab.projects package composing on one
synthetic figure. Proves the planning contracts, the readiness ladder, the
figure-QA bridge, the gap-finder, the compute classifier, and the lane log all
agree on a single, fully-covered plan -- no private artifacts, synthetic only.
"""

from __future__ import annotations

from pathlib import Path

from vaultlab.figures.layout_sidecar import build_matplotlib_layout_sidecar, write_layout_sidecar
from vaultlab.figures.publication.coverage import CoverageManifest
from vaultlab.projects.analysis_planning import find_coverage_gaps
from vaultlab.projects.compute_plan import ComputeTarget, ResourceHints, classify_compute_target
from vaultlab.projects.data_inventory import AccessStatus, DataInventory, DatasetRecord
from vaultlab.projects.figure_plan import (
    FigurePlan,
    SubpanelPlan,
    SubpanelReadiness,
    SupplementPlan,
    SupportRole,
    validate_figure_plan,
)
from vaultlab.projects.figure_trace import trace_subpanel
from vaultlab.projects.lane_log import Lane, LaneHandoff, ReadReceipt, validate_handoff
from vaultlab.slides.panel_contract import (
    PanelLayoutContract,
    PanelSlot,
    audit_panel_layout_contract,
)


def _render_clean_sidecar(path: Path) -> Path:
    import matplotlib

    matplotlib.rcdefaults()
    matplotlib.use("Agg", force=True)
    import matplotlib.pyplot as plt
    import numpy as np

    fig, ax = plt.subplots(figsize=(3.4, 2.6), dpi=120)
    ax.imshow(np.arange(9, dtype=float).reshape(3, 3), cmap="viridis")
    ax.set_title("Synthetic")
    ax.set_xlabel("Region")
    ax.set_ylabel("Donor")
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    sidecar = build_matplotlib_layout_sidecar(fig, figure_path=path, target_width_in=3.4)
    plt.close(fig)
    return write_layout_sidecar(sidecar)


def test_projects_package_composes_on_one_fully_covered_figure(tmp_path: Path) -> None:
    figures = tmp_path / "figures"
    figures.mkdir()

    # --- figure-side artifacts (the existing QA layer) ---
    sidecar = _render_clean_sidecar(figures / "A.png")
    CoverageManifest(
        figure_id="Fig1",
        script_path="plots/A.py",
        regions_included=["R1", "R2"],
        donors_included=["D1", "D2"],
        source_data=["DS1"],
    ).to_json(figures / "A.coverage.json")
    (figures / "A.method.md").write_text(
        "Rendered from D1/D2 across R1/R2 with all parameters recorded.\n",
        encoding="utf-8",
    )

    # --- the plan (the new upstream layer) ---
    subpanel = SubpanelPlan(
        subpanel_id="fig1-a",
        figure_id="Fig1",
        letter="A",
        concept="synthetic concept",
        plot_type="heatmap",
        source_result="DS1",
        analysis_script="analysis/A.py",
        plot_script="plots/A.py",
        output_figure="figures/A.png",
        manifest_path="figures/A.coverage.json",
        layout_sidecar_path=str(sidecar.relative_to(tmp_path)),
        visual_qa_path="figures/A.visual-qa.json",
        provenance_path="figures/A.method.md",
        panel_slot_id="A",
        claim_id="claim-A",
        supplement_ids=["supp-robust", "supp-negctl"],
        readiness=SubpanelReadiness.DECK_READY,
    )
    supplements = [
        SupplementPlan(
            supplement_id="supp-robust",
            parent_subpanel_id="fig1-a",
            support_role=SupportRole.ROBUSTNESS,
            output_figure="supp/robust.png",
            manifest_path="supp/robust.coverage.json",
        ),
        SupplementPlan(
            supplement_id="supp-negctl",
            parent_subpanel_id="fig1-a",
            support_role=SupportRole.NEGATIVE_CONTROL,
            output_figure="supp/negctl.png",
            manifest_path="supp/negctl.coverage.json",
        ),
    ]
    plan = FigurePlan(
        figure_id="Fig1",
        purpose="Synthetic capstone figure.",
        reading_order=["A"],
        subpanel_ids=["fig1-a"],
        supplement_ids=["supp-robust", "supp-negctl"],
    )

    # 1. The plan is internally consistent.
    assert validate_figure_plan(plan, [subpanel], supplements).ok() is True

    # 2. A passing panel contract lets the subpanel trace all the way to DECK_READY.
    contract = PanelLayoutContract(
        figure_id="Fig1",
        slide_width_in=7.5,
        slide_height_in=5.0,
        panels=[PanelSlot(letter="A", image_path="figures/A.png", slot_in=[0.3, 0.4, 2.0, 1.5])],
    )
    panel_audit = audit_panel_layout_contract(contract)
    assert panel_audit.ok() is True

    trace = trace_subpanel(subpanel, base_dir=tmp_path, panel_audit=panel_audit)
    assert trace.problems == []
    assert trace.promotion_gate.passed is True
    assert trace.computed_readiness is SubpanelReadiness.DECK_READY

    # 3. A fully-covered plan (dataset present, negative control + donor support) has no gaps.
    inventory = DataInventory(
        datasets=[
            DatasetRecord(
                dataset_id="DS1",
                modality="ims",
                scale="region",
                unit_coverage=["D1", "D2"],
                replication_unit="donor",
                location="kb/DS1",
                fmt="csv",
                size_bytes=4096,
                processing_stage="processed",
                access=AccessStatus.AVAILABLE,
            )
        ]
    )
    assert find_coverage_gaps(plan, [subpanel], supplements, inventory) == []

    # 4. The compute classifier resolves a small job to LOCAL.
    compute = classify_compute_target(
        ResourceHints(prior_peak_ram_gb=2.0, prior_runtime_min=5.0),
        analysis_id="analysis/A.py",
    )
    assert compute.target is ComputeTarget.LOCAL
    assert compute.analysis_id == "analysis/A.py"

    # 5. A figures->review handoff with the required read receipt validates clean.
    handoff = LaneHandoff(
        source=Lane.FIGURES,
        target=Lane.REVIEW,
        status="ready",
        artifacts=["figures/A.png"],
        verification=["pytest tests/test_vaultlab_projects/ -q"],
        downstream_request="Review Fig1 panel A for the deck.",
        read_receipts=[
            ReadReceipt(
                file_path="figures/A.method.md",
                role="reviewer",
                sections_read=["provenance"],
                key_facts=["Rendered from D1/D2 across R1/R2."],
                timestamp="2026-06-29T10:00:00Z",
            )
        ],
    )
    assert validate_handoff(handoff, required_reads=["figures/A.method.md"]) == []
