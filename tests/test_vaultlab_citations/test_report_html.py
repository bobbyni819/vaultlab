"""Tests for vaultlab.citations.report_html — citation audit HTML consumer."""

from __future__ import annotations

from pathlib import Path

import pytest

from vaultlab.citations.report_html import (
    build_citation_audit_html,
    write_citation_audit_html,
)


@pytest.fixture
def sample_audit() -> dict:
    return {
        "total": 3,
        "by_status": {"verified_fulltext": 1, "unverified": 1, "suspect": 1},
        "high_risk_unverified": 1,
        "audit_date": "2026-05-12",
        "source_files": ["draft.md", "intro.md"],
        "hallucination_flags": ["Author-year mismatch"],
        "action_items": [
            "Re-verify Citation #2 (Park 2023) against the PubMed record",
            "Replace placeholder DOI on Citation #3",
        ],
        "citations": [
            {
                "raw_text": "(Smith 2020)",
                "authors": "Smith J",
                "year": 2020,
                "claim": "Method X maps cells in space.",
                "source_file": "intro.md",
                "line_number": 42,
                "doi": "10.1234/a",
                "title": "Mapping cells",
                "status": "verified_fulltext",
                "risk": "low",
                "hallucination_flags": [],
            },
            {
                "raw_text": "(Park 2023)",
                "authors": "Park S",
                "year": 2023,
                "claim": "X is the best method.",
                "source_file": "draft.md",
                "line_number": 88,
                "doi": "",
                "status": "unverified",
                "risk": "high",
                "hallucination_flags": ["Author-year mismatch"],
            },
            {
                "raw_text": "(Doe 2099)",
                "authors": "Doe J",
                "year": 2099,
                "claim": "Future claim",
                "source_file": "draft.md",
                "line_number": 100,
                "status": "suspect",
                "risk": "medium",
                "hallucination_flags": ["Year in future"],
            },
        ],
    }


def test_renders_basic_audit(sample_audit):
    html = build_citation_audit_html(sample_audit)
    assert "<!doctype html>" in html
    assert "3 citations" in html
    assert "Citation audit" in html


def test_summary_chips(sample_audit):
    html = build_citation_audit_html(sample_audit)
    assert "verified fulltext: 1" in html
    assert "unverified: 1" in html
    assert "suspect: 1" in html
    assert "1 high-risk unverified" in html


def test_action_items_section(sample_audit):
    html = build_citation_audit_html(sample_audit)
    assert "Action items" in html
    assert "Re-verify Citation #2" in html
    assert "Replace placeholder DOI" in html


def test_per_citation_cards(sample_audit):
    html = build_citation_audit_html(sample_audit)
    assert "Method X maps cells in space" in html
    assert "intro.md:42" in html
    assert "Park S" in html
    assert "draft.md:88" in html


def test_hallucination_flags_render(sample_audit):
    html = build_citation_audit_html(sample_audit)
    assert "Author-year mismatch" in html
    assert "Year in future" in html
    # Flags section as a table at the bottom
    assert "Hallucination flag patterns" in html


def test_filter_buckets_match_statuses(sample_audit):
    html = build_citation_audit_html(sample_audit)
    assert 'data-filter="verified_fulltext"' in html
    assert 'data-filter="unverified"' in html
    assert 'data-filter="suspect"' in html
    assert 'data-filter="has-flags"' in html
    assert 'data-filter="risk-high"' in html


def test_per_card_filter_keys(sample_audit):
    html = build_citation_audit_html(sample_audit)
    # verified card → has verified_fulltext + risk-low
    assert 'data-filter-key="verified_fulltext,risk-low"' in html
    # unverified card → has unverified + risk-high + has-flags
    assert 'data-filter-key="unverified,risk-high,has-flags"' in html


def test_copy_doi_action_present(sample_audit):
    html = build_citation_audit_html(sample_audit)
    assert 'data-copy="10.1234/a"' in html


def test_handles_audit_report_dataclass():
    """Should accept anything with .to_dict()."""

    class FakeAudit:
        def to_dict(self):
            return {
                "total": 0,
                "by_status": {},
                "high_risk_unverified": 0,
                "audit_date": "2026-01-01",
                "source_files": [],
                "hallucination_flags": [],
                "action_items": [],
                "citations": [],
            }

    html = build_citation_audit_html(FakeAudit())
    assert "<!doctype html>" in html


def test_empty_audit():
    html = build_citation_audit_html(
        {
            "total": 0,
            "by_status": {},
            "high_risk_unverified": 0,
            "audit_date": "",
            "source_files": [],
            "hallucination_flags": [],
            "action_items": [],
            "citations": [],
        }
    )
    assert "No citations audited" in html


def test_xss_safe_against_evil_claim():
    audit = {
        "total": 1,
        "by_status": {"unverified": 1},
        "high_risk_unverified": 0,
        "audit_date": "x",
        "source_files": [],
        "hallucination_flags": [],
        "action_items": [],
        "citations": [
            {
                "raw_text": "(x)",
                "authors": "<script>alert(1)</script>",
                "year": 2020,
                "claim": "<img src=x onerror=alert(1)>",
                "source_file": "f.md",
                "line_number": 1,
                "status": "unverified",
                "risk": "low",
                "hallucination_flags": [],
            }
        ],
    }
    html = build_citation_audit_html(audit)
    assert "<script>alert(1)</script>" not in html
    assert "<img src=x onerror" not in html
    assert "&lt;script&gt;" in html


def test_write_citation_audit_html(tmp_path: Path, sample_audit):
    out = tmp_path / "audit.html"
    written = write_citation_audit_html(out, sample_audit)
    assert written == out
    assert out.exists()
