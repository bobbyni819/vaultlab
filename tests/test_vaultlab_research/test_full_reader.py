"""Tests for vaultlab.research.full_reader — bilingual figure-aware paper reader.

Sub-goal 2.1 of the north-star plan absorbs the ``nature-reader`` skill into
vaultlab. The contract:

* Input: a paper source (path / DOI / arXiv ID / URL / pasted text), optionally
  routed through paperclip.
* Output: a ``paper.md`` Markdown reading file with bilingual paragraphs,
  inline figure/table blocks, and stable anchor IDs (``S001``/``C001``/``F001``/
  ``T001``).
* Side outputs: ``paper.md.provenance.json`` + ``paper.md.method.md``
  (Red Line #2: every artifact carries a manifest).

These tests stub the LLM translation pass and the figure/extraction layer so
the unit tests are deterministic and fast.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from vaultlab.research import full_reader
from vaultlab.research.full_reader import (
    Block,
    PaperContent,
    build_paper_reader,
    render_paper_md,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _content(
    *,
    title: str = "A Tiny Paper",
    doi: str = "10.1/test.full-reader",
    body: list[tuple[str, str]] | None = None,
    figures: list[tuple[str, str]] | None = None,
    tables: list[tuple[str, str]] | None = None,
    abstract: str | None = "Short abstract.",
) -> PaperContent:
    body_blocks = [
        Block(kind="body", text=text, label=label)
        for label, text in (body or [("Introduction", "First paragraph of intro.")])
    ]
    fig_blocks = [
        Block(kind="figure", text=cap, label=label, asset="figures/fig_1.png")
        for label, cap in (figures or [])
    ]
    table_blocks = [
        Block(kind="table", text=cap, label=label)
        for label, cap in (tables or [])
    ]
    return PaperContent(
        title=title,
        doi=doi,
        source="fixture://tiny",
        abstract=abstract,
        body=body_blocks,
        figures=fig_blocks,
        tables=table_blocks,
    )


def _stub_translator(blocks: list[Block], target_lang: str) -> list[str]:
    """A deterministic translator stub: prefix each block's text with the lang code."""
    return [f"[{target_lang}] {b.text}" for b in blocks]


def _stub_extract(content: PaperContent, source: str) -> PaperContent:
    return content


# ---------------------------------------------------------------------------
# _extract_paper_content — the real default wired to read_paper_sections
# ---------------------------------------------------------------------------


def test_extract_paper_content_reads_local_pdf_flat_text(tmp_path: Path, monkeypatch):
    pdf = tmp_path / "paper.pdf"
    pdf.write_bytes(b"%PDF-1.4 fake")
    # Flat PDF extract -> {"all": text}; default splits into paragraph blocks.
    monkeypatch.setattr(
        "vaultlab.research.read_paper.read_paper_sections",
        lambda *a, **k: {"all": "First paragraph is long enough to keep here.\n\n"
                                 "Second paragraph also clears the minimum length bar."},
    )
    content = full_reader._extract_paper_content(str(pdf))
    assert content.title == "paper"
    assert content.abstract is None
    assert len(content.body) == 2
    assert all(b.kind == "body" for b in content.body)
    assert "First paragraph" in content.body[0].text


def test_extract_paper_content_named_sections(tmp_path: Path, monkeypatch):
    pdf = tmp_path / "p.pdf"
    pdf.write_bytes(b"%PDF-1.4 fake")
    monkeypatch.setattr(
        "vaultlab.research.read_paper.read_paper_sections",
        lambda *a, **k: {"Abstract": "the abstract", "Introduction": "intro text here"},
    )
    content = full_reader._extract_paper_content(str(pdf))
    assert content.abstract == "the abstract"
    labels = [b.label for b in content.body]
    assert "Introduction" in labels


def test_extract_paper_content_rejects_bare_doi():
    with pytest.raises(ValueError) as exc:
        full_reader._extract_paper_content("10.1038/s41586-023-05915-x")
    assert "acquire" in str(exc.value).lower()


def test_extract_paper_content_raises_on_empty_extract(tmp_path: Path, monkeypatch):
    pdf = tmp_path / "blank.pdf"
    pdf.write_bytes(b"%PDF-1.4 fake")
    monkeypatch.setattr(
        "vaultlab.research.read_paper.read_paper_sections", lambda *a, **k: {}
    )
    with pytest.raises(ValueError) as exc:
        full_reader._extract_paper_content(str(pdf))
    assert "empty" in str(exc.value).lower() or "no readable" in str(exc.value).lower()


def test_build_paper_reader_end_to_end_with_real_default(tmp_path: Path, monkeypatch):
    """The flagship path: a local PDF -> paper.md, using the REAL _extract_paper_content
    (only read_paper_sections is stubbed, standing in for the PDF parser)."""
    pdf = tmp_path / "real.pdf"
    pdf.write_bytes(b"%PDF-1.4 fake")
    monkeypatch.setattr(
        "vaultlab.research.read_paper.read_paper_sections",
        lambda *a, **k: {"all": "A substantial body paragraph that survives the length filter."},
    )
    out = build_paper_reader(str(pdf), out_dir=tmp_path / "reading", target_lang="zh-CN")
    assert out.exists()
    md = out.read_text(encoding="utf-8")
    assert "substantial body paragraph" in md
    assert 'id="S001"' in md  # got a real anchored body block


# ---------------------------------------------------------------------------
# render_paper_md unit tests
# ---------------------------------------------------------------------------


def test_render_emits_abstract_with_C001_anchor():
    content = _content(abstract="The abstract paragraph.")
    md = render_paper_md(
        content,
        translations={
            "abstract": ["[zh-CN] The abstract paragraph."],
            "body": ["[zh-CN] First paragraph of intro."],
            "figures": [],
            "tables": [],
        },
        target_lang="zh-CN",
    )
    assert "## Abstract" in md
    assert 'id="C001"' in md
    assert "The abstract paragraph." in md
    assert "[zh-CN] The abstract paragraph." in md


def test_render_emits_body_block_anchors_starting_at_S001():
    content = _content(
        body=[
            ("Introduction", "Intro paragraph one."),
            ("Methods", "Methods paragraph one."),
            ("Results", "Results paragraph one."),
        ],
    )
    md = render_paper_md(
        content,
        translations={
            "abstract": ["[zh-CN] Short abstract."],
            "body": [
                "[zh-CN] Intro paragraph one.",
                "[zh-CN] Methods paragraph one.",
                "[zh-CN] Results paragraph one.",
            ],
            "figures": [],
            "tables": [],
        },
        target_lang="zh-CN",
    )
    for anchor in ('id="S001"', 'id="S002"', 'id="S003"'):
        assert anchor in md, f"missing {anchor}"


def test_render_emits_figure_anchors_and_alt_text():
    content = _content(
        figures=[
            ("Figure 1", "Caption for figure 1."),
            ("Figure 2", "Caption for figure 2."),
        ],
    )
    md = render_paper_md(
        content,
        translations={
            "abstract": ["[zh-CN] Short abstract."],
            "body": ["[zh-CN] First paragraph of intro."],
            "figures": [
                "[zh-CN] Caption for figure 1.",
                "[zh-CN] Caption for figure 2.",
            ],
            "tables": [],
        },
        target_lang="zh-CN",
    )
    assert 'id="F001"' in md
    assert 'id="F002"' in md
    assert "![Figure 1](figures/fig_1.png)" in md
    assert "Caption (original):" in md
    # Translated caption must appear with the target-lang annotation.
    assert "Caption (translated, zh-CN):" in md


def test_render_emits_table_anchors():
    content = _content(
        tables=[("Table 1", "Description of table 1.")],
    )
    md = render_paper_md(
        content,
        translations={
            "abstract": ["[zh-CN] Short abstract."],
            "body": ["[zh-CN] First paragraph of intro."],
            "figures": [],
            "tables": ["[zh-CN] Description of table 1."],
        },
        target_lang="zh-CN",
    )
    assert 'id="T001"' in md
    assert "Table 1" in md


def test_render_falls_back_when_no_abstract():
    content = _content(abstract=None)
    md = render_paper_md(
        content,
        translations={
            "abstract": [],
            "body": ["[zh-CN] First paragraph of intro."],
            "figures": [],
            "tables": [],
        },
        target_lang="zh-CN",
    )
    # No Abstract section appears, but body still gets S001 anchor.
    assert "## Abstract" not in md
    assert 'id="S001"' in md


def test_render_header_carries_doi_and_target_lang():
    content = _content(title="Smith et al. 2026", doi="10.1234/abc")
    md = render_paper_md(
        content,
        translations={
            "abstract": ["[zh-CN] Short abstract."],
            "body": ["[zh-CN] First paragraph of intro."],
            "figures": [],
            "tables": [],
        },
        target_lang="zh-CN",
    )
    assert "# Smith et al. 2026" in md
    assert "**DOI:** 10.1234/abc" in md
    # Footer (or header) should declare target language for downstream tooling.
    assert "zh-CN" in md


# ---------------------------------------------------------------------------
# build_paper_reader end-to-end (with stubbed extract + translator)
# ---------------------------------------------------------------------------


def test_build_paper_reader_writes_paper_md_and_provenance(tmp_path: Path, monkeypatch):
    content = _content(
        body=[("Introduction", "Intro paragraph."), ("Methods", "Methods paragraph.")],
        figures=[("Figure 1", "Caption 1.")],
    )

    monkeypatch.setattr(full_reader, "_extract_paper_content", lambda source, paperclip_id=None: content)
    monkeypatch.setattr(full_reader, "_translate_blocks", _stub_translator)

    out_dir = tmp_path / "reading"
    paper_md = build_paper_reader("fixture://tiny", out_dir=out_dir, target_lang="zh-CN")

    assert paper_md.exists()
    md_text = paper_md.read_text(encoding="utf-8")
    assert 'id="S001"' in md_text
    assert 'id="F001"' in md_text
    assert 'id="C001"' in md_text  # abstract anchor

    # Provenance sidecars exist next to paper.md.
    prov_json = paper_md.with_name(paper_md.name + ".provenance.json")
    prov_md = paper_md.with_name(paper_md.name + ".method.md")
    assert prov_json.exists()
    assert prov_md.exists()

    payload = json.loads(prov_json.read_text(encoding="utf-8"))
    assert payload["generated_by"] == "vaultlab.research.full_reader.build_paper_reader"
    assert payload["kind"] == "paper_reader"
    assert payload["params"]["target_lang"] == "zh-CN"
    assert payload["params"]["n_body_blocks"] == 2
    assert payload["params"]["n_figures"] == 1
    assert payload["params"]["n_tables"] == 0


def test_build_paper_reader_with_no_figures(tmp_path: Path, monkeypatch):
    content = _content(
        body=[("Introduction", "Intro.")],
        figures=[],
    )
    monkeypatch.setattr(full_reader, "_extract_paper_content", lambda source, paperclip_id=None: content)
    monkeypatch.setattr(full_reader, "_translate_blocks", _stub_translator)

    paper_md = build_paper_reader("fixture://tiny", out_dir=tmp_path)
    md = paper_md.read_text(encoding="utf-8")
    assert 'id="F001"' not in md
    assert 'id="S001"' in md


def test_build_paper_reader_with_only_abstract(tmp_path: Path, monkeypatch):
    content = PaperContent(
        title="Abstract-only paper",
        doi="10.1/abs",
        source="fixture://abs",
        abstract="Just the abstract.",
        body=[],
        figures=[],
        tables=[],
    )
    monkeypatch.setattr(full_reader, "_extract_paper_content", lambda source, paperclip_id=None: content)
    monkeypatch.setattr(full_reader, "_translate_blocks", _stub_translator)

    paper_md = build_paper_reader("fixture://abs", out_dir=tmp_path)
    md = paper_md.read_text(encoding="utf-8")
    assert "## Abstract" in md
    assert 'id="C001"' in md
    # No body anchors when body is empty.
    assert 'id="S001"' not in md


def test_build_paper_reader_raises_on_missing_source(tmp_path: Path, monkeypatch):
    def boom(source: str, paperclip_id: str | None = None) -> PaperContent:
        raise FileNotFoundError(f"no such source: {source}")

    monkeypatch.setattr(full_reader, "_extract_paper_content", boom)
    with pytest.raises(FileNotFoundError):
        build_paper_reader("does-not-exist", out_dir=tmp_path)


def test_build_paper_reader_target_lang_threads_through(tmp_path: Path, monkeypatch):
    content = _content(body=[("Introduction", "Hello world.")])

    captured: dict[str, Any] = {}

    def fake_translate(blocks: list[Block], target_lang: str) -> list[str]:
        captured["target_lang"] = target_lang
        return [f"[{target_lang}] {b.text}" for b in blocks]

    monkeypatch.setattr(full_reader, "_extract_paper_content", lambda source, paperclip_id=None: content)
    monkeypatch.setattr(full_reader, "_translate_blocks", fake_translate)

    paper_md = build_paper_reader("fixture://x", out_dir=tmp_path, target_lang="ja")
    assert captured["target_lang"] == "ja"
    md = paper_md.read_text(encoding="utf-8")
    assert "[ja] Hello world." in md


def test_build_paper_reader_uses_paperclip_id_when_given(tmp_path: Path, monkeypatch):
    content = _content()
    captured: dict[str, Any] = {}

    def fake_extract(source: str, paperclip_id: str | None = None) -> PaperContent:
        captured["source"] = source
        captured["paperclip_id"] = paperclip_id
        return content

    monkeypatch.setattr(full_reader, "_extract_paper_content", fake_extract)
    monkeypatch.setattr(full_reader, "_translate_blocks", _stub_translator)

    build_paper_reader(
        "10.1/test",
        out_dir=tmp_path,
        paperclip_id="arx_2107.07953",
    )
    assert captured["paperclip_id"] == "arx_2107.07953"
    assert captured["source"] == "10.1/test"


def test_build_paper_reader_anchor_ids_are_zero_padded(tmp_path: Path, monkeypatch):
    content = _content(
        body=[("Section", f"Paragraph {i}.") for i in range(12)],
    )
    monkeypatch.setattr(full_reader, "_extract_paper_content", lambda source, paperclip_id=None: content)
    monkeypatch.setattr(full_reader, "_translate_blocks", _stub_translator)
    paper_md = build_paper_reader("fixture://x", out_dir=tmp_path)
    md = paper_md.read_text(encoding="utf-8")
    # 12 paragraphs -> S001..S012 (three-digit zero-pad)
    for n in (1, 9, 10, 12):
        assert f'id="S{n:03d}"' in md


def test_build_paper_reader_returns_path_under_out_dir(tmp_path: Path, monkeypatch):
    content = _content()
    monkeypatch.setattr(full_reader, "_extract_paper_content", lambda source, paperclip_id=None: content)
    monkeypatch.setattr(full_reader, "_translate_blocks", _stub_translator)

    paper_md = build_paper_reader("fixture://x", out_dir=tmp_path)
    assert paper_md.parent == tmp_path
    assert paper_md.name == "paper.md"


# ---------------------------------------------------------------------------
# Default translator: when caller doesn't override, a no-op identity translator
# is used so the module degrades gracefully without an LLM wired up.
# ---------------------------------------------------------------------------


def test_default_translator_is_identity_passthrough(tmp_path: Path, monkeypatch):
    """When no real translator is wired and the caller hasn't stubbed
    ``_translate_blocks``, the module must NOT raise — it should fall back to
    passing original text through verbatim. This keeps the contract honest
    even on a fresh checkout with no LLM provider configured."""
    content = _content()
    monkeypatch.setattr(full_reader, "_extract_paper_content", lambda source, paperclip_id=None: content)
    # Do NOT stub _translate_blocks.
    paper_md = build_paper_reader("fixture://x", out_dir=tmp_path)
    md = paper_md.read_text(encoding="utf-8")
    # Original text must always appear; translation may equal it.
    assert "First paragraph of intro." in md
