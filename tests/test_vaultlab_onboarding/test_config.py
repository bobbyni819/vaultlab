"""Tests for vaultlab.onboarding.config — .vaultlab-project.json schema."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from vaultlab.onboarding.config import (
    PROJECT_CONFIG_FILENAME,
    PROJECT_CONFIG_SCHEMA,
    VaultLabProjectConfig,
    load_config,
    load_project_config_from_cwd,
    save_config,
)


class TestSchema:
    def test_default_schema_constant(self) -> None:
        assert PROJECT_CONFIG_SCHEMA == "vaultlab-project/v1"

    def test_default_filename(self) -> None:
        assert PROJECT_CONFIG_FILENAME == ".vaultlab-project.json"

    def test_empty_config_has_schema_field(self) -> None:
        cfg = VaultLabProjectConfig()
        assert cfg.schema == PROJECT_CONFIG_SCHEMA

    def test_to_dict_includes_all_fields(self) -> None:
        cfg = VaultLabProjectConfig(slug="x", topic="y")
        d = cfg.to_dict()
        for key in (
            "slug",
            "topic",
            "goal",
            "audience",
            "kb_root",
            "data_dirs",
            "validation_files",
            "exclusions",
            "voice",
            "pi_preferences",
            "deadlines",
            "schema",
            "created",
            "last_updated",
        ):
            assert key in d, f"missing field {key}"


class TestRoundTrip:
    def test_save_then_load(self, tmp_path: Path) -> None:
        cfg = VaultLabProjectConfig(
            slug="codex-pdac-cn",
            topic="CODEX cellular neighborhoods in PDAC",
            goal=["understand_literature", "build_journal_club_deck"],
            audience=["pi"],
            kb_root="G:/My Drive/Knowledge/vaultlab",
            data_dirs=["Z:/lab/data/codex-pdac-2026-03/"],
            exclusions={"exclude_preprints": True, "min_year": 2015},
            voice={"styles": ["hedged"]},
            pi_preferences="author-year style",
            deadlines=["weekly"],
        )
        save_config(cfg, tmp_path)
        loaded = load_config(tmp_path)
        assert loaded is not None
        assert loaded.slug == "codex-pdac-cn"
        assert loaded.topic == cfg.topic
        assert loaded.goal == cfg.goal
        assert loaded.exclusions["exclude_preprints"] is True
        assert loaded.exclusions["min_year"] == 2015
        assert loaded.voice == {"styles": ["hedged"]}
        assert loaded.deadlines == ["weekly"]

    def test_load_missing_returns_none(self, tmp_path: Path) -> None:
        assert load_config(tmp_path) is None

    def test_save_creates_file(self, tmp_path: Path) -> None:
        cfg = VaultLabProjectConfig(slug="x")
        target = save_config(cfg, tmp_path)
        assert target.exists()
        assert target.name == PROJECT_CONFIG_FILENAME

    def test_save_writes_valid_json(self, tmp_path: Path) -> None:
        cfg = VaultLabProjectConfig(slug="x", topic="y")
        target = save_config(cfg, tmp_path)
        data = json.loads(target.read_text(encoding="utf-8"))
        assert data["slug"] == "x"
        assert data["topic"] == "y"
        assert data["schema"] == PROJECT_CONFIG_SCHEMA


class TestForwardCompat:
    def test_unknown_keys_dropped(self, tmp_path: Path) -> None:
        # Simulate a future-version config with extra keys
        future = {
            "slug": "x",
            "topic": "y",
            "future_field_we_dont_know": "ignore me",
            "schema": "vaultlab-project/v99",
        }
        target = tmp_path / PROJECT_CONFIG_FILENAME
        target.write_text(json.dumps(future), encoding="utf-8")
        loaded = load_config(tmp_path)
        assert loaded is not None
        assert loaded.slug == "x"

    def test_invalid_json_raises(self, tmp_path: Path) -> None:
        target = tmp_path / PROJECT_CONFIG_FILENAME
        target.write_text("not json {{{", encoding="utf-8")
        with pytest.raises(ValueError, match="Invalid JSON"):
            load_config(tmp_path)

    def test_non_object_json_raises(self, tmp_path: Path) -> None:
        target = tmp_path / PROJECT_CONFIG_FILENAME
        target.write_text("[]", encoding="utf-8")
        with pytest.raises(ValueError, match="JSON object"):
            load_config(tmp_path)


class TestUpdateTimestamp:
    def test_save_refreshes_last_updated(self, tmp_path: Path) -> None:
        cfg = VaultLabProjectConfig(slug="x", last_updated="2020-01-01")
        save_config(cfg, tmp_path)
        loaded = load_config(tmp_path)
        assert loaded is not None
        # last_updated should have been refreshed during save
        assert loaded.last_updated != "2020-01-01"


class TestLoadFromCwd:
    """F-1 regression: ``load_project_config_from_cwd`` walks up the tree.

    The slash command bodies for ``/lit-arc`` / ``/build-deck`` /
    ``/lit-report`` call this helper to recover slug + kb_root after
    ``/onboard-project`` has run, so users don't have to re-thread
    project context through every command. We keep the helper out of
    the orchestrators themselves (per Bobby's "explicit over magic"
    rule); these tests pin its behaviour at the seam.
    """

    def test_load_project_config_from_cwd_finds_in_parent(self, tmp_path: Path) -> None:
        """Helper walks up from a nested subdirectory to the project root."""
        cfg = VaultLabProjectConfig(
            slug="codex-test",
            topic="CODEX cellular neighborhoods",
            kb_root="G:/My Drive/Knowledge/vaultlab",
        )
        save_config(cfg, tmp_path)

        # Search starting from a deeply-nested subfolder must still find
        # the config at the project root.
        nested = tmp_path / "data" / "raw" / "2026-04"
        nested.mkdir(parents=True)

        loaded = load_project_config_from_cwd(start=nested)
        assert loaded is not None
        assert loaded.slug == "codex-test"
        assert loaded.topic == "CODEX cellular neighborhoods"
        assert loaded.kb_root == "G:/My Drive/Knowledge/vaultlab"

    def test_load_project_config_from_cwd_returns_none_when_absent(self, tmp_path: Path) -> None:
        """No config anywhere up the tree → None (not a raise)."""
        # tmp_path is an isolated dir below pytest's basetemp; pytest
        # fixtures guarantee no .vaultlab-project.json lives in it.
        empty = tmp_path / "scratch"
        empty.mkdir()
        assert load_project_config_from_cwd(start=empty) is None

    def test_load_project_config_from_cwd_accepts_file_path(self, tmp_path: Path) -> None:
        """Helper tolerates being pointed at a file (uses parent dir)."""
        cfg = VaultLabProjectConfig(slug="x", topic="t")
        save_config(cfg, tmp_path)
        # Pretend the user passed a file inside the project folder.
        sentinel = tmp_path / "scratchpad.txt"
        sentinel.write_text("hi", encoding="utf-8")

        loaded = load_project_config_from_cwd(start=sentinel)
        assert loaded is not None
        assert loaded.slug == "x"
