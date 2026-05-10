"""Tests for vaultlab.research.read_paper — the section-aware dispatcher.

Per the 2026-05-02 paperclip integration design (Q3), Tier-A reading
should prefer paperclip's pre-extracted sections when available and
fall back to PDF text-extraction otherwise.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from vaultlab.research.acquisition import AcquisitionResult
from vaultlab.research.read_paper import (
    list_paper_figures,
    read_paper_sections,
    read_paper_text,
)


def _result(
    *, source: str, pdf_path: Path | None = None, tier_errors: dict[str, str] | None = None
) -> AcquisitionResult:
    return AcquisitionResult(
        doi="10.1/test",
        pdf_path=pdf_path,
        source=source,
        license=None,
        tier_errors=tier_errors or {},
    )


# ---- read_paper_text ----------------------------------------------------


def test_paperclip_outcome_reads_from_client():
    pc = MagicMock()
    pc.get_paper_text.return_value = "Body text from paperclip."
    r = _result(source="paperclip")
    text = read_paper_text(
        r,
        paperclip_client=pc,
        paperclip_paper_id="arx_xxx",
    )
    assert text == "Body text from paperclip."
    pc.get_paper_text.assert_called_once_with("arx_xxx")


def test_paperclip_outcome_without_client_returns_empty():
    r = _result(source="paperclip")
    assert read_paper_text(r) == ""
    assert read_paper_text(r, paperclip_client=MagicMock()) == ""  # no paper_id


def test_pdf_outcome_falls_back_to_extract_text(tmp_path: Path, monkeypatch):
    """When outcome is oa_pdf/cache_hit/gated_pdf_via_key, delegate to
    vaultlab.research.pdf.extract_text."""
    pdf_path = tmp_path / "x.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n" + b"stub" * 500)

    fake_extract = MagicMock(return_value="Extracted PDF text.")
    monkeypatch.setattr("vaultlab.research.pdf.extract_text", fake_extract)

    r = _result(source="unpaywall", pdf_path=pdf_path)
    assert r.outcome == "oa_pdf"
    assert read_paper_text(r) == "Extracted PDF text."
    fake_extract.assert_called_once_with(str(pdf_path))


def test_cache_hit_outcome_uses_extract_text(tmp_path: Path, monkeypatch):
    pdf_path = tmp_path / "x.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n" + b"x" * 2000)
    fake_extract = MagicMock(return_value="Cached PDF text.")
    monkeypatch.setattr("vaultlab.research.pdf.extract_text", fake_extract)

    r = _result(source="cache", pdf_path=pdf_path)
    assert r.outcome == "cache_hit"
    assert read_paper_text(r) == "Cached PDF text."


def test_metadata_only_uses_abstract_fallback():
    r = _result(source="springer", pdf_path=None)
    assert r.outcome == "gated_metadata_only"
    assert read_paper_text(r, abstract_fallback="Abstract text.") == "Abstract text."


def test_metadata_only_empty_fallback_returns_empty():
    r = _result(source="springer", pdf_path=None)
    assert read_paper_text(r) == ""


def test_failed_outcome_returns_empty():
    r = _result(source="failed", tier_errors={"elsevier": "403"})
    # paywalled — no readable source
    assert read_paper_text(r) == ""


# ---- read_paper_sections -----------------------------------------------


def test_paperclip_sections_pulls_per_section():
    pc = MagicMock()
    pc.list_sections.return_value = ["Abstract", "Introduction", "Methods"]
    pc.get_section.side_effect = lambda pid, name: f"<{name} body>"

    r = _result(source="paperclip")
    sections = read_paper_sections(r, paperclip_client=pc, paperclip_paper_id="arx_xxx")
    assert sections == {
        "Abstract": "<Abstract body>",
        "Introduction": "<Introduction body>",
        "Methods": "<Methods body>",
    }


def test_paperclip_sections_skips_empty_sections():
    pc = MagicMock()
    pc.list_sections.return_value = ["Abstract", "References"]
    pc.get_section.side_effect = lambda pid, name: "Abstract body" if name == "Abstract" else ""

    r = _result(source="paperclip")
    sections = read_paper_sections(r, paperclip_client=pc, paperclip_paper_id="x")
    assert sections == {"Abstract": "Abstract body"}


def test_pdf_sections_returns_single_all_entry(tmp_path: Path, monkeypatch):
    pdf_path = tmp_path / "x.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n" + b"x" * 2000)
    monkeypatch.setattr(
        "vaultlab.research.pdf.extract_text",
        MagicMock(return_value="Whole PDF text."),
    )

    r = _result(source="pmc", pdf_path=pdf_path)
    sections = read_paper_sections(r)
    assert sections == {"all": "Whole PDF text."}


def test_metadata_only_sections_returns_abstract():
    r = _result(source="springer", pdf_path=None)
    out = read_paper_sections(r, abstract_fallback="The abstract.")
    assert out == {"Abstract": "The abstract."}


def test_metadata_only_sections_empty_fallback_returns_empty_dict():
    r = _result(source="springer", pdf_path=None)
    assert read_paper_sections(r) == {}


# ---- list_paper_figures ------------------------------------------------


def test_paperclip_figures_lists_from_client():
    pc = MagicMock()
    pc.list_figures.return_value = ["figure_1.jpg", "figure_2.jpg"]
    r = _result(source="paperclip")
    figs = list_paper_figures(r, paperclip_client=pc, paperclip_paper_id="x")
    assert figs == ["figure_1.jpg", "figure_2.jpg"]


def test_pdf_figures_lists_from_local_dir(tmp_path: Path):
    extract_dir = tmp_path / "figures"
    extract_dir.mkdir()
    (extract_dir / "fig_1.png").write_bytes(b"")
    (extract_dir / "fig_2.png").write_bytes(b"")
    (extract_dir / "ignored.txt").write_text("not an image")

    pdf_path = tmp_path / "x.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n" + b"x" * 2000)
    r = _result(source="unpaywall", pdf_path=pdf_path)

    figs = list_paper_figures(r, pdf_extract_dir=extract_dir)
    # Order isn't specified but both PNGs should appear
    assert set(figs) == {"fig_1.png", "fig_2.png"}


def test_pdf_figures_no_extract_dir_returns_empty(tmp_path: Path):
    pdf_path = tmp_path / "x.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n" + b"x" * 2000)
    r = _result(source="unpaywall", pdf_path=pdf_path)
    assert list_paper_figures(r) == []


def test_failed_outcome_returns_empty_figures():
    r = _result(source="failed", tier_errors={"elsevier": "403"})
    assert list_paper_figures(r) == []
