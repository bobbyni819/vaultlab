"""Tests for vaultlab.kb.feedback — async-first feedback channels.

All file writes happen under tmp_path. open_question's auto-open path is
exercised via the launcher hook so no real Obsidian launches.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# open_question
# ---------------------------------------------------------------------------


class TestOpenQuestion:
    def test_writes_grill_doc_with_expected_filename(self, tmp_path: Path) -> None:
        from vaultlab.kb.feedback import open_question

        result = open_question(
            tmp_path,
            slug="figure-granularity",
            title="Figure understanding — granularity",
            questions=["Per-cell-type group, or per-instance?"],
            auto_open=False,
        )
        assert result.path.name.startswith("grill-figure-granularity-")
        assert result.path.name.endswith(".md")
        assert result.path.parent == tmp_path / "Sources" / "Notes"
        assert result.n_questions == 1

    def test_creates_notes_dir_if_missing(self, tmp_path: Path) -> None:
        from vaultlab.kb.feedback import open_question

        # tmp_path has no Sources/Notes yet
        open_question(
            tmp_path,
            slug="x",
            title="X",
            questions=["one?"],
            auto_open=False,
        )
        assert (tmp_path / "Sources" / "Notes").is_dir()

    def test_renders_numbered_questions(self, tmp_path: Path) -> None:
        from vaultlab.kb.feedback import open_question

        result = open_question(
            tmp_path,
            slug="multi",
            title="Multi-question",
            questions=["First?", "Second?", "Third?"],
            auto_open=False,
        )
        body = result.path.read_text(encoding="utf-8")
        assert "### Q1." in body
        assert "### Q2." in body
        assert "### Q3." in body
        # Order preserved
        assert body.index("First?") < body.index("Second?") < body.index("Third?")

    def test_includes_context_section_when_provided(self, tmp_path: Path) -> None:
        from vaultlab.kb.feedback import open_question

        result = open_question(
            tmp_path,
            slug="ctx",
            title="With context",
            questions=["q?"],
            context="This came up while building phase 1.",
            auto_open=False,
        )
        body = result.path.read_text(encoding="utf-8")
        assert "## Context" in body
        assert "phase 1" in body

    def test_no_context_section_when_omitted(self, tmp_path: Path) -> None:
        from vaultlab.kb.feedback import open_question

        result = open_question(
            tmp_path,
            slug="noctx",
            title="No ctx",
            questions=["q?"],
            auto_open=False,
        )
        body = result.path.read_text(encoding="utf-8")
        assert "## Context" not in body

    def test_frontmatter_includes_metadata(self, tmp_path: Path) -> None:
        from vaultlab.kb.feedback import open_question

        result = open_question(
            tmp_path, slug="meta", title="Meta", questions=["q?"], auto_open=False
        )
        body = result.path.read_text(encoding="utf-8")
        assert body.startswith("---\n")
        assert "type: grill" in body
        assert "slug: meta" in body
        assert "managed_by: vaultlab.kb.feedback.open_question" in body

    def test_auto_open_calls_launcher(self, tmp_path: Path) -> None:
        from vaultlab.kb.feedback import open_question

        captured: list[str] = []
        open_question(
            tmp_path,
            slug="launch",
            title="Launch test",
            questions=["q?"],
            auto_open=True,
            launcher=captured.append,
        )
        # If auto-open succeeded the launcher got the URL
        assert any("advanced-uri" in u for u in captured)

    def test_empty_questions_raises(self, tmp_path: Path) -> None:
        from vaultlab.kb.feedback import open_question

        with pytest.raises(ValueError, match="at least one"):
            open_question(tmp_path, slug="x", title="X", questions=[], auto_open=False)

    def test_missing_kb_path_raises(self, tmp_path: Path) -> None:
        from vaultlab.kb.feedback import open_question

        with pytest.raises(FileNotFoundError):
            open_question(
                tmp_path / "missing",
                slug="x",
                title="X",
                questions=["q?"],
                auto_open=False,
            )


# ---------------------------------------------------------------------------
# log_decision
# ---------------------------------------------------------------------------


class TestLogDecision:
    def test_creates_decisions_log_when_missing(self, tmp_path: Path) -> None:
        from vaultlab.kb.feedback import log_decision

        target = log_decision(
            tmp_path,
            project_slug="vaultlab",
            decision="Cap fan-out at 6",
            why="Default per Q3.",
        )
        assert target == tmp_path / "Wiki" / "Projects" / "vaultlab" / "decisions-log.md"
        assert target.exists()
        body = target.read_text(encoding="utf-8")
        assert "Cap fan-out at 6" in body
        assert "Default per Q3." in body
        assert "## Entries" in body

    def test_appends_new_entry_at_top(self, tmp_path: Path) -> None:
        from vaultlab.kb.feedback import log_decision

        log_decision(tmp_path, "vaultlab", "Older decision", "old why")
        log_decision(tmp_path, "vaultlab", "Newer decision", "new why")

        body = (tmp_path / "Wiki" / "Projects" / "vaultlab" / "decisions-log.md").read_text(
            encoding="utf-8"
        )
        # Newer should appear before older (reverse chronological)
        assert body.index("Newer decision") < body.index("Older decision")

    def test_tags_rendered_in_block(self, tmp_path: Path) -> None:
        from vaultlab.kb.feedback import log_decision

        log_decision(tmp_path, "vaultlab", "Decision X", "why X", tags=["scope", "config"])
        body = (tmp_path / "Wiki" / "Projects" / "vaultlab" / "decisions-log.md").read_text(
            encoding="utf-8"
        )
        assert "scope" in body
        assert "config" in body

    def test_creates_project_dir_if_missing(self, tmp_path: Path) -> None:
        from vaultlab.kb.feedback import log_decision

        log_decision(tmp_path, "newproj", "first decision", "first why")
        assert (tmp_path / "Wiki" / "Projects" / "newproj").is_dir()


# ---------------------------------------------------------------------------
# unread_docs_summary
# ---------------------------------------------------------------------------


class TestUnreadDocsSummary:
    def test_returns_recent_grill_docs(self, tmp_path: Path) -> None:
        from vaultlab.kb.feedback import open_question, unread_docs_summary

        open_question(tmp_path, "recent", "Recent", ["q?"], auto_open=False)
        result = unread_docs_summary(tmp_path)
        assert len(result) == 1
        assert result[0].name.startswith("grill-recent-")

    def test_includes_decisions_log_and_start_here(self, tmp_path: Path) -> None:
        from vaultlab.kb.feedback import log_decision, unread_docs_summary

        log_decision(tmp_path, "vaultlab", "decision", "why")
        # And a START_HERE
        proj_dir = tmp_path / "Wiki" / "Projects" / "vaultlab"
        proj_dir.mkdir(parents=True, exist_ok=True)
        (proj_dir / "START_HERE.md").write_text("# Start here")

        result = unread_docs_summary(tmp_path)
        names = {p.name for p in result}
        assert "decisions-log.md" in names
        assert "START_HERE.md" in names

    def test_filters_by_since_threshold(self, tmp_path: Path) -> None:
        from vaultlab.kb.feedback import open_question, unread_docs_summary

        open_question(tmp_path, "old", "Old", ["q?"], auto_open=False)
        # Set since to 1 minute in the future — nothing should match
        future = datetime.now(UTC) + timedelta(minutes=1)
        result = unread_docs_summary(tmp_path, since=future)
        assert result == []

    def test_returns_empty_when_kb_missing(self, tmp_path: Path) -> None:
        from vaultlab.kb.feedback import unread_docs_summary

        result = unread_docs_summary(tmp_path / "missing")
        assert result == []

    def test_sorted_by_mtime_oldest_first(self, tmp_path: Path) -> None:
        import time

        from vaultlab.kb.feedback import open_question, unread_docs_summary

        open_question(tmp_path, "first", "First", ["q?"], auto_open=False)
        time.sleep(0.05)
        open_question(tmp_path, "second", "Second", ["q?"], auto_open=False)

        result = unread_docs_summary(tmp_path)
        assert len(result) == 2
        # Oldest first
        assert "first" in result[0].name
        assert "second" in result[1].name


# ---------------------------------------------------------------------------
# Filename pattern (date in filename)
# ---------------------------------------------------------------------------


class TestFilenamePattern:
    def test_filename_contains_iso_date(self, tmp_path: Path) -> None:
        from vaultlab.kb.feedback import open_question

        result = open_question(tmp_path, "x", "X", ["q?"], auto_open=False)
        # YYYY-MM-DD pattern
        assert re.search(r"grill-x-\d{4}-\d{2}-\d{2}\.md$", result.path.name)
