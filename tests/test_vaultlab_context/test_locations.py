"""Tests for the multi-tenant KB-root resolver.

Specifically covers ``vaultlab.context.locations.resolve_kb_root`` and the
``KbRootNotConfigured`` exception, both added 2026-04-30 to unblock
"someone-other-than-Bobby pip-installs vaultlab" (Layer A in
``Sources/Notes/grill-multi-tenant-routing-2026-04-30.md``).

The resolver chain under test:

    1. explicit arg (skipped here — covered by the function signature)
    2. ``$VAULTLAB_KB_ROOT`` env var
    3. ``~/.config/vaultlab/locations.toml`` ``[paths] kb_root``
    4. ``~/.config/bobby_kb/config.json`` (compat fallback)
    5. interactive first-run prompt → persist to vaultlab config
    6. non-interactive + nothing resolved → ``KbRootNotConfigured``

Each test isolates the resolver from the user's real machine by:

- pointing ``$VAULTLAB_LOCATIONS`` at a tmp file (so vaultlab config writes
  do not touch ``~/.config/vaultlab/locations.toml``);
- monkey-patching ``Path.home()`` for the bobby_kb-config tests so we can
  drop a fake ``~/.config/bobby_kb/config.json`` in tmp_path;
- forcing ``interactive=False`` (or providing a stub ``input_fn``) so no
  test ever blocks on real stdin.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest


@pytest.fixture
def isolated_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Repoint vaultlab + bobby_kb config locations into ``tmp_path``.

    Returns the tmp_path itself so individual tests can drop their own
    config files where they need them.
    """
    # Vaultlab's locations.toml — the resolver respects $VAULTLAB_LOCATIONS
    monkeypatch.setenv("VAULTLAB_LOCATIONS", str(tmp_path / "locations.toml"))
    # Make sure no env override leaks in from the user's shell
    monkeypatch.delenv("VAULTLAB_KB_ROOT", raising=False)

    # Pretend $HOME is tmp_path so bobby_kb's compat fallback reads a
    # tmp config (or no config) instead of the real one on disk.
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: fake_home))
    return tmp_path


def _write_bobby_kb_config(home: Path, root: str, default_kb: str | None = None) -> Path:
    """Helper: drop a bobby_kb-style config.json under fake $HOME."""
    cfg_dir = home / ".config" / "bobby_kb"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    cfg_path = cfg_dir / "config.json"
    payload: dict[str, object] = {"root": root}
    if default_kb is not None:
        payload["default_kb"] = default_kb
    cfg_path.write_text(json.dumps(payload), encoding="utf-8")
    return cfg_path


def _write_vaultlab_locations(toml_path: Path, kb_root: str) -> None:
    """Helper: drop a vaultlab-style locations.toml at the configured path.

    Routes through ``register_path`` so backslashes in Windows paths are
    escaped correctly (raw f-string formatting would emit invalid TOML).
    """
    toml_path.parent.mkdir(parents=True, exist_ok=True)
    from vaultlab.context.locations import register_path

    register_path("paths.kb_root", kb_root, path=toml_path)


# ---------------------------------------------------------------------------
# Resolution chain — happy paths
# ---------------------------------------------------------------------------


class TestResolveKbRoot:
    def test_resolve_kb_root_env_var_wins(
        self,
        isolated_env: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Env var beats every other source (precedence #2)."""
        from vaultlab.context.locations import resolve_kb_root

        # Set a vaultlab config too — env var should still win.
        _write_vaultlab_locations(isolated_env / "locations.toml", str(isolated_env / "from-toml"))
        monkeypatch.setenv("VAULTLAB_KB_ROOT", str(isolated_env / "from-env"))

        result = resolve_kb_root(interactive=False)
        assert result == isolated_env / "from-env"

    def test_resolve_kb_root_vaultlab_config_used(self, isolated_env: Path) -> None:
        """Vaultlab config beats bobby_kb compat (precedence #3 vs #4)."""
        from vaultlab.context.locations import resolve_kb_root

        _write_vaultlab_locations(
            isolated_env / "locations.toml", str(isolated_env / "from-toml")
        )
        # Also drop a bobby_kb config — vaultlab's should still win.
        _write_bobby_kb_config(
            isolated_env / "home", root=str(isolated_env / "from-bobby_kb")
        )

        result = resolve_kb_root(interactive=False)
        assert result == isolated_env / "from-toml"

    def test_resolve_kb_root_bobby_kb_fallback(self, isolated_env: Path) -> None:
        """Bobby's existing setup must keep working invisibly.

        With NO env var, NO vaultlab locations.toml, but a bobby_kb
        config.json present, the resolver returns the bobby_kb path
        (joined with ``default_kb`` when set — mirrors how Bobby's
        machine actually points at ``G:/My Drive/Knowledge/vaultlab``).
        """
        from vaultlab.context.locations import resolve_kb_root

        _write_bobby_kb_config(
            isolated_env / "home",
            root=str(isolated_env / "kb-parent"),
            default_kb="vaultlab",
        )

        result = resolve_kb_root(interactive=False)
        assert result == isolated_env / "kb-parent" / "vaultlab"

    def test_resolve_kb_root_bobby_kb_root_only_no_default_kb(
        self, isolated_env: Path
    ) -> None:
        """When bobby_kb config has root but no default_kb, return root as-is."""
        from vaultlab.context.locations import resolve_kb_root

        _write_bobby_kb_config(isolated_env / "home", root=str(isolated_env / "just-root"))

        result = resolve_kb_root(interactive=False)
        assert result == isolated_env / "just-root"

    def test_resolve_kb_root_bobby_kb_compat_does_not_require_package(
        self, isolated_env: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The compat bridge reads JSON directly and must not import bobby_kb.

        Public users won't have ``bobby_kb`` installed; the bridge has to
        survive on stdlib only. We assert by hiding ``bobby_kb`` from the
        importer for the duration of the test and confirming the resolver
        still works.
        """
        import sys

        # Defensive — make sure any cached import is invisible.
        monkeypatch.setitem(sys.modules, "bobby_kb", None)

        from vaultlab.context.locations import resolve_kb_root

        _write_bobby_kb_config(
            isolated_env / "home", root=str(isolated_env / "no-import-needed")
        )
        result = resolve_kb_root(interactive=False)
        assert result == isolated_env / "no-import-needed"


# ---------------------------------------------------------------------------
# First-run prompt — interactive
# ---------------------------------------------------------------------------


class TestResolveKbRootFirstRunPrompt:
    def test_first_run_prompt_when_interactive(
        self, isolated_env: Path
    ) -> None:
        """All sources absent + interactive → prompt + return user's choice."""
        from vaultlab.context.locations import resolve_kb_root

        chosen = isolated_env / "user-pick"
        captured: list[str] = []

        def fake_input(prompt: str) -> str:
            captured.append(prompt)
            return str(chosen)

        result = resolve_kb_root(
            interactive=True, input_fn=fake_input, persist_first_run=False
        )
        assert result == chosen
        assert len(captured) == 1
        # The prompt should mention the suggested default for clarity.
        assert "vaultlab-kb" in captured[0]

    def test_first_run_default_is_home_vaultlab_kb(
        self, isolated_env: Path
    ) -> None:
        """Bare Enter at the prompt accepts the namespaced default."""
        from vaultlab.context.locations import resolve_kb_root

        result = resolve_kb_root(
            interactive=True,
            input_fn=lambda _prompt: "",  # accept default
            persist_first_run=False,
        )
        # Default is ``$HOME/vaultlab-kb`` (and $HOME is the tmp fake home)
        assert result == isolated_env / "home" / "vaultlab-kb"

    def test_first_run_persists_choice(self, isolated_env: Path) -> None:
        """Successful first-run prompt writes the choice back to locations.toml.

        After persistence, a *second* call (no input_fn) must hit the
        config branch and return the same value without prompting.
        """
        from vaultlab.context.locations import resolve_kb_root

        chosen = isolated_env / "persisted"
        result1 = resolve_kb_root(
            interactive=True,
            input_fn=lambda _prompt: str(chosen),
            persist_first_run=True,
        )
        assert result1 == chosen

        # The file should now exist with the expected entry.
        toml_text = (isolated_env / "locations.toml").read_text(encoding="utf-8")
        assert "[paths]" in toml_text
        assert str(chosen).replace("\\", "\\\\") in toml_text

        # Second call — no prompt should fire (we'd raise if it did).
        def explode(_prompt: str) -> str:  # pragma: no cover — must not run
            raise AssertionError("prompt should not be called after persistence")

        result2 = resolve_kb_root(interactive=True, input_fn=explode)
        assert result2 == chosen


# ---------------------------------------------------------------------------
# Failure path — non-interactive without configuration
# ---------------------------------------------------------------------------


class TestResolveKbRootFailure:
    def test_raises_when_non_interactive_and_unconfigured(
        self, isolated_env: Path
    ) -> None:
        """No env, no vaultlab config, no bobby_kb config, ``interactive=False``."""
        from vaultlab.context.locations import KbRootNotConfigured, resolve_kb_root

        with pytest.raises(KbRootNotConfigured) as excinfo:
            resolve_kb_root(interactive=False)

        # Suggested default should still be carried on the exception so a
        # caller can re-surface a one-key-accept prompt.
        assert excinfo.value.suggested_default == isolated_env / "home" / "vaultlab-kb"
        # Message points at the most useful next step.
        assert "vaultlab init" in str(excinfo.value)


# ---------------------------------------------------------------------------
# Orchestrator integration sanity test
# ---------------------------------------------------------------------------


class TestOrchestratorIntegration:
    def test_orchestrators_call_resolve_kb_root_when_kb_root_is_none(
        self,
        isolated_env: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """When ``kb_root=None`` is threaded through, each orchestrator
        consults ``resolve_kb_root`` — no longer crashes with TypeError.

        We don't run the full pipelines here (slow, network-bound). Instead
        we patch ``resolve_kb_root`` to a sentinel value and confirm the
        orchestrators fail FURTHER DOWN (not at the kb_root step) — proving
        they wired the resolver in.
        """
        from vaultlab.context import locations as _loc

        sentinel = isolated_env / "from-resolver"
        sentinel.mkdir()
        called: list[str] = []

        def fake_resolve(**kwargs: object) -> Path:
            called.append("resolved")
            return sentinel

        monkeypatch.setattr(_loc, "resolve_kb_root", fake_resolve)

        # 1) run_lit_arc — patch the search client so we don't hit the
        #    network. The resolver should be called BEFORE the search runs.
        from vaultlab.research import lineage as _lineage

        class _FakeClient:
            def search(self, *_args: object, **_kwargs: object) -> list[object]:
                # Returning [] takes the orchestrator down its empty-corpus
                # path which exits early without writing files. We don't
                # care what happens after — we only care that resolve was
                # called.
                return []

        # Run with kb_root=None → should call resolve_kb_root, then attempt
        # to write under sentinel/. Errors after that are acceptable; the
        # key assertion is that the resolver fired.
        try:
            _lineage.run_lit_arc(
                "x",
                kb_root=None,
                _client=_FakeClient(),
                max_seeds=0,
            )
        except Exception:
            pass  # downstream phases can fail; resolver call is what matters

        assert "resolved" in called, "run_lit_arc did not call resolve_kb_root"
