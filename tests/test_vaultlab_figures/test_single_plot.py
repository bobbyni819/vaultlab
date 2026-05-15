"""Tests for single-plot vs multi-panel figure detection (sub-goal 5.5).

The `vaultlab.figures.contract` package previously assumed every figure was
multi-panel. Wet-lab + comp-bio researchers regularly submit single-plot
figures (one volcano, one UMAP, one bar chart). Panel-cutting those
incorrectly subdivides legend boxes and axis labels into bogus "panels".

This module adds two primitives:

  * ``detect_panels(image_path) -> list[tuple[int, int, int, int]]`` —
    the XY-cut gutter-projection algorithm, returns bboxes of each
    detected panel (1-element list for single-plot figures).
  * ``is_single_plot(image_path) -> bool`` — convenience predicate;
    True iff ``len(detect_panels(image_path)) == 1``.

Plus a layout-dispatch helper:

  * ``suggest_figure_layout(image_path, *, has_bullets, has_caption) -> str``
    — returns a slide-layout name suitable for the deck planner
    (``"figure_only"``, ``"figure_with_side_caption"``,
    ``"figure_with_bullets"``, or ``"figure_with_panels"``).

Fixtures are generated on the fly with matplotlib so we don't commit
binary PNGs to git.
"""

from __future__ import annotations

from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Fixture builders — matplotlib only, written into tmp_path
# ---------------------------------------------------------------------------


def _make_single_plot_fixture(tmp_path: Path, name: str = "single.png") -> Path:
    matplotlib = pytest.importorskip("matplotlib")
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(5, 4))
    ax.bar(["a", "b", "c"], [1, 2, 3])
    ax.set_title("Single bar chart")
    out = tmp_path / name
    fig.savefig(out, dpi=100, bbox_inches="tight")
    plt.close(fig)
    return out


def _make_four_panel_fixture(tmp_path: Path, name: str = "four_panel.png") -> Path:
    matplotlib = pytest.importorskip("matplotlib")
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(2, 2, figsize=(8, 6))
    for ax in axes.flat:
        ax.scatter([1, 2, 3], [1, 2, 3])
    out = tmp_path / name
    # Significant whitespace between subplots → gutter projection should
    # find ≥1 horizontal and ≥1 vertical gutter.
    fig.subplots_adjust(wspace=0.6, hspace=0.6)
    fig.savefig(out, dpi=100, bbox_inches="tight")
    plt.close(fig)
    return out


def _make_two_panel_fixture(tmp_path: Path, name: str = "two_panel.png") -> Path:
    matplotlib = pytest.importorskip("matplotlib")
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(1, 2, figsize=(8, 4))
    for ax in axes:
        ax.plot([0, 1, 2], [0, 1, 4])
    out = tmp_path / name
    fig.subplots_adjust(wspace=0.6)
    fig.savefig(out, dpi=100, bbox_inches="tight")
    plt.close(fig)
    return out


def _make_single_plot_with_corner_legend_fixture(
    tmp_path: Path, name: str = "single_legend.png"
) -> Path:
    """Single chart whose legend sits in the upper-right corner.

    The legend creates whitespace around it but is NOT a separate panel —
    detection must NOT falsely split this into 2 panels.
    """
    matplotlib = pytest.importorskip("matplotlib")
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(6, 4))
    ax.plot([0, 1, 2, 3], [0, 1, 4, 9], label="series A")
    ax.plot([0, 1, 2, 3], [0, 2, 3, 7], label="series B")
    ax.legend(loc="upper right")
    out = tmp_path / name
    fig.savefig(out, dpi=100, bbox_inches="tight")
    plt.close(fig)
    return out


# ---------------------------------------------------------------------------
# detect_panels — the XY-cut gutter-projection algorithm
# ---------------------------------------------------------------------------


def test_detect_panels_returns_one_bbox_for_single_plot(tmp_path: Path):
    pytest.importorskip("skimage")
    from vaultlab.figures.understand.whitespace import detect_panels

    path = _make_single_plot_fixture(tmp_path)
    panels = detect_panels(path)
    assert len(panels) == 1, f"single plot should produce 1 panel, got {len(panels)}: {panels}"
    # The single panel should cover most of the figure area
    x0, y0, x1, y1 = panels[0]
    from PIL import Image

    w, h = Image.open(path).size
    panel_area = (x1 - x0) * (y1 - y0)
    fig_area = w * h
    assert panel_area / fig_area > 0.3, (
        f"single panel should cover ≥30% of figure (got {panel_area / fig_area:.2%})"
    )


def test_detect_panels_returns_multiple_bboxes_for_4_panel(tmp_path: Path):
    pytest.importorskip("skimage")
    from vaultlab.figures.understand.whitespace import detect_panels

    path = _make_four_panel_fixture(tmp_path)
    panels = detect_panels(path)
    assert len(panels) >= 2, (
        f"4-panel figure should yield ≥2 panels via XY-cut, got {len(panels)}"
    )


def test_detect_panels_finds_two_panels_in_two_panel_figure(tmp_path: Path):
    pytest.importorskip("skimage")
    from vaultlab.figures.understand.whitespace import detect_panels

    path = _make_two_panel_fixture(tmp_path)
    panels = detect_panels(path)
    assert len(panels) >= 2, (
        f"2-panel figure should yield ≥2 panels, got {len(panels)}"
    )


def test_detect_panels_legend_corner_does_not_create_phantom_panel(tmp_path: Path):
    """A chart with a corner legend must not be split into 2 panels."""
    pytest.importorskip("skimage")
    from vaultlab.figures.understand.whitespace import detect_panels

    path = _make_single_plot_with_corner_legend_fixture(tmp_path)
    panels = detect_panels(path)
    assert len(panels) == 1, (
        f"single chart with corner legend should produce 1 panel, got {len(panels)}"
    )


# ---------------------------------------------------------------------------
# is_single_plot — convenience predicate
# ---------------------------------------------------------------------------


def test_is_single_plot_true_for_single_bar_chart(tmp_path: Path):
    pytest.importorskip("skimage")
    from vaultlab.figures.understand.whitespace import is_single_plot

    path = _make_single_plot_fixture(tmp_path)
    assert is_single_plot(path) is True


def test_is_single_plot_false_for_4_panel(tmp_path: Path):
    pytest.importorskip("skimage")
    from vaultlab.figures.understand.whitespace import is_single_plot

    path = _make_four_panel_fixture(tmp_path)
    assert is_single_plot(path) is False


def test_is_single_plot_true_for_chart_with_corner_legend(tmp_path: Path):
    pytest.importorskip("skimage")
    from vaultlab.figures.understand.whitespace import is_single_plot

    path = _make_single_plot_with_corner_legend_fixture(tmp_path)
    assert is_single_plot(path) is True


# ---------------------------------------------------------------------------
# suggest_figure_layout — layout dispatch
# ---------------------------------------------------------------------------


def test_suggest_layout_routes_single_plot_with_bullets_to_figure_with_bullets(
    tmp_path: Path,
):
    pytest.importorskip("skimage")
    from vaultlab.figures.contract import suggest_figure_layout

    path = _make_single_plot_fixture(tmp_path)
    layout = suggest_figure_layout(path, has_bullets=True, has_caption=False)
    assert layout == "figure_with_bullets", (
        f"single plot + bullets should route to figure_with_bullets, got {layout!r}"
    )


def test_suggest_layout_routes_single_plot_with_caption_to_side_caption(
    tmp_path: Path,
):
    pytest.importorskip("skimage")
    from vaultlab.figures.contract import suggest_figure_layout

    path = _make_single_plot_fixture(tmp_path)
    # wide-ish single plot + caption (no bullets) → side caption variant
    layout = suggest_figure_layout(path, has_bullets=False, has_caption=True)
    assert layout in {"figure_with_side_caption", "figure_only"}, (
        f"single plot + caption should route to figure_only or figure_with_side_caption, got {layout!r}"
    )


def test_suggest_layout_routes_bare_single_plot_to_figure_only(tmp_path: Path):
    pytest.importorskip("skimage")
    from vaultlab.figures.contract import suggest_figure_layout

    path = _make_single_plot_fixture(tmp_path)
    layout = suggest_figure_layout(path, has_bullets=False, has_caption=False)
    assert layout == "figure_only", (
        f"bare single plot should route to figure_only, got {layout!r}"
    )


def test_suggest_layout_routes_multi_panel_to_figure_with_panels(tmp_path: Path):
    pytest.importorskip("skimage")
    from vaultlab.figures.contract import suggest_figure_layout

    path = _make_four_panel_fixture(tmp_path)
    layout = suggest_figure_layout(path, has_bullets=False, has_caption=False)
    assert layout == "figure_with_panels", (
        f"multi-panel figure should route to figure_with_panels (NOT subdivided), got {layout!r}"
    )


def test_suggest_layout_never_subdivides_single_plot(tmp_path: Path):
    """Regression: single-plot input must never produce figure_with_panels."""
    pytest.importorskip("skimage")
    from vaultlab.figures.contract import suggest_figure_layout

    path = _make_single_plot_fixture(tmp_path)
    for has_bullets in (False, True):
        for has_caption in (False, True):
            layout = suggest_figure_layout(
                path, has_bullets=has_bullets, has_caption=has_caption
            )
            assert layout != "figure_with_panels", (
                f"single plot must never be classed as figure_with_panels "
                f"(has_bullets={has_bullets}, has_caption={has_caption}, got {layout!r})"
            )


# ---------------------------------------------------------------------------
# Aspect-ratio edge cases — narrow vs wide single plots
# ---------------------------------------------------------------------------


def test_suggest_layout_for_very_wide_single_plot_prefers_figure_only(tmp_path: Path):
    """A wide aspect-ratio single plot with no bullets/caption should hero."""
    pytest.importorskip("skimage")
    matplotlib = pytest.importorskip("matplotlib")
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    from vaultlab.figures.contract import suggest_figure_layout

    fig, ax = plt.subplots(figsize=(10, 3))  # very wide
    ax.plot(range(100))
    path = tmp_path / "wide.png"
    fig.savefig(path, dpi=100, bbox_inches="tight")
    plt.close(fig)

    layout = suggest_figure_layout(path, has_bullets=False, has_caption=False)
    assert layout == "figure_only"


# ---------------------------------------------------------------------------
# Inset-axes edge case (deferred-followups bundle, 2026-05-15)
# ---------------------------------------------------------------------------
#
# A parent plot with a corner inset axes registers as 1 panel via XY-cut
# (which is correct — we don't want to subdivide it), but downstream
# captioning / LLM-side awareness needs to know there IS an inset. The
# `has_corner_inset` heuristic + the `classify_panel_layout` wrapper add
# that signal without changing the layout dispatcher's no-subdivide
# behavior.


def _make_inset_axes_fixture(
    tmp_path: Path,
    name: str = "single_inset.png",
    *,
    loc: str = "upper left",
) -> Path:
    """Single plot with a `inset_axes` at the given corner location."""
    matplotlib = pytest.importorskip("matplotlib")
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from mpl_toolkits.axes_grid1.inset_locator import inset_axes

    fig, ax = plt.subplots(figsize=(6, 4))
    ax.plot([0, 1, 2, 3, 4, 5], [0, 1, 4, 9, 16, 25])
    ax.set_title("Main plot with inset axes")
    axins = inset_axes(ax, width="30%", height="30%", loc=loc)
    axins.plot([0, 1, 2], [5, 3, 8])
    axins.tick_params(labelsize=6)
    out = tmp_path / name
    fig.savefig(out, dpi=100, bbox_inches="tight")
    plt.close(fig)
    return out


def test_has_corner_inset_true_for_inset_axes(tmp_path: Path):
    pytest.importorskip("skimage")
    from vaultlab.figures.understand.whitespace import has_corner_inset

    path = _make_inset_axes_fixture(tmp_path)
    assert has_corner_inset(path) is True


def test_has_corner_inset_detects_inset_at_multiple_corners(tmp_path: Path):
    pytest.importorskip("skimage")
    from vaultlab.figures.understand.whitespace import has_corner_inset

    for loc in ("upper left", "upper right", "lower left", "lower right"):
        path = _make_inset_axes_fixture(
            tmp_path, f"inset_{loc.replace(' ', '_')}.png", loc=loc
        )
        assert has_corner_inset(path) is True, f"Inset at {loc!r} not detected"


def test_has_corner_inset_false_for_plain_single_plot(tmp_path: Path):
    pytest.importorskip("skimage")
    from vaultlab.figures.understand.whitespace import has_corner_inset

    path = _make_single_plot_fixture(tmp_path)
    assert has_corner_inset(path) is False


def test_has_corner_inset_false_for_corner_legend(tmp_path: Path):
    """A chart with an in-axes legend in the corner must NOT register as inset."""
    pytest.importorskip("skimage")
    from vaultlab.figures.understand.whitespace import has_corner_inset

    path = _make_single_plot_with_corner_legend_fixture(tmp_path)
    assert has_corner_inset(path) is False


def test_classify_panel_layout_returns_single_plot_with_inset(tmp_path: Path):
    pytest.importorskip("skimage")
    from vaultlab.figures.understand.whitespace import classify_panel_layout

    path = _make_inset_axes_fixture(tmp_path)
    assert classify_panel_layout(path) == "single_plot_with_inset"


def test_classify_panel_layout_returns_single_plot(tmp_path: Path):
    pytest.importorskip("skimage")
    from vaultlab.figures.understand.whitespace import classify_panel_layout

    path = _make_single_plot_fixture(tmp_path)
    assert classify_panel_layout(path) == "single_plot"


def test_classify_panel_layout_returns_multi_panel(tmp_path: Path):
    pytest.importorskip("skimage")
    from vaultlab.figures.understand.whitespace import classify_panel_layout

    path = _make_four_panel_fixture(tmp_path)
    assert classify_panel_layout(path) == "multi_panel"


def test_is_single_plot_true_for_figure_with_inset(tmp_path: Path):
    """An inset-bearing figure is STILL one panel — `is_single_plot` must
    return True so the layout dispatcher doesn't try to subdivide it."""
    pytest.importorskip("skimage")
    from vaultlab.figures.understand.whitespace import is_single_plot

    path = _make_inset_axes_fixture(tmp_path)
    assert is_single_plot(path) is True


def test_suggest_layout_for_inset_figure_does_not_subdivide(tmp_path: Path):
    """Layout dispatch on an inset-bearing single plot must NOT route to
    figure_with_panels — the inset is part of the same panel."""
    pytest.importorskip("skimage")
    from vaultlab.figures.contract import suggest_figure_layout

    path = _make_inset_axes_fixture(tmp_path)
    for has_bullets in (False, True):
        for has_caption in (False, True):
            layout = suggest_figure_layout(
                path, has_bullets=has_bullets, has_caption=has_caption
            )
            assert layout != "figure_with_panels", (
                f"inset figure must never be classed as figure_with_panels "
                f"(has_bullets={has_bullets}, has_caption={has_caption}, got {layout!r})"
            )
