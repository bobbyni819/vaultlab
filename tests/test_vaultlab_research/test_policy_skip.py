"""Tests for the policy_skip + fetch_list_paywalled module.

Covers the skip-on-refusal pattern and the manual-fetch shopping
list generation that paired commits land together.
"""

from __future__ import annotations

import json
from pathlib import Path

from vaultlab.research.policy_skip import (
    fetch_list_paywalled,
    is_policy_refusal_error,
    is_skipped,
    list_skipped,
    mark_skipped,
)

# ---- is_policy_refusal_error -------------------------------------------


def test_detects_aup_refusal():
    msg = (
        "API Error: Claude Code is unable to respond to this request, "
        "which appears to violate our Usage Policy "
        "(https://www.anthropic.com/legal/aup)."
    )
    assert is_policy_refusal_error(msg)


def test_detects_aup_url():
    assert is_policy_refusal_error("see https://www.anthropic.com/legal/aup")


def test_does_not_match_internal_server_error():
    """Internal-server-error 500s have many causes; don't auto-classify."""
    assert not is_policy_refusal_error("API Error: Internal server error")


def test_handles_none_and_empty():
    assert not is_policy_refusal_error(None)
    assert not is_policy_refusal_error("")


def test_case_insensitive():
    assert is_policy_refusal_error("VIOLATE OUR USAGE POLICY")


# ---- mark_skipped + list_skipped + is_skipped --------------------------


def test_mark_skipped_writes_log(tmp_path: Path):
    project = tmp_path / "proj"
    mark_skipped(
        "10.1/test",
        project_dir=project,
        reason="AUP refusal",
        batch="B5-test",
    )
    log_path = project / "policy_skipped.json"
    assert log_path.exists()
    entries = json.loads(log_path.read_text(encoding="utf-8"))
    assert len(entries) == 1
    assert entries[0]["doi"] == "10.1/test"
    assert entries[0]["batch"] == "B5-test"
    assert entries[0]["needs_human_review"] is True


def test_mark_skipped_appends_distinct_dois(tmp_path: Path):
    project = tmp_path / "proj"
    mark_skipped("10.1/a", project_dir=project)
    mark_skipped("10.1/b", project_dir=project)
    entries = list_skipped(project)
    dois = {e["doi"] for e in entries}
    assert dois == {"10.1/a", "10.1/b"}


def test_mark_skipped_dedupes_repeated_doi(tmp_path: Path):
    project = tmp_path / "proj"
    mark_skipped("10.1/a", project_dir=project, reason="first")
    mark_skipped("10.1/a", project_dir=project, reason="second")
    entries = list_skipped(project)
    assert len(entries) == 1
    # Keeps first record (additive)
    assert entries[0]["reason"] == "first"


def test_mark_skipped_writes_stub_summary(tmp_path: Path):
    project = tmp_path / "proj"
    summaries = tmp_path / "summaries"
    mark_skipped(
        "10.1/X",
        project_dir=project,
        summaries_dir=summaries,
        reason="AUP test",
    )
    stub = summaries / "10.1_x.md"
    assert stub.exists()
    text = stub.read_text(encoding="utf-8")
    assert "tier: skipped_policy" in text
    assert "needs_human_review: true" in text


def test_mark_skipped_does_not_overwrite_existing_summary(tmp_path: Path):
    project = tmp_path / "proj"
    summaries = tmp_path / "summaries"
    summaries.mkdir()
    stub = summaries / "10.1_x.md"
    stub.write_text("ORIGINAL CONTENT", encoding="utf-8")
    mark_skipped(
        "10.1/X",
        project_dir=project,
        summaries_dir=summaries,
    )
    # Original file untouched
    assert stub.read_text(encoding="utf-8") == "ORIGINAL CONTENT"


def test_is_skipped_round_trip(tmp_path: Path):
    project = tmp_path / "proj"
    mark_skipped("10.1/X", project_dir=project)
    assert is_skipped("10.1/X", project)
    assert is_skipped("10.1/x", project)  # case-insensitive
    assert not is_skipped("10.1/y", project)


def test_list_skipped_empty_when_no_log(tmp_path: Path):
    project = tmp_path / "proj"
    assert list_skipped(project) == []


def test_list_skipped_corrupted_json_returns_empty(tmp_path: Path):
    project = tmp_path / "proj"
    project.mkdir()
    (project / "policy_skipped.json").write_text("not valid json", encoding="utf-8")
    assert list_skipped(project) == []


# ---- fetch_list_paywalled ----------------------------------------------


def test_fetch_list_filters_failed_paywalled():
    log = {
        "10.1/oa": {"outcome": "oa_pdf"},
        "10.1/cache": {"outcome": "cache_hit"},
        "10.1/paywall": {
            "outcome": "failed_paywalled",
            "title": "Paywalled paper",
            "journal": "Nature",
            "year": 2024,
            "publisher_url": "https://doi.org/10.1/paywall",
            "tier_errors": {"elsevier": "403"},
        },
        "10.1/notindex": {"outcome": "failed_not_indexed"},
    }
    out = fetch_list_paywalled(log)
    assert len(out) == 1
    assert out[0]["doi"] == "10.1/paywall"
    assert "401/403" in out[0]["why_paywalled"] or "403" in out[0]["why_paywalled"]


def test_fetch_list_groups_by_publisher_cluster():
    """Sort order: Nature → Cell → Science → Wiley → Springer → other Elsevier → other."""
    log = {
        "10.1126/science.x": {  # Science
            "outcome": "failed_paywalled",
            "journal": "Science",
            "tier_errors": {"elsevier": "403"},
        },
        "10.1038/nature.x": {  # Nature
            "outcome": "failed_paywalled",
            "journal": "Nature",
            "tier_errors": {"elsevier": "403"},
        },
        "10.1016/j.cell.x": {  # Cell (Cell Press)
            "outcome": "failed_paywalled",
            "journal": "Cell",
            "tier_errors": {"elsevier": "403"},
        },
    }
    out = fetch_list_paywalled(log)
    journals = [e["journal"] for e in out]
    assert journals == ["Nature", "Cell", "Science"]


def test_fetch_list_handles_legacy_log_without_outcome():
    """Records without outcome field still get classified via tier_errors."""
    log = {
        "10.1/legacy": {
            "source": "failed",
            "tier_errors": {"elsevier": "401 Unauthorized"},
            "title": "Legacy paywalled",
        },
    }
    out = fetch_list_paywalled(log)
    assert len(out) == 1
    assert out[0]["doi"] == "10.1/legacy"


def test_fetch_list_skips_key_missing_legacy():
    """'key missing' in legacy logs is not a paywall signal."""
    log = {
        "10.1/missingkey": {
            "source": "failed",
            "tier_errors": {"elsevier": "key missing"},
        },
    }
    assert fetch_list_paywalled(log) == []


def test_fetch_list_reads_from_path(tmp_path: Path):
    log = {
        "10.1/x": {
            "outcome": "failed_paywalled",
            "tier_errors": {"elsevier": "403"},
            "title": "X",
        },
    }
    log_path = tmp_path / "acquisition.json"
    log_path.write_text(json.dumps(log), encoding="utf-8")
    out = fetch_list_paywalled(log_path)
    assert len(out) == 1


def test_fetch_list_invalid_input_returns_empty():
    assert fetch_list_paywalled({"not": "structured"}) == []
    assert fetch_list_paywalled(Path("/nonexistent/path.json")) == []
