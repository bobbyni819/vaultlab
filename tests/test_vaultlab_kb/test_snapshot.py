"""Tests for vaultlab.kb.snapshot — point-in-time KB backups."""

from __future__ import annotations

import tarfile
import time
from pathlib import Path

import pytest


def _seed_kb(tmp_path: Path) -> Path:
    """Build a minimal KB with Sources/, Wiki/, and an _Index.md."""
    (tmp_path / "Sources").mkdir()
    (tmp_path / "Sources" / "a.md").write_text("# A")
    (tmp_path / "Wiki").mkdir()
    (tmp_path / "Wiki" / "b.md").write_text("# B")
    (tmp_path / "_Index.md").write_text("# Index")
    # Junk that should be excluded
    (tmp_path / ".obsidian").mkdir()
    (tmp_path / ".obsidian" / "config.json").write_text("{}")
    (tmp_path / ".embeddings").mkdir()
    (tmp_path / ".embeddings" / "cache.npy").write_text("binary")
    return tmp_path


class TestCreateSnapshot:
    def test_writes_archive(self, tmp_path: Path) -> None:
        from vaultlab.kb.snapshot import create_snapshot

        _seed_kb(tmp_path)
        archive = create_snapshot(tmp_path, name="initial")
        assert archive.exists()
        assert archive.suffix == ".gz"
        assert archive.parent == tmp_path / "_Snapshots"
        assert "initial" in archive.name

    def test_archive_includes_kb_files(self, tmp_path: Path) -> None:
        from vaultlab.kb.snapshot import create_snapshot

        _seed_kb(tmp_path)
        archive = create_snapshot(tmp_path)
        with tarfile.open(archive, "r:gz") as tar:
            names = set(tar.getnames())
        assert "Sources/a.md" in names
        assert "Wiki/b.md" in names
        assert "_Index.md" in names

    def test_archive_excludes_dot_dirs_and_embeddings(self, tmp_path: Path) -> None:
        from vaultlab.kb.snapshot import create_snapshot

        _seed_kb(tmp_path)
        archive = create_snapshot(tmp_path)
        with tarfile.open(archive, "r:gz") as tar:
            names = set(tar.getnames())
        assert not any(n.startswith(".obsidian") for n in names)
        assert not any(".embeddings" in n for n in names)
        assert not any("_Snapshots" in n for n in names)

    def test_safe_slugifies_name(self, tmp_path: Path) -> None:
        from vaultlab.kb.snapshot import create_snapshot

        _seed_kb(tmp_path)
        archive = create_snapshot(tmp_path, name="weird name (with) spaces!")
        assert "weird-name--with--spaces" in archive.name

    def test_missing_kb_raises(self, tmp_path: Path) -> None:
        from vaultlab.kb.snapshot import create_snapshot

        with pytest.raises(FileNotFoundError):
            create_snapshot(tmp_path / "missing")


class TestListSnapshots:
    def test_lists_after_create(self, tmp_path: Path) -> None:
        from vaultlab.kb.snapshot import create_snapshot, list_snapshots

        _seed_kb(tmp_path)
        create_snapshot(tmp_path, name="alpha")
        # Sleep a moment so the next timestamp differs
        time.sleep(1.1)
        create_snapshot(tmp_path, name="beta")

        snaps = list_snapshots(tmp_path)
        assert len(snaps) == 2
        # Newest first
        names_in_order = [s.name for s in snaps]
        assert names_in_order[0] == "beta"
        assert names_in_order[1] == "alpha"

    def test_empty_when_no_snapshots(self, tmp_path: Path) -> None:
        from vaultlab.kb.snapshot import list_snapshots

        assert list_snapshots(tmp_path) == []

    def test_size_bytes_populated(self, tmp_path: Path) -> None:
        from vaultlab.kb.snapshot import create_snapshot, list_snapshots

        _seed_kb(tmp_path)
        create_snapshot(tmp_path)
        snap = list_snapshots(tmp_path)[0]
        assert snap.size_bytes > 0


class TestRestoreSnapshot:
    def test_refuses_without_confirm(self, tmp_path: Path) -> None:
        from vaultlab.kb.snapshot import create_snapshot, restore_snapshot

        _seed_kb(tmp_path)
        archive = create_snapshot(tmp_path)
        with pytest.raises(PermissionError, match="confirm=True"):
            restore_snapshot(tmp_path, archive)

    def test_restores_when_confirmed(self, tmp_path: Path) -> None:
        from vaultlab.kb.snapshot import create_snapshot, restore_snapshot

        _seed_kb(tmp_path)
        archive = create_snapshot(tmp_path)
        # Mutate the KB
        (tmp_path / "Sources" / "a.md").write_text("# Mutated")

        restore_snapshot(tmp_path, archive, confirm=True)
        assert (tmp_path / "Sources" / "a.md").read_text() == "# A"

    def test_missing_archive_raises(self, tmp_path: Path) -> None:
        from vaultlab.kb.snapshot import restore_snapshot

        with pytest.raises(FileNotFoundError):
            restore_snapshot(tmp_path, tmp_path / "missing.tar.gz", confirm=True)
