"""Tests for vaultlab.kb.retrieve — frontmatter-first lookup."""

from __future__ import annotations

from pathlib import Path

from vaultlab.kb.retrieve import retrieve_by_frontmatter


# ---------------------------------------------------------------------------
# Fixture builder
# ---------------------------------------------------------------------------


def _write(path: Path, frontmatter_dict: dict | None, body: str = "") -> None:
    """Write a markdown file with optional YAML frontmatter."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if frontmatter_dict is None:
        path.write_text(body, encoding="utf-8")
        return
    lines = ["---"]
    for k, v in frontmatter_dict.items():
        if isinstance(v, list):
            joined = ", ".join(repr(x) if not isinstance(x, str) else x for x in v)
            lines.append(f"{k}: [{joined}]")
        else:
            lines.append(f"{k}: {v}")
    lines.append("---")
    lines.append("")
    lines.append(body)
    path.write_text("\n".join(lines), encoding="utf-8")


def _make_kb(tmp_path: Path) -> Path:
    """Build a fixture KB with 8 files spanning varied frontmatter."""
    _write(
        tmp_path / "Sources" / "Notes" / "lipidomics-overview.md",
        {"type": "note", "project": "metabolism", "tags": ["lipidomics", "review"]},
        "Lipidomics overview. See [[lipid-pathway]] and [[maldi-imaging]].",
    )
    _write(
        tmp_path / "Sources" / "Papers" / "10.1234_paper-one.md",
        {"type": "paper", "project": "metabolism", "year": 2023},
        "Paper one full text.",
    )
    _write(
        tmp_path / "Sources" / "Papers" / "10.1234_paper-two.md",
        {"type": "paper", "project": "flu", "year": 2024},
        "Paper two on flu.",
    )
    _write(
        tmp_path / "Wiki" / "Concepts" / "lipid-pathway.md",
        {"type": "wiki", "project": "metabolism", "tags": ["lipidomics"]},
        "Lipid-pathway concept. References [[maldi-imaging]].",
    )
    _write(
        tmp_path / "Wiki" / "Concepts" / "maldi-imaging.md",
        {"type": "wiki", "project": "metabolism", "tags": ["maldi"]},
        "MALDI imaging concept.",
    )
    _write(
        tmp_path / "Wiki" / "Concepts" / "flu-overview.md",
        {"type": "wiki", "project": "flu", "tags": ["virology"]},
        "Flu overview.",
    )
    # File WITHOUT frontmatter — should be skipped by retrieve_by_frontmatter.
    _write(
        tmp_path / "Sources" / "Notes" / "scratch.md",
        None,
        "A scratch note without frontmatter referencing [[lipid-pathway]].",
    )
    # File under a dotfile dir — should also be skipped.
    _write(
        tmp_path / ".obsidian" / "leaked.md",
        {"type": "wiki", "project": "metabolism"},
        "Should never appear.",
    )
    return tmp_path


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestRetrieveByFrontmatter:
    def test_single_key_filter(self, tmp_path: Path) -> None:
        kb = _make_kb(tmp_path)
        wikis = retrieve_by_frontmatter({"type": "wiki"}, kb)
        names = sorted(p.name for p in wikis)
        assert names == ["flu-overview.md", "lipid-pathway.md", "maldi-imaging.md"]

    def test_multiple_keys_are_and(self, tmp_path: Path) -> None:
        kb = _make_kb(tmp_path)
        out = retrieve_by_frontmatter(
            {"type": "wiki", "project": "metabolism"}, kb
        )
        names = sorted(p.name for p in out)
        assert names == ["lipid-pathway.md", "maldi-imaging.md"]

    def test_set_value_is_or_within_key(self, tmp_path: Path) -> None:
        kb = _make_kb(tmp_path)
        out = retrieve_by_frontmatter({"type": {"wiki", "paper"}}, kb)
        # Should pull all 5 wiki/paper notes (excluding the unfrontmattered
        # scratch note and the .obsidian leak).
        assert len(out) == 5

    def test_set_value_against_list_field(self, tmp_path: Path) -> None:
        """A set filter against a list-valued frontmatter field is OR."""
        kb = _make_kb(tmp_path)
        out = retrieve_by_frontmatter({"tags": {"lipidomics", "maldi"}}, kb)
        names = sorted(p.name for p in out)
        # lipidomics-overview (lipidomics), lipid-pathway (lipidomics),
        # maldi-imaging (maldi).
        assert names == ["lipid-pathway.md", "lipidomics-overview.md", "maldi-imaging.md"]

    def test_scalar_against_list_field(self, tmp_path: Path) -> None:
        """A scalar filter checks membership when frontmatter value is a list."""
        kb = _make_kb(tmp_path)
        out = retrieve_by_frontmatter({"tags": "review"}, kb)
        names = [p.name for p in out]
        assert names == ["lipidomics-overview.md"]

    def test_files_without_frontmatter_are_skipped(self, tmp_path: Path) -> None:
        kb = _make_kb(tmp_path)
        # No filter that matches an unfrontmattered file (since no metadata)
        # — but assert the unfrontmattered file never shows up no matter what.
        all_wikis = retrieve_by_frontmatter({"type": "wiki"}, kb)
        for p in all_wikis:
            assert p.name != "scratch.md"

    def test_dotfile_directories_skipped(self, tmp_path: Path) -> None:
        kb = _make_kb(tmp_path)
        out = retrieve_by_frontmatter({"type": "wiki", "project": "metabolism"}, kb)
        for p in out:
            assert ".obsidian" not in p.parts

    def test_index_files_excluded(self, tmp_path: Path) -> None:
        """The auto-index files themselves are never returned."""
        kb = _make_kb(tmp_path)
        # Plant a fake _Index.md with matching frontmatter.
        _write(
            kb / "_Index.md",
            {"type": "wiki", "project": "metabolism"},
            "Fake index.",
        )
        _write(
            kb / "_Catalog.md",
            {"type": "wiki", "project": "metabolism"},
            "Fake catalog.",
        )
        _write(
            kb / "_BackLinks.md",
            {"type": "wiki", "project": "metabolism"},
            "Fake backlinks.",
        )
        out = retrieve_by_frontmatter({"type": "wiki"}, kb)
        for p in out:
            assert p.name not in {"_Index.md", "_Catalog.md", "_BackLinks.md"}

    def test_no_match_returns_empty(self, tmp_path: Path) -> None:
        kb = _make_kb(tmp_path)
        out = retrieve_by_frontmatter({"type": "nonexistent"}, kb)
        assert out == []

    def test_missing_kb_returns_empty(self, tmp_path: Path) -> None:
        out = retrieve_by_frontmatter({"type": "wiki"}, tmp_path / "missing")
        assert out == []

    def test_missing_key_no_match(self, tmp_path: Path) -> None:
        """If a file's frontmatter lacks the filter key, it doesn't match."""
        kb = _make_kb(tmp_path)
        out = retrieve_by_frontmatter({"nonexistent_key": "anything"}, kb)
        assert out == []

    def test_returns_sorted_paths(self, tmp_path: Path) -> None:
        kb = _make_kb(tmp_path)
        out = retrieve_by_frontmatter({"type": {"wiki", "paper"}}, kb)
        # Sorted alphabetically by path for stability across runs.
        assert [p for p in out] == sorted(out)
