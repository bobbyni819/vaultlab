"""Object-level layout sidecars for rendered scientific figures.

Pixel-only audits can see image dimensions and edge clipping, but they cannot
reliably know which rectangle is an axis, legend, colorbar, or label. This
module captures those object boxes while the matplotlib figure object still
exists, then audits the boxes deterministically.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

LayoutSeverity = Literal["pass", "warn", "fail"]

_SEVERITY_RANK: dict[LayoutSeverity, int] = {"pass": 0, "warn": 1, "fail": 2}


@dataclass(frozen=True)
class CanvasSpec:
    """Rendered canvas size."""

    width_px: int
    height_px: int
    dpi: float
    width_in: float
    height_in: float


@dataclass(frozen=True)
class DisplaySpec:
    """Intended display slot for the rendered figure."""

    target_width_in: float | None = None
    target_height_in: float | None = None
    scale_factor: float | None = None


@dataclass(frozen=True)
class FigureLayoutObject:
    """One object recovered from the figure renderer."""

    id: str
    type: str
    bbox_px: list[int]
    text: str | None = None
    text_role: str | None = None
    font_pt_native: float | None = None
    font_pt_effective: float | None = None
    placement: str | None = None


@dataclass(frozen=True)
class FigureLayoutSidecar:
    """Machine-readable object layout sidecar for one rendered figure."""

    figure_path: str
    canvas: CanvasSpec
    display: DisplaySpec | None = None
    objects: list[FigureLayoutObject] = field(default_factory=list)
    version: int = 1

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable representation."""

        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FigureLayoutSidecar:
        """Build a sidecar from a JSON-like dict."""

        canvas = CanvasSpec(**data["canvas"])
        display_data = data.get("display")
        display = DisplaySpec(**display_data) if display_data else None
        objects = [FigureLayoutObject(**obj) for obj in data.get("objects", [])]
        return cls(
            figure_path=str(data["figure_path"]),
            canvas=canvas,
            display=display,
            objects=objects,
            version=int(data.get("version", 1)),
        )


@dataclass(frozen=True)
class LayoutSidecarCheck:
    """One sidecar audit check."""

    name: str
    severity: LayoutSeverity
    detail: str
    evidence: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class LayoutSidecarAudit:
    """Aggregate sidecar audit result."""

    overall_severity: LayoutSeverity
    checks: list[LayoutSidecarCheck]

    @property
    def n_fail(self) -> int:
        return sum(1 for check in self.checks if check.severity == "fail")

    @property
    def n_warn(self) -> int:
        return sum(1 for check in self.checks if check.severity == "warn")

    def ok(self) -> bool:
        return self.n_fail == 0


def build_matplotlib_layout_sidecar(
    fig: Any,
    *,
    figure_path: Path | str,
    target_width_in: float | None = None,
    target_height_in: float | None = None,
) -> FigureLayoutSidecar:
    """Capture axes, legends, labels, annotations, and display metadata.

    The figure should be fully configured but does not need to be saved before
    this function is called. The function draws the canvas so matplotlib's
    renderer has current bounding boxes.
    """

    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    width_px, height_px = fig.canvas.get_width_height()
    width_in, height_in = (float(v) for v in fig.get_size_inches())
    dpi = float(fig.dpi)
    scale_factor = target_width_in / width_in if target_width_in and width_in else None
    display = DisplaySpec(
        target_width_in=target_width_in,
        target_height_in=target_height_in,
        scale_factor=scale_factor,
    )

    objects: list[FigureLayoutObject] = []
    for axis_index, ax in enumerate(fig.axes):
        axes_bbox = _bbox_to_px(ax.get_window_extent(renderer))

        if _is_colorbar_axes(ax):
            objects.append(
                FigureLayoutObject(id=f"colorbar.{axis_index}", type="colorbar", bbox_px=axes_bbox)
            )
            for axis_name, label_obj in (("y", ax.yaxis.label), ("x", ax.xaxis.label)):
                _append_text_object(
                    objects,
                    id_=f"colorbar_label.{axis_index}.{axis_name}",
                    text_obj=label_obj,
                    renderer=renderer,
                    role="colorbar_label",
                    scale_factor=scale_factor,
                )
            continue

        objects.append(FigureLayoutObject(id=f"axes.{axis_index}", type="axes", bbox_px=axes_bbox))

        _append_text_object(
            objects,
            id_=f"title.{axis_index}",
            text_obj=ax.title,
            renderer=renderer,
            role="title",
            scale_factor=scale_factor,
        )
        _append_text_object(
            objects,
            id_=f"xlabel.{axis_index}",
            text_obj=ax.xaxis.label,
            renderer=renderer,
            role="axis_label",
            scale_factor=scale_factor,
        )
        _append_text_object(
            objects,
            id_=f"ylabel.{axis_index}",
            text_obj=ax.yaxis.label,
            renderer=renderer,
            role="axis_label",
            scale_factor=scale_factor,
        )

        legend = ax.get_legend()
        if legend is not None:
            objects.append(
                FigureLayoutObject(
                    id=f"legend.{axis_index}",
                    type="legend",
                    bbox_px=_bbox_to_px(legend.get_window_extent(renderer)),
                    placement=_legend_placement(legend),
                )
            )

        for text_index, text_obj in enumerate(ax.texts):
            _append_text_object(
                objects,
                id_=f"annotation.{axis_index}.{text_index}",
                text_obj=text_obj,
                renderer=renderer,
                role="annotation",
                scale_factor=scale_factor,
            )

    return FigureLayoutSidecar(
        figure_path=str(figure_path),
        canvas=CanvasSpec(
            width_px=int(width_px),
            height_px=int(height_px),
            dpi=dpi,
            width_in=width_in,
            height_in=height_in,
        ),
        display=display,
        objects=objects,
    )


def write_layout_sidecar(sidecar: FigureLayoutSidecar, path: Path | str | None = None) -> Path:
    """Write a sidecar JSON file and return its path."""

    out = Path(path) if path is not None else Path(str(sidecar.figure_path) + ".layout.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(sidecar.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return out


def load_layout_sidecar(path: Path | str) -> FigureLayoutSidecar:
    """Read a sidecar JSON file."""

    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return FigureLayoutSidecar.from_dict(data)


def audit_layout_sidecar(
    sidecar: FigureLayoutSidecar | Path | str,
    *,
    min_effective_font_pt: float = 5.5,
) -> LayoutSidecarAudit:
    """Run deterministic object-level layout checks."""

    if not isinstance(sidecar, FigureLayoutSidecar):
        sidecar = load_layout_sidecar(sidecar)

    checks = [
        _check_objects_inside_canvas(sidecar),
        _check_minimum_effective_font(sidecar, min_effective_font_pt=min_effective_font_pt),
        _check_legend_overlap(sidecar),
        _check_colorbar_overlap(sidecar),
    ]
    return LayoutSidecarAudit(overall_severity=_aggregate(checks), checks=checks)


def _append_text_object(
    objects: list[FigureLayoutObject],
    *,
    id_: str,
    text_obj: Any,
    renderer: Any,
    role: str,
    scale_factor: float | None,
) -> None:
    text = str(text_obj.get_text() or "")
    if not text:
        return
    native = float(text_obj.get_fontsize())
    effective = native * scale_factor if scale_factor else None
    objects.append(
        FigureLayoutObject(
            id=id_,
            type="text",
            bbox_px=_bbox_to_px(text_obj.get_window_extent(renderer)),
            text=text,
            text_role=role,
            font_pt_native=native,
            font_pt_effective=effective,
        )
    )


def _bbox_to_px(bbox: Any) -> list[int]:
    x0, y0, width, height = bbox.bounds
    x1 = x0 + width
    y1 = y0 + height
    return [round(float(x0)), round(float(y0)), round(float(x1)), round(float(y1))]


def _legend_placement(legend: Any) -> str:
    try:
        loc = legend._loc
    except Exception:
        return "unknown"
    return "inside_axes" if loc in range(0, 11) else "unknown"


def _is_colorbar_axes(ax: Any) -> bool:
    """Detect a matplotlib colorbar axis.

    matplotlib labels a colorbar's own axes ``<colorbar>``; this public-label
    signal is the canonical, version-stable check. The private ``ax._colorbar``
    attribute is deliberately NOT used as a fallback: on some matplotlib
    versions it was set on the *parent* data axes rather than the colorbar's own
    axes, so trusting it would misclassify a real plot axes as a colorbar and
    silently drop that axes' labels/legend. If the label signal ever disappears
    a colorbar simply reverts to being captured as a generic axes (fail-safe),
    which is strictly better than dropping data-axes objects (fail-dangerous).
    """

    try:
        return str(ax.get_label()) == "<colorbar>"
    except Exception:
        return False


def _check_objects_inside_canvas(sidecar: FigureLayoutSidecar) -> LayoutSidecarCheck:
    out: list[str] = []
    for obj in sidecar.objects:
        x0, y0, x1, y1 = obj.bbox_px
        if x0 < 0 or y0 < 0 or x1 > sidecar.canvas.width_px or y1 > sidecar.canvas.height_px:
            out.append(obj.id)
    if out:
        return LayoutSidecarCheck(
            name="objects_inside_canvas",
            severity="warn",
            detail=f"{len(out)} object(s) extend outside the rendered canvas",
            evidence={"object_ids": out},
        )
    return LayoutSidecarCheck(
        name="objects_inside_canvas",
        severity="pass",
        detail="all captured objects are inside the rendered canvas",
    )


def _check_minimum_effective_font(
    sidecar: FigureLayoutSidecar, *, min_effective_font_pt: float
) -> LayoutSidecarCheck:
    small = [
        {
            "id": obj.id,
            "font_pt_effective": obj.font_pt_effective,
            "font_pt_native": obj.font_pt_native,
        }
        for obj in sidecar.objects
        if obj.type == "text"
        and obj.font_pt_effective is not None
        and obj.font_pt_effective < min_effective_font_pt
    ]
    if small:
        return LayoutSidecarCheck(
            name="minimum_effective_font",
            severity="fail",
            detail=(
                f"{len(small)} text object(s) fall below the "
                f"{min_effective_font_pt:.1f} pt effective font floor"
            ),
            evidence={"objects": small, "min_effective_font_pt": min_effective_font_pt},
        )
    return LayoutSidecarCheck(
        name="minimum_effective_font",
        severity="pass",
        detail=f"captured text meets the {min_effective_font_pt:.1f} pt effective font floor",
    )


def _check_legend_overlap(sidecar: FigureLayoutSidecar) -> LayoutSidecarCheck:
    legends = [obj for obj in sidecar.objects if obj.type == "legend"]
    axes = [obj for obj in sidecar.objects if obj.type == "axes"]
    overlaps = [
        record
        for legend in legends
        for ax in axes
        if (record := _overlap_record(legend, ax)) is not None
    ]
    if overlaps:
        return LayoutSidecarCheck(
            name="legend_overlap",
            severity="fail",
            detail=f"{len(overlaps)} legend/axes overlap(s) detected",
            evidence={"overlaps": overlaps},
        )
    return LayoutSidecarCheck(
        name="legend_overlap",
        severity="pass",
        detail="no legend/axes overlaps detected",
    )


def _check_colorbar_overlap(sidecar: FigureLayoutSidecar) -> LayoutSidecarCheck:
    """Flag a colorbar that lands on top of a plot's data region.

    The meaningful failure is a colorbar occluding a data axes. Colorbar-vs-text
    intersection is intentionally *not* checked: a long figure title has a wide
    bounding box that legitimately spans the top of the canvas (including over a
    side colorbar's column), so that comparison produces false positives on
    perfectly good figures. Clipped colorbar/axis labels are handled by the
    canvas-bounds check, not here.
    """

    colorbars = [obj for obj in sidecar.objects if obj.type == "colorbar"]
    if not colorbars:
        return LayoutSidecarCheck(
            name="colorbar_overlap",
            severity="pass",
            detail="no colorbar objects were captured",
        )
    axes = [obj for obj in sidecar.objects if obj.type == "axes"]
    overlaps = [
        record
        for colorbar in colorbars
        for ax in axes
        if (record := _overlap_record(colorbar, ax)) is not None
    ]
    if overlaps:
        return LayoutSidecarCheck(
            name="colorbar_overlap",
            severity="fail",
            detail=f"{len(overlaps)} colorbar/plot-axes overlap(s) detected",
            evidence={"overlaps": overlaps},
        )
    return LayoutSidecarCheck(
        name="colorbar_overlap",
        severity="pass",
        detail="colorbar does not overlap any plot axes",
    )


def _overlap_record(a: FigureLayoutObject, b: FigureLayoutObject) -> dict[str, Any] | None:
    area = _overlap_area(a.bbox_px, b.bbox_px)
    if area <= 0:
        return None
    return {"a": a.id, "b": b.id, "overlap_area_px": area}


def _overlap_area(a: list[int], b: list[int]) -> int:
    ix = max(0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0, min(a[3], b[3]) - max(a[1], b[1]))
    return int(ix * iy)


def _aggregate(checks: list[LayoutSidecarCheck]) -> LayoutSeverity:
    if not checks:
        return "pass"
    return max((check.severity for check in checks), key=lambda severity: _SEVERITY_RANK[severity])


__all__ = [
    "CanvasSpec",
    "DisplaySpec",
    "FigureLayoutObject",
    "FigureLayoutSidecar",
    "LayoutSidecarAudit",
    "LayoutSidecarCheck",
    "audit_layout_sidecar",
    "build_matplotlib_layout_sidecar",
    "load_layout_sidecar",
    "write_layout_sidecar",
]
