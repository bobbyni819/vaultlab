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

    def test_collects_kb_under_dot_prefixed_root(self, tmp_path: Path) -> None:
        # A KB mounted under a hidden ancestor (e.g. Google Drive's
        # `.shortcut-targets-by-id` shortcut) must still be scanned — only
        # hidden segments *inside* the KB are excluded.
        from vaultlab.kb.semantic_search import search

        kb = tmp_path / ".shortcut-targets-by-id" / "abc123" / "dataplus"
        sources = kb / "Sources"
        sources.mkdir(parents=True)
        (sources / "real.md").write_text("# real T cell content")
        hidden = sources / ".obsidian"
        hidden.mkdir()
        (hidden / "leaked.md").write_text("# leaked T cell")

        hits = search(kb, "T cell")
        names = [h.path.name for h in hits]
        assert "real.md" in names  # not zeroed out by the dot-prefixed root
        assert "leaked.md" not in names  # in-KB hidden dir still skipped

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


class TestBM25:
    def test_default_backend_is_bm25(self, tmp_path: Path, monkeypatch) -> None:
        from vaultlab.kb import semantic_search as ss

        called = {"bm25": False, "tfidf": False}
        real_bm25 = ss._search_bm25

        def spy_bm25(*a, **k):
            called["bm25"] = True
            return real_bm25(*a, **k)

        monkeypatch.setattr(ss, "_search_bm25", spy_bm25)
        monkeypatch.setattr(ss, "_search_tfidf", lambda *a, **k: called.__setitem__("tfidf", True) or [])

        kb = _make_kb(tmp_path, {"a.md": "T cell exhaustion notes"})
        ss.search(kb, "T cell")  # no explicit backend
        assert called["bm25"] and not called["tfidf"]

    def test_bm25_returns_relevant_hit_descending(self, tmp_path: Path) -> None:
        from vaultlab.kb.semantic_search import search

        kb = _make_kb(
            tmp_path,
            {
                "a.md": "# Exhausted T cells\n\nExtensive notes on CD8 T-cell exhaustion.",
                "b.md": "# Microbiome\n\nGut bacteria diversity.",
                "c.md": "# T-cell activation\n\nReceptor signaling.",
            },
        )
        hits = search(kb, "exhausted T cells", backend="bm25")
        assert hits and hits[0].path.name == "a.md"
        scores = [h.score for h in hits]
        assert scores == sorted(scores, reverse=True)
        assert "b.md" not in {h.path.name for h in hits}  # no query-term overlap → excluded

    def test_bm25_no_overlap_returns_empty(self, tmp_path: Path) -> None:
        from vaultlab.kb.semantic_search import search

        kb = _make_kb(tmp_path, {"a.md": "# Nothing related here"})
        # Unambiguously-absent token (not just hyphen-split words that might appear).
        assert search(kb, "xyzzy zznomatchzz", backend="bm25") == []

    def test_bm25_length_normalization(self, tmp_path: Path) -> None:
        # Equal raw term frequency (perforin × 1 in both), differing only in length.
        # BM25's length norm ranks the short doc first; a raw-TF model would tie —
        # so this genuinely discriminates the length-normalization property.
        from vaultlab.kb.semantic_search import search

        filler = " ".join(f"word{i}" for i in range(2000))
        kb = _make_kb(
            tmp_path,
            {
                "short.md": "perforin",
                "long.md": "perforin " + filler,
            },
        )
        hits = search(kb, "perforin", backend="bm25")
        assert hits[0].path.name == "short.md"

    def test_tfidf_backend_still_selectable(self, tmp_path: Path) -> None:
        from vaultlab.kb.semantic_search import search

        kb = _make_kb(
            tmp_path,
            {"a.md": "exhausted T cells", "b.md": "microbiome diversity"},
        )
        hits = search(kb, "exhausted T cells", backend="tfidf")
        assert hits and hits[0].path.name == "a.md"
