"""vaultlab.kb.dossier — Project dossier compilation (SPEC-N).

The project dossier is the standing mental model of an entire project —
auto-compiled, source-cited, refreshed on a cadence, loaded as Layer 0
before any non-trivial primitive. It's the answer to *"what does the
agent know about this project before doing anything?"*

Inspired by the senior-PI mental-model concept from
``conceptual-deep-dive-project-context-2026-05-08.md``: the equivalent of
a senior researcher's working narrative of a project — refreshed
continuously, always-loaded, source-cited, used as the backdrop for any
specific task.

Structure
---------
The compiled dossier is a single markdown file at::

    <kb_root>/Wiki/Projects/<project-slug>/Project-Dossier.md

with 9 canonical sections covering origin, current state, methodology
commitments, established findings, frontier questions, literature
backdrop, cross-project connections, anticipated PI/advisor questions,
and recent rolling tail.

Public API
----------
- :func:`compile_dossier` — synthesize a fresh dossier from KB sources
- :func:`load_dossier` — read the compiled dossier (with staleness check)
- :func:`dossier_path` — resolve the canonical path
- :func:`dossier_age_hours` — how long since last compile
- :class:`Dossier` — structured representation
- :class:`DossierSection` — one section of the structured form

Cadence
-------
Refresh policy (caller's responsibility):

- Daily by default (or every 24h since last compile)
- On big events: new audit-clean concept doc, new decisions-log entry,
  new lit-arc completion → :func:`compile_dossier(force=True)`
- On demand via ``/refresh-dossier`` slash command
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path

from vaultlab.kb.paths import (
    ensure_parent,
    project_decisions_path,
    project_state_path,
    slugify_topic,
)

logger = logging.getLogger(__name__)

__all__ = [
    "Dossier",
    "DossierSection",
    "DossierStateUnreadable",
    "compile_dossier",
    "dossier_age_hours",
    "dossier_archive_dir",
    "dossier_path",
    "load_dossier",
]


# Canonical section structure — order matters for the rendered file.
# Each section has a heading + a slug used for source-tracking.
_SECTION_TITLES: list[tuple[str, str]] = [
    ("origin", "Why this project exists (the origin)"),
    ("current_state", "Where we are (current state, last 2 weeks)"),
    ("methodology_commitments", "Methodology commitments"),
    ("established_findings", "Established findings (high-confidence)"),
    ("frontier", "Active frontier (open questions, last 30 days)"),
    ("literature", "Pertinent literature backdrop"),
    ("cross_project", "Cross-project connections"),
    ("anticipated_questions", "Anticipated PI / advisor questions"),
    ("recent_tail", "What changed in the last 7 days (rolling tail)"),
]


_DEFAULT_RECENT_DECISIONS_LOOKBACK_DAYS = 30
_DEFAULT_FRONTIER_LOOKBACK_DAYS = 30
_DEFAULT_ROLLING_TAIL_DAYS = 7
_DEFAULT_TOP_LITERATURE_N = 30
_DEFAULT_FRESHNESS_HOURS = 24


class DossierStateUnreadable(RuntimeError):
    """Project state can't be read for dossier compilation.

    Raised when the project's KB folder doesn't exist or required source
    files (START_HERE.md, decisions-log.md) are missing entirely. Note:
    decisions-log absent is acceptable (just produces an empty section);
    project folder missing is not.
    """


@dataclass(frozen=True)
class DossierSection:
    """One section of the project dossier.

    Attributes
    ----------
    slug
        Short identifier (e.g. ``"origin"``, ``"methodology_commitments"``).
    title
        Human-readable heading.
    body
        Markdown content (no leading heading — that's added at render time).
    sources
        List of source-file paths that contributed to this section.
    """

    slug: str
    title: str
    body: str
    sources: list[Path] = field(default_factory=list)


@dataclass(frozen=True)
class Dossier:
    """Structured project dossier.

    Attributes
    ----------
    project_slug
        Project slug (e.g. ``"metabolism"``).
    kb_root
        Resolved KB root.
    sections
        Ordered list of 9 :class:`DossierSection` instances.
    compiled_at
        UTC timestamp the dossier was compiled.
    """

    project_slug: str
    kb_root: Path
    sections: list[DossierSection]
    compiled_at: datetime

    def render(self) -> str:
        """Render the dossier as a single markdown file.

        Output structure: YAML frontmatter + level-1 heading + 9 level-2
        sections + footer with source list.
        """
        all_sources: set[Path] = set()
        for sec in self.sections:
            all_sources.update(sec.sources)

        frontmatter = (
            "---\n"
            f"title: Project Dossier — {self.project_slug}\n"
            f"type: project-dossier\n"
            f"project: {self.project_slug}\n"
            f"compiled_at: {self.compiled_at.isoformat()}\n"
            "auto_generated: true\n"
            "compiled_by: vaultlab.kb.dossier.compile_dossier\n"
            "---\n\n"
        )

        body_parts = [f"# Project Dossier — {self.project_slug}\n"]
        body_parts.append(
            "> Auto-compiled standing mental model of this project. "
            "Refreshed daily (or on big events). Loaded as Layer 0 "
            "before any non-trivial primitive.\n"
        )

        for n, section in enumerate(self.sections, start=1):
            body_parts.append(f"\n## {n}. {section.title}\n")
            body_parts.append(section.body.rstrip() + "\n")

        if all_sources:
            sources_str = "\n".join(f"- `{p}`" for p in sorted(all_sources, key=str))
            body_parts.append(
                "\n---\n\n## Sources\n\nFiles consulted during compilation:\n\n"
                + sources_str
                + "\n"
            )

        return frontmatter + "\n".join(body_parts)


# --- Public API --------------------------------------------------------------


def dossier_path(kb_root: Path, project_slug: str) -> Path:
    """Resolve the canonical dossier path for a project.

    Returns ``<kb_root>/Wiki/Projects/<slug>/Project-Dossier.md``.
    """
    return Path(kb_root) / "Wiki" / "Projects" / slugify_topic(project_slug) / "Project-Dossier.md"


def dossier_archive_dir(kb_root: Path, project_slug: str) -> Path:
    """Resolve the archive directory for old dossier versions."""
    return (
        Path(kb_root)
        / "Wiki"
        / "Projects"
        / slugify_topic(project_slug)
        / "Project-Dossier.archive"
    )


def dossier_age_hours(kb_root: Path, project_slug: str) -> float | None:
    """Return age of the current dossier in hours, or ``None`` if absent."""
    path = dossier_path(kb_root, project_slug)
    if not path.exists():
        return None
    mtime = datetime.fromtimestamp(path.stat().st_mtime)
    delta = datetime.now() - mtime
    # Clamp to zero: a just-written dossier can read a filesystem mtime a hair
    # ahead of the wall clock (timestamp granularity / clock skew), which would
    # otherwise yield a nonsensical tiny-negative age and a flaky `0 <= age` test.
    return max(0.0, delta.total_seconds() / 3600.0)


def load_dossier(kb_root: Path, project_slug: str) -> str:
    """Load the compiled dossier markdown text.

    Returns empty string if the dossier doesn't exist (caller can then
    call :func:`compile_dossier`).
    """
    path = dossier_path(kb_root, project_slug)
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def compile_dossier(
    kb_root: Path | str,
    project_slug: str,
    *,
    archive_existing: bool = True,
    freshness_hours: float = _DEFAULT_FRESHNESS_HOURS,
    force: bool = False,
) -> Dossier:
    """Compile a fresh project dossier from KB sources.

    Reads the project's START_HERE, decisions log, recent concept docs,
    Tier-A summaries, and recent outputs. Synthesizes them into the 9
    canonical sections. Writes the rendered file to disk.

    Parameters
    ----------
    kb_root
        KB root path.
    project_slug
        Project to compile for.
    archive_existing
        If a previous dossier exists, archive it to
        ``Wiki/Projects/<slug>/Project-Dossier.archive/<timestamp>.md``
        before writing the new one. Default ``True``.
    freshness_hours
        Skip recompile if the existing dossier is younger than this.
        Default 24h.
    force
        Override freshness check. Default ``False``.

    Returns
    -------
    Dossier
        Structured form (also written to disk).

    Raises
    ------
    DossierStateUnreadable
        Project folder doesn't exist (run /onboard-project first).
    """
    kb = Path(kb_root)
    proj_dir = kb / "Wiki" / "Projects" / slugify_topic(project_slug)
    if not proj_dir.exists():
        raise DossierStateUnreadable(
            f"Project folder missing at {proj_dir} — run /onboard-project "
            f"or /start-project to create it before compiling a dossier."
        )

    # Freshness check
    target = dossier_path(kb, project_slug)
    if not force and target.exists():
        age = dossier_age_hours(kb, project_slug)
        if age is not None and age < freshness_hours:
            logger.info(
                "Dossier for %s is %.1f hours old (< %s hours threshold); "
                "loading instead of recompiling. Pass force=True to override.",
                project_slug,
                age,
                freshness_hours,
            )
            return _load_existing_as_dossier(kb, project_slug)

    sections = [
        _section_origin(kb, project_slug),
        _section_current_state(kb, project_slug),
        _section_methodology(kb, project_slug),
        _section_established(kb, project_slug),
        _section_frontier(kb, project_slug),
        _section_literature(kb, project_slug),
        _section_cross_project(kb, project_slug),
        _section_anticipated(kb, project_slug),
        _section_recent_tail(kb, project_slug),
    ]

    dossier = Dossier(
        project_slug=project_slug,
        kb_root=kb,
        sections=sections,
        compiled_at=datetime.now(UTC),
    )

    if archive_existing and target.exists():
        _archive_existing_dossier(kb, project_slug)

    ensure_parent(target)
    target.write_text(dossier.render(), encoding="utf-8")
    logger.info("Compiled dossier for %s → %s", project_slug, target)

    return dossier


# --- Section compilers -------------------------------------------------------
# Each section reads its source files and produces a DossierSection.
# At v0.1, these are skeleton-style — a real LLM-driven synthesis would
# replace the body with a model call. The skeletons surface the right
# source material; downstream LLM calls (or manual edits) refine.


def _section_origin(kb: Path, slug: str) -> DossierSection:
    """Section 1: Why this project exists.

    Reads the project's intake.md (saved by /onboard-project) and the
    earliest decisions log entry. Body is a skeleton with source pointers.
    """
    sources = []
    body_parts = []

    intake = kb / "Wiki" / "Projects" / slugify_topic(slug) / "intake.md"
    if intake.exists():
        sources.append(intake)
        # Pull the first ~800 chars of the intake (the goal section)
        intake_text = intake.read_text(encoding="utf-8")
        excerpt = (
            _excerpt_section(intake_text, "Goal")
            or _excerpt_section(intake_text, "Topic")
            or intake_text[:800]
        )
        body_parts.append("From intake form:\n\n" + excerpt.strip())

    if not body_parts:
        body_parts.append(
            "_No intake.md found. Run `/onboard-project` to capture project "
            "origin so this section can be auto-filled._"
        )

    return DossierSection(
        slug="origin",
        title=_SECTION_TITLES[0][1],
        body="\n\n".join(body_parts),
        sources=sources,
    )


def _section_current_state(kb: Path, slug: str) -> DossierSection:
    """Section 2: Where we are (last 2 weeks).

    Reads the most-recent days from START_HERE.md (per the daily-brief
    convention).
    """
    sources = []
    body_parts = []

    sh = project_state_path(kb, slug)
    if sh.exists():
        sources.append(sh)
        sh_text = sh.read_text(encoding="utf-8")
        # Take the most-recent ~3000 chars (typically covers the latest 2-3 days)
        recent = sh_text[:3000].strip()
        body_parts.append(recent)
        if len(sh_text) > 3000:
            body_parts.append(f"_…truncated; see `{sh}` for full daily brief._")

    if not body_parts:
        body_parts.append("_No START_HERE.md found. Run `/onboard-project` to scaffold._")

    return DossierSection(
        slug="current_state",
        title=_SECTION_TITLES[1][1],
        body="\n\n".join(body_parts),
        sources=sources,
    )


def _section_methodology(kb: Path, slug: str) -> DossierSection:
    """Section 3: Methodology commitments — from decisions-log.md."""
    sources = []
    body_parts = []

    dec = project_decisions_path(kb, slug)
    if dec.exists():
        sources.append(dec)
        dec_text = dec.read_text(encoding="utf-8")
        # Decisions-log is chronological; take all entries (typically <10K chars)
        body_parts.append(
            "Methodology decisions logged for this project (chronological):\n\n"
            + dec_text.strip()[:5000]
        )

    if not body_parts:
        body_parts.append(
            "_No `decisions-log.md` found. Decisions get auto-appended when "
            "the agent picks methods; run a `/analyze` or `/lit-arc` session "
            "to populate._"
        )

    return DossierSection(
        slug="methodology_commitments",
        title=_SECTION_TITLES[2][1],
        body="\n\n".join(body_parts),
        sources=sources,
    )


def _section_established(kb: Path, slug: str) -> DossierSection:
    """Section 4: Established findings — concept docs + audit reports."""
    sources = []
    body_parts = []

    concepts_dir = kb / "Wiki" / "Concepts"
    if concepts_dir.exists():
        # Prefer concepts that mention the project slug, or recent ones
        recent = sorted(
            concepts_dir.glob("*.md"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )[:10]
        if recent:
            sources.extend(recent)
            entries = [
                f"- [[{p.stem}]] — {_excerpt_first_paragraph(p, max_chars=200)}" for p in recent
            ]
            body_parts.append("Top concept docs (most-recently-updated):\n\n" + "\n".join(entries))

    reports_dir = kb / "Output" / slugify_topic(slug) / "Reports"
    if reports_dir.exists():
        recent_reports = sorted(
            reports_dir.glob("*audit*.md"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )[:5]
        if recent_reports:
            sources.extend(recent_reports)
            entries = [f"- `{p.name}`" for p in recent_reports]
            body_parts.append("Recent audit reports for this project:\n\n" + "\n".join(entries))

    if not body_parts:
        body_parts.append(
            "_No concept docs or audit reports yet. Findings will appear "
            "here as `Wiki/Concepts/` and `Output/Reports/` get populated._"
        )

    return DossierSection(
        slug="established_findings",
        title=_SECTION_TITLES[3][1],
        body="\n\n".join(body_parts),
        sources=sources,
    )


def _section_frontier(kb: Path, slug: str) -> DossierSection:
    """Section 5: Active frontier — open items + grill docs."""
    sources = []
    body_parts = []

    sh = project_state_path(kb, slug)
    if sh.exists():
        sh_text = sh.read_text(encoding="utf-8")
        open_items = _excerpt_section(sh_text, "Open items") or _excerpt_section(
            sh_text, "Frontier"
        )
        if open_items:
            sources.append(sh)
            body_parts.append("Open items from START_HERE:\n\n" + open_items.strip())

    grills = (
        list((kb / "Sources" / "Notes").glob("grill-*.md"))
        if (kb / "Sources" / "Notes").exists()
        else []
    )
    grills.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    recent_grills = grills[:5]
    if recent_grills:
        sources.extend(recent_grills)
        entries = [f"- `{p.name}`" for p in recent_grills]
        body_parts.append("Recent grill docs (open design questions):\n\n" + "\n".join(entries))

    if not body_parts:
        body_parts.append(
            "_No frontier questions found. Add `## Open items` "
            "to START_HERE or write a `Sources/Notes/grill-*.md`._"
        )

    return DossierSection(
        slug="frontier",
        title=_SECTION_TITLES[4][1],
        body="\n\n".join(body_parts),
        sources=sources,
    )


def _section_literature(kb: Path, slug: str) -> DossierSection:
    """Section 6: Pertinent literature backdrop — Tier-A summaries."""
    sources = []
    body_parts = []

    summaries_dir = kb / "Wiki" / "Summaries"
    if summaries_dir.exists():
        recent = sorted(
            summaries_dir.glob("*.md"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )[:_DEFAULT_TOP_LITERATURE_N]
        if recent:
            sources.extend(recent)
            entries = []
            for p in recent:
                takeaway = _excerpt_first_paragraph(p, max_chars=160)
                entries.append(f"- [[{p.stem}]] — {takeaway}")
            body_parts.append(
                f"Top {len(recent)} Tier-A summaries (most-recently-updated):\n\n"
                + "\n".join(entries)
            )

    if not body_parts:
        body_parts.append(
            "_No `Wiki/Summaries/` found. Run `/lit-arc <topic>` to populate "
            "the literature backdrop._"
        )

    return DossierSection(
        slug="literature",
        title=_SECTION_TITLES[5][1],
        body="\n\n".join(body_parts),
        sources=sources,
    )


def _section_cross_project(kb: Path, slug: str) -> DossierSection:
    """Section 7: Cross-project connections — find-analogs cache."""
    sources = []
    body_parts = []

    # Look for find-analogs cache
    output_dir = kb / "Output" / slugify_topic(slug)
    cache_files = list(output_dir.glob("find-analogs-*.md")) if output_dir.exists() else []
    if cache_files:
        recent = sorted(cache_files, key=lambda p: p.stat().st_mtime, reverse=True)[:3]
        sources.extend(recent)
        entries = [f"- `{p.name}`" for p in recent]
        body_parts.append("Recent find-analogs results:\n\n" + "\n".join(entries))

    # List sibling projects
    projects_dir = kb / "Wiki" / "Projects"
    if projects_dir.exists():
        sibling_dirs = [
            p for p in projects_dir.iterdir() if p.is_dir() and p.name != slugify_topic(slug)
        ]
        if sibling_dirs:
            sib_names = sorted(p.name for p in sibling_dirs)[:10]
            entries = [f"- `{name}`" for name in sib_names]
            body_parts.append(
                "Sibling projects in this KB (potential analog sources):\n\n" + "\n".join(entries)
            )

    if not body_parts:
        body_parts.append(
            "_No cross-project connections cached yet. Run `/find-analogs <concept>` to discover._"
        )

    return DossierSection(
        slug="cross_project",
        title=_SECTION_TITLES[6][1],
        body="\n\n".join(body_parts),
        sources=sources,
    )


def _section_anticipated(kb: Path, slug: str) -> DossierSection:
    """Section 8: Anticipated PI / advisor questions.

    Pulls from prior expert_reviewer audit reports' expert_questions
    field. Also surfaces patterns from grill docs flagged with
    "anticipated questions" sections.
    """
    sources = []
    body_parts = []

    reports_dir = kb / "Output" / slugify_topic(slug) / "Reports"
    if reports_dir.exists():
        expert_reports = sorted(
            reports_dir.glob("*expert-reviewer*.md"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )[:3]
        questions: list[str] = []
        for p in expert_reports:
            sources.append(p)
            text = p.read_text(encoding="utf-8")
            extracted = _extract_expert_questions(text)
            questions.extend(extracted)

        if questions:
            entries = [f"- {q}" for q in questions[:8]]  # cap at 8
            body_parts.append("From prior expert-reviewer audits:\n\n" + "\n".join(entries))

    if not body_parts:
        body_parts.append(
            "_No expert-reviewer audits run yet. Run "
            "`/expert-reviewer-audit <artifact>` to populate this section._"
        )

    return DossierSection(
        slug="anticipated_questions",
        title=_SECTION_TITLES[7][1],
        body="\n\n".join(body_parts),
        sources=sources,
    )


def _section_recent_tail(kb: Path, slug: str) -> DossierSection:
    """Section 9: What changed in the last 7 days — rolling tail."""
    sources = []
    body_parts = []
    cutoff = datetime.now() - timedelta(days=_DEFAULT_ROLLING_TAIL_DAYS)

    output_dir = kb / "Output" / slugify_topic(slug)
    if output_dir.exists():
        recent = [
            p
            for p in output_dir.rglob("*.md")
            if datetime.fromtimestamp(p.stat().st_mtime) > cutoff
        ]
        recent.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        recent = recent[:15]
        if recent:
            sources.extend(recent)
            entries = []
            for p in recent:
                rel = p.relative_to(output_dir)
                date_str = datetime.fromtimestamp(p.stat().st_mtime).strftime("%Y-%m-%d")
                entries.append(f"- {date_str} — `{rel}`")
            body_parts.append(
                f"Outputs touched in last {_DEFAULT_ROLLING_TAIL_DAYS} days:\n\n"
                + "\n".join(entries)
            )

    if not body_parts:
        body_parts.append("_No recent outputs in the rolling window._")

    return DossierSection(
        slug="recent_tail",
        title=_SECTION_TITLES[8][1],
        body="\n\n".join(body_parts),
        sources=sources,
    )


# --- Helpers -----------------------------------------------------------------


def _excerpt_section(text: str, heading: str) -> str | None:
    """Extract content under a level-2 heading (case-insensitive substring)."""
    lines = text.splitlines()
    in_section = False
    section_lines: list[str] = []
    heading_lower = heading.lower()

    for line in lines:
        if line.startswith("## "):
            if in_section:
                # Hit the next ## section → end current
                break
            if heading_lower in line.lower():
                in_section = True
                continue
        elif line.startswith("# ") and in_section:
            break  # hit a new top-level section

        if in_section:
            section_lines.append(line)

    if not section_lines:
        return None
    return "\n".join(section_lines).strip()


def _excerpt_first_paragraph(path: Path, max_chars: int = 200) -> str:
    """Read the first non-frontmatter paragraph of a markdown file."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return ""

    # Skip YAML frontmatter
    if text.startswith("---\n"):
        end = text.find("\n---\n", 4)
        if end != -1:
            text = text[end + 5 :]

    # Skip leading whitespace + headings, find first paragraph
    for paragraph in text.split("\n\n"):
        para = paragraph.strip()
        if not para or para.startswith("#") or para.startswith("```"):
            continue
        # Strip wikilink/code formatting noise for a clean excerpt
        cleaned = " ".join(para.split())
        if len(cleaned) > max_chars:
            return cleaned[: max_chars - 1].rstrip() + "…"
        return cleaned

    return ""


def _extract_expert_questions(text: str) -> list[str]:
    """Pull the expert_questions field from an expert_reviewer audit JSON
    embedded in a markdown report. Falls back to scanning for question-style
    bullets if structured JSON not found."""
    questions: list[str] = []

    # Look for a JSON block
    in_json = False
    json_lines: list[str] = []
    for line in text.splitlines():
        if line.strip().startswith("```json"):
            in_json = True
            continue
        if in_json:
            if line.strip() == "```":
                in_json = False
                blob = "\n".join(json_lines)
                json_lines = []
                try:
                    parsed = json.loads(blob)
                    if isinstance(parsed, dict):
                        eq = parsed.get("expert_questions") or parsed.get("expected_questions")
                        if isinstance(eq, list):
                            questions.extend(str(q) for q in eq)
                except json.JSONDecodeError:
                    pass
                continue
            json_lines.append(line)

    # Fallback: scan for bullets ending in "?"
    if not questions:
        for line in text.splitlines():
            stripped = line.strip().lstrip("-*0123456789. ").strip()
            if stripped.endswith("?") and 10 < len(stripped) < 250:
                questions.append(stripped)

    return questions[:10]  # cap


def _archive_existing_dossier(kb: Path, project_slug: str) -> None:
    """Move the current dossier into the archive directory with a date stamp."""
    target = dossier_path(kb, project_slug)
    if not target.exists():
        return

    archive_dir = dossier_archive_dir(kb, project_slug)
    archive_dir.mkdir(parents=True, exist_ok=True)

    mtime = datetime.fromtimestamp(target.stat().st_mtime)
    archive_name = mtime.strftime("%Y-%m-%dT%H-%M-%S") + ".md"
    archive_path = archive_dir / archive_name

    target.rename(archive_path)
    logger.info("Archived prior dossier to %s", archive_path)


def _load_existing_as_dossier(kb: Path, project_slug: str) -> Dossier:
    """Construct a Dossier from an already-on-disk file (no recompile)."""
    target = dossier_path(kb, project_slug)
    text = target.read_text(encoding="utf-8")
    mtime = datetime.fromtimestamp(target.stat().st_mtime)

    # The on-disk file is what matters; just return a degenerate Dossier
    # with the rendered text in a single section. Callers that need
    # structured access should call compile_dossier(force=True).
    return Dossier(
        project_slug=project_slug,
        kb_root=kb,
        sections=[
            DossierSection(
                slug="raw",
                title="Raw dossier (loaded from disk)",
                body=text,
                sources=[target],
            )
        ],
        compiled_at=mtime,
    )
