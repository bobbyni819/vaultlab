"""Tests for vaultlab.citations.export — ENW / RIS / Zotero RDF exporters."""

from __future__ import annotations

from pathlib import Path

import pytest

from vaultlab.citations.export import (
    to_enw,
    to_ris,
    to_zotero_rdf,
    write_export,
)


@pytest.fixture
def sample_cits() -> list[dict]:
    return [
        {
            "authors": "Smith J, Park S, Lee M",
            "year": 2020,
            "title": "Method X maps cells in tissue space",
            "journal": "Nature",
            "doi": "10.1038/abc",
            "pmid": "12345",
            "claim": "Method X maps cells with high fidelity.",
        },
        {
            "authors": "Park S",
            "year": 2023,
            "title": "Multi-modal follow-up",
            "journal": "Cell",
            "doi": "10.1016/xyz",
            "claim": "Validates Smith et al.",
        },
        {
            # Edge case: empty author, no DOI
            "authors": "",
            "year": "",
            "title": "Anonymous note",
            "claim": "",
        },
    ]


# ---------------------------------------------------------------------------
# ENW


def test_enw_basic_record(sample_cits):
    out = to_enw([sample_cits[0]])
    assert "%0 Journal Article" in out
    assert "%A Smith J" in out
    assert "%A Park S" in out
    assert "%A Lee M" in out
    assert "%D 2020" in out
    assert "%T Method X maps cells in tissue space" in out
    assert "%J Nature" in out
    assert "%R 10.1038/abc" in out
    assert "%U https://doi.org/10.1038/abc" in out
    assert "%M 12345" in out


def test_enw_handles_multiple_records(sample_cits):
    out = to_enw(sample_cits)
    # Three records, separated by blank lines
    assert out.count("%0 Journal Article") == 3
    # Second record has only 1 author
    assert "%A Park S" in out


def test_enw_handles_missing_fields(sample_cits):
    out = to_enw([sample_cits[2]])
    # Should still produce a valid record without DOI/journal
    assert "%0 Journal Article" in out
    assert "%T Anonymous note" in out
    assert "%R " not in out  # no DOI line
    assert "%J " not in out  # no journal line


def test_enw_accepts_list_authors():
    cit = {
        "authors": ["A B", "C D"],
        "year": 2020,
        "title": "T",
    }
    out = to_enw([cit])
    assert "%A A B" in out
    assert "%A C D" in out


# ---------------------------------------------------------------------------
# RIS


def test_ris_basic_record(sample_cits):
    out = to_ris([sample_cits[0]])
    assert "TY  - JOUR" in out
    assert "AU  - Smith J" in out
    assert "AU  - Park S" in out
    assert "AU  - Lee M" in out
    assert "PY  - 2020" in out
    assert "TI  - Method X maps cells in tissue space" in out
    assert "JO  - Nature" in out
    assert "DO  - 10.1038/abc" in out
    assert "UR  - https://doi.org/10.1038/abc" in out
    assert "AN  - 12345" in out
    assert "ER  -" in out


def test_ris_handles_multiple_records(sample_cits):
    out = to_ris(sample_cits)
    assert out.count("TY  - JOUR") == 3
    assert out.count("ER  -") == 3


# ---------------------------------------------------------------------------
# Zotero RDF


def test_rdf_starts_with_xml_declaration(sample_cits):
    out = to_zotero_rdf(sample_cits)
    assert out.startswith('<?xml version="1.0" encoding="UTF-8"?>')
    assert "<rdf:RDF" in out
    assert "</rdf:RDF>" in out


def test_rdf_includes_bib_articles(sample_cits):
    out = to_zotero_rdf(sample_cits)
    assert "<bib:Article rdf:about=" in out
    assert out.count("<bib:Article") == 3


def test_rdf_includes_authors(sample_cits):
    out = to_zotero_rdf(sample_cits)
    assert "<foaf:surname>Smith J</foaf:surname>" in out
    assert "<foaf:surname>Park S</foaf:surname>" in out
    assert "<foaf:surname>Lee M</foaf:surname>" in out


def test_rdf_includes_doi(sample_cits):
    out = to_zotero_rdf(sample_cits)
    assert "DOI 10.1038/abc" in out
    assert "https://doi.org/10.1038/abc" in out


def test_rdf_escapes_html_in_title():
    out = to_zotero_rdf([{"title": "Cells & <Mice>", "authors": "", "year": 2020}])
    assert "Cells &amp; &lt;Mice&gt;" in out
    assert "<Mice>" not in out


# ---------------------------------------------------------------------------
# write_export


def test_write_export_infers_format_from_extension(tmp_path: Path, sample_cits):
    enw_path = tmp_path / "out.enw"
    ris_path = tmp_path / "out.ris"
    rdf_path = tmp_path / "out.rdf"

    write_export(enw_path, sample_cits)
    write_export(ris_path, sample_cits)
    write_export(rdf_path, sample_cits)

    assert "%0 Journal Article" in enw_path.read_text(encoding="utf-8")
    assert "TY  - JOUR" in ris_path.read_text(encoding="utf-8")
    assert "<rdf:RDF" in rdf_path.read_text(encoding="utf-8")


def test_write_export_explicit_format(tmp_path: Path, sample_cits):
    out = tmp_path / "out.txt"
    write_export(out, sample_cits, fmt="ris")
    assert "TY  - JOUR" in out.read_text(encoding="utf-8")


def test_write_export_unknown_extension_raises(tmp_path: Path, sample_cits):
    with pytest.raises(ValueError, match="Cannot infer format"):
        write_export(tmp_path / "out.txt", sample_cits)


def test_write_export_creates_parent_dirs(tmp_path: Path, sample_cits):
    out = tmp_path / "nested" / "deeper" / "out.ris"
    write_export(out, sample_cits)
    assert out.exists()


def test_handles_citation_dataclass():
    """Should accept anything with .to_dict()."""

    class FakeCit:
        def to_dict(self):
            return {
                "authors": "X Y",
                "year": 2020,
                "title": "T",
                "doi": "10.1/x",
            }

    out = to_enw([FakeCit()])
    assert "%A X Y" in out
    assert "%T T" in out
