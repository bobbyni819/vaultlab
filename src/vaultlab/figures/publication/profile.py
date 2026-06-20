"""Project-configurable publication style profiles.

Profiles layer journal/font/palette/heatmap choices over the existing
publication helpers. They do not replace :mod:`style` or :mod:`color`; they
call into those modules so old recipes keep their current Nature look unless
the caller opts into a project profile.
"""

from __future__ import annotations

import tomllib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Final, Self

from vaultlab.figures.publication.color import (
    CB_PALETTE,
    NEUTRAL_GREY,
    SIG_COLOR_DOWN,
    SIG_COLOR_UP,
    PaletteRegistry,
    palette_for,
)
from vaultlab.figures.publication.style import (
    BAR_EDGE_WIDTH,
    LABEL_SIZE,
    LEGEND_SIZE,
    LINE_WIDTH,
    SPINE_WIDTH,
    TICK_SIZE,
    TITLE_SIZE,
    setup_rcparams,
)

NATURE_DOUBLE_COLUMN_WIDTH_MM: Final = 177.8
NATURE_DEFAULT_MAX_HEIGHT_MM: Final = 127.0
DEFAULT_COLORBAR_LABEL_ROTATION: Final = 270


class FontRegime(str, Enum):
    """Typography regimes for publication panels versus presentation slides."""

    MANUSCRIPT = "manuscript"
    TALK = "talk"


@dataclass(frozen=True)
class FontRegimeSizes:
    """Base font size and minimum readable floor for a font regime."""

    base_size: float
    floor_size: float


def font_regime_sizes(regime: FontRegime) -> FontRegimeSizes:
    """Return the base font size and floor for ``regime``."""
    if regime is FontRegime.TALK:
        return FontRegimeSizes(base_size=22.0, floor_size=20.0)
    return FontRegimeSizes(base_size=8.0, floor_size=5.0)


def _default_semantic_colors() -> dict[str, str]:
    return {
        "neutral_grey": NEUTRAL_GREY,
        "positive": SIG_COLOR_UP,
        "negative": SIG_COLOR_DOWN,
        "emphasis": CB_PALETTE[0],
    }


def _default_heatmap() -> dict[str, Any]:
    return {
        "bicluster": True,
        "gridlines": False,
        "annotate_cells": False,
        "cmap": "RdBu_r",
    }


def _coerce_font_regime(value: Any) -> FontRegime:
    if isinstance(value, FontRegime):
        return value
    if isinstance(value, str):
        return FontRegime(value.lower())
    raise TypeError(f"font_regime must be a FontRegime or str, got {type(value).__name__}")


def _coerce_str_list_mapping(value: Any, *, field_name: str) -> dict[str, list[str]]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise TypeError(f"{field_name} must be a mapping, got {type(value).__name__}")

    coerced: dict[str, list[str]] = {}
    for raw_key, raw_colors in value.items():
        key = str(raw_key)
        if isinstance(raw_colors, str) or not isinstance(raw_colors, Sequence):
            raise TypeError(f"{field_name}.{key} must be a sequence of color strings")
        coerced[key] = [str(color) for color in raw_colors]
    return coerced


def _coerce_str_mapping(value: Any, *, defaults: Mapping[str, str], field_name: str) -> dict[str, str]:
    merged = dict(defaults)
    if value is None:
        return merged
    if not isinstance(value, Mapping):
        raise TypeError(f"{field_name} must be a mapping, got {type(value).__name__}")
    merged.update({str(key): str(color) for key, color in value.items()})
    return merged


def _coerce_heatmap(value: Any, *, defaults: Mapping[str, Any]) -> dict[str, Any]:
    merged = dict(defaults)
    if value is None:
        return merged
    if not isinstance(value, Mapping):
        raise TypeError(f"heatmap must be a mapping, got {type(value).__name__}")
    merged.update({str(key): item for key, item in value.items()})
    return merged


@dataclass(frozen=True)
class StyleProfile:
    """One project-level figure style configuration."""

    journal: str = "nature"
    width_mm: float = NATURE_DOUBLE_COLUMN_WIDTH_MM
    max_height_mm: float = NATURE_DEFAULT_MAX_HEIGHT_MM
    font_regime: FontRegime = FontRegime.MANUSCRIPT
    entity_palettes: dict[str, list[str]] = field(default_factory=dict)
    semantic_colors: dict[str, str] = field(default_factory=_default_semantic_colors)
    heatmap: dict[str, Any] = field(default_factory=_default_heatmap)
    greek_glyphs: bool = True
    colorbar_label_rotation: int = DEFAULT_COLORBAR_LABEL_ROTATION
    no_emdash_titles: bool = True

    def to_dict(self) -> dict[str, Any]:
        """Return a TOML/JSON-serializable representation."""
        return {
            "journal": self.journal,
            "width_mm": self.width_mm,
            "max_height_mm": self.max_height_mm,
            "font_regime": self.font_regime.value,
            "entity_palettes": {key: list(colors) for key, colors in self.entity_palettes.items()},
            "semantic_colors": dict(self.semantic_colors),
            "heatmap": dict(self.heatmap),
            "greek_glyphs": self.greek_glyphs,
            "colorbar_label_rotation": self.colorbar_label_rotation,
            "no_emdash_titles": self.no_emdash_titles,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Self:
        """Build a profile from a partial mapping, filling missing defaults."""
        defaults = cls()
        return cls(
            journal=str(data.get("journal", defaults.journal)),
            width_mm=float(data.get("width_mm", defaults.width_mm)),
            max_height_mm=float(data.get("max_height_mm", defaults.max_height_mm)),
            font_regime=_coerce_font_regime(data.get("font_regime", defaults.font_regime)),
            entity_palettes=_coerce_str_list_mapping(
                data.get("entity_palettes", defaults.entity_palettes),
                field_name="entity_palettes",
            ),
            semantic_colors=_coerce_str_mapping(
                data.get("semantic_colors"),
                defaults=defaults.semantic_colors,
                field_name="semantic_colors",
            ),
            heatmap=_coerce_heatmap(data.get("heatmap"), defaults=defaults.heatmap),
            greek_glyphs=bool(data.get("greek_glyphs", defaults.greek_glyphs)),
            colorbar_label_rotation=int(
                data.get("colorbar_label_rotation", defaults.colorbar_label_rotation)
            ),
            no_emdash_titles=bool(data.get("no_emdash_titles", defaults.no_emdash_titles)),
        )

    @classmethod
    def from_toml(cls, path: Path | str) -> Self:
        """Read a ``[figure_profile]`` table from TOML."""
        with Path(path).open("rb") as handle:
            raw = tomllib.load(handle)
        table = raw.get("figure_profile", {})
        if not isinstance(table, Mapping):
            raise TypeError("[figure_profile] must be a TOML table")
        return cls.from_dict(table)


def default_profile() -> StyleProfile:
    """Return the default Nature-style manuscript profile."""
    return StyleProfile()


def _rcparams_for_profile(profile: StyleProfile) -> dict[str, Any]:
    sizes = font_regime_sizes(profile.font_regime)
    if profile.font_regime is FontRegime.TALK:
        title_size = sizes.base_size + 4.0
        label_size = sizes.base_size + 2.0
        tick_size = sizes.floor_size
        legend_size = sizes.floor_size
    else:
        title_size = float(TITLE_SIZE)
        label_size = float(LABEL_SIZE)
        tick_size = float(TICK_SIZE)
        legend_size = float(LEGEND_SIZE)

    return {
        "font.size": sizes.base_size,
        "axes.titlesize": title_size,
        "axes.labelsize": label_size,
        "xtick.labelsize": tick_size,
        "ytick.labelsize": tick_size,
        "legend.fontsize": legend_size,
        "axes.linewidth": SPINE_WIDTH,
        "lines.linewidth": LINE_WIDTH,
        "patch.linewidth": BAR_EDGE_WIDTH,
    }


def apply_profile(
    profile: StyleProfile,
    *,
    registry: PaletteRegistry | None = None,
) -> PaletteRegistry:
    """Apply rcParams and register project palettes for ``profile``."""
    import matplotlib as mpl

    setup_rcparams()
    mpl.rcParams.update(_rcparams_for_profile(profile))

    active_registry = registry or PaletteRegistry()
    for entity, colors in profile.entity_palettes.items():
        active_registry.register(entity, {str(index): color for index, color in enumerate(colors)})
    active_registry.register("semantic_colors", profile.semantic_colors)
    return active_registry


def resolve_entity_palette(profile: StyleProfile, entity: str, n: int) -> tuple[str, ...]:
    """Resolve colors for an entity, falling back to the colorblind-safe palette."""
    if n <= 0:
        return ()

    declared = tuple(profile.entity_palettes.get(entity, ()))
    if len(declared) >= n:
        return declared[:n]
    if declared:
        fallback = tuple(color for color in palette_for(n) if color not in declared)
        return (*declared, *fallback)[:n]
    return palette_for(n)


def heatmap_kwargs(profile: StyleProfile) -> dict[str, Any]:
    """Return heatmap plotting kwargs implied by ``profile``."""
    gridlines = bool(profile.heatmap.get("gridlines", False))
    return {
        "cmap": str(profile.heatmap.get("cmap", "RdBu_r")),
        "linewidths": 0.5 if gridlines else 0,
        "linecolor": "white" if gridlines else None,
        "annot": bool(profile.heatmap.get("annotate_cells", False)),
        "bicluster": bool(profile.heatmap.get("bicluster", True)),
    }


__all__ = [
    "FontRegime",
    "FontRegimeSizes",
    "StyleProfile",
    "apply_profile",
    "default_profile",
    "font_regime_sizes",
    "heatmap_kwargs",
    "resolve_entity_palette",
]
