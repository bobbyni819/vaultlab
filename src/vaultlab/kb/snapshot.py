"""KB snapshots — point-in-time tar+gzip backups under ``<kb>/_Snapshots/``.

Master plan §5 (file 05). Lightweight, stdlib-only. Useful before
risky operations (mass renames, regenerating wiki concepts, accepting an
LLM-driven refactor of `_Index.md`).

Public API:

- :func:`create_snapshot` — write a ``<name>-<utc-date>.tar.gz`` archive.
- :func:`list_snapshots` — return the snapshot inventory.
- :func:`restore_snapshot` — extract an archive back into the KB. **Destructive
  by design** — overwrites existing files; the caller MUST confirm with the
  user (per Invariant 10 destructive-action rule).

Examples
--------
>>> from vaultlab.kb.snapshot import create_snapshot, list_snapshots  # doctest: +SKIP
>>> archive = create_snapshot("/g/My Drive/Knowledge/research", name="pre-wiki-rebuild")
>>> for snap in list_snapshots("/g/My Drive/Knowledge/research"):  # doctest: +SKIP
...     print(snap.path.name, snap.size_bytes)
"""

from __future__ import annotations

import re
import tarfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

# Default subdirectories to include — the user-authored content
_DEFAULT_INCLUDE = ("Sources", "Wiki", "Output", "_Index.md", "_Catalog.md")

# Subdirs we deliberately exclude — derived caches + Obsidian's own state
_EXCLUDE_PATTERNS = re.compile(r"(^|/)(\.|\.embeddings|_Snapshots)(/|$)")


@dataclass
class SnapshotInfo:
    """One row of the snapshot inventory."""

    path: Path
    name: str
    timestamp: str
    size_bytes: int


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def create_snapshot(
    kb_path: str | Path,
    *,
    name: str = "snapshot",
    include: tuple[str, ...] = _DEFAULT_INCLUDE,
) -> Path:
    """Create a tar+gzip snapshot under ``<kb>/_Snapshots/``.

    Filename pattern: ``<name>-<YYYY-MM-DDTHH-MM-SS-UTC>.tar.gz``.

    Parameters
    ----------
    kb_path
        Root folder of the knowledge base.
    name
        Short identifier for this snapshot (e.g. ``"pre-wiki-rebuild"``).
    include
        Subpaths within the KB root to include. Files (e.g. ``_Index.md``)
        are added directly; directories are added recursively (with
        ``.embeddings/`` and ``_Snapshots/`` excluded automatically).

    Returns
    -------
    Path
        Path to the written archive.
    """
    kb_root = Path(kb_path)
    if not kb_root.exists() or not kb_root.is_dir():
        raise FileNotFoundError(f"KB root does not exist: {kb_root}")

    snap_dir = kb_root / "_Snapshots"
    snap_dir.mkdir(exist_ok=True)

    timestamp = datetime.now(UTC).strftime("%Y-%m-%dT%H-%M-%S-UTC")
    target = snap_dir / f"{_safe_slug(name)}-{timestamp}.tar.gz"

    with tarfile.open(target, "w:gz") as tar:
        for sub in include:
            entry = kb_root / sub
            if not entry.exists():
                continue
            if entry.is_file():
                tar.add(entry, arcname=sub)
            else:
                # Directory — walk + filter
                for path in sorted(entry.rglob("*")):
                    if not path.is_file():
                        continue
                    rel = path.relative_to(kb_root).as_posix()
                    if _EXCLUDE_PATTERNS.search(rel):
                        continue
                    tar.add(path, arcname=rel)
    return target


def list_snapshots(kb_path: str | Path) -> list[SnapshotInfo]:
    """Return the snapshots stored under ``<kb>/_Snapshots/`` in time order.

    Newest first.
    """
    kb_root = Path(kb_path)
    snap_dir = kb_root / "_Snapshots"
    if not snap_dir.exists():
        return []

    out: list[SnapshotInfo] = []
    for archive in snap_dir.glob("*.tar.gz"):
        # Strip both .tar AND .gz extensions to get the bare stem
        bare = archive.name
        if bare.endswith(".tar.gz"):
            bare = bare[: -len(".tar.gz")]
        m = re.match(r"(?P<name>.+)-(?P<ts>\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2}-UTC)$", bare)
        if m:
            n = m.group("name")
            ts = m.group("ts")
        else:
            n = bare
            ts = ""
        out.append(
            SnapshotInfo(
                path=archive,
                name=n,
                timestamp=ts,
                size_bytes=archive.stat().st_size,
            )
        )
    out.sort(key=lambda s: s.timestamp, reverse=True)
    return out


def restore_snapshot(
    kb_path: str | Path,
    archive: str | Path,
    *,
    confirm: bool = False,
) -> Path:
    """Extract a snapshot back into the KB.

    **Destructive** — overwrites any existing files at the same paths inside
    the KB. The caller must pass ``confirm=True`` to proceed. Per AGENTS.md
    Invariant 10, restore is an explicitly-blocking operation; the slash
    command that wraps this MUST surface the confirmation in chat, not via
    grill doc.

    Parameters
    ----------
    kb_path
        KB root to restore into.
    archive
        Path to the ``.tar.gz`` snapshot.
    confirm
        Must be ``True`` — the explicit guard.

    Returns
    -------
    Path
        The KB root.
    """
    if not confirm:
        raise PermissionError(
            "restore_snapshot is destructive — pass confirm=True after "
            "explicitly confirming with the user. Per AGENTS.md Invariant 10, "
            "this is one of the few operations that must NOT be queued via "
            "grill doc; surface the confirmation in chat."
        )

    kb_root = Path(kb_path)
    archive_path = Path(archive)
    if not archive_path.exists():
        raise FileNotFoundError(f"Archive not found: {archive_path}")

    with tarfile.open(archive_path, "r:gz") as tar:
        # Defensive: don't allow path-traversal members
        for member in tar.getmembers():
            if member.name.startswith(("/", "..")) or ".." in Path(member.name).parts:
                raise ValueError(f"Refusing path-traversal member: {member.name!r}")
        tar.extractall(kb_root)

    return kb_root


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _safe_slug(name: str) -> str:
    """Filesystem-safe version of a snapshot name."""
    out = "".join(ch if (ch.isalnum() or ch in "-_") else "-" for ch in name)
    return out.strip("-") or "snapshot"


__all__ = ["SnapshotInfo", "create_snapshot", "list_snapshots", "restore_snapshot"]
