"""vaultlab.onboarding.project_init — turn an intake form into a project view.

This module is the orchestrator that ``/onboard-project`` invokes. Given
a filled intake form + a project folder + a KB root, it:

1. Scans the project folder, classifying files by type (Python, notebooks,
   data, papers, manuscripts).
2. Combines the intake answers + folder inventory into a
   :class:`ProjectInit` view.
3. Writes the canonical onboarding outputs to the KB:

   - ``Wiki/Projects/<slug>/START_HERE.md`` (auto-resume page)
   - ``Wiki/Projects/<slug>/intake.md`` (saved intake copy)
   - ``Wiki/Projects/<slug>/decisions-log.md`` (initial entry)

4. Writes the machine-readable ``<project>/.vaultlab-project.json``.

The Python here is **deliberately deterministic** — no LLM calls. The
slash command body (in ``.claude/commands/onboard-project.md``) is
where Claude Code asks any follow-up questions. This split keeps the
test surface small and the failure modes obvious.
"""

from __future__ import annotations

import shutil
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from vaultlab.kb.paths import (
    ensure_parent,
    project_decisions_path,
    project_intake_path,
    project_state_path,
    slugify_topic,
)
from vaultlab.onboarding.config import VaultLabProjectConfig, save_config
from vaultlab.onboarding.intake import IntakeForm, parse_intake_md

__all__ = [
    "FILE_TYPE_PATTERNS",
    "FolderInventory",
    "ProjectInit",
    "init_project_from_intake",
    "scan_project_folder",
]


# ---------------------------------------------------------------------------
# File-type classification
# ---------------------------------------------------------------------------

# Suffix → category. The categories are deliberately coarse so the inventory
# is at-a-glance useful in START_HERE.md without being noisy.
FILE_TYPE_PATTERNS: dict[str, str] = {
    # Code
    ".py": "python",
    ".ipynb": "notebook",
    ".r": "r",
    ".rmd": "rmarkdown",
    # Data — wet-lab + tabular
    ".h5ad": "data_anndata",
    ".h5": "data_hdf5",
    ".tiff": "data_image",
    ".tif": "data_image",
    ".czi": "data_image",
    ".nd2": "data_image",
    ".ome.tif": "data_image",
    ".csv": "data_tabular",
    ".tsv": "data_tabular",
    ".parquet": "data_tabular",
    ".xlsx": "data_tabular",
    ".fcs": "data_flow",
    ".imzml": "data_maldi",
    ".ibd": "data_maldi",
    # Papers & manuscripts
    ".pdf": "paper",
    ".bib": "citations",
    ".ris": "citations",
    ".docx": "manuscript",
    ".tex": "manuscript",
    # Notes / docs
    ".md": "notes",
    ".txt": "notes",
    # Figures
    ".png": "figure",
    ".jpg": "figure",
    ".jpeg": "figure",
    ".svg": "figure",
}

# Directories to skip during scanning — they bloat counts without insight.
_SKIP_DIRS = {
    ".git",
    ".obsidian",
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


# ---------------------------------------------------------------------------
# Inventory
# ---------------------------------------------------------------------------


@dataclass
class FolderInventory:
    """Summary of a project folder's contents.

    ``counts`` maps category → count; ``samples`` maps category → up to
    5 representative file paths (relative to the project root).
    ``total_files`` is the count of files actually classified (not the
    raw filesystem total — directories under ``_SKIP_DIRS`` are
    excluded).
    """

    project_path: Path
    counts: dict[str, int] = field(default_factory=dict)
    samples: dict[str, list[Path]] = field(default_factory=dict)
    total_files: int = 0
    has_readme: bool = False
    has_claude_md: bool = False
    has_pyproject: bool = False

    def summary_lines(self) -> list[str]:
        """Render the inventory as bullet lines for START_HERE.md."""
        if not self.counts:
            return ["- (folder is empty or all files were skipped)"]
        out: list[str] = []
        for category in sorted(self.counts, key=lambda k: -self.counts[k]):
            out.append(f"- **{category}**: {self.counts[category]}")
        return out


def scan_project_folder(path: str | Path) -> FolderInventory:
    """Walk ``path`` and classify files by extension.

    Skips well-known noisy directories (``.git``, ``__pycache__`` etc.)
    so the inventory reflects user-authored content. Returns a
    :class:`FolderInventory`.
    """
    project_path = Path(path).resolve()
    if not project_path.exists():
        raise FileNotFoundError(f"Project folder not found: {project_path}")
    if not project_path.is_dir():
        raise NotADirectoryError(f"Not a directory: {project_path}")

    counter: Counter[str] = Counter()
    samples: dict[str, list[Path]] = {}

    for sub in project_path.rglob("*"):
        if not sub.is_file():
            continue
        # Skip files inside a skipped directory anywhere in the tree
        if any(part in _SKIP_DIRS for part in sub.relative_to(project_path).parts):
            continue
        category = _classify_file(sub)
        if category is None:
            continue
        counter[category] += 1
        rel = sub.relative_to(project_path)
        bucket = samples.setdefault(category, [])
        if len(bucket) < 5:
            bucket.append(rel)

    total = sum(counter.values())
    return FolderInventory(
        project_path=project_path,
        counts=dict(counter),
        samples=samples,
        total_files=total,
        has_readme=(project_path / "README.md").exists()
        or (project_path / "README.rst").exists(),
        has_claude_md=(project_path / "CLAUDE.md").exists(),
        has_pyproject=(project_path / "pyproject.toml").exists(),
    )


def _classify_file(file: Path) -> str | None:
    """Map a file to a category, or None if it's not a tracked type."""
    name = file.name.lower()
    # Multi-suffix matches (e.g. .ome.tif) take priority
    for ext, category in FILE_TYPE_PATTERNS.items():
        if name.endswith(ext):
            return category
    return None


# ---------------------------------------------------------------------------
# ProjectInit view
# ---------------------------------------------------------------------------


@dataclass
class ProjectInit:
    """Result of :func:`init_project_from_intake`.

    Bundles the resolved slug, the intake form, the folder inventory,
    and the paths of every file written. ``follow_up_questions`` is a
    short list of gaps the slash command should ask the user about
    (3-5 items).
    """

    slug: str
    intake: IntakeForm
    inventory: FolderInventory
    kb_root: Path
    project_path: Path
    config: VaultLabProjectConfig

    # Paths of files written
    start_here_path: Path | None = None
    intake_kb_copy_path: Path | None = None
    decisions_log_path: Path | None = None
    project_config_path: Path | None = None

    follow_up_questions: list[str] = field(default_factory=list)

    def files_written(self) -> list[Path]:
        return [
            p
            for p in (
                self.start_here_path,
                self.intake_kb_copy_path,
                self.decisions_log_path,
                self.project_config_path,
            )
            if p is not None
        ]


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


def init_project_from_intake(
    intake_path: str | Path,
    kb_root: str | Path,
    project_path: str | Path,
    *,
    slug: str | None = None,
) -> ProjectInit:
    """Read an intake form, scan the project folder, write the project view.

    Parameters
    ----------
    intake_path
        Path to the user's filled-in ``project_intake.md``. Usually
        lives at ``<project_path>/project_intake.md``.
    kb_root
        Root of the target KB (e.g. ``G:/My Drive/Knowledge/vaultlab``).
    project_path
        The user's project folder (the one containing data / code /
        notes). Used both for the folder scan and for writing
        ``.vaultlab-project.json``.
    slug
        Optional override for the project slug. If omitted, derived from
        the intake topic via :func:`vaultlab.kb.paths.slugify_topic`.

    Returns
    -------
    ProjectInit
        Bundle with the resolved slug, the intake form, the folder
        inventory, the paths written, and a list of follow-up questions
        the slash command should ask.

    Side effects
    ------------
    Writes 4 files:

    - ``<kb>/Wiki/Projects/<slug>/START_HERE.md``
    - ``<kb>/Wiki/Projects/<slug>/intake.md``
    - ``<kb>/Wiki/Projects/<slug>/decisions-log.md``
    - ``<project>/.vaultlab-project.json``
    """
    intake_p = Path(intake_path)
    kb_root_p = Path(kb_root)
    project_p = Path(project_path).resolve()

    # 1. Read the intake (raises if missing required fields)
    intake = parse_intake_md(intake_p)

    # 2. Resolve slug
    project_slug = slug or slugify_topic(intake.topic)

    # 3. Scan the folder
    inventory = scan_project_folder(project_p)

    # 4. Build the config
    config = _build_config(intake, kb_root_p, project_p, inventory, project_slug)

    # 5. Write all four artifacts
    intake_kb_copy = _write_intake_kb_copy(kb_root_p, project_slug, intake)
    start_here = _write_start_here(kb_root_p, project_slug, intake, inventory)
    decisions = _write_decisions_log(kb_root_p, project_slug, intake)
    project_cfg = save_config(config, project_p)

    # 6. Identify follow-up questions
    follow_ups = _compose_follow_ups(intake, inventory)

    return ProjectInit(
        slug=project_slug,
        intake=intake,
        inventory=inventory,
        kb_root=kb_root_p,
        project_path=project_p,
        config=config,
        start_here_path=start_here,
        intake_kb_copy_path=intake_kb_copy,
        decisions_log_path=decisions,
        project_config_path=project_cfg,
        follow_up_questions=follow_ups,
    )


# ---------------------------------------------------------------------------
# Internal: build the config
# ---------------------------------------------------------------------------


def _build_config(
    intake: IntakeForm,
    kb_root: Path,
    project_path: Path,
    inventory: FolderInventory,
    slug: str,
) -> VaultLabProjectConfig:
    """Translate the intake + inventory into a :class:`VaultLabProjectConfig`."""
    # Data dirs: any dir that contains a data file becomes a data dir
    data_dirs: list[str] = []
    seen_dirs: set[Path] = set()
    for category, sample_paths in inventory.samples.items():
        if not category.startswith("data_"):
            continue
        for rel in sample_paths:
            d = (inventory.project_path / rel).parent
            if d not in seen_dirs:
                seen_dirs.add(d)
                data_dirs.append(str(d))

    return VaultLabProjectConfig(
        slug=slug,
        topic=intake.topic,
        goal=list(intake.goals),
        audience=list(intake.audiences),
        kb_root=str(kb_root),
        project_path=str(project_path),
        data_dirs=data_dirs,
        validation_files=[],
        exclusions=dict(intake.exclusions),
        voice={"styles": list(intake.style)} if intake.style else {},
        pi_preferences=intake.pi_preferences,
        deadlines=list(intake.deadlines),
        free_form=intake.free_form,
    )


# ---------------------------------------------------------------------------
# Internal: write artifacts
# ---------------------------------------------------------------------------


def _write_intake_kb_copy(kb_root: Path, slug: str, intake: IntakeForm) -> Path:
    """Save the intake form to the KB-side ``Wiki/Projects/<slug>/intake.md``."""
    target = ensure_parent(project_intake_path(kb_root, slug))
    target.write_text(intake.to_markdown(), encoding="utf-8")
    return target


def _write_start_here(
    kb_root: Path,
    slug: str,
    intake: IntakeForm,
    inventory: FolderInventory,
) -> Path:
    """Render the auto-resume START_HERE.md page."""
    target = ensure_parent(project_state_path(kb_root, slug))
    body = _render_start_here_body(slug, intake, inventory)
    target.write_text(body, encoding="utf-8")
    return target


def _render_start_here_body(
    slug: str,
    intake: IntakeForm,
    inventory: FolderInventory,
) -> str:
    """Compose the markdown body for START_HERE.md."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    audience = ", ".join(intake.audiences) if intake.audiences else "(unspecified)"
    goals = ", ".join(intake.goals) if intake.goals else "(unspecified)"
    inventory_lines = "\n".join(inventory.summary_lines())

    suggested_files: list[str] = []
    if inventory.has_readme:
        suggested_files.append("- `README.md`")
    if inventory.has_claude_md:
        suggested_files.append("- `CLAUDE.md`")
    # Top-3 sample paths from the largest categories
    top_categories = sorted(
        inventory.counts.items(), key=lambda kv: -kv[1]
    )[:3]
    for cat, _count in top_categories:
        for rel in inventory.samples.get(cat, [])[:2]:
            suggested_files.append(f"- `{rel}`")
    if not suggested_files:
        suggested_files.append(
            "- (no obvious entry-point files — start with `/lit-search` to seed the KB)"
        )

    return f"""---
slug: {slug}
schema: vaultlab-start-here/v1
last_updated: {now}
managed_by: vaultlab.onboarding.project_init
version: 1
---

# START_HERE — {slug}

> **What this is.** vaultlab maintains this file automatically. When you (or a
> future Claude Code session) come back to this project, read this first.
> Last update: {now}.

## Topic

{intake.topic or "(unspecified)"}

## Goals

{goals}

## Audience

{audience}

## Folder inventory

{inventory_lines}

Project root: `{inventory.project_path}`

## Files to read first if resuming

{chr(10).join(suggested_files)}

## Recent activity

- **{now}** — Project onboarded via `/onboard-project`

## Open questions

(none yet — `/onboard-project` may have queued some in `decisions-log.md`)

## How vaultlab updates this

This file is auto-maintained. Every slash command that completes
meaningful work appends to "Recent activity" and refreshes "Files to
read first". Manual edits are preserved across updates.
"""


def _write_decisions_log(kb_root: Path, slug: str, intake: IntakeForm) -> Path:
    """Initialize the decisions-log.md with the onboarding entry."""
    target = ensure_parent(project_decisions_path(kb_root, slug))
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    body = f"""# Decisions log — {slug}

This file records non-obvious choices vaultlab made on your behalf.
Every slash command that takes a fork (e.g. "summarize all 30 papers
or just Tier-A?") appends a row here so you can audit the decisions
later.

## {timestamp} — Project onboarded

- **Slug:** `{slug}`
- **Topic:** {intake.topic or "(unspecified)"}
- **Goals:** {', '.join(intake.goals) if intake.goals else '(none)'}
- **Audience:** {', '.join(intake.audiences) if intake.audiences else '(none)'}
- **Why:** Initial onboarding via `/onboard-project`. Intake form
  saved at `Wiki/Projects/{slug}/intake.md`.
"""
    target.write_text(body, encoding="utf-8")
    return target


# ---------------------------------------------------------------------------
# Internal: follow-up questions
# ---------------------------------------------------------------------------


def _compose_follow_ups(
    intake: IntakeForm, inventory: FolderInventory
) -> list[str]:
    """Identify 3-5 gaps the slash command should ask about.

    Heuristics:
    - If the intake says they have wet-lab data but no data files are
      in the folder → ask where the data lives.
    - If goals include manuscript drafting but no .docx/.tex is
      present → ask for the prior-draft path.
    - If audience includes PI but no PI preferences listed → ask.
    - If exclusions are empty but goals include literature work → ask
      about year-window / preprint filters.
    - If free_form is empty and the project has >0 files → ask the
      "anything else?" question.
    """
    qs: list[str] = []

    have_keys = set(intake.have)
    has_data_files = any(c.startswith("data_") for c in inventory.counts)

    if "wet_lab_data" in have_keys and not has_data_files:
        qs.append(
            "You ticked 'Wet-lab data' on the intake — where exactly does it "
            "live? (full path, e.g. `Z:/lab/data/2026-03/`)"
        )

    drafting_goals = {"draft_manuscript_section", "build_deep_research_report"}
    if drafting_goals & set(intake.goals):
        has_manuscript = (
            inventory.counts.get("manuscript", 0) > 0
            or "prior_drafts" in have_keys
        )
        if not has_manuscript:
            qs.append(
                "You're drafting written output but I don't see a manuscript "
                "or prior draft in the folder. Want me to start from scratch, "
                "or is there a draft elsewhere I should read first?"
            )

    if "pi" in intake.audiences and not intake.pi_preferences.strip():
        qs.append(
            "Your audience includes PI — any specific preferences I should "
            "mirror? (e.g. citation style, diagram-vs-text preference)"
        )

    literature_goals = {
        "understand_literature",
        "build_journal_club_deck",
        "build_deep_research_report",
    }
    if (literature_goals & set(intake.goals)) and not intake.exclusions:
        qs.append(
            "For literature search — any year window or preprint filter? "
            "(e.g. 'last 10 years, no preprints')"
        )

    if not intake.free_form.strip() and inventory.total_files > 0:
        qs.append(
            "Anything else a smart collaborator would need to know about "
            "this project? (skip if nothing comes to mind)"
        )

    # Cap at 5; pad to 3 with a generic catch-all if we have <3
    if len(qs) < 3:
        qs.append(
            "Is there a related project or KB note vaultlab should "
            "cross-reference? (skip if not)"
        )
    return qs[:5]


# ---------------------------------------------------------------------------
# Convenience: copy the intake template into a new project folder
# ---------------------------------------------------------------------------


def copy_intake_template_to(project_path: str | Path) -> Path:
    """Drop a blank ``project_intake.md`` into ``project_path``.

    Tries the on-disk template at ``templates/project_intake.md`` first;
    falls back to the in-memory empty template from
    :func:`vaultlab.onboarding.intake.render_intake_template` so this
    works even when vaultlab is installed via pip without templates
    on disk.
    """
    from vaultlab.onboarding.intake import render_intake_template

    target = Path(project_path) / "project_intake.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    # Try the repo-relative template first
    repo_template = (
        Path(__file__).resolve().parents[3] / "templates" / "project_intake.md"
    )
    if repo_template.exists():
        shutil.copyfile(repo_template, target)
    else:
        target.write_text(render_intake_template(), encoding="utf-8")
    return target
