"""Tests for the new vaultlab CLI subcommands shipped with the
2026-05-02 paperclip integration.

Covers:
* ``vaultlab list-policy-skipped <project>``
* ``vaultlab fetch-list paywalled <log.json>``
* ``vaultlab paperclip-grep`` (subprocess passthrough)
* ``vaultlab paperclip-sql``  (subprocess passthrough)
"""

from __future__ import annotations

import io
import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from vaultlab.cli import main


# ---- list-policy-skipped -----------------------------------------------

def test_list_policy_skipped_no_log(tmp_path, capsys):
    """No log file → exit 0 with empty-state message."""
    rc = main(["list-policy-skipped", str(tmp_path)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "no policy-skipped papers" in out


def test_list_policy_skipped_prints_records(tmp_path, capsys):
    project = tmp_path / "proj"
    project.mkdir()
    (project / "policy_skipped.json").write_text(json.dumps([
        {
            "doi": "10.1/x",
            "reason": "AUP refusal",
            "batch": "B5-test",
            "skipped_at": "2026-05-02T12:00:00Z",
            "needs_human_review": True,
        }
    ]), encoding="utf-8")

    rc = main(["list-policy-skipped", str(project)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "10.1/x" in out
    assert "AUP refusal" in out
    assert "B5-test" in out


def test_list_policy_skipped_help(capsys):
    rc = main(["list-policy-skipped"])
    err = capsys.readouterr().err
    assert rc == 1
    assert "Usage:" in err


# ---- fetch-list paywalled ----------------------------------------------

def test_fetch_list_paywalled_no_args(capsys):
    rc = main(["fetch-list"])
    err = capsys.readouterr().err
    assert rc == 1
    assert "Usage:" in err


def test_fetch_list_paywalled_missing_file(capsys, tmp_path):
    fake = tmp_path / "nope.json"
    rc = main(["fetch-list", "paywalled", str(fake)])
    err = capsys.readouterr().err
    assert rc == 1
    assert "file not found" in err


def test_fetch_list_paywalled_empty_log(tmp_path, capsys):
    log = tmp_path / "log.json"
    log.write_text("{}", encoding="utf-8")
    rc = main(["fetch-list", "paywalled", str(log)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "no paywalled" in out


def test_fetch_list_paywalled_renders_shopping_list(tmp_path, capsys):
    log = tmp_path / "log.json"
    log.write_text(json.dumps({
        "10.1038/s41586-2024-x": {
            "outcome": "failed_paywalled",
            "title": "A Nature paper",
            "journal": "Nature",
            "year": 2024,
            "publisher_url": "https://doi.org/10.1038/s41586-2024-x",
            "tier_errors": {"elsevier": "403"},
        },
    }), encoding="utf-8")

    rc = main(["fetch-list", "paywalled", str(log)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "1 paywalled paper(s)" in out
    assert "A Nature paper" in out
    assert "10.1038/s41586-2024-x" in out
    assert "Nature" in out
    assert "2024" in out


def test_fetch_list_unknown_subcommand(capsys):
    rc = main(["fetch-list", "wrongthing"])
    err = capsys.readouterr().err
    assert rc == 1
    assert "Usage:" in err


# ---- paperclip-grep / paperclip-sql passthrough ------------------------

def test_paperclip_grep_help(capsys):
    rc = main(["paperclip-grep"])
    err = capsys.readouterr().err
    assert rc == 1
    assert "paperclip grep" in err


def test_paperclip_sql_help(capsys):
    rc = main(["paperclip-sql"])
    err = capsys.readouterr().err
    assert rc == 1
    assert "paperclip sql" in err


def test_paperclip_grep_calls_subprocess():
    with patch("subprocess.call", return_value=0) as mock_call:
        rc = main(["paperclip-grep", "alphafold", "/papers/"])
        assert rc == 0
        called_cmd = mock_call.call_args[0][0]
        assert called_cmd == ["paperclip", "grep", "alphafold", "/papers/"]


def test_paperclip_sql_calls_subprocess():
    with patch("subprocess.call", return_value=0) as mock_call:
        rc = main(["paperclip-sql", "SELECT title FROM documents LIMIT 1"])
        assert rc == 0
        called_cmd = mock_call.call_args[0][0]
        assert called_cmd[:2] == ["paperclip", "sql"]


def test_paperclip_grep_handles_missing_binary(capsys):
    """When paperclip CLI not installed, surface a helpful message."""
    with patch("subprocess.call",
               side_effect=FileNotFoundError("paperclip not found")):
        rc = main(["paperclip-grep", "x", "/papers/"])
        assert rc == 1
        err = capsys.readouterr().err
        assert "paperclip CLI not on PATH" in err
        assert "pip install" in err


# ---- main dispatcher ---------------------------------------------------

def test_main_help_lists_new_subcommands(capsys):
    rc = main(["--help"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "list-policy-skipped" in out
    assert "fetch-list paywalled" in out
    assert "paperclip-grep" in out
    assert "paperclip-sql" in out


def test_main_unknown_subcommand(capsys):
    rc = main(["nonexistent-command"])
    err = capsys.readouterr().err
    assert rc == 1
    assert "unknown command" in err
