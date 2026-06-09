"""Tests for the per-project papers index."""

from __future__ import annotations

from vaultlab.research.papers_index import (
    build_papers_index,
    render_index_markdown,
    save_index,
    scan_paper_note,
)

NOTE_DEEP = '''---
title: "A general-purpose foundation model"
authors: "Chen RJ, Mahmood F"
year: 2024
journal: "Nature Medicine"
doi: 10.1038/s41591-024-02857-3
ref_number: 57
status: VERIFIED
---

# Chen 2024 — UNI

## What it does
Introduces UNI, a self-supervised vision encoder for computational pathology.

## Pretraining scale (verified, with quotes)
Abstract (p.850): *"pretrained using more than 100 million images"*.

## Verdict: ACCURATE
Confirmed.
'''

NOTE_THIN = '''---
title: "A thin note"
year: 2023
status: UNVERIFIED
---

Short summary, no sections.
'''


def _write_pdf(path, *, valid: bool):
    if valid:
        path.write_bytes(b"%PDF-1.7\n" + b"x" * 2000)
    else:  # HTML paywall stub saved as .pdf
        path.write_bytes(b"<html><body>Access denied</body></html>")


def test_scan_parses_frontmatter_and_sections(tmp_path):
    note = tmp_path / "Chen2024_UNI.md"
    note.write_text(NOTE_DEEP, encoding="utf-8")
    _write_pdf(tmp_path / "Chen2024_UNI.pdf", valid=True)

    entry = scan_paper_note(note)
    assert entry.slug == "Chen2024_UNI"
    assert entry.title == "A general-purpose foundation model"
    assert entry.doi == "10.1038/s41591-024-02857-3"
    assert entry.ref_number == "57"
    assert entry.verification == "VERIFIED"
    assert entry.pdf_present and entry.pdf_readable
    assert "What it does" in entry.sections
    assert entry.read_depth == "deep"
    assert entry.digest  # first prose paragraph captured


def test_unreadable_pdf_flagged(tmp_path):
    note = tmp_path / "Bad2023.md"
    note.write_text(NOTE_THIN, encoding="utf-8")
    _write_pdf(tmp_path / "Bad2023.pdf", valid=False)

    entry = scan_paper_note(note)
    assert entry.pdf_present is True
    assert entry.pdf_readable is False  # the stub is caught
    assert entry.read_depth == "noted"
    assert entry.verification == "UNVERIFIED"


def test_missing_pdf(tmp_path):
    note = tmp_path / "NoPdf2022.md"
    note.write_text(NOTE_THIN, encoding="utf-8")
    entry = scan_paper_note(note)
    assert entry.pdf_present is False
    assert entry.pdf_readable is False


def test_build_counts_and_render_and_save(tmp_path):
    (tmp_path / "Chen2024_UNI.md").write_text(NOTE_DEEP, encoding="utf-8")
    _write_pdf(tmp_path / "Chen2024_UNI.pdf", valid=True)
    (tmp_path / "Bad2023.md").write_text(NOTE_THIN, encoding="utf-8")
    _write_pdf(tmp_path / "Bad2023.pdf", valid=False)
    # an index/underscore file that must be skipped
    (tmp_path / "_TO_FETCH.md").write_text("- something\n", encoding="utf-8")

    index = build_papers_index(tmp_path)
    c = index.counts
    assert c["total"] == 2  # _TO_FETCH skipped
    assert c["pdf_present"] == 2
    assert c["pdf_unreadable"] == 1
    assert c["verified"] == 1
    assert c["deep_read"] == 1

    md = render_index_markdown(index)
    assert "UNREADABLE" in md
    assert "Papers index" in md

    json_path, md_path = save_index(index, tmp_path)
    assert json_path.exists() and md_path.exists()
    assert "_papers_index.json" == json_path.name
