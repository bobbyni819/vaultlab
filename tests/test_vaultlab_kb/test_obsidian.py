"""Tests for vaultlab.kb.obsidian — vault scaffolding, plugin config,
templates, deep-link URLs, install detection.

All tests use tmp_path; nothing touches a real KB or launches Obsidian.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# init_vault
# ---------------------------------------------------------------------------


class TestInitVault:
    def test_creates_obsidian_dir(self, tmp_path: Path) -> None:
        from vaultlab.kb.obsidian import init_vault

        result = init_vault(tmp_path)
        assert result == tmp_path / ".obsidian"
        assert result.is_dir()

    def test_writes_core_config_files(self, tmp_path: Path) -> None:
        from vaultlab.kb.obsidian import init_vault

        init_vault(tmp_path)
        for fname in ("app.json", "appearance.json", "core-plugins.json", "workspace.json"):
            assert (tmp_path / ".obsidian" / fname).exists(), fname

    def test_uses_wikilinks_not_markdown_links(self, tmp_path: Path) -> None:
        from vaultlab.kb.obsidian import init_vault

        init_vault(tmp_path)
        app = json.loads((tmp_path / ".obsidian" / "app.json").read_text())
        assert app["useMarkdownLinks"] is False

    def test_workspace_opens_default_file(self, tmp_path: Path) -> None:
        from vaultlab.kb.obsidian import init_vault

        init_vault(tmp_path, default_open_file="START_HERE.md")
        ws = json.loads((tmp_path / ".obsidian" / "workspace.json").read_text())
        leaf = ws["main"]["children"][0]
        assert leaf["state"]["state"]["file"] == "START_HERE.md"

    def test_idempotent_does_not_overwrite(self, tmp_path: Path) -> None:
        from vaultlab.kb.obsidian import init_vault

        init_vault(tmp_path)
        # User edits app.json
        custom = {"showLineNumber": False, "custom_user_setting": True}
        (tmp_path / ".obsidian" / "app.json").write_text(json.dumps(custom))

        # Re-init: must NOT clobber
        init_vault(tmp_path)
        result = json.loads((tmp_path / ".obsidian" / "app.json").read_text())
        assert result == custom

    def test_raises_when_kb_path_missing(self, tmp_path: Path) -> None:
        from vaultlab.kb.obsidian import init_vault

        with pytest.raises(FileNotFoundError):
            init_vault(tmp_path / "does-not-exist")


# ---------------------------------------------------------------------------
# configure_plugins
# ---------------------------------------------------------------------------


class TestConfigurePlugins:
    def test_writes_three_recommended_plugins(self, tmp_path: Path) -> None:
        from vaultlab.kb.obsidian import RECOMMENDED_PLUGINS, configure_plugins, init_vault

        init_vault(tmp_path)
        target = configure_plugins(tmp_path)
        assert target == tmp_path / ".obsidian" / "community-plugins.json"

        plugins = json.loads(target.read_text())
        assert isinstance(plugins, list)
        assert len(plugins) == len(RECOMMENDED_PLUGINS)
        ids = [p.plugin_id for p in RECOMMENDED_PLUGINS]
        assert "obsidian-advanced-uri" in plugins
        assert plugins == ids  # order preserved

    def test_merges_with_existing_user_plugins(self, tmp_path: Path) -> None:
        from vaultlab.kb.obsidian import configure_plugins, init_vault

        init_vault(tmp_path)
        # User had their own plugins enabled before
        existing = ["my-custom-plugin", "another-plugin"]
        (tmp_path / ".obsidian" / "community-plugins.json").write_text(json.dumps(existing))

        configure_plugins(tmp_path)
        merged = json.loads((tmp_path / ".obsidian" / "community-plugins.json").read_text())
        assert "my-custom-plugin" in merged
        assert "another-plugin" in merged
        assert "obsidian-advanced-uri" in merged
        # No duplicates if re-run
        configure_plugins(tmp_path)
        merged2 = json.loads((tmp_path / ".obsidian" / "community-plugins.json").read_text())
        assert len(merged2) == len(merged)

    def test_raises_when_obsidian_dir_missing(self, tmp_path: Path) -> None:
        from vaultlab.kb.obsidian import configure_plugins

        with pytest.raises(FileNotFoundError):
            configure_plugins(tmp_path)

    def test_install_instructions_mentions_each_plugin(self) -> None:
        from vaultlab.kb.obsidian import RECOMMENDED_PLUGINS
        from vaultlab.kb.obsidian.plugins import install_instructions_markdown

        text = install_instructions_markdown()
        for plugin in RECOMMENDED_PLUGINS:
            assert plugin.display_name in text
            assert plugin.plugin_id in text


# ---------------------------------------------------------------------------
# write_templates
# ---------------------------------------------------------------------------


class TestWriteTemplates:
    def test_creates_template_files(self, tmp_path: Path) -> None:
        from vaultlab.kb.obsidian import write_templates

        target_dir = write_templates(tmp_path)
        assert target_dir == tmp_path / ".templates"
        files = {f.name for f in target_dir.iterdir()}
        assert "source-paper.md" in files
        assert "source-note.md" in files
        assert "wiki-concept.md" in files
        assert "project-start-here.md" in files
        assert "decisions-log.md" in files

    def test_does_not_overwrite_user_edited_template(self, tmp_path: Path) -> None:
        from vaultlab.kb.obsidian import write_templates

        write_templates(tmp_path)
        custom = "# my custom paper template\n\nedited by user"
        (tmp_path / ".templates" / "source-paper.md").write_text(custom)

        # Re-run: must not clobber
        write_templates(tmp_path)
        assert (tmp_path / ".templates" / "source-paper.md").read_text() == custom

    def test_writes_obsidian_templates_config_when_obsidian_dir_exists(
        self, tmp_path: Path
    ) -> None:
        from vaultlab.kb.obsidian import init_vault, write_templates

        init_vault(tmp_path)
        write_templates(tmp_path)
        cfg = tmp_path / ".obsidian" / "templates.json"
        assert cfg.exists()
        assert json.loads(cfg.read_text())["folder"] == ".templates"


# ---------------------------------------------------------------------------
# open_in_obsidian — URL construction (no actual launch)
# ---------------------------------------------------------------------------


class TestOpenInObsidian:
    def test_new_tab_uses_advanced_uri(self, tmp_path: Path) -> None:
        from vaultlab.kb.obsidian import open_in_obsidian

        captured: list[str] = []
        # File must exist for verify_exists to pass
        (tmp_path / "Sources").mkdir()
        (tmp_path / "Sources" / "Notes.md").write_text("# Notes")

        result = open_in_obsidian(
            "Sources/Notes",
            vault_root=tmp_path,
            vault_name="MyVault",
            new_tab=True,
            launcher=captured.append,
        )
        assert result.success
        assert "advanced-uri" in result.url
        assert "openmode=tab" in result.url
        assert "vault=MyVault" in result.url
        assert captured == [result.url]

    def test_current_pane_uses_native_scheme(self, tmp_path: Path) -> None:
        from vaultlab.kb.obsidian import open_in_obsidian

        (tmp_path / "x.md").write_text("# x")
        result = open_in_obsidian(
            "x", vault_root=tmp_path, vault_name="V", new_tab=False, launcher=lambda u: None
        )
        assert result.success
        assert "obsidian://open?" in result.url
        assert "advanced-uri" not in result.url

    def test_normalizes_md_suffix(self, tmp_path: Path) -> None:
        from vaultlab.kb.obsidian import open_in_obsidian

        (tmp_path / "x.md").write_text("# x")
        for variant in ("x", "x.md", "/x", "x\\"):
            result = open_in_obsidian(
                variant,
                vault_root=tmp_path,
                vault_name="V",
                launcher=lambda u: None,
            )
            assert result.success
            assert "filepath=x" in result.url, variant

    def test_returns_failure_if_file_missing(self, tmp_path: Path) -> None:
        from vaultlab.kb.obsidian import open_in_obsidian

        result = open_in_obsidian(
            "missing/path", vault_root=tmp_path, vault_name="V", launcher=lambda u: None
        )
        assert not result.success
        assert "not found" in result.message.lower()

    def test_skip_verify_for_unknown_vault(self) -> None:
        from vaultlab.kb.obsidian import open_in_obsidian

        result = open_in_obsidian(
            "any/path",
            vault_root=None,
            vault_name="V",
            verify_exists=False,
            launcher=lambda u: None,
        )
        assert result.success
        assert "filepath=any/path" in result.url


# ---------------------------------------------------------------------------
# detect_install — uses pure auto-detect; just check it returns something sane
# ---------------------------------------------------------------------------


class TestDetectInstall:
    def test_returns_obsidian_install_object(self) -> None:
        from vaultlab.kb.obsidian import ObsidianInstall, detect_install

        result = detect_install()
        assert isinstance(result, ObsidianInstall)
        # missing_recommended is always populated based on RECOMMENDED_PLUGINS
        assert isinstance(result.missing_recommended, list)

    def test_summarize_renders_human_readable(self) -> None:
        from vaultlab.kb.obsidian import ObsidianInstall
        from vaultlab.kb.obsidian.detect import summarize_install

        # Empty install — should render gracefully
        empty = ObsidianInstall()
        text = summarize_install(empty)
        assert "Obsidian install report" in text
        assert "❌" in text or "Not found" in text
