"""vaultlab.kb.feedback — async-first feedback channels.

Implements CLAUDE.md commitment 5 / AGENTS.md invariant 10 mechanically:

- :func:`open_question` — write a numbered grill-style markdown asking the user
  for input on N+ pending decisions; auto-open in Obsidian.
- :func:`log_decision` — append a decision (with reasoning) to the project's
  ``decisions-log.md``.
- :func:`unread_docs_summary` — list grill / decisions-log / START_HERE files
  modified since the user last acknowledged them; surfaced at end-of-turn so
  the user knows what to read.

The module is **stateless on the user side** — it writes markdown files and
returns paths. The user reads them in Obsidian; their replies come back as
edits to the same files (or chat messages referencing the question numbers).

These channels exist so VaultLab can keep working when there's a fork in the
plan, instead of blocking the chat with mid-flight questions.

Examples
--------
>>> from pathlib import Path
>>> from vaultlab.kb.feedback import open_question, log_decision
>>>
>>> # When a slash command hits a fork it can't decide on its own:
>>> path = open_question(  # doctest: +SKIP
...     kb_path="/g/My Drive/Knowledge/research",
...     slug="figure-granularity",
...     title="Figure understanding — bbox granularity",
...     questions=[
...         "Per-cell-type group bbox, or per-instance?",
...         "Should SAM2 segmentation always run, or only when confidence is low?",
...     ],
...     context="Phase 1 of vaultlab.figures.understand build.",
... )
>>>
>>> # When a non-blocking decision is made autonomously:
>>> log_decision(  # doctest: +SKIP
...     kb_path="/g/My Drive/Knowledge/research",
...     project_slug="vaultlab",
...     decision="Cap parallel subagent fan-out at 6",
...     why="Bobby's grill Q3 default; protects API spend.",
... )
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


@dataclass
class GrillDoc:
    """Result of writing a grill / open-question doc."""

    path: Path
    slug: str
    n_questions: int
    open_command: str = ""

    def __post_init__(self) -> None:
        if not self.open_command:
            # Vault-relative path for `bobby-kb open`; vault root is the parent
            # of the KB folder, so we strip the KB-root prefix to get a slug
            # like `<kb>/Sources/Notes/grill-<slug>-<date>.md`.
            self.open_command = f"bobby-kb open {self.path.parent.name}/{self.path.stem}"


@dataclass
class DecisionEntry:
    """One row of the decisions-log."""

    timestamp: str
    decision: str
    why: str
    tags: list[str] = field(default_factory=list)


def open_question(
    kb_path: str | Path,
    slug: str,
    title: str,
    questions: list[str],
    *,
    context: str | None = None,
    notes_subdir: str = "Sources/Notes",
    auto_open: bool = True,
    launcher: object = None,
) -> GrillDoc:
    """Write a numbered grill-style markdown asking the user for input.

    Filename pattern: ``<notes_subdir>/grill-<slug>-<YYYY-MM-DD>.md``.

    Parameters
    ----------
    kb_path
        Root folder of the knowledge base.
    slug
        Topic identifier — kebab-case. Used in filename + frontmatter.
    title
        Human-readable title of the grill (rendered as H1).
    questions
        List of question strings. Each rendered as a numbered ``### Q<n>`` heading
        with a checkbox / write-in area below.
    context
        Optional paragraph above the questions explaining what triggered the grill.
    notes_subdir
        Where in the KB to write. ``Sources/Notes`` matches Bobby's convention.
    auto_open
        If ``True`` (default), call ``open_in_obsidian`` to surface the doc.
        Set to ``False`` for tests or when the user has paused auto-open.
    launcher
        Test hook — passed through to ``open_in_obsidian``. Production code
        should leave this as ``None``.

    Returns
    -------
    GrillDoc
        Path written + the ``bobby-kb open`` command to surface it.
    """
    if not questions:
        raise ValueError("open_question requires at least one question")

    kb_root = Path(kb_path)
    if not kb_root.exists():
        raise FileNotFoundError(f"KB root does not exist: {kb_root}")

    target_dir = kb_root / notes_subdir
    target_dir.mkdir(parents=True, exist_ok=True)

    today = datetime.now(UTC).strftime("%Y-%m-%d")
    filename = f"grill-{slug}-{today}.md"
    target = target_dir / filename

    body = _render_grill_body(
        slug=slug, title=title, questions=questions, context=context, today=today
    )
    target.write_text(body, encoding="utf-8")

    result = GrillDoc(path=target, slug=slug, n_questions=len(questions))

    if auto_open:
        # Imported lazily so feedback is callable in environments that don't
        # have Obsidian config (e.g., CI). Failures are non-fatal.
        try:
            from vaultlab.kb.obsidian import open_in_obsidian

            rel = f"{kb_root.name}/{notes_subdir}/{filename[:-3]}"  # strip .md
            open_in_obsidian(
                rel,
                vault_root=kb_root.parent,
                verify_exists=False,
                launcher=launcher,  # type: ignore[arg-type]
            )
        except Exception:
            pass

    return result


def log_decision(
    kb_path: str | Path,
    project_slug: str,
    decision: str,
    why: str,
    *,
    tags: list[str] | None = None,
    project_dir: str = "Wiki/Projects",
) -> Path:
    """Append a decision to the project's ``decisions-log.md``.

    Creates the file if it doesn't exist. Newest entries go at the top
    (reverse chronological).

    Parameters
    ----------
    kb_path
        Root folder of the knowledge base.
    project_slug
        Project identifier — kebab-case (matches the START_HERE slug).
    decision
        One-sentence statement of what was decided.
    why
        Reasoning. Can be multi-line.
    tags
        Optional tags attached to this entry (e.g., ``["scope", "config"]``).
    project_dir
        Where projects live in the KB. Defaults to ``Wiki/Projects``.

    Returns
    -------
    Path
        Path to the (created or appended) decisions-log file.
    """
    kb_root = Path(kb_path)
    if not kb_root.exists():
        raise FileNotFoundError(f"KB root does not exist: {kb_root}")

    target_dir = kb_root / project_dir / project_slug
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / "decisions-log.md"

    timestamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    entry = DecisionEntry(timestamp=timestamp, decision=decision, why=why, tags=list(tags or []))
    entry_block = _render_decision_block(entry)

    if target.exists():
        existing = target.read_text(encoding="utf-8")
        # Preserve the frontmatter + heading; insert under "## Entries" if present.
        if "## Entries" in existing:
            head, tail = existing.split("## Entries", 1)
            new_text = f"{head}## Entries\n\n{entry_block}\n{tail.lstrip()}"
        else:
            # Append to the bottom — file pre-exists but lacks the section
            new_text = existing.rstrip() + "\n\n## Entries\n\n" + entry_block + "\n"
        target.write_text(new_text, encoding="utf-8")
    else:
        target.write_text(_render_new_decisions_log(project_slug, entry_block), encoding="utf-8")

    return target


def unread_docs_summary(
    kb_path: str | Path,
    *,
    since: datetime | None = None,
    notes_subdir: str = "Sources/Notes",
    project_dir: str = "Wiki/Projects",
) -> list[Path]:
    """List grill / decisions-log / START_HERE files modified after ``since``.

    Used at end-of-turn to surface what the user should read on their schedule.
    The caller renders each path as a ``bobby-kb open <path>`` line.

    Parameters
    ----------
    kb_path
        Root folder of the knowledge base.
    since
        Modified-after threshold. Defaults to "1 hour ago" — practical for
        end-of-turn surfacing during an active session. Pass a specific
        ``datetime`` for cross-session catch-up.
    notes_subdir
        Where grill docs live.
    project_dir
        Where project state lives.

    Returns
    -------
    list[Path]
        Paths in modification-time order (oldest first → most-recent last).
        Empty list when nothing is unread.
    """
    kb_root = Path(kb_path)
    if not kb_root.exists():
        return []

    if since is None:
        from datetime import timedelta

        since = datetime.now(UTC) - timedelta(hours=1)
    threshold = since.timestamp()

    candidates: list[Path] = []

    notes_dir = kb_root / notes_subdir
    if notes_dir.exists():
        for p in notes_dir.glob("grill-*.md"):
            if p.stat().st_mtime >= threshold:
                candidates.append(p)

    proj_root = kb_root / project_dir
    if proj_root.exists():
        for proj in proj_root.iterdir():
            if not proj.is_dir():
                continue
            for fname in ("START_HERE.md", "decisions-log.md"):
                p = proj / fname
                if p.exists() and p.stat().st_mtime >= threshold:
                    candidates.append(p)

    candidates.sort(key=lambda p: p.stat().st_mtime)
    return candidates


# ---------------------------------------------------------------------------
# Internal rendering helpers
# ---------------------------------------------------------------------------


def _render_grill_body(
    *, slug: str, title: str, questions: list[str], context: str | None, today: str
) -> str:
    lines: list[str] = [
        "---",
        f"title: {title}",
        "type: grill",
        f"slug: {slug}",
        f"created: {today}",
        "status: awaiting-user-feedback",
        "managed_by: vaultlab.kb.feedback.open_question",
        "---",
        "",
        f"# {title}",
        "",
        "> VaultLab wrote this so it could keep working without blocking the "
        "chat. Read at your leisure; edit answers under each question or reply "
        "in chat by question number.",
        "",
    ]
    if context:
        lines.append("## Context")
        lines.append("")
        lines.append(context.strip())
        lines.append("")

    lines.append("## Questions")
    lines.append("")
    for i, q in enumerate(questions, start=1):
        lines.append(f"### Q{i}. {q.strip()}")
        lines.append("")
        lines.append("- [ ] Answer / decision (write below):")
        lines.append("")
        lines.append("")  # blank slot for user

    lines.append("---")
    lines.append("")
    lines.append(
        'When done, tell VaultLab *"answers are in the grill doc"* '
        "or reply in chat by question number."
    )
    lines.append("")
    return "\n".join(lines)


def _render_decision_block(entry: DecisionEntry) -> str:
    tag_line = f"  *(tags: {', '.join(entry.tags)})*" if entry.tags else ""
    return (
        f"### {entry.timestamp}{tag_line}\n\n"
        f"**Decision:** {entry.decision}\n\n"
        f"**Why:** {entry.why}\n"
    )


def _render_new_decisions_log(project_slug: str, first_entry_block: str) -> str:
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    return (
        "---\n"
        f"title: Decisions log — {project_slug}\n"
        "type: project\n"
        "kind: decisions-log\n"
        f"slug: {project_slug}\n"
        f"created: {today}\n"
        "managed_by: vaultlab.kb.feedback.log_decision\n"
        "---\n"
        "\n"
        f"# Decisions log — {project_slug}\n"
        "\n"
        "> Append-only record of design + scope decisions. VaultLab writes; "
        "you correct. Newest entries at top.\n"
        "\n"
        "## Entries\n"
        "\n"
        f"{first_entry_block}\n"
    )


__all__ = [
    "DecisionEntry",
    "GrillDoc",
    "log_decision",
    "open_question",
    "unread_docs_summary",
]
