"""Tests for vaultlab.report.pr_writeup_html — pattern #5 consumer.

Deterministic string-level + filesystem tests. Conventions match
:mod:`test_weekly_status_html` and :mod:`test_state_dashboard_html`.
"""

from __future__ import annotations

import json
from pathlib import Path

from vaultlab.report.pr_writeup_html import (
    CommitEntry,
    FileChange,
    PRWriteup,
    build_pr_writeup_html,
    write_pr_writeup_html,
)


# ---------------------------------------------------------------------------
# Fixtures


def _minimal() -> PRWriteup:
    return PRWriteup(
        title="v0.0.5 release notes",
        summary="One-line summary of a quiet release.",
    )


def _full() -> PRWriteup:
    return PRWriteup(
        title="v0.0.5 release notes",
        summary="Shipped 3 new HTML pattern consumers; no breaking changes.",
        commits=[
            CommitEntry(
                sha="abc1234",
                title="feat(report): PR writeup consumer",
                body="Adds pattern #5 — file table + commit log.",
                files=[
                    FileChange(
                        "src/vaultlab/report/pr_writeup_html.py",
                        "added",
                        330,
                        0,
                        "new module",
                    ),
                    FileChange(
                        "src/vaultlab/report/__init__.py",
                        "modified",
                        5,
                        0,
                        "re-exports",
                    ),
                ],
            ),
            CommitEntry(
                sha="def5678",
                title="feat(report): flowchart consumer",
                body="",
                files=[
                    FileChange(
                        "src/vaultlab/report/flowchart_html.py",
                        "added",
                        260,
                        0,
                        "new module",
                    ),
                ],
            ),
        ],
        test_summary="2049 passed, 6 deselected",
        test_summary_before="2046 passed, 6 deselected",
        breaking_changes=["Removed legacy `vaultlab.foo.bar.deprecated_func`."],
    )


# ---------------------------------------------------------------------------
# build_pr_writeup_html


def test_build_minimal_returns_well_formed_html():
    html = build_pr_writeup_html(_minimal())
    assert isinstance(html, str)
    assert html.startswith("<!doctype html>")
    assert "</html>" in html
    assert "v0.0.5 release notes" in html
    assert "One-line summary" in html


def test_build_full_renders_all_sections():
    html = build_pr_writeup_html(_full())
    # Section headers
    assert "Breaking changes" in html
    assert "Test suite" in html
    assert "Files changed" in html
    assert "Commits" in html
    # Item content
    assert "PR writeup consumer" in html
    assert "flowchart consumer" in html
    assert "pr_writeup_html.py" in html
    assert "flowchart_html.py" in html
    # Compare panel for before/after
    assert "Before" in html
    assert "After" in html
    assert "2046 passed" in html
    assert "2049 passed" in html


def test_build_aggregates_files_across_commits_when_top_level_empty():
    """When PRWriteup.files is empty, the renderer should roll up per-commit files."""
    pr = PRWriteup(
        title="multi-commit",
        summary="",
        commits=[
            CommitEntry(
                sha="111",
                title="c1",
                files=[FileChange("a.py", "modified", 3, 1, "")],
            ),
            CommitEntry(
                sha="222",
                title="c2",
                files=[FileChange("a.py", "modified", 2, 0, ""), FileChange("b.py", "added", 5, 0, "")],
            ),
        ],
    )
    html = build_pr_writeup_html(pr)
    # Both paths appear in the rolled-up table
    assert "a.py" in html
    assert "b.py" in html
    # Aggregated additions for a.py (3 + 2 = 5)
    assert "+5" in html


def test_build_no_test_summary_omits_compare_panel():
    pr = PRWriteup(title="quiet", summary="ok")
    html = build_pr_writeup_html(pr)
    # Should not crash and should not include the test-suite section header
    assert "Test suite" not in html


def test_build_no_breaking_changes_omits_section():
    pr = PRWriteup(title="quiet", summary="ok")
    html = build_pr_writeup_html(pr)
    assert "Breaking changes" not in html


def test_build_escapes_user_text():
    """User-supplied strings with HTML special chars must be escaped."""
    pr = PRWriteup(
        title="<script>alert(1)</script>",
        summary="Test & verify <b>escaping</b>.",
        commits=[
            CommitEntry(
                sha="<sha>",
                title="<bad title>",
                body="<script>evil()</script>",
                files=[FileChange("<x>", "modified", 1, 0, "<s>")],
            )
        ],
        breaking_changes=["<break>"],
    )
    html = build_pr_writeup_html(pr)
    # No raw script tags from user input survive
    assert "<script>alert(1)</script>" not in html
    assert "<script>evil()</script>" not in html
    # Escaped form should be present
    assert "&lt;script&gt;" in html or "&lt;script" in html


def test_build_empty_commits_still_renders():
    pr = PRWriteup(title="empty", summary="nothing happened")
    html = build_pr_writeup_html(pr)
    assert html.startswith("<!doctype html>")
    assert "</html>" in html


# ---------------------------------------------------------------------------
# write_pr_writeup_html + provenance


def test_write_creates_output_file(tmp_path: Path):
    out = tmp_path / "pr.html"
    result = write_pr_writeup_html(_minimal(), out)
    assert result == out
    assert out.exists()
    assert out.read_text(encoding="utf-8").startswith("<!doctype html>")


def test_write_creates_provenance_sidecars(tmp_path: Path):
    out = tmp_path / "pr.html"
    write_pr_writeup_html(_full(), out)
    prov_json = out.with_name(out.name + ".provenance.json")
    method_md = out.with_name(out.name + ".method.md")
    assert prov_json.exists(), f"missing provenance sidecar at {prov_json}"
    assert method_md.exists(), f"missing method.md sidecar at {method_md}"
    payload = json.loads(prov_json.read_text(encoding="utf-8"))
    assert payload["generated_by"] == "vaultlab.report.pr_writeup_html"
    assert payload["kind"] == "pr_writeup_html"
    assert payload["params"]["title"] == "v0.0.5 release notes"
    assert payload["params"]["commit_count"] == 2
    # 3 unique file paths from the two commits
    assert payload["params"]["file_count"] == 3
    assert payload["params"]["breaking_change_count"] == 1
    assert payload["params"]["has_test_summary"] is True
    assert payload["params"]["has_test_summary_before"] is True


def test_write_accepts_string_path(tmp_path: Path):
    out = tmp_path / "pr.html"
    result = write_pr_writeup_html(_minimal(), str(out))
    assert result == Path(str(out))
    assert out.exists()


def test_write_creates_parent_directories(tmp_path: Path):
    out = tmp_path / "nested" / "subdir" / "pr.html"
    write_pr_writeup_html(_minimal(), out)
    assert out.exists()
    assert out.parent.exists()
