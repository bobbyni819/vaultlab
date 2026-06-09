"""Tests for _extract_paper_content via PaperclipClient — no network.

Covers:
- structured path: sections available → PaperContent with correct fields
- fallback path: no sections but get_paper_text → single Body block
- end-to-end: build_paper_reader writes paper.md without raising NotImplementedError
- empty-everything → RuntimeError
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from vaultlab.research.full_reader import (
    Block,
    PaperContent,
    _extract_paper_content,
    build_paper_reader,
)
from vaultlab.research.sources.paperclip import PaperclipClient
from vaultlab.research.paper import Paper


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_FAKE_PAPER = Paper(
    title="Fake Title",
    authors=["Author A"],
    year=2024,
    journal="Nature",
    doi="10.9999/fake",
    abstract="Fake abstract text.",
    url="https://doi.org/10.9999/fake",
    source_api="paperclip",
)

_SECTION_TEXTS = {
    "Title": "Fake Title",
    "Abstract": "Fake abstract text.",
    "Introduction": "This paper introduces stuff.",
    "References": "Smith et al., 2020.",
}

_FIGURE_FILES = ["figure_1.jpg", "figure_2.png"]


def _patch_structured(monkeypatch):
    """Patch PaperclipClient for the structured (sections available) path."""
    monkeypatch.setattr(
        PaperclipClient,
        "list_sections",
        lambda self, pid: ["Title", "Abstract", "Introduction", "References"],
    )
    monkeypatch.setattr(
        PaperclipClient,
        "get_section",
        lambda self, pid, name: _SECTION_TEXTS.get(name, ""),
    )
    monkeypatch.setattr(
        PaperclipClient,
        "list_figures",
        lambda self, pid: _FIGURE_FILES,
    )
    monkeypatch.setattr(
        PaperclipClient,
        "lookup_doi",
        lambda self, doi: _FAKE_PAPER,
    )
    monkeypatch.setattr(
        PaperclipClient,
        "get_paper_text",
        lambda self, pid: "",
    )


# ---------------------------------------------------------------------------
# Test: structured path
# ---------------------------------------------------------------------------


def test_structured_path_abstract(monkeypatch):
    """Abstract section is present → abstract field is set."""
    _patch_structured(monkeypatch)
    content = _extract_paper_content("10.9999/fake", paperclip_id="PMC123")
    assert content.abstract == "Fake abstract text."


def test_structured_path_body_excludes_skip_sections(monkeypatch):
    """Title, Abstract, References must be excluded from body blocks."""
    _patch_structured(monkeypatch)
    content = _extract_paper_content("10.9999/fake", paperclip_id="PMC123")
    labels = [b.label for b in content.body]
    assert "Introduction" in labels
    assert "Title" not in labels
    assert "Abstract" not in labels
    assert "References" not in labels


def test_structured_path_body_text(monkeypatch):
    """Body block text matches get_section output."""
    _patch_structured(monkeypatch)
    content = _extract_paper_content("10.9999/fake", paperclip_id="PMC123")
    intro_block = next(b for b in content.body if b.label == "Introduction")
    assert intro_block.text == "This paper introduces stuff."
    assert intro_block.kind == "body"


def test_structured_path_figures(monkeypatch):
    """Figures from list_figures become figure blocks with correct labels/assets."""
    _patch_structured(monkeypatch)
    content = _extract_paper_content("10.9999/fake", paperclip_id="PMC123")
    assert len(content.figures) == 2
    assert content.figures[0].kind == "figure"
    assert content.figures[0].label == "Figure 1"
    assert content.figures[0].asset == "figure_1.jpg"
    assert content.figures[0].text == ""
    assert content.figures[1].label == "Figure 2"
    assert content.figures[1].asset == "figure_2.png"


def test_structured_path_tables_empty(monkeypatch):
    """Tables list is always [] — paperclip exposes no tables."""
    _patch_structured(monkeypatch)
    content = _extract_paper_content("10.9999/fake", paperclip_id="PMC123")
    assert content.tables == []


def test_structured_path_doi_from_lookup(monkeypatch):
    """DOI is filled from lookup_doi when source looks like a DOI."""
    _patch_structured(monkeypatch)
    content = _extract_paper_content("10.9999/fake", paperclip_id="PMC123")
    assert content.doi == "10.9999/fake"


def test_structured_path_source_preserved(monkeypatch):
    """source field on PaperContent always equals the original source arg."""
    _patch_structured(monkeypatch)
    content = _extract_paper_content("10.9999/fake", paperclip_id="PMC123")
    assert content.source == "10.9999/fake"


def test_structured_path_uses_pid_not_source_for_sections(monkeypatch):
    """list_sections/get_section/list_figures are called with the effective pid."""
    calls = []

    def _list_sections(self, pid):
        calls.append(("list_sections", pid))
        return ["Title", "Introduction"]

    def _get_section(self, pid, name):
        return "text"

    def _list_figures(self, pid):
        return []

    def _lookup_doi(self, doi):
        return None

    def _get_paper_text(self, pid):
        return ""

    monkeypatch.setattr(PaperclipClient, "list_sections", _list_sections)
    monkeypatch.setattr(PaperclipClient, "get_section", _get_section)
    monkeypatch.setattr(PaperclipClient, "list_figures", _list_figures)
    monkeypatch.setattr(PaperclipClient, "lookup_doi", _lookup_doi)
    monkeypatch.setattr(PaperclipClient, "get_paper_text", _get_paper_text)

    _extract_paper_content("10.9999/fake", paperclip_id="PMC_OVERRIDE")
    # The effective pid must be "PMC_OVERRIDE" (paperclip_id takes precedence)
    assert calls[0] == ("list_sections", "PMC_OVERRIDE")


# ---------------------------------------------------------------------------
# Test: fallback path (no sections, but text available)
# ---------------------------------------------------------------------------


def test_fallback_path_single_body_block(monkeypatch):
    """When list_sections is empty, fall back to get_paper_text → one Body block."""
    monkeypatch.setattr(PaperclipClient, "list_sections", lambda self, pid: [])
    monkeypatch.setattr(
        PaperclipClient, "get_paper_text", lambda self, pid: "Full body text here."
    )
    monkeypatch.setattr(PaperclipClient, "lookup_doi", lambda self, doi: None)

    content = _extract_paper_content("PMC99999")
    assert len(content.body) == 1
    assert content.body[0].kind == "body"
    assert content.body[0].label == "Body"
    assert content.body[0].text == "Full body text here."


def test_fallback_path_doi_source_fills_metadata(monkeypatch):
    """Fallback with DOI source fills title/abstract/doi from lookup_doi."""
    monkeypatch.setattr(PaperclipClient, "list_sections", lambda self, pid: [])
    monkeypatch.setattr(
        PaperclipClient, "get_paper_text", lambda self, pid: "Full body text."
    )
    monkeypatch.setattr(PaperclipClient, "lookup_doi", lambda self, doi: _FAKE_PAPER)

    content = _extract_paper_content("10.9999/fake")
    assert content.title == "Fake Title"
    assert content.abstract == "Fake abstract text."
    assert content.doi == "10.9999/fake"


def test_fallback_path_non_doi_source_no_metadata(monkeypatch):
    """Fallback with non-DOI source: title/doi/abstract are empty/None."""
    monkeypatch.setattr(PaperclipClient, "list_sections", lambda self, pid: [])
    monkeypatch.setattr(
        PaperclipClient, "get_paper_text", lambda self, pid: "Body text."
    )
    monkeypatch.setattr(PaperclipClient, "lookup_doi", lambda self, doi: None)

    content = _extract_paper_content("arx_2501.06039")
    assert content.title == ""
    assert content.doi == ""
    assert content.abstract is None


# ---------------------------------------------------------------------------
# Test: empty-everything → RuntimeError
# ---------------------------------------------------------------------------


def test_empty_everything_raises_runtime_error(monkeypatch):
    """Both paths empty → RuntimeError, NOT NotImplementedError."""
    monkeypatch.setattr(PaperclipClient, "list_sections", lambda self, pid: [])
    monkeypatch.setattr(PaperclipClient, "get_paper_text", lambda self, pid: "")
    monkeypatch.setattr(PaperclipClient, "lookup_doi", lambda self, doi: None)

    with pytest.raises(RuntimeError, match="no content"):
        _extract_paper_content("PMC_EMPTY")


def test_empty_everything_not_notimplemented(monkeypatch):
    """Ensure the old NotImplementedError is gone — only RuntimeError now."""
    monkeypatch.setattr(PaperclipClient, "list_sections", lambda self, pid: [])
    monkeypatch.setattr(PaperclipClient, "get_paper_text", lambda self, pid: "")
    monkeypatch.setattr(PaperclipClient, "lookup_doi", lambda self, doi: None)

    with pytest.raises(RuntimeError):
        _extract_paper_content("PMC_EMPTY")


# ---------------------------------------------------------------------------
# Test: end-to-end build_paper_reader writes paper.md without NotImplementedError
# ---------------------------------------------------------------------------


def test_build_paper_reader_structured_writes_paper_md(monkeypatch, tmp_path):
    """build_paper_reader completes and writes paper.md given structured sections."""
    _patch_structured(monkeypatch)

    out = build_paper_reader(
        "10.9999/fake",
        out_dir=tmp_path,
        target_lang="en",
        paperclip_id="PMC123",
    )
    assert out.exists()
    assert out.name == "paper.md"
    text = out.read_text(encoding="utf-8")
    assert "Introduction" in text
    assert "Fake abstract" in text


def test_build_paper_reader_fallback_writes_paper_md(monkeypatch, tmp_path):
    """build_paper_reader completes via fallback path and writes paper.md."""
    monkeypatch.setattr(PaperclipClient, "list_sections", lambda self, pid: [])
    monkeypatch.setattr(
        PaperclipClient, "get_paper_text", lambda self, pid: "Body text from fallback."
    )
    monkeypatch.setattr(PaperclipClient, "lookup_doi", lambda self, doi: _FAKE_PAPER)

    out = build_paper_reader(
        "10.9999/fake",
        out_dir=tmp_path,
        target_lang="en",
    )
    assert out.exists()
    text = out.read_text(encoding="utf-8")
    assert "Body text from fallback." in text


def test_build_paper_reader_provenance_sidecar_written(monkeypatch, tmp_path):
    """Provenance sidecar paper.md.provenance.json is written alongside paper.md."""
    _patch_structured(monkeypatch)
    build_paper_reader(
        "10.9999/fake",
        out_dir=tmp_path,
        paperclip_id="PMC123",
    )
    assert (tmp_path / "paper.md.provenance.json").exists()
