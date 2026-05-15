"""Standalone integration test for vaultlab.kb.

Implements north-star Criterion #3 ("plug-in companion"): the primary
entrypoints of ``vaultlab.kb`` must be invocable from a fresh
``tmp_path`` fixture with no prior vaultlab state.

We exercise ``scaffold_kb`` (create a fresh project tree) followed by
``search`` over that tree — proving the bare-minimum init + search
round-trip works without any external state.

Note: ``vaultlab.kb.__init__`` is presently a migration placeholder.
This test uses the canonical submodule imports
(``vaultlab.kb.setup``, ``vaultlab.kb.semantic_search``) which are the
real public entrypoints today. When the package ``__init__`` is
backfilled, the imports can be flattened.
"""

from __future__ import annotations

from pathlib import Path

import pytest


def test_kb_scaffold_and_search_runs_standalone_from_fresh_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``scaffold_kb`` creates the canonical KB tree and ``search``
    returns hits over that tree — all from a fresh tmp_path."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / ".config"))

    from vaultlab.kb.semantic_search import SearchHit, search
    from vaultlab.kb.setup import scaffold_kb

    kb_root = tmp_path / "knowledge"
    proj_dir = scaffold_kb(kb_root, "standalone-demo")

    assert proj_dir.exists()
    # Canonical files written by the scaffolder.
    for fname in ("START_HERE.md", "_Index.md", "_Catalog.md", "_Log.md"):
        assert (proj_dir / fname).exists(), f"missing {fname} after scaffold_kb"

    # Canonical folders.
    for sub in ("Sources", "Wiki", "Output"):
        assert (proj_dir / sub).is_dir(), f"missing folder {sub}"

    # Drop a tiny source file so the TF-IDF backend has something to find.
    note = proj_dir / "Sources" / "Notes" / "demo-note.md"
    note.parent.mkdir(parents=True, exist_ok=True)
    note.write_text(
        "# Demo note\nThe quick brown fox jumps over the lazy dog.\n",
        encoding="utf-8",
    )

    hits = search(proj_dir, "brown fox")
    assert isinstance(hits, list)
    assert len(hits) >= 1
    assert all(isinstance(h, SearchHit) for h in hits)
    assert any("demo-note" in str(h.path) for h in hits)
