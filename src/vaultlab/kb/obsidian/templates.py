"""vaultlab note templates — frontmatter scaffolds installed into the vault.

Writes a small library of markdown templates into ``<vault>/.templates/`` (or
the Obsidian-configured template folder when present). Templater plugin (see
:mod:`vaultlab.kb.obsidian.plugins`) consumes these for date stamps + slug
helpers.

Templates are deliberately minimal — they exist so the user has a starting
point, not a prescriptive structure. Each template lives in its own ``.md`` file
so users can edit them without re-running setup.
"""

from __future__ import annotations

import json
from pathlib import Path

# Each entry: (filename, body). Body is markdown; <% ... %> blocks are
# Templater syntax (only fired when Templater is installed and enabled).
_TEMPLATES: tuple[tuple[str, str], ...] = (
    (
        "source-paper.md",
        """\
---
type: source
kind: paper
title: <% tp.file.title %>
authors: []
year:
doi:
ingested: <% tp.date.now("YYYY-MM-DD") %>
tags: [paper]
---

# <% tp.file.title %>

## Why this is in the KB

<!-- One sentence: what question does this paper help answer? -->

## Key claims

-

## Methods worth borrowing

-

## Open questions / disagreements

-

## Citation

```bibtex

```
""",
    ),
    (
        "source-note.md",
        """\
---
type: source
kind: note
title: <% tp.file.title %>
created: <% tp.date.now("YYYY-MM-DD") %>
tags: [note]
---

# <% tp.file.title %>

<!-- Free-form notes. Link with [[wikilinks]] to other vault entries. -->
""",
    ),
    (
        "wiki-concept.md",
        """\
---
type: wiki
kind: concept
title: <% tp.file.title %>
created: <% tp.date.now("YYYY-MM-DD") %>
sources: []
tags: [concept]
---

# <% tp.file.title %>

## Definition

## Why it matters in this KB

## Sources cited

<!-- Linked to entries in Sources/ via [[wikilinks]] -->
""",
    ),
    (
        "project-start-here.md",
        """\
---
type: project
kind: start-here
slug: <% tp.file.title %>
managed_by: vaultlab.kb.start_here
created: <% tp.date.now("YYYY-MM-DD") %>
---

# START_HERE — <% tp.file.title %>

> vaultlab maintains this file automatically. When you (or a future Claude Code
> session) come back to this project, read this first.

## Current focus

## Recent activity

## Files to read first if resuming

## Open questions

## How vaultlab updates this

This file is auto-maintained. Every slash command that completes meaningful work
appends to "Recent activity" and refreshes "Files to read first". Manual edits
are preserved across updates.
""",
    ),
    (
        "decisions-log.md",
        """\
---
type: project
kind: decisions-log
slug: <% tp.file.title %>
managed_by: vaultlab.kb.feedback
created: <% tp.date.now("YYYY-MM-DD") %>
---

# Decisions log — <% tp.file.title %>

> Append-only record of design + scope decisions. vaultlab writes; you correct.

<!-- New entries inserted at the top by vaultlab.kb.feedback.log_decision() -->
""",
    ),
)


def write_templates(kb_path: str | Path, *, template_dir: str = ".templates") -> Path:
    """Install vaultlab note templates into the vault.

    Parameters
    ----------
    kb_path
        Root folder of the knowledge base.
    template_dir
        Subdirectory inside the vault where templates live. ``.templates`` is the
        Obsidian default; users who configured a different folder should pass it
        explicitly.

    Returns
    -------
    Path
        The created template directory.

    Notes
    -----
    Idempotent — never overwrites existing templates the user may have edited.
    """
    kb_root = Path(kb_path)
    if not kb_root.exists():
        raise FileNotFoundError(f"KB root does not exist: {kb_root}")

    target_dir = kb_root / template_dir
    target_dir.mkdir(exist_ok=True)

    for filename, body in _TEMPLATES:
        target = target_dir / filename
        if not target.exists():
            target.write_text(body, encoding="utf-8")

    # Tell Obsidian where templates live so the Templates core plugin finds them
    obsidian_dir = kb_root / ".obsidian"
    if obsidian_dir.exists():
        templates_config = obsidian_dir / "templates.json"
        if not templates_config.exists():
            templates_config.write_text(
                json.dumps({"folder": template_dir}, indent=2), encoding="utf-8"
            )

    return target_dir
