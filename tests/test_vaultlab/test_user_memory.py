"""Tests for vaultlab.context.user_memory — per-user auto-memory."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def mem_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point VAULTLAB_USER_MEMORY at tmp_path for isolation."""
    target = tmp_path / "user_memory"
    monkeypatch.setenv("VAULTLAB_USER_MEMORY", str(target))
    return target


class TestRemember:
    def test_writes_entry_with_frontmatter(self, mem_root: Path) -> None:
        from vaultlab.context.user_memory import remember

        path = remember(
            category="feedback",
            name="hedged-voice",
            description="Always hedge LLM-generated interpretations.",
            content="Use 'consistent with X' not 'is X'.",
        )
        assert path.exists()
        assert path.name == "feedback_hedged-voice.md"
        text = path.read_text(encoding="utf-8")
        assert text.startswith("---\n")
        assert "type: feedback" in text
        assert "name: hedged-voice" in text
        assert "consistent with X" in text

    def test_index_updated(self, mem_root: Path) -> None:
        from vaultlab.context.user_memory import INDEX_FILENAME, remember

        remember(
            category="feedback",
            name="hedged-voice",
            description="Always hedge.",
            content="body",
        )
        remember(
            category="preference",
            name="terse-output",
            description="Bobby wants concise responses.",
            content="No preambles.",
        )

        index = (mem_root / INDEX_FILENAME).read_text()
        assert "## Feedback" in index
        assert "## Preference" in index
        assert "hedged-voice" in index
        assert "terse-output" in index
        assert "Always hedge." in index

    def test_re_remember_overwrites(self, mem_root: Path) -> None:
        from vaultlab.context.user_memory import recall, remember

        remember(category="feedback", name="x", description="first", content="A")
        remember(category="feedback", name="x", description="second", content="B")

        entry = recall("feedback", "x")
        assert entry is not None
        assert entry.description == "second"
        assert "B" in entry.content
        assert "A" not in entry.content

    def test_invalid_category_raises(self, mem_root: Path) -> None:
        from vaultlab.context.user_memory import remember

        with pytest.raises(ValueError, match="category must be"):
            remember(
                category="bogus",  # type: ignore[arg-type]
                name="x",
                description="x",
                content="x",
            )

    def test_invalid_name_raises(self, mem_root: Path) -> None:
        from vaultlab.context.user_memory import remember

        with pytest.raises(ValueError, match="kebab-case"):
            remember(category="feedback", name="Has Spaces", description="x", content="y")

    def test_long_description_raises(self, mem_root: Path) -> None:
        from vaultlab.context.user_memory import remember

        with pytest.raises(ValueError, match="≤200 chars"):
            remember(
                category="feedback",
                name="x",
                description="y" * 250,
                content="z",
            )


class TestRecall:
    def test_recalls_existing(self, mem_root: Path) -> None:
        from vaultlab.context.user_memory import recall, remember

        remember(
            category="pattern",
            name="dogfood-kb-feedback",
            description="Use kb.feedback.log_decision when locking design choices.",
            content="Especially for runner / config / invariant decisions.",
        )

        entry = recall("pattern", "dogfood-kb-feedback")
        assert entry is not None
        assert entry.category == "pattern"
        assert entry.name == "dogfood-kb-feedback"
        assert "kb.feedback.log_decision" in entry.description

    def test_returns_none_for_missing(self, mem_root: Path) -> None:
        from vaultlab.context.user_memory import recall

        assert recall("feedback", "does-not-exist") is None


class TestRecallAll:
    def test_returns_index_and_entries(self, mem_root: Path) -> None:
        from vaultlab.context.user_memory import recall_all, remember

        remember(category="feedback", name="a", description="alpha", content="A")
        remember(category="preference", name="b", description="beta", content="B")

        index_text, entries = recall_all()
        assert "VaultLab — User Memory Index" in index_text
        names = [e.name for e in entries]
        assert "a" in names
        assert "b" in names

    def test_empty_root_returns_empty(self, mem_root: Path) -> None:
        from vaultlab.context.user_memory import recall_all

        index_text, entries = recall_all()
        assert index_text == ""
        assert entries == []


class TestForget:
    def test_removes_entry(self, mem_root: Path) -> None:
        from vaultlab.context.user_memory import forget, recall, remember

        remember(category="feedback", name="temp", description="x", content="y")
        assert recall("feedback", "temp") is not None

        assert forget("feedback", "temp") is True
        assert recall("feedback", "temp") is None

    def test_returns_false_when_missing(self, mem_root: Path) -> None:
        from vaultlab.context.user_memory import forget

        assert forget("feedback", "never-existed") is False


class TestEnvOverride:
    def test_env_var_overrides_default(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from vaultlab.context.user_memory import memory_root

        custom = tmp_path / "custom-memory"
        monkeypatch.setenv("VAULTLAB_USER_MEMORY", str(custom))
        assert memory_root() == custom

    def test_default_path_uses_home_config(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from vaultlab.context.user_memory import memory_root

        monkeypatch.delenv("VAULTLAB_USER_MEMORY", raising=False)
        result = memory_root()
        assert result.parts[-3:] == (".config", "vaultlab", "user_memory")
