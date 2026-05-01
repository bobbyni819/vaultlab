"""vaultlab.context.code — link a code repo to a vaultlab project.

This module surfaces the *linked codebase* feature: a vaultlab project
can have an associated code repository (e.g. an analysis repo, a
simulation codebase, an experiment-runner repo). When linked, the
crosstalk meeting machinery can:

* Read source files from the repo as context for a deep-think meeting
* Surface recent file changes (e.g. "you edited model.py 5 minutes ago,
  here's the diff to consider")
* Run scripts in the repo (the user-side Claude Code session has Bash;
  the meeting machinery doesn't run subprocesses itself, but can
  surface "user, please run X and paste the output" as part of the
  meeting agenda)

Public surface:

* :func:`get_linked_repo` — read the project config and return the linked
  repo's :class:`Path`, or ``None`` when no repo is linked.
* :func:`set_linked_repo` — write the linked-repo path back into the
  project config. Used by the ``/link-repo`` slash command.
* :func:`list_recent_changes` — git-log over the linked repo, returning
  a structured list of recent commits.
* :func:`read_file` — read a file from the linked repo (path resolved
  relative to the repo root).
* :func:`list_files` — glob the linked repo for files matching a pattern,
  with sane exclusions (no `.git/`, no `__pycache__`, etc.).

Convention
----------

The linked repo is a *separate* directory from the vaultlab KB. The KB
holds knowledge artifacts (papers, summaries, arcs, transcripts); the
linked repo holds *executable* artifacts (source code, scripts, data).
Crosstalk meetings can reference both — the linked-repo feature is what
lets a researcher with their own codebase + data use vaultlab's
multi-agent reasoning machinery without first having to convert their
work into KB notes.

Limitations (v0.1.x)
--------------------

* No automatic execution. The wrapper does not run user code on its
  own; it surfaces files and changes for the meeting context. The user
  (via Claude Code) decides what to run.
* One linked repo per project. Multi-repo support deferred.
* Git-only at first (``list_recent_changes`` calls ``git log``). Other
  VCS support deferred.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


__all__ = [
    "CommitInfo",
    "get_linked_repo",
    "list_files",
    "list_recent_changes",
    "read_file",
    "set_linked_repo",
]


# ---------------------------------------------------------------------------
# Config-side: read / write the linked repo path
# ---------------------------------------------------------------------------


def get_linked_repo(project_path: Path | str) -> Path | None:
    """Return the linked repo path for the project, or ``None`` if not linked.

    Reads ``<project_path>/.vaultlab-project.json`` and returns the
    ``linked_repo`` field as a :class:`Path` (expanded). Returns
    ``None`` when:

    * The config file doesn't exist
    * The ``linked_repo`` field is empty / missing
    * The path doesn't exist on disk (treated as "not linked")
    """
    from vaultlab.onboarding.config import load_config

    try:
        cfg = load_config(project_path)
    except FileNotFoundError:
        return None
    if cfg is None:
        # load_config returns None for missing files in some code paths
        return None
    raw = (cfg.linked_repo or "").strip()
    if not raw:
        return None
    p = Path(raw).expanduser()
    if not p.exists():
        return None
    return p


def set_linked_repo(
    project_path: Path | str,
    repo_path: Path | str,
) -> Path:
    """Write a linked-repo path into the project config.

    Creates ``<project_path>/.vaultlab-project.json`` if it doesn't
    exist; merges the ``linked_repo`` field into the existing config
    otherwise. Returns the canonicalized repo path that was stored.

    Raises:
        FileNotFoundError: When ``repo_path`` doesn't exist.
        NotADirectoryError: When ``repo_path`` exists but isn't a
            directory.
    """
    from vaultlab.onboarding.config import (
        VaultLabProjectConfig,
        load_config,
        save_config,
    )

    repo_resolved = Path(repo_path).expanduser().resolve()
    if not repo_resolved.exists():
        raise FileNotFoundError(f"linked repo not found: {repo_resolved}")
    if not repo_resolved.is_dir():
        raise NotADirectoryError(f"linked repo must be a directory: {repo_resolved}")

    try:
        cfg = load_config(project_path)
    except FileNotFoundError:
        cfg = None
    if cfg is None:
        cfg = VaultLabProjectConfig(
            project_path=str(Path(project_path).resolve())
        )
    cfg.linked_repo = str(repo_resolved)
    save_config(cfg, project_path)
    return repo_resolved


# ---------------------------------------------------------------------------
# Read-side: surface files and changes from the linked repo
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CommitInfo:
    """One commit from the linked repo's git log.

    Attributes:
        sha: 7-char short commit SHA.
        date: ISO date string ``YYYY-MM-DD``.
        author: Commit author name (no email).
        subject: Commit subject line (no body).
    """

    sha: str
    date: str
    author: str
    subject: str


def list_recent_changes(
    repo_path: Path | str,
    *,
    limit: int = 10,
    since: str = "",
) -> list[CommitInfo]:
    """Return the last ``limit`` commits in the linked repo.

    Args:
        repo_path: Path to the linked repo (typically from
            :func:`get_linked_repo`).
        limit: Max number of commits to return (default 10).
        since: Optional git ``--since`` argument (e.g. ``"1 week ago"``,
            ``"2026-04-01"``). Empty string disables the filter.

    Returns:
        List of :class:`CommitInfo`, newest first. Empty list when the
        path isn't a git repo or git isn't installed.
    """
    rp = Path(repo_path).expanduser()
    if not (rp / ".git").exists():
        return []
    cmd = [
        "git",
        "-C",
        str(rp),
        "log",
        f"-n{int(limit)}",
        "--pretty=format:%h|%ad|%an|%s",
        "--date=short",
    ]
    if since:
        cmd.insert(-1, f"--since={since}")
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
            encoding="utf-8",
            errors="replace",
        )
    except FileNotFoundError:
        return []
    if result.returncode != 0:
        return []
    out: list[CommitInfo] = []
    for line in result.stdout.splitlines():
        if not line.strip():
            continue
        parts = line.split("|", 3)
        if len(parts) != 4:
            continue
        sha, date, author, subject = parts
        out.append(
            CommitInfo(
                sha=sha.strip(),
                date=date.strip(),
                author=author.strip(),
                subject=subject.strip(),
            )
        )
    return out


def read_file(
    repo_path: Path | str,
    relpath: Path | str,
    *,
    max_bytes: int = 1_000_000,
) -> str:
    """Read a file from the linked repo, by relative path.

    Args:
        repo_path: Linked repo root.
        relpath: File path relative to the repo root (e.g.
            ``"src/model.py"``).
        max_bytes: Cap on bytes returned. Files larger than this are
            truncated at ``max_bytes``; the caller can re-request with a
            larger cap if needed.

    Returns:
        File contents (UTF-8 with replace-on-error). Empty string when
        the file doesn't exist or is outside the repo.
    """
    rp = Path(repo_path).expanduser().resolve()
    target = (rp / relpath).resolve()
    # Refuse to read outside the repo (path-traversal guard).
    try:
        target.relative_to(rp)
    except ValueError:
        return ""
    if not target.exists() or not target.is_file():
        return ""
    raw = target.read_bytes()
    if len(raw) > max_bytes:
        raw = raw[:max_bytes]
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("utf-8", errors="replace")


_DEFAULT_EXCLUDE_DIRS = frozenset(
    {
        ".git",
        ".venv",
        "venv",
        "env",
        "node_modules",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        "build",
        "dist",
        ".idea",
        ".vscode",
    }
)


def list_files(
    repo_path: Path | str,
    *,
    pattern: str = "**/*",
    exclude_dirs: Iterable[str] | None = None,
    max_results: int = 500,
) -> list[Path]:
    """List files in the linked repo matching ``pattern``.

    Skips standard noise directories (``.git/``, ``__pycache__/`` etc.)
    by default. Returns absolute paths.

    Args:
        repo_path: Linked repo root.
        pattern: glob pattern relative to the repo root (default
            ``"**/*"`` = every file).
        exclude_dirs: Override the default exclude set.
        max_results: Cap on returned paths (default 500). Prevents
            runaway returns on large repos.

    Returns:
        List of absolute paths. Empty list when the repo doesn't exist.
    """
    rp = Path(repo_path).expanduser().resolve()
    if not rp.exists() or not rp.is_dir():
        return []
    exclude = frozenset(exclude_dirs) if exclude_dirs else _DEFAULT_EXCLUDE_DIRS

    out: list[Path] = []
    for p in rp.glob(pattern):
        if not p.is_file():
            continue
        # Skip if any component is in the exclude set.
        if any(part in exclude for part in p.relative_to(rp).parts):
            continue
        out.append(p)
        if len(out) >= max_results:
            break
    return out
