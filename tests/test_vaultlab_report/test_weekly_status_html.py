"""Tests for vaultlab.report.weekly_status_html — pattern #16 consumer.

Deterministic string-level + filesystem tests. No browser rendering.

These match the conventions in ``test_html.py`` (well-formedness probe,
substring checks on the rendered HTML) and in
``test_vaultlab_slides/test_audit_html.py`` (rendered-string snapshots).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from vaultlab.report.weekly_status_html import (
    WeeklyStatusReport,
    build_weekly_status_html,
    write_weekly_status_html,
)


# ---------------------------------------------------------------------------
# Fixtures


def _minimal_report() -> WeeklyStatusReport:
    return WeeklyStatusReport(
        week_label="Week of 2026-05-15",
        project="vaultlab",
        tldr="A minimal weekly summary with nothing shipped yet.",
    )


def _full_report() -> WeeklyStatusReport:
    return WeeklyStatusReport(
        week_label="Week of 2026-05-15",
        project="vaultlab",
        tldr=(
            "Shipped HTML pattern #16 weekly-status consumer; figure-pack "
            "lint blocker still open."
        ),
        shipped=[
            ("Pattern #16 weekly-status", "Composes tldr_box + card_grid + matrix_table."),
            ("Provenance receipts wired", "Calls write_receipts per Red Line #2."),
        ],
        in_flight=[
            ("Figure-pack lint", "Investigating false positives on multi-panel figures."),
        ],
        blockers=[
            ("OA PDF resolver", "CrossRef rate-limit on lit-arc batch ingest."),
        ],
        carryover_next_week=[
            "Wire dispatch.py to route weekly-status dicts",
            "Add /weekly-status slash command",
        ],
        metrics={
            "commits": "12",
            "tests": "1734 passing",
            "lines changed": "+842 / -103",
        },
    )


# ---------------------------------------------------------------------------
# build_weekly_status_html


def test_build_minimal_returns_non_empty_html():
    html = build_weekly_status_html(_minimal_report())
    assert isinstance(html, str)
    assert html.startswith("<!doctype html>")
    assert "</html>" in html
    assert "vaultlab" in html  # project name appears
    assert "Week of 2026-05-15" in html  # week label appears


def test_build_minimal_contains_tldr():
    html = build_weekly_status_html(_minimal_report())
    # tldr_box renders the "TL;DR" label by default
    assert "TL;DR" in html
    assert "A minimal weekly summary" in html


def test_build_full_contains_shipped_in_flight_blockers():
    html = build_weekly_status_html(_full_report())
    # Section titles
    assert "Shipped" in html
    assert "In flight" in html
    assert "Blockers" in html
    # Item contents
    assert "Pattern #16 weekly-status" in html
    assert "Figure-pack lint" in html
    assert "OA PDF resolver" in html
    # Carryover bullets
    assert "Wire dispatch.py" in html


def test_build_full_renders_metrics():
    html = build_weekly_status_html(_full_report())
    # Metric labels + values should both be present
    assert "commits" in html
    assert "12" in html
    assert "1734 passing" in html


def test_build_empty_shipped_omits_or_handles_gracefully():
    """No shipped items → either section omitted or shows an explicit empty state.
    Either is acceptable; we just don't want a crash or a broken tag.
    """
    report = WeeklyStatusReport(
        week_label="Week of 2026-05-15",
        project="vaultlab",
        tldr="Slow week.",
    )
    html = build_weekly_status_html(report)
    assert html.startswith("<!doctype html>")
    assert "</html>" in html


def test_build_no_metrics_no_blockers_still_renders():
    report = WeeklyStatusReport(
        week_label="Week of 2026-05-15",
        project="vaultlab",
        tldr="Quiet week, no blockers.",
        shipped=[("One thing", "Did one thing.")],
    )
    html = build_weekly_status_html(report)
    assert "One thing" in html
    assert "Quiet week" in html
    # Should not contain a Blockers section header when there are no blockers
    # (but it's fine if it does — we only require it doesn't crash)
    assert html.startswith("<!doctype html>")


def test_build_escapes_user_text():
    """User-supplied strings with HTML special chars must be escaped."""
    report = WeeklyStatusReport(
        week_label="Week of 2026-05-15",
        project="<script>alert(1)</script>",
        tldr="Test & verify <b>escaping</b>.",
        shipped=[("<bad>", "<also bad>")],
    )
    html = build_weekly_status_html(report)
    # Raw script tag from user input must not appear in the rendered output
    assert "<script>alert(1)</script>" not in html
    # Escaped form should be present somewhere
    assert "&lt;script&gt;" in html or "&lt;script" in html


# ---------------------------------------------------------------------------
# write_weekly_status_html + provenance


def test_write_creates_output_file(tmp_path: Path):
    out = tmp_path / "weekly.html"
    result = write_weekly_status_html(_minimal_report(), out)
    assert result == out
    assert out.exists()
    assert out.read_text(encoding="utf-8").startswith("<!doctype html>")


def test_write_creates_provenance_sidecars(tmp_path: Path):
    out = tmp_path / "weekly.html"
    write_weekly_status_html(_full_report(), out)
    prov_json = out.with_name(out.name + ".provenance.json")
    method_md = out.with_name(out.name + ".method.md")
    assert prov_json.exists(), f"missing provenance sidecar at {prov_json}"
    assert method_md.exists(), f"missing method.md sidecar at {method_md}"
    payload = json.loads(prov_json.read_text(encoding="utf-8"))
    assert payload["generated_by"] == "vaultlab.report.weekly_status_html"
    assert payload["kind"] == "weekly_status_html"
    assert payload["params"]["project"] == "vaultlab"
    assert payload["params"]["week_label"] == "Week of 2026-05-15"
    assert payload["params"]["shipped_count"] == 2


def test_write_accepts_string_path(tmp_path: Path):
    out = tmp_path / "weekly.html"
    result = write_weekly_status_html(_minimal_report(), str(out))
    assert result == Path(str(out))
    assert out.exists()


def test_write_creates_parent_directories(tmp_path: Path):
    out = tmp_path / "nested" / "subdir" / "weekly.html"
    write_weekly_status_html(_minimal_report(), out)
    assert out.exists()
    assert out.parent.exists()
