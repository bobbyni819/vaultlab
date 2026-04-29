"""Tests for vaultlab.kb.tools_index — package catalog + external repos."""

from __future__ import annotations

import pytest


class TestLoadIndex:
    def test_loads_seeded_packages(self) -> None:
        from vaultlab.kb.tools_index import load_index

        index = load_index()
        for pkg in (
            "scanpy",
            "squidpy",
            "anndata",
            "scikit-image",
            "cellpose",
            "scipy.stats",
            "statsmodels",
            "pingouin",
            "pyimzML",
            "scvi-tools",
            "harmony",
            "palantir",
        ):
            assert pkg in index, f"missing package: {pkg}"

    def test_each_entry_has_required_fields(self) -> None:
        from vaultlab.kb.tools_index import load_index

        for entry in load_index().values():
            assert entry.name
            assert entry.description, f"{entry.name} missing description"
            assert entry.summary, f"{entry.name} missing summary (## Summary section)"
            assert entry.domains, f"{entry.name} missing domains"
            assert entry.docs_url, f"{entry.name} missing docs_url"
            assert entry.body, f"{entry.name} body should be non-empty"

    def test_key_functions_extracted(self) -> None:
        from vaultlab.kb.tools_index import load_index

        scanpy = load_index()["scanpy"]
        # We listed many sc.* / sc.pp.* / sc.pl.* entries
        assert any("sc.pp" in fn for fn in scanpy.key_functions)


class TestSuggestForTopic:
    def test_spatial_returns_squidpy_and_pyimzml(self) -> None:
        from vaultlab.kb.tools_index import suggest_for_topic

        hits = {e.name for e in suggest_for_topic("spatial")}
        assert "squidpy" in hits
        assert "pyimzML" in hits

    def test_single_cell_returns_scanpy_anndata(self) -> None:
        from vaultlab.kb.tools_index import suggest_for_topic

        hits = {e.name for e in suggest_for_topic("single-cell")}
        assert "scanpy" in hits
        assert "anndata" in hits

    def test_statistics_returns_stats_packages(self) -> None:
        from vaultlab.kb.tools_index import suggest_for_topic

        hits = {e.name for e in suggest_for_topic("statistics")}
        assert "statsmodels" in hits
        assert "pingouin" in hits

    def test_no_match_returns_empty(self) -> None:
        from vaultlab.kb.tools_index import suggest_for_topic

        assert suggest_for_topic("a-topic-that-cannot-possibly-match") == []

    def test_empty_topic_returns_empty(self) -> None:
        from vaultlab.kb.tools_index import suggest_for_topic

        assert suggest_for_topic("") == []

    def test_case_insensitive(self) -> None:
        from vaultlab.kb.tools_index import suggest_for_topic

        hits = {e.name for e in suggest_for_topic("SPATIAL")}
        assert "squidpy" in hits


class TestExternalRepos:
    def test_loads_seeded_repo(self) -> None:
        from vaultlab.kb.tools_index import load_external_repos

        repos = load_external_repos()
        assert len(repos) >= 1
        slugs = {r.get("slug") for r in repos}
        assert "spatial-omics-algorithms" in slugs

    def test_pending_repo_has_empty_url(self) -> None:
        from vaultlab.kb.tools_index import load_external_repos

        repos = load_external_repos()
        spatial = next(r for r in repos if r["slug"] == "spatial-omics-algorithms")
        assert spatial["url"] == ""
        assert spatial["status"] == "pending-access"
        assert "spatial-omics" in spatial["domains"]


class TestTieredSearch:
    def test_summary_for_returns_one_paragraph(self) -> None:
        from vaultlab.kb.tools_index import summary_for

        s = summary_for("scanpy")
        assert s is not None
        assert len(s) < 1000  # one paragraph, not the full body
        assert "scRNA-seq" in s or "single-cell" in s.lower()

    def test_summary_for_unknown_returns_none(self) -> None:
        from vaultlab.kb.tools_index import summary_for

        assert summary_for("not-a-real-pkg") is None

    def test_deep_doc_for_returns_full_body(self) -> None:
        from vaultlab.kb.tools_index import deep_doc_for, summary_for

        s = summary_for("scanpy")
        deep = deep_doc_for("scanpy")
        assert deep is not None
        assert len(deep) > len(s or "")  # deep doc longer than summary
        # The deep doc contains sections beyond just Summary
        assert "## Key functions" in deep

    def test_deep_doc_for_unknown_returns_none(self) -> None:
        from vaultlab.kb.tools_index import deep_doc_for

        assert deep_doc_for("not-a-real-pkg") is None


class TestParseFailures:
    def test_missing_frontmatter_raises(self, tmp_path, monkeypatch) -> None:
        # Replace the packages dir with a fixture containing a malformed file
        from vaultlab.kb.tools_index import loader as loader_mod

        bad_file = tmp_path / "bad.md"
        bad_file.write_text("# no frontmatter here\n")

        monkeypatch.setattr(loader_mod, "packages_dir", lambda: tmp_path)

        with pytest.raises(loader_mod.ToolsIndexError):
            loader_mod.load_index()

    def test_missing_packages_dir_returns_empty(self, tmp_path, monkeypatch) -> None:
        from vaultlab.kb.tools_index import loader as loader_mod

        monkeypatch.setattr(loader_mod, "packages_dir", lambda: tmp_path / "absent")
        assert loader_mod.load_index() == {}
