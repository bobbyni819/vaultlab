"""Tests for vaultlab.slides.kb_reader — KB reader.

Ported from ``bobby-tools/tests/test_bobby_slides/test_content.py``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from vaultlab.slides.kb_reader import KBNotFoundError, KBReader


@pytest.fixture
def kb_root(tmp_path):
    """Build a minimal KB structure for testing."""
    (tmp_path / "Wiki" / "Concepts").mkdir(parents=True)
    (tmp_path / "Wiki" / "Methodology").mkdir(parents=True)
    (tmp_path / "Wiki" / "Summaries").mkdir(parents=True)
    (tmp_path / "Sources" / "Articles").mkdir(parents=True)
    (tmp_path / "Sources" / "Papers").mkdir(parents=True)
    (tmp_path / "Sources" / "Notes").mkdir(parents=True)
    (tmp_path / "Sources" / "Assets").mkdir(parents=True)
    (tmp_path / "Output" / "Reports").mkdir(parents=True)

    (tmp_path / "_Index.md").write_text("# Test KB\n", encoding="utf-8")
    (tmp_path / "_Catalog.md").write_text("# Catalog\n", encoding="utf-8")

    (tmp_path / "Wiki" / "Concepts" / "alpha.md").write_text(
        "---\ntitle: Alpha\ntags: [concept]\n---\n# Alpha\n\nBody text.\n",
        encoding="utf-8",
    )
    (tmp_path / "Wiki" / "Concepts" / "beta.md").write_text(
        "# Beta\n\nNo frontmatter here.\n",
        encoding="utf-8",
    )
    (tmp_path / "Sources" / "Articles" / "Smith_2024.md").write_text(
        "---\ntitle: Smith study\nauthors: [Smith]\nyear: 2024\n---\n# Smith\n",
        encoding="utf-8",
    )
    return tmp_path


class TestKBReaderInit:
    def test_accepts_valid_root(self, kb_root):
        reader = KBReader(kb_root)
        assert reader.root == kb_root

    def test_rejects_missing_root(self, tmp_path):
        with pytest.raises(KBNotFoundError):
            KBReader(tmp_path / "does_not_exist")

    def test_rejects_file_as_root(self, tmp_path):
        f = tmp_path / "not_a_dir.txt"
        f.write_text("x")
        with pytest.raises(KBNotFoundError):
            KBReader(f)


class TestListing:
    def test_list_concepts(self, kb_root):
        reader = KBReader(kb_root)
        assert reader.list_concepts() == ["alpha", "beta"]

    def test_list_articles(self, kb_root):
        reader = KBReader(kb_root)
        assert reader.list_articles() == ["Smith_2024"]

    def test_empty_directory_returns_empty_list(self, kb_root):
        reader = KBReader(kb_root)
        assert reader.list_methodology() == []

    def test_missing_directory_returns_empty(self, tmp_path):
        # KB root exists but has no subdirectories
        reader = KBReader(tmp_path)
        assert reader.list_concepts() == []


class TestReading:
    def test_read_concept_with_frontmatter(self, kb_root):
        reader = KBReader(kb_root)
        result = reader.read_concept("alpha")
        assert result["name"] == "alpha"
        assert result["frontmatter"]["title"] == "Alpha"
        assert "Body text" in result["body"]

    def test_read_concept_without_frontmatter(self, kb_root):
        reader = KBReader(kb_root)
        result = reader.read_concept("beta")
        assert result["frontmatter"] == {}
        assert "# Beta" in result["body"]

    def test_read_missing_concept_raises(self, kb_root):
        reader = KBReader(kb_root)
        with pytest.raises(FileNotFoundError):
            reader.read_concept("does_not_exist")

    def test_read_article_with_frontmatter(self, kb_root):
        reader = KBReader(kb_root)
        result = reader.read_article("Smith_2024")
        assert result["frontmatter"]["title"] == "Smith study"
        assert result["frontmatter"]["year"] == 2024

    def test_read_index(self, kb_root):
        reader = KBReader(kb_root)
        assert "Test KB" in reader.read_index()

    def test_read_index_returns_empty_if_missing(self, tmp_path):
        reader = KBReader(tmp_path)
        assert reader.read_index() == ""


class TestFigures:
    def test_find_figures(self, kb_root):
        PIL = pytest.importorskip("PIL")
        from PIL import Image

        Image.new("RGB", (100, 100), "red").save(kb_root / "Sources" / "Assets" / "fig1.png")
        Image.new("RGB", (100, 100), "blue").save(kb_root / "Sources" / "Assets" / "fig2.jpg")
        (kb_root / "Sources" / "Assets" / "notes.txt").write_text("not an image")

        reader = KBReader(kb_root)
        figs = reader.find_figures()
        names = sorted(f.name for f in figs)
        assert names == ["fig1.png", "fig2.jpg"]

    def test_find_figures_empty_when_missing(self, tmp_path):
        reader = KBReader(tmp_path)
        assert reader.find_figures() == []


class TestActivityLog:
    def test_append_first_entry(self, kb_root):
        reader = KBReader(kb_root)
        reader.append_log("compile", "Test deck", body="Generated 5 slides")
        log_text = (kb_root / "_Log.md").read_text(encoding="utf-8")
        assert "compile | Test deck" in log_text
        assert "Generated 5 slides" in log_text

    def test_append_multiple_entries(self, kb_root):
        reader = KBReader(kb_root)
        reader.append_log("ingest", "Source 1")
        reader.append_log("compile", "Source 2")
        log_text = (kb_root / "_Log.md").read_text(encoding="utf-8")
        assert "Source 1" in log_text
        assert "Source 2" in log_text

    def test_append_with_pages(self, kb_root):
        reader = KBReader(kb_root)
        reader.append_log("update", "Wiki refresh", pages=["alpha", "beta"])
        log_text = (kb_root / "_Log.md").read_text(encoding="utf-8")
        assert "[[alpha]]" in log_text
        assert "[[beta]]" in log_text


class TestWriteReport:
    def test_creates_report(self, kb_root):
        reader = KBReader(kb_root)
        path = reader.write_report("test-report.md", "# Test\n\nContent.\n")
        assert path.exists()
        assert path.parent.name == "Reports"
        assert "Test" in path.read_text(encoding="utf-8")

    def test_creates_reports_dir_if_missing(self, tmp_path):
        reader = KBReader(tmp_path)
        path = reader.write_report("first.md", "x")
        assert path.exists()
        assert path.parent == tmp_path / "Output" / "Reports"


class TestSmokeAgainstVaultlabKB:
    """Smoke test against the actual vaultlab KB on Google Drive.

    Skips when the KB isn't available (CI / fresh machine).
    """

    def test_lists_existing_concepts(self):
        kb_root = Path("G:/My Drive/Knowledge/vaultlab")
        if not kb_root.is_dir():
            pytest.skip("vaultlab KB not available on this machine")
        reader = KBReader(kb_root)
        concepts = reader.list_concepts()
        # The KB has at least the codex-cellular-neighborhoods concept
        assert any("codex-cellular-neighborhoods" in c for c in concepts), (
            f"Expected 'codex-cellular-neighborhoods*' in concepts; got {concepts}"
        )
