"""Tests for vaultlab.research.arc_styles_loader."""

from __future__ import annotations

from pathlib import Path

import pytest

from vaultlab.research.arc_styles_loader import (
    ArcStyle,
    UnknownArcStyleError,
    all_arc_styles,
    get_arc_style,
    list_arc_styles,
)


def _write_style(path: Path, *, style_id: str, target_paragraphs: int = 3,
                 body: str = "# Style body\n") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fm = (
        "---\n"
        f"style_id: {style_id}\n"
        f"title: Test {style_id}\n"
        f"audience: Test audience\n"
        f"target_paragraphs: {target_paragraphs}\n"
        f"default_scope: short\n"
        "---\n\n"
    )
    path.write_text(fm + body, encoding="utf-8")


def test_list_arc_styles_includes_shipped_styles():
    """The bundled styles should be discoverable without test overrides."""
    styles = list_arc_styles()
    assert "journal_club" in styles
    assert "review_paper_strict" in styles
    assert "slide_deck_script" in styles
    assert "grant_aims" in styles


def test_get_arc_style_loads_journal_club():
    style = get_arc_style("journal_club")
    assert isinstance(style, ArcStyle)
    assert style.style_id == "journal_club"
    assert style.target_paragraphs == 3
    assert style.default_scope == "short"
    assert "thesis" in style.system_prompt.lower()
    assert "head-to-head" in style.system_prompt.lower()


def test_get_arc_style_loads_review_paper_strict():
    style = get_arc_style("review_paper_strict")
    assert style.target_paragraphs >= 10  # comprehensive review
    assert style.default_scope == "review-paper"
    assert "methodology paragraph" in style.system_prompt.lower()


def test_get_arc_style_returns_path_to_source():
    style = get_arc_style("journal_club")
    assert style.source_path.name == "journal_club.md"
    assert style.source_path.is_file()


def test_unknown_style_raises():
    with pytest.raises(UnknownArcStyleError):
        get_arc_style("nonexistent_style")


def test_styles_dir_override(tmp_path: Path):
    """Test injection: load from a custom styles directory."""
    _write_style(tmp_path / "custom.md", style_id="custom",
                 body="# Custom guidance\n")

    assert list_arc_styles(styles_dir=tmp_path) == ["custom"]
    style = get_arc_style("custom", styles_dir=tmp_path)
    assert style.style_id == "custom"
    assert "Custom guidance" in style.system_prompt


def test_missing_frontmatter_raises(tmp_path: Path):
    bad = tmp_path / "bad.md"
    bad.write_text("just a body, no frontmatter\n", encoding="utf-8")
    with pytest.raises(ValueError, match="frontmatter"):
        get_arc_style("bad", styles_dir=tmp_path)


def test_missing_required_field_raises(tmp_path: Path):
    bad = tmp_path / "bad.md"
    bad.write_text(
        "---\nstyle_id: bad\ntitle: bad\n---\nbody\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="required frontmatter fields"):
        get_arc_style("bad", styles_dir=tmp_path)


def test_invalid_yaml_raises(tmp_path: Path):
    bad = tmp_path / "bad.md"
    bad.write_text(
        "---\nstyle_id: [unclosed\n---\nbody\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="invalid frontmatter"):
        get_arc_style("bad", styles_dir=tmp_path)


def test_all_arc_styles_returns_full_catalog():
    styles = all_arc_styles()
    style_ids = {s.style_id for s in styles}
    assert "journal_club" in style_ids
    assert "review_paper_strict" in style_ids
    assert "slide_deck_script" in style_ids
    assert "grant_aims" in style_ids


def test_all_arc_styles_skips_malformed_silently(tmp_path: Path):
    """A broken .md file in the directory should not crash the catalog."""
    _write_style(tmp_path / "good.md", style_id="good")
    (tmp_path / "broken.md").write_text(
        "---\nstyle_id: [bad\n---\n",
        encoding="utf-8",
    )

    styles = all_arc_styles(styles_dir=tmp_path)
    style_ids = {s.style_id for s in styles}
    assert "good" in style_ids
    assert "broken" not in style_ids


def test_arc_style_is_immutable():
    style = get_arc_style("journal_club")
    with pytest.raises((AttributeError, Exception)):
        style.title = "modified"  # frozen dataclass
