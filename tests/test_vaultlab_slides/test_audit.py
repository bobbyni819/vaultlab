"""Tests for vaultlab.slides.audit — deck self-evaluation."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from vaultlab.slides.audit import (
    DeckAuditResult,
    SlideAudit,
    audit_deck,
    _extract_dois_from_arc,
)


def _mk_slide(*, title: str, n_images: int, text_chars: int):
    """Build a fake pptx slide with the given image and text counts."""
    shapes = []
    if title:
        title_sh = MagicMock()
        title_sh.has_text_frame = True
        title_sh.text_frame.text = title
        title_sh.shape_type = 1
        shapes.append(title_sh)
    if text_chars > 0:
        body = MagicMock()
        body.has_text_frame = True
        body.text_frame.text = "x" * text_chars
        body.shape_type = 2
        shapes.append(body)
    for _ in range(n_images):
        img = MagicMock()
        img.has_text_frame = False
        img.shape_type = 13
        shapes.append(img)
    slide = MagicMock()
    slide.shapes = shapes
    return slide


def _patch_presentation(slides_data):
    fake_prs = MagicMock()
    fake_prs.slides = [_mk_slide(**s) for s in slides_data]
    fake_prs.slide_width = 9144000
    fake_prs.slide_height = 6858000
    return patch("vaultlab.slides.audit.Presentation", return_value=fake_prs)


def test_audit_zero_images_is_fail(tmp_path):
    deck = tmp_path / "x.pptx"
    deck.write_bytes(b"fake")
    slides = [{"title": f"S{i}", "n_images": 0, "text_chars": 100} for i in range(5)]
    with _patch_presentation(slides):
        r = audit_deck(deck)
    assert r.n_total_images == 0
    assert r.severity == "fail"


def test_audit_some_images_is_ok(tmp_path):
    deck = tmp_path / "x.pptx"
    deck.write_bytes(b"fake")
    slides = [
        {"title": "Title", "n_images": 0, "text_chars": 100},
        {"title": "Methods overview", "n_images": 1, "text_chars": 100},
        {"title": "Results panel", "n_images": 2, "text_chars": 100},
        {"title": "Discussion", "n_images": 0, "text_chars": 200},
    ]
    with _patch_presentation(slides):
        r = audit_deck(deck)
    assert r.n_total_images == 3
    assert r.severity == "ok"


def test_audit_warn_when_thin_slides(tmp_path):
    deck = tmp_path / "x.pptx"
    deck.write_bytes(b"fake")
    slides = [
        {"title": "Methods", "n_images": 1, "text_chars": 200},
        {"title": "S", "n_images": 0, "text_chars": 5},
        {"title": "S", "n_images": 0, "text_chars": 5},
        {"title": "Refs", "n_images": 0, "text_chars": 200},
    ]
    with _patch_presentation(slides):
        r = audit_deck(deck)
    assert r.thin_slides == 2
    assert r.severity == "warn"


def test_audit_section_intro_titles_flagged(tmp_path):
    """Canonical 'History/Development/State of the art' titles are figure-intended."""
    deck = tmp_path / "x.pptx"
    deck.write_bytes(b"fake")
    slides = [
        {"title": "Title", "n_images": 0, "text_chars": 100},
        {"title": "HISTORY", "n_images": 0, "text_chars": 100},
        {"title": "DEVELOPMENT", "n_images": 0, "text_chars": 100},
        {"title": "State of the art", "n_images": 0, "text_chars": 100},
    ]
    with _patch_presentation(slides):
        r = audit_deck(deck)
    assert r.figure_gap_slides == 3


def test_audit_extracts_dois_from_arc(tmp_path):
    deck = tmp_path / "x.pptx"
    deck.write_bytes(b"fake")
    arc = tmp_path / "arc.md"
    arc.write_text(
        "Hickey at 10.48550/arxiv.2107.07953 and Sorin at "
        "10.1038/s41586-022-05672-3.",
        encoding="utf-8",
    )
    slides = [{"title": "x", "n_images": 0, "text_chars": 100}]
    with _patch_presentation(slides):
        r = audit_deck(deck, arc_path=arc)
    assert "10.48550/arxiv.2107.07953" in r.citations_in_arc
    assert "10.1038/s41586-022-05672-3" in r.citations_in_arc


def test_extract_dois_dedupes():
    """Real-world DOIs have 4-9 digit registrants."""
    text = "10.1038/x and 10.1038/x and 10.1101/y"
    out = _extract_dois_from_arc(text)
    assert out == ["10.1038/x", "10.1101/y"]


def test_manual_fetch_uses_realistic_dois():
    r = DeckAuditResult(
        deck_path=Path("/fake/x.pptx"),
        n_slides=5, n_total_images=0,
        slides_with_images=0, text_only_slides=5, thin_slides=0,
        figure_gap_slides=3,
        citations_in_arc=["10.1038/a", "10.1101/b"],
    )
    out = r.manual_fetch_shopping_list()
    assert "10.1038/a" in out


def test_to_markdown_includes_severity(tmp_path):
    deck = tmp_path / "x.pptx"
    deck.write_bytes(b"fake")
    slides = [{"title": "x", "n_images": 0, "text_chars": 100}] * 5
    with _patch_presentation(slides):
        r = audit_deck(deck)
    md = r.to_markdown_report()
    assert "fail" in md.lower()
    assert "5 slides" in md


def test_manual_fetch_shopping_list():
    r = DeckAuditResult(
        deck_path=Path("/fake/x.pptx"),
        n_slides=5, n_total_images=0,
        slides_with_images=0, text_only_slides=5, thin_slides=0,
        figure_gap_slides=3,
        citations_in_arc=["10.1038/a", "10.1101/b"],
    )
    out = r.manual_fetch_shopping_list()
    assert "10.1038/a" in out
    assert "doi.org" in out


def test_manual_fetch_empty_list_message():
    r = DeckAuditResult(
        deck_path=Path("/fake/x.pptx"),
        n_slides=5, n_total_images=0,
        slides_with_images=0, text_only_slides=5, thin_slides=0,
        figure_gap_slides=0,
        citations_in_arc=[],
    )
    out = r.manual_fetch_shopping_list()
    assert "no arc citations" in out.lower()
