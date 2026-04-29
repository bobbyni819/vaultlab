"""Tests for vaultlab.context.locations — per-user locations registry."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def loc_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point VAULTLAB_LOCATIONS at a tmp_path file for isolation."""
    target = tmp_path / "locations.toml"
    monkeypatch.setenv("VAULTLAB_LOCATIONS", str(target))
    return target


class TestLoad:
    def test_load_returns_empty_when_missing(self, loc_file: Path) -> None:
        from vaultlab.context.locations import load_locations

        assert load_locations() == {}

    def test_load_parses_existing_toml(self, loc_file: Path) -> None:
        from vaultlab.context.locations import load_locations

        loc_file.write_text('[work_log]\ngoogle_doc_id = "abc123"\ndefault_tab = "daily updates"\n')
        result = load_locations()
        assert result == {"work_log": {"google_doc_id": "abc123", "default_tab": "daily updates"}}


class TestGetPath:
    def test_returns_value_for_dotted_slug(self) -> None:
        from vaultlab.context.locations import get_path

        locations = {"work_log": {"google_doc_id": "abc"}}
        assert get_path("work_log.google_doc_id", locations=locations) == "abc"

    def test_returns_none_for_missing_section(self) -> None:
        from vaultlab.context.locations import get_path

        assert get_path("missing.key", locations={}) is None

    def test_returns_none_for_missing_key(self) -> None:
        from vaultlab.context.locations import get_path

        assert get_path("work_log.unknown", locations={"work_log": {}}) is None

    def test_supports_dashes_in_slug(self) -> None:
        from vaultlab.context.locations import get_path

        locations = {"projects": {"car-t": "research/Wiki/Projects/car-t"}}
        assert get_path("projects.car-t", locations=locations) == "research/Wiki/Projects/car-t"

    def test_returns_none_for_non_string_value(self) -> None:
        from vaultlab.context.locations import get_path

        # If something nested is a dict, get_path returns None — caller wanted a leaf
        locations = {"work_log": {"nested": {"deeper": "x"}}}
        assert get_path("work_log.nested", locations=locations) is None


class TestRegisterPath:
    def test_writes_new_file(self, loc_file: Path) -> None:
        from vaultlab.context.locations import register_path

        target = register_path("work_log.google_doc_id", "abc123")
        assert target == loc_file
        assert loc_file.exists()
        text = loc_file.read_text()
        assert "[work_log]" in text
        assert 'google_doc_id = "abc123"' in text

    def test_updates_existing_section(self, loc_file: Path) -> None:
        from vaultlab.context.locations import get_path, load_locations, register_path

        register_path("work_log.google_doc_id", "old")
        register_path("work_log.google_doc_id", "new")
        register_path("work_log.default_tab", "daily updates")

        locations = load_locations()
        assert get_path("work_log.google_doc_id", locations=locations) == "new"
        assert get_path("work_log.default_tab", locations=locations) == "daily updates"

    def test_supports_dashes_in_keys(self, loc_file: Path) -> None:
        from vaultlab.context.locations import get_path, load_locations, register_path

        register_path("projects.car-t", "research/Wiki/Projects/car-t")
        text = loc_file.read_text()
        assert '"car-t" = ' in text  # dashed key gets quoted
        locations = load_locations()
        assert get_path("projects.car-t", locations=locations) == "research/Wiki/Projects/car-t"

    def test_creates_parent_dir(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        from vaultlab.context.locations import register_path

        deep = tmp_path / "a" / "b" / "c" / "locations.toml"
        monkeypatch.setenv("VAULTLAB_LOCATIONS", str(deep))
        register_path("k.v", "x")
        assert deep.exists()

    def test_rejects_top_level_key(self, loc_file: Path) -> None:
        from vaultlab.context.locations import register_path

        # Schema requires section.key, not bare key
        with pytest.raises(ValueError, match="section.key"):
            register_path("flat", "value")

    def test_handles_paths_with_backslashes(self, loc_file: Path) -> None:
        from vaultlab.context.locations import get_path, load_locations, register_path

        # Windows-style path
        register_path("meetings.local_video_dir", "D:\\Meetings\\Videos\\")
        result = get_path("meetings.local_video_dir", locations=load_locations())
        assert result == "D:\\Meetings\\Videos\\"


class TestMissingPathsGrillDoc:
    def test_writes_grill_doc(self, tmp_path: Path) -> None:
        from vaultlab.context.locations import missing_paths_grill_doc

        result = missing_paths_grill_doc(
            tmp_path,
            ["work_log.google_doc_id", "meetings.transcript_drive_path"],
            triggered_by="/log-meeting",
            auto_open=False,
        )
        assert result is not None
        assert result.exists()
        body = result.read_text()
        assert "work_log.google_doc_id" in body
        assert "meetings.transcript_drive_path" in body
        assert "/log-meeting" in body

    def test_returns_none_when_nothing_missing(self, tmp_path: Path) -> None:
        from vaultlab.context.locations import missing_paths_grill_doc

        result = missing_paths_grill_doc(tmp_path, [], triggered_by="/x", auto_open=False)
        assert result is None


class TestEnvOverride:
    def test_env_var_overrides_default_path(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from vaultlab.context.locations import locations_path

        custom = tmp_path / "custom.toml"
        monkeypatch.setenv("VAULTLAB_LOCATIONS", str(custom))
        assert locations_path() == custom

    def test_default_path_uses_home_config(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from vaultlab.context.locations import locations_path

        monkeypatch.delenv("VAULTLAB_LOCATIONS", raising=False)
        result = locations_path()
        assert result.parts[-3:] == (".config", "vaultlab", "locations.toml")
