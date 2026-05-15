"""Tests for vaultlab.kb.indexes — auto-generated _Index/_Catalog/_BackLinks."""

from __future__ import annotations

from pathlib import Path

from vaultlab.kb.indexes import build_indexes


# ---------------------------------------------------------------------------
# Fixture builder (mirrors test_retrieve so the two tests are easy to read
# side-by-side).
# ---------------------------------------------------------------------------


def _write(path: Path, frontmatter_dict: dict | None, body: str = "") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if frontmatter_dict is None:
        path.write_text(body, encoding="utf-8")
        return
    lines = ["---"]
    for k, v in frontmatter_dict.items():
        lines.append(f"{k}: {v}")
    lines.append("---")
    lines.append("")
    lines.append(body)
    path.write_text("\n".join(lines), encoding="utf-8")


def _make_kb(tmp_path: Path) -> Path:
    _write(
        tmp_path / "Wiki" / "Concepts" / "lipid-pathway.md",
        {"type": "wiki", "project": "metabolism", "created": "2026-04-21"},
        "Lipid-pathway concept. See [[maldi-imaging]] and [[paper-one]].",
    )
    _write(
        tmp_path / "Wiki" / "Concepts" / "maldi-imaging.md",
        {"type": "wiki", "project": "metabolism", "created": "2026-04-22"},
        "MALDI imaging concept. See [[lipid-pathway]].",
    )
    _write(
        tmp_path / "Sources" / "Papers" / "paper-one.md",
        {"type": "paper", "year": 2023, "created": "2026-01-15"},
        "Paper one full text referencing [[lipid-pathway]].",
    )
    _write(
        tmp_path / "Sources" / "Papers" / "paper-two.md",
        {"type": "paper", "year": 2024},  # no `created:`
        "Paper two on a different topic referencing [[maldi-imaging|MALDI]].",
    )
    _write(
        tmp_path / "Sources" / "Notes" / "scratch.md",
        None,
        "Scratch note (no frontmatter) referencing [[maldi-imaging]].",
    )
    _write(
        tmp_path / ".obsidian" / "leaked.md",
        {"type": "wiki", "created": "2026-04-23"},
        "Should never appear.",
    )
    return tmp_path


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestBuildIndexes:
    def test_returns_three_paths(self, tmp_path: Path) -> None:
        kb = _make_kb(tmp_path)
        result = build_indexes(kb)
        assert set(result.keys()) == {"index", "catalog", "backlinks"}
        for key in ("index", "catalog", "backlinks"):
            assert result[key].exists()
            assert result[key].parent == kb

    def test_index_groups_by_type(self, tmp_path: Path) -> None:
        kb = _make_kb(tmp_path)
        build_indexes(kb)
        text = (kb / "_Index.md").read_text(encoding="utf-8")
        # Has type sections
        assert "## wiki" in text
        assert "## paper" in text
        # Wiki notes appear under wiki
        wiki_section_idx = text.index("## wiki")
        paper_section_idx = text.index("## paper")
        # Both files should appear in the right sections (we check by name).
        # Paper section starts before wiki alphabetically.
        assert paper_section_idx < wiki_section_idx
        assert "lipid-pathway" in text
        assert "maldi-imaging" in text
        assert "paper-one" in text
        assert "paper-two" in text
        # Scratch note (no frontmatter) is NOT in _Index.md
        assert "scratch" not in text
        # .obsidian leak is NOT included
        assert "leaked" not in text

    def test_catalog_chronological_newest_first(self, tmp_path: Path) -> None:
        kb = _make_kb(tmp_path)
        build_indexes(kb)
        text = (kb / "_Catalog.md").read_text(encoding="utf-8")
        # maldi-imaging (2026-04-22) should appear before lipid-pathway (2026-04-21)
        idx_maldi = text.index("maldi-imaging")
        idx_lipid = text.index("lipid-pathway")
        idx_paper_one = text.index("paper-one")
        assert idx_maldi < idx_lipid < idx_paper_one
        # paper-two has no `created:` → Undated section, appears last.
        assert "## Undated" in text
        idx_undated = text.index("## Undated")
        idx_paper_two = text.index("paper-two")
        assert idx_undated < idx_paper_two

    def test_backlinks_lists_referrers(self, tmp_path: Path) -> None:
        kb = _make_kb(tmp_path)
        build_indexes(kb)
        text = (kb / "_BackLinks.md").read_text(encoding="utf-8")

        # `lipid-pathway` is referenced by maldi-imaging.md and paper-one.md.
        # Find the section header then verify referrers below it.
        assert "## lipid-pathway" in text
        # `maldi-imaging` is referenced by lipid-pathway.md, paper-two.md
        # (with alias), AND scratch.md (no frontmatter — should still count
        # as a referrer per docstring).
        assert "## maldi-imaging" in text
        # `paper-one` is referenced by lipid-pathway.md.
        assert "## paper-one" in text

        # Inspect the maldi-imaging section to verify three referrers.
        idx = text.index("## maldi-imaging")
        # Read until next section or EOF.
        next_idx = text.find("\n## ", idx + 1)
        section = text[idx : next_idx if next_idx != -1 else len(text)]
        # All three referrer paths should appear.
        assert "Wiki/Concepts/lipid-pathway.md" in section
        assert "Sources/Papers/paper-two.md" in section
        assert "Sources/Notes/scratch.md" in section

    def test_self_reference_not_recorded(self, tmp_path: Path) -> None:
        """A file referencing itself by stem is not a backlink."""
        _write(
            tmp_path / "Wiki" / "Concepts" / "selfref.md",
            {"type": "wiki"},
            "I reference [[selfref]] for fun.",
        )
        build_indexes(tmp_path)
        text = (tmp_path / "_BackLinks.md").read_text(encoding="utf-8")
        # The `selfref` section should not exist (no real backlinks).
        assert "## selfref" not in text

    def test_dotfile_dirs_excluded(self, tmp_path: Path) -> None:
        kb = _make_kb(tmp_path)
        build_indexes(kb)
        for name in ("_Index.md", "_Catalog.md", "_BackLinks.md"):
            text = (kb / name).read_text(encoding="utf-8")
            assert "leaked" not in text
            assert ".obsidian" not in text

    def test_idempotent(self, tmp_path: Path) -> None:
        """Running build_indexes twice produces byte-identical output."""
        kb = _make_kb(tmp_path)
        build_indexes(kb)
        first = {
            name: (kb / name).read_bytes()
            for name in ("_Index.md", "_Catalog.md", "_BackLinks.md")
        }
        build_indexes(kb)
        second = {
            name: (kb / name).read_bytes()
            for name in ("_Index.md", "_Catalog.md", "_BackLinks.md")
        }
        assert first == second

    def test_index_files_not_treated_as_sources(self, tmp_path: Path) -> None:
        """Existing index files shouldn't leak into a rebuild."""
        kb = _make_kb(tmp_path)
        build_indexes(kb)  # produces indexes
        build_indexes(kb)  # rebuild — should not show _Index.md as content
        text = (kb / "_Index.md").read_text(encoding="utf-8")
        # No self-referential entries
        assert "[[_Index]]" not in text
        assert "[[_Catalog]]" not in text
        assert "[[_BackLinks]]" not in text

    def test_empty_kb_writes_placeholder(self, tmp_path: Path) -> None:
        result = build_indexes(tmp_path)
        for key in ("index", "catalog", "backlinks"):
            assert result[key].exists()
        idx_text = (tmp_path / "_Index.md").read_text(encoding="utf-8")
        assert "No frontmattered entries" in idx_text

    def test_wikilink_with_alias_resolves_to_target(self, tmp_path: Path) -> None:
        """[[Target|Alias]] should record a backlink to Target, not Alias."""
        _write(
            tmp_path / "Wiki" / "a.md",
            {"type": "wiki"},
            "See [[target-page|the target page]].",
        )
        _write(
            tmp_path / "Wiki" / "target-page.md",
            {"type": "wiki"},
            "I am the target.",
        )
        build_indexes(tmp_path)
        text = (tmp_path / "_BackLinks.md").read_text(encoding="utf-8")
        assert "## target-page" in text
        # No section for "the target page" (the alias).
        assert "## the target page" not in text

    def test_wikilink_with_section_anchor_resolves_to_target(
        self, tmp_path: Path
    ) -> None:
        """[[Target#Section]] should record a backlink to Target."""
        _write(
            tmp_path / "Wiki" / "a.md",
            {"type": "wiki"},
            "See [[target-page#methods]].",
        )
        _write(
            tmp_path / "Wiki" / "target-page.md",
            {"type": "wiki"},
            "I am the target.",
        )
        build_indexes(tmp_path)
        text = (tmp_path / "_BackLinks.md").read_text(encoding="utf-8")
        assert "## target-page" in text
        assert "target-page#methods" not in text
