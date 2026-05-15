"""Tests for vaultlab.report.incident_timeline_html — pattern #17 consumer.

Deterministic string-level + filesystem tests. Conventions match
:mod:`test_weekly_status_html` and :mod:`test_state_dashboard_html`.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from vaultlab.report.incident_timeline_html import (
    IncidentChecklist,
    IncidentReport,
    TimelineEntry,
    build_incident_timeline_html,
    write_incident_timeline_html,
)


# ---------------------------------------------------------------------------
# Fixtures


def _minimal() -> IncidentReport:
    return IncidentReport(
        title="A small hiccup",
        summary="Tiny incident, no entries.",
        started=datetime(2026, 5, 15, 8, 0, 0),
    )


def _full() -> IncidentReport:
    return IncidentReport(
        title="Lit-arc pipeline run, 2026-05-12, partial failure",
        summary=(
            "Tier-B summarization stalled on CrossRef rate-limit during "
            "burst; pipeline recovered after backoff retry."
        ),
        started=datetime(2026, 5, 12, 22, 30, 0),
        resolved=datetime(2026, 5, 13, 0, 45, 0),
        entries=[
            TimelineEntry(
                timestamp=datetime(2026, 5, 12, 22, 30, 0),
                event="Pipeline launched",
                severity="info",
            ),
            TimelineEntry(
                timestamp=datetime(2026, 5, 12, 22, 45, 0),
                event="Crosstalk round 2 stuck",
                severity="warning",
                log_excerpt="WARN crosstalk loop reached 8/8 with no convergence",
            ),
            TimelineEntry(
                timestamp=datetime(2026, 5, 12, 23, 0, 0),
                event="CrossRef rate-limit hit",
                severity="error",
                log_excerpt="ERROR 429 Too Many Requests\nretry-after: 60s",
            ),
            TimelineEntry(
                timestamp=datetime(2026, 5, 13, 0, 45, 0),
                event="Recovered via backoff",
                severity="resolution",
            ),
        ],
        followup_checklist=[
            IncidentChecklist("Add adaptive backoff to CrossRef client", False),
            IncidentChecklist("Cap Tier-B burst to 25 papers", True),
        ],
    )


# ---------------------------------------------------------------------------
# build_incident_timeline_html


def test_build_minimal_returns_well_formed_html():
    html = build_incident_timeline_html(_minimal())
    assert isinstance(html, str)
    assert html.startswith("<!doctype html>")
    assert "</html>" in html
    assert "A small hiccup" in html
    # Started timestamp shows up
    assert "2026-05-15 08:00:00" in html


def test_build_minimal_shows_open_status():
    html = build_incident_timeline_html(_minimal())
    # No resolved timestamp → OPEN chip + "still open" caption
    assert "OPEN" in html
    assert "still open" in html


def test_build_full_renders_all_entries():
    html = build_incident_timeline_html(_full())
    # All four event labels appear
    assert "Pipeline launched" in html
    assert "Crosstalk round 2 stuck" in html
    assert "CrossRef rate-limit hit" in html
    assert "Recovered via backoff" in html
    # Followup checklist items
    assert "Add adaptive backoff" in html
    assert "Cap Tier-B burst" in html
    # Resolved status
    assert "RESOLVED" in html


def test_build_full_includes_log_excerpt_tab():
    html = build_incident_timeline_html(_full())
    # When at least one entry has a log_excerpt, the "Log excerpts" tab renders
    assert "Log excerpts" in html
    # Excerpt content shows up
    assert "429 Too Many Requests" in html


def test_build_no_log_excerpts_omits_logs_tab():
    """When no entry has a log_excerpt, the Log excerpts tab is omitted."""
    report = IncidentReport(
        title="quiet incident",
        summary="just info events",
        started=datetime(2026, 5, 15, 8, 0, 0),
        resolved=datetime(2026, 5, 15, 8, 5, 0),
        entries=[
            TimelineEntry(
                timestamp=datetime(2026, 5, 15, 8, 0, 0),
                event="x",
                severity="info",
            ),
        ],
    )
    html = build_incident_timeline_html(report)
    assert "Log excerpts" not in html
    # Timeline tab still present
    assert "Timeline" in html


def test_build_empty_entries_renders_placeholder():
    report = IncidentReport(
        title="nothing happened",
        summary="we just opened a ticket",
        started=datetime(2026, 5, 15, 8, 0, 0),
    )
    html = build_incident_timeline_html(report)
    assert "No timeline entries" in html


def test_build_severity_chip_counts_appear():
    html = build_incident_timeline_html(_full())
    # 1 error, 1 warning, 1 info, 1 resolution
    assert "1 error" in html
    assert "1 warning" in html
    assert "1 info" in html
    assert "1 resolution" in html


def test_build_escapes_user_text():
    report = IncidentReport(
        title="<script>alert(1)</script>",
        summary="Test & <b>escape</b>.",
        started=datetime(2026, 5, 15, 8, 0, 0),
        entries=[
            TimelineEntry(
                timestamp=datetime(2026, 5, 15, 8, 1, 0),
                event="<bad event>",
                severity="error",
                log_excerpt="<scripted log>",
            )
        ],
        followup_checklist=[IncidentChecklist("<bad followup>")],
    )
    html = build_incident_timeline_html(report)
    assert "<script>alert(1)</script>" not in html
    assert "<scripted log>" not in html
    assert "&lt;script&gt;" in html or "&lt;script" in html


# ---------------------------------------------------------------------------
# write_incident_timeline_html + provenance


def test_write_creates_output_file(tmp_path: Path):
    out = tmp_path / "incident.html"
    result = write_incident_timeline_html(_minimal(), out)
    assert result == out
    assert out.exists()


def test_write_creates_provenance_sidecars(tmp_path: Path):
    out = tmp_path / "incident.html"
    write_incident_timeline_html(_full(), out)
    prov_json = out.with_name(out.name + ".provenance.json")
    method_md = out.with_name(out.name + ".method.md")
    assert prov_json.exists()
    assert method_md.exists()
    payload = json.loads(prov_json.read_text(encoding="utf-8"))
    assert payload["generated_by"] == "vaultlab.report.incident_timeline_html"
    assert payload["kind"] == "incident_timeline_html"
    assert payload["params"]["entry_count"] == 4
    assert payload["params"]["followup_count"] == 2
    # Severity rollup
    assert payload["params"]["severity_counts"]["error"] == 1
    assert payload["params"]["severity_counts"]["warning"] == 1
    assert payload["params"]["severity_counts"]["info"] == 1
    assert payload["params"]["severity_counts"]["resolution"] == 1
    assert payload["params"]["any_log_excerpts"] is True
    # ISO timestamp on started
    assert "2026-05-12" in payload["params"]["started"]
    assert payload["params"]["resolved"]


def test_write_accepts_string_path(tmp_path: Path):
    out = tmp_path / "incident.html"
    result = write_incident_timeline_html(_minimal(), str(out))
    assert result == Path(str(out))
    assert out.exists()


def test_write_creates_parent_directories(tmp_path: Path):
    out = tmp_path / "nested" / "deeper" / "incident.html"
    write_incident_timeline_html(_minimal(), out)
    assert out.exists()
    assert out.parent.exists()


def test_write_unresolved_incident_records_empty_resolved(tmp_path: Path):
    out = tmp_path / "incident.html"
    write_incident_timeline_html(_minimal(), out)
    prov_json = out.with_name(out.name + ".provenance.json")
    payload = json.loads(prov_json.read_text(encoding="utf-8"))
    assert payload["params"]["resolved"] == ""
    assert payload["params"]["any_log_excerpts"] is False
