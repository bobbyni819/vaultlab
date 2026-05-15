"""Standalone integration test for vaultlab.citations.

Implements north-star Criterion #3 ("plug-in companion"): the primary
entrypoint of ``vaultlab.citations`` must be invocable from a fresh
``tmp_path`` fixture with no prior vaultlab state.

We exercise ``audit_file`` on a tiny markdown fixture written to
``tmp_path``. Because we don't pass a ``research_client``, the auditor
runs extraction-only — no network mocks needed. This proves the
extraction half of the pipeline is plug-in usable.
"""

from __future__ import annotations

from pathlib import Path

import pytest


def test_audit_file_runs_standalone_from_fresh_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``audit_file`` extracts citations from a fresh markdown file
    without any KB, evidence index, or research client present."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / ".config"))

    from vaultlab.citations import AuditReport, audit_file

    md = tmp_path / "draft.md"
    md.write_text(
        "# Test draft\n"
        "\n"
        "The signal was observed (Smith et al., 2024).\n"
        "See also doi:10.1038/s41586-024-99999-9 for the original method.\n"
        "PMID: 12345678 covers the orthogonal finding.\n",
        encoding="utf-8",
    )

    report = audit_file(str(md))

    assert isinstance(report, AuditReport)
    # We expect at least the author-year, DOI, and PMID citations.
    assert report.total >= 3
    raw = " ".join(c.raw_text for c in report.citations)
    assert "Smith" in raw
    assert "10.1038/s41586-024-99999-9" in raw
    assert "12345678" in raw
