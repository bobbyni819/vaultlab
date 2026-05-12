"""Tests for vaultlab.kb.dossier_html — dossier HTML consumer."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import pytest

from vaultlab.kb.dossier_html import (
    build_dossier_report_html,
    write_dossier_report,
)


@pytest.fixture
def fresh_dossier_dict() -> dict:
    return {
        "project_slug": "metabolism",
        "kb_root": Path("/kb/metabolism"),
        "compiled_at": datetime.now(UTC),
        "sections": [
            {
                "slug": "origin",
                "title": "Why this project exists (the origin)",
                "body": "# Origin\n\nThe **metabolism** project began in 2024.\n\n"
                "- First milestone\n- Second milestone",
                "sources": [Path("kb/origin.md"), Path("kb/notes.md")],
            },
            {
                "slug": "current_state",
                "title": "Where we are (current state)",
                "body": "Currently working on `lipid_xgboost`.",
                "sources": [Path("kb/state.md")],
            },
            {
                "slug": "frontier",
                "title": "Active frontier",
                "body": "",
                "sources": [],
            },
        ],
    }


@pytest.fixture
def stale_dossier_dict(fresh_dossier_dict) -> dict:
    d = dict(fresh_dossier_dict)
    d["compiled_at"] = datetime.now(UTC) - timedelta(days=5)
    return d


def test_renders_basic_dossier(fresh_dossier_dict):
    html = build_dossier_report_html(fresh_dossier_dict)
    assert "<!doctype html>" in html
    assert "metabolism" in html
    assert "3 sections" in html


def test_fresh_dossier_gets_good_badge(fresh_dossier_dict):
    html = build_dossier_report_html(fresh_dossier_dict)
    assert "fresh" in html
    # No stale warning
    assert "stale" not in html or "stale (" not in html


def test_stale_dossier_gets_bad_badge(stale_dossier_dict):
    html = build_dossier_report_html(stale_dossier_dict)
    assert "stale" in html
    assert "refresh via /refresh-dossier" in html


def test_sections_render_as_tabs(fresh_dossier_dict):
    html = build_dossier_report_html(fresh_dossier_dict)
    assert "vl-tabs" in html
    assert "Why this project exists" in html
    assert "Where we are" in html
    assert "Active frontier" in html


def test_section_markdown_renders(fresh_dossier_dict):
    html = build_dossier_report_html(fresh_dossier_dict)
    # H1 → h3+ in dossier
    assert "<h3>Origin</h3>" in html
    # Bold
    assert "<strong>metabolism</strong>" in html
    # Bullets
    assert "<li>First milestone</li>" in html
    # Inline code
    assert "<code>lipid_xgboost</code>" in html


def test_empty_section_shows_placeholder(fresh_dossier_dict):
    html = build_dossier_report_html(fresh_dossier_dict)
    assert "(empty)" in html


def test_sources_collapsible_per_section(fresh_dossier_dict):
    html = build_dossier_report_html(fresh_dossier_dict)
    assert "Sources (2)" in html  # origin section has 2 sources
    # Path uses native separator on Windows; check basenames instead.
    assert "origin.md" in html
    assert "notes.md" in html


def test_all_sources_appendix(fresh_dossier_dict):
    html = build_dossier_report_html(fresh_dossier_dict)
    assert "All source files referenced" in html


def test_handles_dataclass_dossier():
    """Should accept anything with project_slug/sections/compiled_at attrs."""
    from dataclasses import dataclass

    @dataclass
    class FakeSection:
        slug: str
        title: str
        body: str
        sources: list

    @dataclass
    class FakeDossier:
        project_slug: str
        kb_root: Path
        sections: list
        compiled_at: datetime

    d = FakeDossier(
        project_slug="x",
        kb_root=Path("/kb"),
        sections=[FakeSection("a", "A title", "body", [Path("p.md")])],
        compiled_at=datetime.now(UTC),
    )
    html = build_dossier_report_html(d)
    assert "<!doctype html>" in html
    assert "A title" in html


def test_xss_safe_against_evil_section_body():
    d = {
        "project_slug": "x",
        "compiled_at": datetime.now(UTC),
        "sections": [
            {
                "slug": "a",
                "title": "Section",
                "body": "<script>alert(1)</script>",
                "sources": [],
            }
        ],
    }
    html = build_dossier_report_html(d)
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html


def test_empty_dossier():
    d = {
        "project_slug": "empty",
        "compiled_at": datetime.now(UTC),
        "sections": [],
    }
    html = build_dossier_report_html(d)
    assert "<!doctype html>" in html
    assert "No sections compiled" in html


def test_write_dossier_report(tmp_path: Path, fresh_dossier_dict):
    out = tmp_path / "dossier.html"
    written = write_dossier_report(out, fresh_dossier_dict)
    assert written == out
    assert out.exists()
