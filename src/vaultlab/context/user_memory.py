"""Per-user auto-memory — VaultLab gets smarter session-over-session.

Master plan §4b sibling module (added 2026-04-29). When the user gives
important feedback or VaultLab learns a non-obvious calibration that should
persist, write it here. Future sessions read this back so the system
inherits prior tuning instead of relearning from zero each chat.

Mirrors Claude Code's own auto-memory pattern but **scoped to VaultLab** —
this is the place where preferences specific to research-companion behavior
live (figure-style preferences, hedging-strictness, parallel-fan-out tastes,
etc.).

File layout
-----------

::

    ~/.config/vaultlab/user_memory/
      MEMORY.md                      # one-line index, always loaded into context
      feedback_<topic>.md            # corrections + confirmations
      preference_<topic>.md          # workflow / style preferences
      pattern_<topic>.md             # decisions that worked; reuse in similar contexts
      project_<slug>.md              # project-specific calibration

Each entry file has frontmatter + a body. The MEMORY.md index is the only
file the LLM is required to read every session — it lists pointers that the
LLM dives into selectively (tiered just like the tools-index).

Public API
----------

- :func:`memory_root` — return the user_memory directory path
- :func:`remember` — save a memory entry; updates ``MEMORY.md`` index
- :func:`recall` — read one entry by name
- :func:`recall_all` — return the index + all entries (for system-prompt seeding)
- :func:`forget` — delete a memory entry (rare; explicit)

Categories
----------

- ``feedback`` — corrections the user made + confirmations of approaches that worked.
  Lead with the rule, then *why* (the reason the user gave) and *how to apply*
  (when this kicks in). Knowing why lets the LLM judge edge cases.
- ``preference`` — workflow / style choices (e.g., "Bobby wants public docs
  name-agnostic; personal contribution audits stay in KB").
- ``pattern`` — design decisions that proved out across sessions.
- ``project`` — project-specific calibration ("this project uses Box for raw
  data, GitHub for code, KB for analysis writeups").

Examples
--------

>>> from vaultlab.context.user_memory import remember, recall_all
>>> remember(  # doctest: +SKIP
...     category="feedback",
...     name="hedged-voice-strictness",
...     description="Bobby never wants 'X is Y'; always 'X is consistent with Y'.",
...     content=(
...         "Always use hedged voice in scientific output.\\n\\n"
...         "**Why:** Reviewers can tell when an LLM wrote something. Hedged voice"
...         " + quoted evidence makes outputs read like a careful researcher's notes.\\n\\n"
...         "**How to apply:** Every LLM-generated interpretation; flag assertions in code review."
...     ),
... )
>>> all_mem = recall_all()  # doctest: +SKIP
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

Category = Literal["feedback", "preference", "pattern", "project"]
_CATEGORIES: tuple[Category, ...] = ("feedback", "preference", "pattern", "project")

INDEX_FILENAME = "MEMORY.md"


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------


def memory_root() -> Path:
    """Return ``~/.config/vaultlab/user_memory`` (or env override).

    Honors ``$VAULTLAB_USER_MEMORY`` for tests.
    """
    override = os.environ.get("VAULTLAB_USER_MEMORY")
    if override:
        return Path(override)
    return Path.home() / ".config" / "vaultlab" / "user_memory"


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class MemoryEntry:
    """One memory file."""

    path: Path
    name: str
    category: Category
    description: str
    content: str
    last_updated: str


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def remember(
    *,
    category: Category,
    name: str,
    description: str,
    content: str,
) -> Path:
    """Save (or update) a memory entry; refresh the index.

    Parameters
    ----------
    category
        One of ``feedback`` / ``preference`` / ``pattern`` / ``project``.
    name
        Kebab-case identifier (e.g. ``hedged-voice-strictness``). Combined
        with category to form the filename: ``<category>_<name>.md``.
    description
        One line, ≤150 chars. Used in ``MEMORY.md`` as the tagline.
    content
        Full memory body. Markdown. For ``feedback``-category entries,
        recommend the structure: rule → ``**Why:**`` → ``**How to apply:**``.

    Returns
    -------
    Path
        Path to the written entry file.
    """
    if category not in _CATEGORIES:
        raise ValueError(f"category must be one of {_CATEGORIES}, got {category!r}")
    if not name or not _is_safe_slug(name):
        raise ValueError(f"name must be a kebab-case slug, got {name!r}")
    if len(description) > 200:
        # Allow a little slack but flag huge descriptions
        raise ValueError(
            f"description should be one short line (≤200 chars); got {len(description)} chars"
        )

    root = memory_root()
    root.mkdir(parents=True, exist_ok=True)

    target = root / f"{category}_{name}.md"
    timestamp = datetime.now(UTC).strftime("%Y-%m-%d")

    body = (
        "---\n"
        f"name: {name}\n"
        f"description: {description}\n"
        f"type: {category}\n"
        f"last_updated: {timestamp}\n"
        "---\n\n"
        f"{content.rstrip()}\n"
    )
    target.write_text(body, encoding="utf-8")

    _refresh_index(root)
    return target


def recall(category: Category, name: str) -> MemoryEntry | None:
    """Read one memory entry by category + name. ``None`` if absent."""
    root = memory_root()
    target = root / f"{category}_{name}.md"
    if not target.exists():
        return None
    return _parse_entry(target)


def recall_all() -> tuple[str, list[MemoryEntry]]:
    """Return (index_text, all_entries).

    Use ``index_text`` to seed a system prompt (it's the always-loaded summary).
    Use ``all_entries`` when the LLM has decided to dive into specific items.
    """
    root = memory_root()
    if not root.exists():
        return "", []

    index_path = root / INDEX_FILENAME
    index_text = index_path.read_text(encoding="utf-8") if index_path.exists() else ""

    entries: list[MemoryEntry] = []
    for path in sorted(root.glob("*.md")):
        if path.name == INDEX_FILENAME:
            continue
        try:
            entries.append(_parse_entry(path))
        except _MalformedEntry:
            continue
    return index_text, entries


def forget(category: Category, name: str, *, dry_run: bool = False) -> bool:
    """Delete a memory entry. Returns True if a file was (or would be) removed.

    Rare operation — only for outdated / contradictory memories. Caller
    should confirm with the user before invoking (Invariant 10 destructive).

    Args:
        category: Memory category (``user`` / ``feedback`` / ``project`` / ``reference``).
        name: Memory slug (the ``name:`` frontmatter field).
        dry_run: When ``True``, return whether the entry exists without
            actually deleting it. Lets callers preview the action before
            committing to it. Defaults to ``False`` (perform the deletion).
    """
    root = memory_root()
    target = root / f"{category}_{name}.md"
    if not target.exists():
        return False
    if dry_run:
        return True
    target.unlink()
    _refresh_index(root)
    return True


# ---------------------------------------------------------------------------
# Index rendering
# ---------------------------------------------------------------------------


def _refresh_index(root: Path) -> None:
    """Rebuild ``MEMORY.md`` to reflect the current set of entries."""
    entries: list[MemoryEntry] = []
    for path in sorted(root.glob("*.md")):
        if path.name == INDEX_FILENAME:
            continue
        try:
            entries.append(_parse_entry(path))
        except _MalformedEntry:
            continue

    by_category: dict[str, list[MemoryEntry]] = {c: [] for c in _CATEGORIES}
    for entry in entries:
        by_category.setdefault(entry.category, []).append(entry)

    lines = [
        "# VaultLab — User Memory Index",
        "",
        "> Auto-maintained by `vaultlab.context.user_memory`. One line per memory; "
        "VaultLab dives into the full file when relevant to the current task.",
        "",
    ]
    for cat in _CATEGORIES:
        items = by_category.get(cat, [])
        if not items:
            continue
        lines.append(f"## {cat.title()}")
        lines.append("")
        for entry in items:
            lines.append(f"- [{entry.name}]({entry.path.name}) — {entry.description}")
        lines.append("")

    if not entries:
        lines.append(
            "*(No memories yet. Use `remember()` to save calibration "
            "the LLM should retain across sessions.)*"
        )
        lines.append("")

    (root / INDEX_FILENAME).write_text("\n".join(lines), encoding="utf-8")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


_FRONT_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)
_SLUG_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


class _MalformedEntry(Exception):
    pass


def _is_safe_slug(name: str) -> bool:
    return bool(_SLUG_RE.match(name))


def _parse_entry(path: Path) -> MemoryEntry:
    text = path.read_text(encoding="utf-8")
    m = _FRONT_RE.match(text)
    if not m:
        raise _MalformedEntry(f"Missing frontmatter: {path}")

    fm: dict[str, str] = {}
    for line in m.group(1).splitlines():
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        fm[key.strip()] = value.strip().strip("\"'")

    name = fm.get("name") or path.stem.split("_", 1)[-1]
    description = fm.get("description", "")
    category_str = fm.get("type", "feedback")
    category: Category = (
        category_str if category_str in _CATEGORIES else "feedback"  # type: ignore[assignment]
    )
    last_updated = fm.get("last_updated", "")
    body = text[m.end() :].strip()

    return MemoryEntry(
        path=path,
        name=name,
        category=category,
        description=description,
        content=body,
        last_updated=last_updated,
    )


__all__ = [
    "INDEX_FILENAME",
    "Category",
    "MemoryEntry",
    "forget",
    "memory_root",
    "recall",
    "recall_all",
    "remember",
]
