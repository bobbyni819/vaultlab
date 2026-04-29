"""START_HERE auto-update — Bobby's pattern for resuming work.

Every vaultlab session that does meaningful work updates `<kb>/Wiki/Projects/<slug>/START_HERE.md`
with: current focus, recent activity, files to read first if resuming, open questions.

The file is markdown so Claude Code can read it directly when opening the project.
The frontmatter has structured fields so other slash commands can query/update it.

Convention: every slash command that completes meaningful work calls
`update_start_here(slug, activity, files_to_read_next)` so the START_HERE
stays current automatically. Bobby never manually edits it; vaultlab does.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import frontmatter  # python-frontmatter, dependency from pyproject.toml

_TEMPLATE = """\
# START_HERE — {slug}

> **What this is.** vaultlab maintains this file automatically. When you (or a future
> Claude Code session) come back to this project, read this first. Last update: {last_updated}.

## Current focus

{current_focus}

## Recent activity

{recent_activity}

## Files to read first if resuming

{files_to_read}

## Open questions

{open_questions}

## How vaultlab updates this

This file is auto-maintained. Every slash command that completes meaningful work
appends to "Recent activity" and refreshes "Files to read first". Manual edits
are preserved across updates (vaultlab only modifies the auto-managed sections).

To force a refresh: `vaultlab kb start-here refresh --project {slug}`
"""


def init_start_here(
    kb_path: Path,
    slug: str,
    draft_understanding: str,
    suggested_files: list[Path],
) -> Path:
    """Initialize a START_HERE.md for a freshly-onboarded project.

    Called by `/onboard-project`. Subsequent slash commands use update_start_here
    to keep it current.
    """
    target_dir = kb_path / "Wiki" / "Projects" / slug
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / "START_HERE.md"

    body = _TEMPLATE.format(
        slug=slug,
        last_updated=datetime.now().strftime("%Y-%m-%d %H:%M"),
        current_focus=_extract_focus_from_draft(draft_understanding),
        recent_activity="(no activity yet — project just onboarded)",
        files_to_read="\n".join(f"- `{f}`" for f in suggested_files[:5]),
        open_questions="(none yet — `/onboard-project` may have queued some in `onboarding-grill.md`)",
    )

    post = frontmatter.Post(
        body,
        slug=slug,
        last_updated=datetime.now().isoformat(),
        managed_by="vaultlab.kb.start_here",
        version=1,
    )
    target.write_text(frontmatter.dumps(post), encoding="utf-8")
    return target


def update_start_here(
    kb_path: Path,
    slug: str,
    activity: str,
    files_to_read_next: list[Path] | None = None,
    new_open_questions: list[str] | None = None,
) -> Path | None:
    """Append a new activity entry + refresh the resume-files list.

    Called by every slash command that completes meaningful work:
        update_start_here(slug, "Drafted Methods §3.2; 47/50 citations SUPPORTED",
                          files_to_read_next=[methods_md_path])

    If START_HERE.md doesn't exist yet, returns None (project isn't onboarded —
    the calling command should suggest /onboard-project).
    """
    target = kb_path / "Wiki" / "Projects" / slug / "START_HERE.md"
    if not target.exists():
        return None

    post = frontmatter.load(target)

    # Update frontmatter timestamp + version
    post["last_updated"] = datetime.now().isoformat()
    post["version"] = post.get("version", 1) + 1

    # Insert activity at the top of "Recent activity" section, keep only last ~10 entries
    body = post.content
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    activity_line = f"- **{timestamp}** — {activity}"

    body = _insert_under_section(body, "## Recent activity", activity_line, max_entries=10)

    if files_to_read_next:
        files_section = "\n".join(f"- `{f}`" for f in files_to_read_next[:5])
        body = _replace_section(body, "## Files to read first if resuming", files_section)

    if new_open_questions:
        for q in new_open_questions:
            body = _insert_under_section(body, "## Open questions", f"- {q}", max_entries=20)

    post.content = body
    target.write_text(frontmatter.dumps(post), encoding="utf-8")
    return target


def read_start_here(kb_path: Path, slug: str) -> dict[str, Any] | None:
    """Read the structured contents of START_HERE.md.

    Returns dict with keys: slug, last_updated, current_focus, recent_activity,
    files_to_read, open_questions. Or None if file doesn't exist.
    """
    target = kb_path / "Wiki" / "Projects" / slug / "START_HERE.md"
    if not target.exists():
        return None
    post = frontmatter.load(target)
    return {
        "slug": slug,
        "last_updated": post.get("last_updated"),
        "version": post.get("version"),
        "body": post.content,
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _extract_focus_from_draft(draft: str) -> str:
    """Pull a 1-3 sentence current-focus summary from the draft understanding.

    Placeholder: returns the first paragraph. Real impl uses Claude to summarize.
    """
    # TODO: replace with Claude call when runner module lands
    para = draft.strip().split("\n\n")[0] if draft.strip() else ""
    return para or "(focus to be set on next /research-status)"


def _insert_under_section(body: str, heading: str, line: str, max_entries: int) -> str:
    """Insert a line just under a heading, capping the section at max_entries."""
    lines = body.split("\n")
    try:
        i = lines.index(heading)
    except ValueError:
        # Heading missing; append at end
        return body.rstrip() + f"\n\n{heading}\n\n{line}\n"

    # Find next heading or end-of-doc
    j = i + 1
    while j < len(lines) and not lines[j].startswith("## "):
        j += 1

    # Existing list items in this section
    section_lines = lines[i + 1 : j]
    existing_bullets = [ln for ln in section_lines if ln.startswith("- ")]
    new_bullets = [line, *existing_bullets[: max_entries - 1]]

    # Reassemble
    new_section = [heading, "", *new_bullets, ""]
    return "\n".join(lines[:i] + new_section + lines[j:])


def _replace_section(body: str, heading: str, replacement: str) -> str:
    """Replace the body of a section (between this heading and the next)."""
    lines = body.split("\n")
    try:
        i = lines.index(heading)
    except ValueError:
        return body.rstrip() + f"\n\n{heading}\n\n{replacement}\n"

    j = i + 1
    while j < len(lines) and not lines[j].startswith("## "):
        j += 1

    new_section = [heading, "", replacement, ""]
    return "\n".join(lines[:i] + new_section + lines[j:])
