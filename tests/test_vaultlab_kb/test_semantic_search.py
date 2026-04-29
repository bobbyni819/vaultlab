"""Tests for vaultlab.kb.semantic_search — TF-IDF backend (always-available)."""

from __future__ import annotations

from pathlib import Path


def _make_kb(tmp_path: Path, files: dict[str, str]) -> Path:
    """Build a minimal KB layout under tmp_path with the given files."""
    sources = tmp_path / "Sources"
    sources.mkdir()
    for relpath, content in files.items():
        target = sources / relpath
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    return tmp_path


class TestSearch:
    def test_returns_relevant_hits(self, tmp_path: Path) -> None:
        from vaultlab.kb.semantic_search import search

        kb = _make_kb(
            tmp_path,
            {
                "a.md": "# Exhausted T cells\n\nLong-form notes on T-cell exhaustion in CD8 populations.",
                "b.md": "# Microbiome composition\n\nGut bacteria diversity in mouse colon.",
                "c.md": "# T-cell activation\n\nNotes on T-cell receptor signaling.",
            },
        )

        hits = search(kb, "exhausted T cells")
        assert len(hits) >= 1
        assert hits[0].path.name == "a.md"
        # Microbiome should rank low (or be excluded entirely)
        names_top2 = {h.path.name for h in hits[:2]}
        assert "b.md" not in names_top2

    def test_top_k_caps_results(self, tmp_path: Path) -> None:
        from vaultlab.kb.semantic_search import search

        kb = _make_kb(
            tmp_path,
            {f"f{i}.md": f"# Title {i}\n\nT-cell content {i}." for i in range(20)},
        )
        hits = search(kb, "T-cell", top_k=5)
        assert len(hits) <= 5

    def test_empty_query_returns_empty(self, tmp_path: Path) -> None:
        from vaultlab.kb.semantic_search import search

        kb = _make_kb(tmp_path, {"a.md": "# T cell"})
        assert search(kb, "") == []
        assert search(kb, "   ") == []

    def test_no_kb_returns_empty(self, tmp_path: Path) -> None:
        from vaultlab.kb.semantic_search import search

        assert search(tmp_path / "missing", "anything") == []

    def test_no_matches_returns_empty(self, tmp_path: Path) -> None:
        from vaultlab.kb.semantic_search import search

        kb = _make_kb(tmp_path, {"a.md": "# Nothing related"})
        # No token overlap with "completely-different-keyword"
        hits = search(kb, "completely-different-keyword")
        assert hits == []

    def test_snippet_includes_matching_context(self, tmp_path: Path) -> None:
        from vaultlab.kb.semantic_search import search

        kb = _make_kb(
            tmp_path,
            {
                "a.md": "intro paragraph not matching\n\nspecific keyword foo bar appears here\n\nlater"
            },
        )
        hits = search(kb, "specific keyword")
        assert hits
        assert "specific" in hits[0].snippet.lower() or "keyword" in hits[0].snippet.lower()

    def test_skips_dot_directories(self, tmp_path: Path) -> None:
        from vaultlab.kb.semantic_search import search

        sources = tmp_path / "Sources"
        sources.mkdir()
        (sources / "real.md").write_text("# real T cell")
        hidden = sources / ".obsidian"
        hidden.mkdir()
        (hidden / "leaked.md").write_text("# leaked T cell")

        hits = search(tmp_path, "T cell")
        names = [h.path.name for h in hits]
        assert "leaked.md" not in names

    def test_scans_wiki_and_output_too(self, tmp_path: Path) -> None:
        from vaultlab.kb.semantic_search import search

        for sub in ("Sources", "Wiki", "Output"):
            d = tmp_path / sub
            d.mkdir()
            (d / "f.md").write_text(f"# T cell in {sub}\nsome content")

        hits = search(tmp_path, "T cell")
        assert len(hits) == 3

    def test_scores_are_descending(self, tmp_path: Path) -> None:
        from vaultlab.kb.semantic_search import search

        kb = _make_kb(
            tmp_path,
            {
                "high.md": "exhausted T cells exhausted T cells exhausted T cells",
                "low.md": "barely exhausted",
            },
        )
        hits = search(kb, "exhausted T cells")
        scores = [h.score for h in hits]
        assert scores == sorted(scores, reverse=True)


class TestIndexKb:
    def test_returns_count_of_indexed_files(self, tmp_path: Path) -> None:
        from vaultlab.kb.semantic_search import index_kb

        kb = _make_kb(
            tmp_path,
            {
                "a.md": "# A",
                "b.md": "# B",
                "sub/c.md": "# C",
            },
        )
        assert index_kb(kb) == 3

    def test_empty_kb_returns_zero(self, tmp_path: Path) -> None:
        from vaultlab.kb.semantic_search import index_kb

        assert index_kb(tmp_path / "missing") == 0
