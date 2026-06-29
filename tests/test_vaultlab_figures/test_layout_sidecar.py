from __future__ import annotations

from pathlib import Path

import pytest


def _render_synthetic_matplotlib_figure(path: Path) -> object:
    matplotlib = pytest.importorskip("matplotlib")
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    fig, ax = plt.subplots(figsize=(4, 3), dpi=200)
    data = np.arange(12, dtype=float).reshape(3, 4)
    image = ax.imshow(data, cmap="viridis")
    ax.set_title("Synthetic heatmap")
    ax.set_xlabel("Long synthetic x label")
    ax.set_ylabel("Long synthetic y label")
    ax.text(0.2, 0.2, "annotation", transform=ax.transAxes, fontsize=8)
    ax.plot([], [], label="synthetic legend")
    ax.legend(loc="upper right")
    fig.colorbar(image, ax=ax, label="synthetic colorbar")
    fig.savefig(path, dpi=200)
    return fig


def test_matplotlib_layout_sidecar_records_canvas_objects_and_effective_fonts(
    tmp_path: Path,
) -> None:
    from vaultlab.figures.layout_sidecar import build_matplotlib_layout_sidecar

    png = tmp_path / "synthetic_heatmap.png"
    fig = _render_synthetic_matplotlib_figure(png)

    sidecar = build_matplotlib_layout_sidecar(
        fig,
        figure_path=png,
        target_width_in=2.0,
        target_height_in=1.5,
    )

    assert sidecar.figure_path == str(png)
    assert sidecar.canvas.width_px > 0
    assert sidecar.canvas.height_px > 0
    assert sidecar.canvas.dpi == pytest.approx(200)
    assert sidecar.display is not None
    assert sidecar.display.scale_factor == pytest.approx(0.5)

    object_ids = {obj.id for obj in sidecar.objects}
    object_types = {obj.type for obj in sidecar.objects}
    assert "axes.0" in object_ids
    assert "legend.0" in object_ids
    assert "title.0" in object_ids
    assert "xlabel.0" in object_ids
    assert "ylabel.0" in object_ids
    assert "annotation.0.0" in object_ids
    assert "axes" in object_types
    assert "legend" in object_types
    assert "text" in object_types

    text_objects = [obj for obj in sidecar.objects if obj.type == "text"]
    assert any(obj.font_pt_native and obj.font_pt_effective for obj in text_objects)
    assert all(obj.bbox_px[2] >= obj.bbox_px[0] for obj in sidecar.objects)
    assert all(obj.bbox_px[3] >= obj.bbox_px[1] for obj in sidecar.objects)


def test_layout_sidecar_helpers_are_exported_from_figures_package() -> None:
    from vaultlab.figures import (
        FigureLayoutSidecar,
        audit_layout_sidecar,
        build_matplotlib_layout_sidecar,
        write_layout_sidecar,
    )

    assert FigureLayoutSidecar.__name__ == "FigureLayoutSidecar"
    assert callable(audit_layout_sidecar)
    assert callable(build_matplotlib_layout_sidecar)
    assert callable(write_layout_sidecar)


def test_layout_sidecar_round_trips_to_json(tmp_path: Path) -> None:
    from vaultlab.figures.layout_sidecar import (
        build_matplotlib_layout_sidecar,
        load_layout_sidecar,
        write_layout_sidecar,
    )

    png = tmp_path / "synthetic_heatmap.png"
    fig = _render_synthetic_matplotlib_figure(png)
    sidecar = build_matplotlib_layout_sidecar(fig, figure_path=png, target_width_in=2.0)

    written = write_layout_sidecar(sidecar)
    loaded = load_layout_sidecar(written)

    assert written == Path(str(png) + ".layout.json")
    assert loaded.figure_path == sidecar.figure_path
    assert loaded.canvas.width_px == sidecar.canvas.width_px
    assert [obj.id for obj in loaded.objects] == [obj.id for obj in sidecar.objects]


def test_audit_layout_sidecar_flags_legend_overlap_and_tiny_effective_text() -> None:
    from vaultlab.figures.layout_sidecar import (
        CanvasSpec,
        DisplaySpec,
        FigureLayoutObject,
        FigureLayoutSidecar,
        audit_layout_sidecar,
    )

    sidecar = FigureLayoutSidecar(
        figure_path="synthetic.png",
        canvas=CanvasSpec(width_px=800, height_px=600, dpi=200, width_in=4.0, height_in=3.0),
        display=DisplaySpec(target_width_in=2.0, target_height_in=1.5, scale_factor=0.5),
        objects=[
            FigureLayoutObject(id="axes.0", type="axes", bbox_px=[100, 100, 700, 500]),
            FigureLayoutObject(
                id="legend.0",
                type="legend",
                bbox_px=[550, 120, 760, 260],
                placement="inside_axes",
            ),
            FigureLayoutObject(
                id="xlabel.0",
                type="text",
                bbox_px=[300, 520, 500, 560],
                text_role="axis_label",
                font_pt_native=8.0,
                font_pt_effective=4.0,
            ),
        ],
    )

    audit = audit_layout_sidecar(sidecar, min_effective_font_pt=5.5)

    assert audit.overall_severity == "fail"
    failures = {(check.name, check.severity) for check in audit.checks}
    assert ("legend_overlap", "fail") in failures
    assert ("minimum_effective_font", "fail") in failures


def test_matplotlib_layout_sidecar_emits_typed_colorbar_object(tmp_path: Path) -> None:
    from vaultlab.figures.layout_sidecar import (
        audit_layout_sidecar,
        build_matplotlib_layout_sidecar,
    )

    png = tmp_path / "synthetic_heatmap.png"
    fig = _render_synthetic_matplotlib_figure(png)
    sidecar = build_matplotlib_layout_sidecar(fig, figure_path=png, target_width_in=2.0)

    colorbars = [obj for obj in sidecar.objects if obj.type == "colorbar"]
    assert len(colorbars) == 1
    assert colorbars[0].id.startswith("colorbar.")

    # A normal fig.colorbar() sits beside the axes, so the (now live) overlap
    # check passes -- but it ran against a real colorbar rather than vacuously.
    colorbar_check = next(c for c in audit_layout_sidecar(sidecar).checks if c.name == "colorbar_overlap")
    assert colorbar_check.severity == "pass"
    assert "no colorbar objects" not in colorbar_check.detail


def test_audit_layout_sidecar_flags_colorbar_over_plot() -> None:
    from vaultlab.figures.layout_sidecar import (
        CanvasSpec,
        FigureLayoutObject,
        FigureLayoutSidecar,
        audit_layout_sidecar,
    )

    sidecar = FigureLayoutSidecar(
        figure_path="bad.png",
        canvas=CanvasSpec(width_px=800, height_px=600, dpi=200, width_in=4.0, height_in=3.0),
        objects=[
            FigureLayoutObject(id="axes.0", type="axes", bbox_px=[100, 100, 700, 500]),
            # colorbar dropped on top of the data axes (bad manual placement)
            FigureLayoutObject(id="colorbar.1", type="colorbar", bbox_px=[300, 200, 360, 480]),
        ],
    )

    audit = audit_layout_sidecar(sidecar)
    colorbar_check = next(c for c in audit.checks if c.name == "colorbar_overlap")
    assert colorbar_check.severity == "fail"
    assert audit.overall_severity == "fail"


def test_audit_layout_sidecar_colorbar_beside_axes_passes_despite_wide_title() -> None:
    from vaultlab.figures.layout_sidecar import (
        CanvasSpec,
        FigureLayoutObject,
        FigureLayoutSidecar,
        audit_layout_sidecar,
    )

    # A colorbar sits beside the plot; a long title's wide bbox grazes the
    # colorbar column. That is benign and must NOT be flagged as an overlap.
    sidecar = FigureLayoutSidecar(
        figure_path="ok.png",
        canvas=CanvasSpec(width_px=800, height_px=600, dpi=200, width_in=4.0, height_in=3.0),
        objects=[
            FigureLayoutObject(id="axes.0", type="axes", bbox_px=[100, 100, 600, 500]),
            FigureLayoutObject(id="colorbar.1", type="colorbar", bbox_px=[650, 150, 690, 470]),
            FigureLayoutObject(
                id="title.0",
                type="text",
                bbox_px=[40, 520, 700, 560],
                text_role="title",
                font_pt_native=12.0,
            ),
        ],
    )

    audit = audit_layout_sidecar(sidecar)
    colorbar_check = next(c for c in audit.checks if c.name == "colorbar_overlap")
    assert colorbar_check.severity == "pass"


def test_audit_layout_sidecar_flags_clipped_labels_as_fail_and_other_text_as_warn() -> None:
    from vaultlab.figures.layout_sidecar import (
        CanvasSpec,
        FigureLayoutObject,
        FigureLayoutSidecar,
        audit_layout_sidecar,
    )

    canvas = CanvasSpec(width_px=800, height_px=600, dpi=200, width_in=4.0, height_in=3.0)

    # A colorbar label whose bbox runs past the right edge -> FAIL (clipped in export).
    clipped_label = FigureLayoutSidecar(
        figure_path="clip.png",
        canvas=canvas,
        objects=[
            FigureLayoutObject(id="axes.0", type="axes", bbox_px=[60, 60, 700, 520]),
            FigureLayoutObject(
                id="colorbar_label.1.y",
                type="text",
                bbox_px=[770, 200, 860, 420],
                text_role="colorbar_label",
            ),
        ],
    )
    label_audit = audit_layout_sidecar(clipped_label)
    clip_check = next(c for c in label_audit.checks if c.name == "clipped_label")
    assert clip_check.severity == "fail"
    assert label_audit.overall_severity == "fail"
    assert clip_check.evidence["clipped"][0]["id"] == "colorbar_label.1.y"

    # A clipped in-axes annotation (not a label) is only a WARN.
    clipped_annotation = FigureLayoutSidecar(
        figure_path="clip2.png",
        canvas=canvas,
        objects=[
            FigureLayoutObject(
                id="annotation.0.0",
                type="text",
                bbox_px=[10, 590, 200, 640],
                text_role="annotation",
            ),
        ],
    )
    annot_check = next(
        c for c in audit_layout_sidecar(clipped_annotation).checks if c.name == "clipped_label"
    )
    assert annot_check.severity == "warn"

    # All text inside the canvas -> pass.
    clean = FigureLayoutSidecar(
        figure_path="clean.png",
        canvas=canvas,
        objects=[
            FigureLayoutObject(
                id="title.0", type="text", bbox_px=[100, 540, 700, 580], text_role="title"
            ),
        ],
    )
    clean_check = next(c for c in audit_layout_sidecar(clean).checks if c.name == "clipped_label")
    assert clean_check.severity == "pass"
