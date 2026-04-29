"""Tests for vaultlab.kb.ingest — pluggable ingestors + dispatcher routing."""

from __future__ import annotations

from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# KbDocument data class
# ---------------------------------------------------------------------------


class TestKbDocument:
    def test_auto_slug_from_title(self) -> None:
        from vaultlab.kb.ingest.models import KbDocument

        doc = KbDocument(kind="note", title="My Cool Note!", body="x", source="x")
        assert doc.slug == "my-cool-note"

    def test_explicit_slug_preserved(self) -> None:
        from vaultlab.kb.ingest.models import KbDocument

        doc = KbDocument(kind="note", title="X", body="x", source="x", slug="custom-slug")
        assert doc.slug == "custom-slug"

    def test_slug_handles_special_chars(self) -> None:
        from vaultlab.kb.ingest.models import KbDocument

        doc = KbDocument(kind="note", title="A/B (test) — '23'", body="", source="")
        assert "-" in doc.slug
        # No punctuation, no spaces
        assert all(c.isalnum() or c == "-" for c in doc.slug)

    def test_empty_title_falls_back_to_untitled(self) -> None:
        from vaultlab.kb.ingest.models import KbDocument

        doc = KbDocument(kind="note", title="!!!", body="", source="")
        assert doc.slug == "untitled"


# ---------------------------------------------------------------------------
# Markdown ingestor
# ---------------------------------------------------------------------------


class TestMarkdownIngestor:
    def test_passthrough_with_frontmatter(self, tmp_path: Path) -> None:
        from vaultlab.kb.ingest import ingest

        p = tmp_path / "note.md"
        p.write_text(
            "---\ntitle: Real Title\ntype: note\ntags: alpha\n---\n\n# Heading\n\nBody here.",
            encoding="utf-8",
        )

        doc = ingest(p)
        assert not isinstance(doc, list)
        assert doc.title == "Real Title"
        assert doc.kind == "note"
        assert "Body here." in doc.body
        assert doc.metadata["tags"] == "alpha"

    def test_falls_back_to_h1_when_no_frontmatter(self, tmp_path: Path) -> None:
        from vaultlab.kb.ingest import ingest

        p = tmp_path / "x.md"
        p.write_text("# H1 Title\n\nBody", encoding="utf-8")
        doc = ingest(p)
        assert not isinstance(doc, list)
        assert doc.title == "H1 Title"

    def test_falls_back_to_filename_stem(self, tmp_path: Path) -> None:
        from vaultlab.kb.ingest import ingest

        p = tmp_path / "my-note.md"
        p.write_text("just body", encoding="utf-8")
        doc = ingest(p)
        assert not isinstance(doc, list)
        assert doc.title == "my-note"


# ---------------------------------------------------------------------------
# BibTeX ingestor
# ---------------------------------------------------------------------------


class TestBibtexIngestor:
    def test_parses_single_entry(self, tmp_path: Path) -> None:
        from vaultlab.kb.ingest import ingest

        p = tmp_path / "refs.bib"
        p.write_text(
            "@article{smith2024,\n"
            "  title = {Some Paper Title},\n"
            "  author = {Smith, J. and Jones, A.},\n"
            "  year = {2024},\n"
            "  doi = {10.1234/abc}\n"
            "}\n",
            encoding="utf-8",
        )
        result = ingest(p)
        assert isinstance(result, list)
        assert len(result) == 1
        doc = result[0]
        assert doc.title == "Some Paper Title"
        assert doc.metadata["bibtex_key"] == "smith2024"
        assert doc.metadata["doi"] == "10.1234/abc"
        assert doc.kind == "citation"

    def test_parses_multiple_entries(self, tmp_path: Path) -> None:
        from vaultlab.kb.ingest import ingest

        p = tmp_path / "refs.bib"
        p.write_text(
            "@article{a2024, title = {A}, year = {2024}}\n"
            "@book{b2025, title = {B}, year = {2025}}\n",
            encoding="utf-8",
        )
        result = ingest(p)
        assert isinstance(result, list)
        assert len(result) == 2

    def test_quoted_field_values_supported(self, tmp_path: Path) -> None:
        from vaultlab.kb.ingest import ingest

        p = tmp_path / "refs.bib"
        p.write_text(
            '@article{q2024, title = "Quoted Title", year = "2024"}\n',
            encoding="utf-8",
        )
        result = ingest(p)
        assert isinstance(result, list)
        assert result[0].title == "Quoted Title"


# ---------------------------------------------------------------------------
# RIS ingestor
# ---------------------------------------------------------------------------


class TestRisIngestor:
    def test_parses_single_record(self, tmp_path: Path) -> None:
        from vaultlab.kb.ingest import ingest

        p = tmp_path / "refs.ris"
        p.write_text(
            "TY  - JOUR\n"
            "TI  - Sample Title\n"
            "AU  - Smith, John\n"
            "AU  - Jones, Alice\n"
            "PY  - 2024\n"
            "DO  - 10.1234/abc\n"
            "ER  - \n",
            encoding="utf-8",
        )
        result = ingest(p)
        assert isinstance(result, list)
        assert len(result) == 1
        doc = result[0]
        assert doc.title == "Sample Title"
        assert "Smith, John" in doc.metadata["authors"]
        assert "Jones, Alice" in doc.metadata["authors"]
        assert doc.metadata["doi"] == "10.1234/abc"


# ---------------------------------------------------------------------------
# Folder ingestor
# ---------------------------------------------------------------------------


class TestFolderIngestor:
    def test_recurses_and_dispatches(self, tmp_path: Path) -> None:
        from vaultlab.kb.ingest import ingest

        (tmp_path / "a.md").write_text("# A", encoding="utf-8")
        sub = tmp_path / "sub"
        sub.mkdir()
        (sub / "b.md").write_text("# B", encoding="utf-8")
        (sub / "ignore.txt").write_text("plain", encoding="utf-8")  # unsupported; skipped

        result = ingest(tmp_path)
        assert isinstance(result, list)
        titles = sorted(d.title for d in result)
        assert titles == ["A", "B"]

    def test_skips_obsidian_dot_dirs(self, tmp_path: Path) -> None:
        from vaultlab.kb.ingest import ingest

        (tmp_path / "ok.md").write_text("# OK", encoding="utf-8")
        skip_dir = tmp_path / ".obsidian"
        skip_dir.mkdir()
        (skip_dir / "config.md").write_text("# leak", encoding="utf-8")

        result = ingest(tmp_path)
        assert isinstance(result, list)
        titles = [d.title for d in result]
        assert titles == ["OK"]


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------


class TestDispatcher:
    def test_unknown_input_raises_ingest_error(self, tmp_path: Path) -> None:
        from vaultlab.kb.ingest import IngestError, ingest

        weird = tmp_path / "weird.xyz"
        weird.write_text("x", encoding="utf-8")
        with pytest.raises(IngestError, match="No ingestor matches"):
            ingest(weird)

    def test_url_stub_raises_not_implemented(self) -> None:
        from vaultlab.kb.ingest import ingest

        with pytest.raises(NotImplementedError, match="not yet implemented"):
            ingest("https://example.com/article")

    def test_doi_stub_raises_not_implemented(self) -> None:
        from vaultlab.kb.ingest import ingest

        with pytest.raises(NotImplementedError, match="not yet implemented"):
            ingest("10.1038/s41586-023-05915-x")

    def test_registered_ingestors_lists_all(self) -> None:
        from vaultlab.kb.ingest import registered_ingestors

        names = {e.name for e in registered_ingestors()}
        for required in (
            "markdown",
            "pdf",
            "bibtex",
            "ris",
            "folder",
            "url",
            "doi",
            "pmid",
            "zotero",
            "notebooklm",
        ):
            assert required in names

    def test_implemented_flag_separates_real_from_stub(self) -> None:
        from vaultlab.kb.ingest import registered_ingestors

        entries = {e.name: e for e in registered_ingestors()}
        assert entries["markdown"].implemented
        assert entries["bibtex"].implemented
        assert not entries["url"].implemented
        assert not entries["doi"].implemented
