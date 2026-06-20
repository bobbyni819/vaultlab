"""Tests for project-configurable publication figure profiles."""

from __future__ import annotations

from pathlib import Path


def test_default_profile_round_trips_via_dict() -> None:
    from vaultlab.figures.publication.profile import StyleProfile, default_profile

    profile = default_profile()
    assert StyleProfile.from_dict(profile.to_dict()) == profile


def test_from_toml_reads_figure_profile_and_defaults_missing_keys(tmp_path: Path) -> None:
    from vaultlab.figures.publication.profile import FontRegime, StyleProfile

    config = tmp_path / "figure-profile.toml"
    config.write_text(
        """
[figure_profile]
journal = "cell"
width_mm = 89.0
font_regime = "talk"
entity_palettes = { cell_type = ["#111111", "#222222"] }
semantic_colors = { emphasis = "#ABCDEF" }
heatmap = { cmap = "viridis", gridlines = true }
""".lstrip(),
        encoding="utf-8",
    )

    profile = StyleProfile.from_toml(config)

    assert profile.journal == "cell"
    assert profile.width_mm == 89.0
    assert profile.max_height_mm == StyleProfile().max_height_mm
    assert profile.font_regime is FontRegime.TALK
    assert profile.entity_palettes["cell_type"] == ["#111111", "#222222"]
    assert profile.semantic_colors["emphasis"] == "#ABCDEF"
    assert profile.semantic_colors["neutral_grey"] == StyleProfile().semantic_colors["neutral_grey"]
    assert profile.heatmap["cmap"] == "viridis"
    assert profile.heatmap["gridlines"] is True
    assert profile.heatmap["annotate_cells"] is False


def test_apply_profile_registers_entity_palettes_and_semantic_colors() -> None:
    import matplotlib

    matplotlib.use("Agg")

    from vaultlab.figures.publication.color import PaletteRegistry
    from vaultlab.figures.publication.profile import StyleProfile, apply_profile

    profile = StyleProfile(
        entity_palettes={"cell_type": ["#111111", "#222222"]},
        semantic_colors={"neutral_grey": "#888888", "positive": "#00AA00"},
    )

    registry = apply_profile(profile, registry=PaletteRegistry())

    assert registry["cell_type"] == {"0": "#111111", "1": "#222222"}
    assert registry["semantic_colors"]["positive"] == "#00AA00"


def test_resolve_entity_palette_uses_declared_palette_then_palette_for_fallback() -> None:
    from vaultlab.figures.publication.color import palette_for
    from vaultlab.figures.publication.profile import StyleProfile, resolve_entity_palette

    profile = StyleProfile(entity_palettes={"cell_type": ["#111111", "#222222", "#333333"]})

    assert resolve_entity_palette(profile, "cell_type", 2) == ("#111111", "#222222")
    assert resolve_entity_palette(profile, "missing", 3) == palette_for(3)


def test_heatmap_kwargs_reflect_profile_conventions() -> None:
    from vaultlab.figures.publication.profile import StyleProfile, heatmap_kwargs

    kwargs = heatmap_kwargs(StyleProfile())

    assert kwargs["cmap"] == "RdBu_r"
    assert kwargs["linewidths"] == 0
    assert kwargs["linecolor"] is None
    assert kwargs["annot"] is False
    assert kwargs["bicluster"] is True


def test_font_regime_changes_active_base_font_size() -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib as mpl

    from vaultlab.figures.publication.profile import FontRegime, StyleProfile, apply_profile

    apply_profile(StyleProfile(font_regime=FontRegime.MANUSCRIPT))
    manuscript_size = mpl.rcParams["font.size"]

    apply_profile(StyleProfile(font_regime=FontRegime.TALK))
    talk_size = mpl.rcParams["font.size"]

    assert manuscript_size < talk_size
    assert talk_size >= 20
