"""Unit tests for vaultlab.figures.publication.

Tests the pure-Python parts (no matplotlib needed). Tests that touch
matplotlib are marked `slow` and run with optional matplotlib install.
"""

from __future__ import annotations

import pytest

# -----------------------------------------------------------------------------
# color.py — palettes and Rule 14 discipline
# -----------------------------------------------------------------------------


class TestPalettes:
    """Colorblind-safe palettes are correctly sized and shaped."""

    def test_cb_palette_has_9_colors(self) -> None:
        from vaultlab.figures.publication import CB_PALETTE

        assert len(CB_PALETTE) == 9
        assert all(c.startswith("#") and len(c) == 7 for c in CB_PALETTE)

    def test_ext_palette_has_24_colors(self) -> None:
        from vaultlab.figures.publication import EXT_PALETTE

        assert len(EXT_PALETTE) == 24
        # CB_PALETTE is the prefix of EXT_PALETTE — preserves stable mapping
        from vaultlab.figures.publication import CB_PALETTE

        assert EXT_PALETTE[: len(CB_PALETTE)] == CB_PALETTE

    def test_palette_for_small_n_uses_cb_palette(self) -> None:
        from vaultlab.figures.publication import CB_PALETTE, palette_for

        assert palette_for(3) == CB_PALETTE[:3]
        assert palette_for(9) == CB_PALETTE

    def test_palette_for_medium_n_uses_ext_palette(self) -> None:
        from vaultlab.figures.publication import EXT_PALETTE, palette_for

        assert palette_for(15) == EXT_PALETTE[:15]
        assert palette_for(24) == EXT_PALETTE

    def test_palette_for_zero_or_negative_returns_empty(self) -> None:
        from vaultlab.figures.publication import palette_for

        assert palette_for(0) == ()
        assert palette_for(-1) == ()

    def test_palette_for_oversize_warns_and_cycles(self) -> None:
        from vaultlab.figures.publication import palette_for

        with pytest.warns(UserWarning, match="exceeds 24"):
            result = palette_for(30)
        assert len(result) == 30


class TestPaletteRegistry:
    """PaletteRegistry holds named palettes for cross-figure consistency."""

    def test_register_and_retrieve(self) -> None:
        from vaultlab.figures.publication import PaletteRegistry

        reg = PaletteRegistry()
        reg.register("cell_types", {"T cell": "#5A89A7", "B cell": "#8B008B"})
        assert reg["cell_types"]["T cell"] == "#5A89A7"

    def test_get_with_default(self) -> None:
        from vaultlab.figures.publication import PaletteRegistry

        reg = PaletteRegistry()
        assert reg.get("missing") is None
        assert reg.get("missing", default={}) == {}

    def test_list_palettes_sorted(self) -> None:
        from vaultlab.figures.publication import PaletteRegistry

        reg = PaletteRegistry()
        reg.register("zoo", {})
        reg.register("alpha", {})
        assert reg.list_palettes() == ["alpha", "zoo"]

    def test_membership(self) -> None:
        from vaultlab.figures.publication import PaletteRegistry

        reg = PaletteRegistry()
        reg.register("foo", {})
        assert "foo" in reg
        assert "bar" not in reg


class TestBarFillRule14:
    """bar_fill() enforces Rule 14 neutral-grey discipline."""

    def test_default_is_neutral_grey(self) -> None:
        from vaultlab.figures.publication import NEUTRAL_GREY, bar_fill

        result = bar_fill(["A", "B", "C"])
        assert result == [NEUTRAL_GREY] * 3

    def test_sign_overrides_to_red_blue_grey(self) -> None:
        from vaultlab.figures.publication import (
            SIG_COLOR_DOWN,
            SIG_COLOR_NS,
            SIG_COLOR_UP,
            bar_fill,
        )

        result = bar_fill(["up", "down", "ns"], sign=[2.0, -1.5, 0.0])
        assert result == [SIG_COLOR_UP, SIG_COLOR_DOWN, SIG_COLOR_NS]

    def test_sign_threshold_near_zero_is_ns(self) -> None:
        from vaultlab.figures.publication import SIG_COLOR_NS, bar_fill

        # Values within +/- 1e-3 are treated as non-significant
        result = bar_fill(["a", "b"], sign=[5e-4, -5e-4])
        assert result == [SIG_COLOR_NS, SIG_COLOR_NS]

    def test_palette_overrides_default_for_known_labels(self) -> None:
        from vaultlab.figures.publication import NEUTRAL_GREY, bar_fill

        palette = {"T cell": "#5A89A7", "B cell": "#8B008B"}
        result = bar_fill(["T cell", "B cell", "Unknown"], palette=palette)
        assert result == ["#5A89A7", "#8B008B", NEUTRAL_GREY]

    def test_sign_takes_precedence_over_palette(self) -> None:
        # When both provided, sign wins (Rule 14: sign-encoding is the
        # only opt-in for emphasis)
        from vaultlab.figures.publication import SIG_COLOR_UP, bar_fill

        result = bar_fill(["A"], sign=[1.0], palette={"A": "#000000"})
        assert result == [SIG_COLOR_UP]

    def test_mismatched_lengths_raises(self) -> None:
        from vaultlab.figures.publication import bar_fill

        with pytest.raises(ValueError, match="len"):
            bar_fill(["A", "B"], sign=[1.0])  # mismatched lengths


# -----------------------------------------------------------------------------
# legend.py — density-aware positioning
# -----------------------------------------------------------------------------


class TestLegendPositionForDensity:
    """legend_position_for_density picks the emptiest quadrant."""

    def test_returns_valid_position_string(self) -> None:
        from vaultlab.figures.publication import legend_position_for_density

        result = legend_position_for_density([0, 1, 2], [0, 1, 2])
        assert result in {"upper right", "upper left", "lower right", "lower left"}

    def test_picks_emptiest_quadrant(self) -> None:
        from vaultlab.figures.publication import legend_position_for_density

        # All points in upper-right; legend should go to one of the other 3
        x = [0.6, 0.7, 0.8, 0.9]
        y = [0.6, 0.7, 0.8, 0.9]
        result = legend_position_for_density(x, y)
        assert result != "upper right"

    def test_empty_data_returns_first_candidate(self) -> None:
        from vaultlab.figures.publication import legend_position_for_density

        result = legend_position_for_density([], [])
        assert result == "upper right"  # first default candidate

    def test_mismatched_lengths_raises(self) -> None:
        from vaultlab.figures.publication import legend_position_for_density

        with pytest.raises(ValueError, match="len"):
            legend_position_for_density([1, 2], [1])


# -----------------------------------------------------------------------------
# stamp.py — parameter-aware filenames
# -----------------------------------------------------------------------------


class TestParameterStamp:
    """parameter_stamp embeds CLI params into filenames."""

    def test_no_params_returns_base(self) -> None:
        from vaultlab.figures.publication.stamp import parameter_stamp

        assert parameter_stamp(base="heatmap") == "heatmap"

    def test_single_param_appends(self) -> None:
        from vaultlab.figures.publication.stamp import parameter_stamp

        assert parameter_stamp(base="cluster_umap", K=8) == "cluster_umap_K8"

    def test_multiple_params_appended(self) -> None:
        from vaultlab.figures.publication.stamp import parameter_stamp

        result = parameter_stamp(base="cluster_umap", K=8, resolution=0.6)
        # multi-letter keys get abbreviated to first 3 chars
        assert "K8" in result
        assert "res0.6" in result

    def test_string_values_preserved(self) -> None:
        from vaultlab.figures.publication.stamp import parameter_stamp

        assert parameter_stamp(base="x", method="leiden") == "x_metleiden"


# -----------------------------------------------------------------------------
# coverage.py — CoverageManifest skeleton
# -----------------------------------------------------------------------------


class TestCoverageManifest:
    """CoverageManifest skeleton (P0.2 placeholder)."""

    def test_creation_with_required_fields(self) -> None:
        from vaultlab.figures.publication.coverage import CoverageManifest

        m = CoverageManifest(
            figure_id="fig1",
            script_path="recipes/heatmap.py",
            timestamp="2026-04-28T15:00:00Z",
        )
        assert m.figure_id == "fig1"
        assert m.regions_included == []  # default

    def test_footer_text_with_no_coverage(self) -> None:
        from vaultlab.figures.publication.coverage import CoverageManifest

        m = CoverageManifest(figure_id="fig1", script_path="x", timestamp="t")
        assert "unspecified" in m.as_footer_text()

    def test_footer_text_with_regions_donors_celltypes(self) -> None:
        from vaultlab.figures.publication.coverage import CoverageManifest

        m = CoverageManifest(
            figure_id="fig1",
            script_path="x",
            timestamp="t",
            regions_included=["mucosa", "submucosa"],
            donors_included=["d1", "d2", "d3"],
            cell_types_included=["T", "B", "NK"],
            exclusions=["muscularis"],
        )
        text = m.as_footer_text()
        assert "mucosa, submucosa" in text
        assert "n=3" in text  # donors
        assert "muscularis" in text


# -----------------------------------------------------------------------------
# style.py — rcParams and style_ax (require matplotlib; marked slow)
# -----------------------------------------------------------------------------


@pytest.mark.slow
class TestStyleAx:
    """style_ax applies publication-tight defaults to a matplotlib axis."""

    def test_setup_rcparams_idempotent(self) -> None:
        from vaultlab.figures.publication import setup_rcparams

        setup_rcparams()
        setup_rcparams()  # no error on second call

    def test_style_ax_sets_title_and_labels(self) -> None:
        import matplotlib

        matplotlib.use("Agg")  # headless
        import matplotlib.pyplot as plt

        from vaultlab.figures.publication import style_ax

        fig, ax = plt.subplots()
        style_ax(ax, title="My Title", xlabel="x", ylabel="y")
        assert ax.get_title() == "My Title"
        assert ax.get_xlabel() == "x"
        assert ax.get_ylabel() == "y"
        plt.close(fig)

    def test_style_ax_despine_hides_top_and_right(self) -> None:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        from vaultlab.figures.publication import style_ax

        fig, ax = plt.subplots()
        style_ax(ax, despine=True)
        assert not ax.spines["top"].get_visible()
        assert not ax.spines["right"].get_visible()
        plt.close(fig)
