"""Load arc-style prompts from ``arc_styles/<name>.md`` files.

Per Karpathy 2026-05-01 + vaultlab META PRINCIPLE #1: framing /
voice / structural-discipline differences between report types
(journal club vs review paper vs grant background vs slide deck) are
prompt-level differences, not Python differences. This module just
reads the markdown files and exposes them as :class:`ArcStyle`
objects the narrator can use.

Adding a new style: drop a ``<name>.md`` in ``arc_styles/`` with the
required frontmatter (``style_id``, ``title``, ``audience``,
``target_paragraphs``, ``default_scope``); it becomes available
immediately via :func:`get_arc_style(name)`. No Python changes
required.

Public API
----------
* :func:`list_arc_styles` — names of all available styles.
* :func:`get_arc_style` — load one style by name.
* :class:`ArcStyle` — frontmatter + body content as a frozen dataclass.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import yaml

_ARC_STYLES_DIR = Path(__file__).parent / "arc_styles"


@dataclass(frozen=True)
class ArcStyle:
    """One rendering style for a literature lineage arc.

    Attributes:
        style_id: Filename-friendly id (e.g., ``"journal_club"``).
        title: Human-readable title (e.g., ``"Journal-club intro"``).
        audience: One-line audience description.
        target_paragraphs: Suggested total paragraph count.
        default_scope: Default scope to pair with this style if no
            explicit ``--scope`` is passed.
        system_prompt: The full markdown body of the style file (used
            as the narrator's system prompt overrride).
        source_path: Path to the style's source ``.md`` file.
        requires_comparison_table: When True, the narrator emits a
            markdown comparison table whenever ≥3 methods are
            compared in one section. Defaults to False.
        defend_thesis_section: When True, the narrator adds a
            2-paragraph thesis-defense section immediately after
            Introduction. Defaults to False.
        run_empty_tldr_audit: When True, a pre-flight audit flags
            Tier-A summaries with empty TL;DR content; the narrator
            then either re-reads those PDFs or excludes them from
            citation. Defaults to False.
    """

    style_id: str
    title: str
    audience: str
    target_paragraphs: int
    default_scope: str
    system_prompt: str
    source_path: Path
    requires_comparison_table: bool = False
    defend_thesis_section: bool = False
    run_empty_tldr_audit: bool = False


class UnknownArcStyleError(KeyError):
    """Raised when :func:`get_arc_style` is asked for a non-existent style."""


def list_arc_styles(*, styles_dir: Path | None = None) -> list[str]:
    """Return the names of all available arc styles.

    Args:
        styles_dir: Override the default ``arc_styles/`` location
            (test injection).

    Returns:
        Sorted list of style ids (filenames without ``.md``).
    """
    target = styles_dir or _ARC_STYLES_DIR
    if not target.is_dir():
        return []
    return sorted(p.stem for p in target.glob("*.md"))


def get_arc_style(
    name: str,
    *,
    styles_dir: Path | None = None,
) -> ArcStyle:
    """Load one arc style by name.

    Args:
        name: Style id (filename without ``.md``).
        styles_dir: Override the default ``arc_styles/`` location.

    Raises:
        UnknownArcStyleError: When no such style file exists.
        ValueError: When the style file lacks required frontmatter.
    """
    target_dir = styles_dir or _ARC_STYLES_DIR
    style_path = target_dir / f"{name}.md"
    if not style_path.is_file():
        available = list_arc_styles(styles_dir=target_dir)
        raise UnknownArcStyleError(
            f"Unknown arc style {name!r}. Available: {available}"
        )

    text = style_path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        raise ValueError(
            f"Arc style {style_path} missing YAML frontmatter "
            "(must start with '---')."
        )

    try:
        _, fm_text, body = text.split("---", 2)
        fm = yaml.safe_load(fm_text) or {}
    except (ValueError, yaml.YAMLError) as exc:
        raise ValueError(
            f"Arc style {style_path} has invalid frontmatter: {exc}"
        ) from exc

    required = {"style_id", "title", "audience", "target_paragraphs",
                "default_scope"}
    missing = required - set(fm.keys())
    if missing:
        raise ValueError(
            f"Arc style {style_path} missing required frontmatter "
            f"fields: {sorted(missing)}"
        )

    return ArcStyle(
        style_id=str(fm["style_id"]),
        title=str(fm["title"]),
        audience=str(fm["audience"]),
        target_paragraphs=int(fm["target_paragraphs"]),
        default_scope=str(fm["default_scope"]),
        system_prompt=body.strip(),
        source_path=style_path,
        requires_comparison_table=bool(fm.get("requires_comparison_table", False)),
        defend_thesis_section=bool(fm.get("defend_thesis_section", False)),
        run_empty_tldr_audit=bool(fm.get("run_empty_tldr_audit", False)),
    )


def all_arc_styles(*, styles_dir: Path | None = None) -> list[ArcStyle]:
    """Load every arc style from disk (convenience for help / catalog UIs).

    Returns:
        List of all :class:`ArcStyle` instances, sorted by id.
    """
    out: list[ArcStyle] = []
    for name in list_arc_styles(styles_dir=styles_dir):
        try:
            out.append(get_arc_style(name, styles_dir=styles_dir))
        except (UnknownArcStyleError, ValueError):
            # Malformed style file — skip but don't crash the catalog.
            continue
    return out


__all__ = [
    "ArcStyle",
    "UnknownArcStyleError",
    "all_arc_styles",
    "get_arc_style",
    "list_arc_styles",
]
