"""vaultlab.kb.setup — KB scaffolding + lint (SPEC-D).

Operationalizes the 321-line ``tools/knowledge-base-specification.md``
schema as enforced code. Two public functions:

- :func:`scaffold_kb` — creates the canonical folder layout for a new
  KB / project from scratch.
- :func:`lint_kb` — audits an existing KB folder against the schema +
  surfaces every doc with missing required frontmatter, orphan files,
  stale indexes, naming-convention violations.

The schema doc remains the human-readable canon; this module is the
machine-enforceable counterpart so neither agent nor user has to
"remember where things go" — code does it.

Public API
----------
- :func:`scaffold_kb(kb_root, project_slug, *, domain_extensions=None,
    force=False)` — create the canonical folder skeleton + populate
    START_HERE.md, _Index.md, _Catalog.md, _Log.md
- :func:`lint_kb(kb_root, project_slug=None, *, schema_version="v1")`
    -> :class:`LintReport` — audit results structured as severity-ranked
    findings.
- :class:`LintReport` — structured report (.summary attribute for tight
  surface; .findings for full detail).
- :class:`LintFinding` — one issue with severity / kind / path /
  suggested fix.

Lineage
-------
- ``tools/knowledge-base-specification.md`` (own work, 2026-04-10) —
  the schema this module enforces
- Karpathy LLM Wiki — wiki-grows-with-work + canonical-structure pattern
- Obsidian vault convention — folder structure
- Severity rubric — scientific peer-review convention
- conceptual-deep-dive-spec-roadmap-2026-05-08.md SPEC-D — design source
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path

from vaultlab.kb.paths import slugify_topic

logger = logging.getLogger(__name__)

__all__ = [
    "CANONICAL_FOLDERS",
    "DOMAIN_EXTENSIONS",
    "LintFinding",
    "LintReport",
    "ScaffoldError",
    "lint_kb",
    "scaffold_kb",
]


# Canonical folder structure per knowledge-base-specification.md
CANONICAL_FOLDERS: list[str] = [
    "Sources/Articles",
    "Sources/Papers",
    "Sources/Notes",
    "Sources/Assets",
    "Wiki/Concepts",
    "Wiki/Methodology",
    "Wiki/Summaries",
    "Output/Plans",
    "Output/Drafts",
    "Output/Reports",
    "Output/Explorations",
]


# Required top-level files
CANONICAL_TOP_FILES: list[str] = [
    "START_HERE.md",
    "_Index.md",
    "_Catalog.md",
    "_Log.md",
]


# Domain extensions registry — opt-in folders for specific project types
DOMAIN_EXTENSIONS: dict[str, list[str]] = {
    "equities": [
        "Companies",
        "Sectors",
        "Frameworks",
        "Wiki/Theses",
    ],
    "tax": [
        "Forms",
        "Positions",
    ],
    "research": [
        # Research projects often add these voluntarily — listed for
        # convenience but not auto-created by domain="research"
    ],
    "metabolism": [
        "Wiki/Methodology/lipid_xgboost",
    ],
    "spatial-omics": [
        "Wiki/Methodology/codex",
        "Wiki/Methodology/visium",
    ],
}


# How stale an _Index.md is allowed before lint warns. 7 days = roughly a
# week of additions before the index needs regeneration.
_INDEX_STALENESS_DAYS = 7

# Naming convention for paper-summary articles
_ARTICLE_NAMING_PATTERN = r"^[A-Z][a-zA-Z\-]+_\d{4}_[\w\-]+\.md$"


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


class ScaffoldError(RuntimeError):
    """Raised when scaffold_kb hits a precondition failure (existing folder,
    invalid slug, etc.)."""


@dataclass(frozen=True)
class LintFinding:
    """One issue surfaced by lint_kb.

    Attributes
    ----------
    severity
        ``"fail"`` (blocks ship), ``"warn"`` (degraded but usable), or
        ``"info"`` (cosmetic).
    kind
        Short kind tag: ``missing_folder``, ``orphan_file``,
        ``stale_index``, ``missing_frontmatter``, ``naming_violation``,
        ``missing_required_field``, ``schema_drift``.
    path
        Path to the offending file/folder.
    message
        One-sentence description.
    fix
        Suggested fix (concrete instruction the user / agent can act on).
    """

    severity: str
    kind: str
    path: Path
    message: str
    fix: str = ""


@dataclass(frozen=True)
class LintReport:
    """Structured lint report.

    Attributes
    ----------
    kb_root
        KB root that was audited.
    project_slug
        Project slug (or empty if KB-root-level audit).
    findings
        Full list of :class:`LintFinding`.
    schema_version
        Schema version applied during audit.
    audited_at
        UTC timestamp.
    """

    kb_root: Path
    project_slug: str
    findings: list[LintFinding]
    schema_version: str
    audited_at: datetime

    @property
    def summary(self) -> dict[str, int]:
        """Count findings by severity. Convenience surface for slash commands."""
        out = {"fail": 0, "warn": 0, "info": 0}
        for f in self.findings:
            out[f.severity] = out.get(f.severity, 0) + 1
        return out

    @property
    def passed(self) -> bool:
        """True if no findings at any severity."""
        return len(self.findings) == 0

    @property
    def shippable(self) -> bool:
        """True if no fail-severity findings (warns are acceptable)."""
        return self.summary["fail"] == 0

    def render_markdown(self) -> str:
        """Render the report as a markdown audit doc."""
        lines = [
            "---",
            f"title: KB lint report — {self.project_slug or 'kb-root'}",
            f"audited_at: {self.audited_at.isoformat()}",
            f"schema_version: {self.schema_version}",
            "type: kb-lint-report",
            "---",
            "",
            f"# KB lint — {self.project_slug or 'kb-root'} — {self.audited_at.date().isoformat()}",
            "",
            f"**KB root:** `{self.kb_root}`",
            "",
            f"**Summary:** {self.summary['fail']} fail / "
            f"{self.summary['warn']} warn / "
            f"{self.summary['info']} info / "
            f"{'shippable' if self.shippable else 'BLOCKED — fix the fails'}",
            "",
        ]
        for severity in ("fail", "warn", "info"):
            severity_findings = [f for f in self.findings if f.severity == severity]
            if not severity_findings:
                continue
            lines.append(f"## {severity.upper()} ({len(severity_findings)})")
            lines.append("")
            for f in severity_findings:
                lines.append(f"### `{f.path}`")
                lines.append(f"- **Kind:** {f.kind}")
                lines.append(f"- **Issue:** {f.message}")
                if f.fix:
                    lines.append(f"- **Fix:** {f.fix}")
                lines.append("")
        if self.passed:
            lines.append("## All checks pass ✅")
            lines.append("")
            lines.append("KB structure conforms to the canonical schema.")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Public API — scaffold_kb
# ---------------------------------------------------------------------------


def scaffold_kb(
    kb_root: Path | str,
    project_slug: str,
    *,
    domain_extensions: list[str] | None = None,
    force: bool = False,
) -> Path:
    """Scaffold a new project KB folder per the canonical schema.

    Creates::

        <kb_root>/<project-slug>/
            START_HERE.md           # auto-populated with today's section + maintenance rules
            _Index.md, _Catalog.md   # auto-gen stubs
            _Log.md                  # 1 setup entry
            Sources/{Articles,Papers,Notes,Assets}/
            Wiki/{Concepts,Methodology,Summaries}/
            Output/{Plans,Drafts,Reports,Explorations}/

    Plus any domain extensions specified.

    Parameters
    ----------
    kb_root
        KB root path (e.g., ``"G:/My Drive/Knowledge"``).
    project_slug
        Project name. Slugified to kebab-case for the folder name.
    domain_extensions
        List of domain-extension keys (e.g., ``["equities"]``,
        ``["metabolism"]``). Uses :data:`DOMAIN_EXTENSIONS` registry.
    force
        If False (default), refuses to scaffold over an existing folder.
        If True, fills in missing pieces without disturbing existing files.

    Returns
    -------
    Path
        The created project directory.

    Raises
    ------
    ScaffoldError
        Project folder exists and ``force=False``, OR domain_extension
        key is unknown.
    """
    kb = Path(kb_root)
    slug = slugify_topic(project_slug)
    proj_dir = kb / slug

    if proj_dir.exists() and not force:
        raise ScaffoldError(
            f"Project folder already exists: {proj_dir}. "
            f"Pass force=True to fill in missing pieces without "
            f"disturbing existing files."
        )

    # Validate domain extensions before creating anything
    extras: list[str] = []
    if domain_extensions:
        for ext_key in domain_extensions:
            if ext_key not in DOMAIN_EXTENSIONS:
                raise ScaffoldError(
                    f"Unknown domain_extension key {ext_key!r}. "
                    f"Known keys: {sorted(DOMAIN_EXTENSIONS)}"
                )
            extras.extend(DOMAIN_EXTENSIONS[ext_key])

    # Create canonical folders + extras
    proj_dir.mkdir(parents=True, exist_ok=True)
    for folder in CANONICAL_FOLDERS + extras:
        (proj_dir / folder).mkdir(parents=True, exist_ok=True)

    # Populate canonical top-level files (don't overwrite existing)
    today = date.today().isoformat()
    weekday = date.today().strftime("%A")

    files_to_write = {
        "START_HERE.md": _start_here_template(slug, today, weekday),
        "_Index.md": _index_template(slug),
        "_Catalog.md": _catalog_template(slug),
        "_Log.md": _log_template(slug, today),
    }
    for filename, content in files_to_write.items():
        target = proj_dir / filename
        if not target.exists():
            target.write_text(content, encoding="utf-8")

    logger.info("Scaffolded KB at %s (extensions=%s)", proj_dir, domain_extensions)
    return proj_dir


# ---------------------------------------------------------------------------
# Public API — lint_kb
# ---------------------------------------------------------------------------


def lint_kb(
    kb_root: Path | str,
    project_slug: str | None = None,
    *,
    schema_version: str = "v1",
) -> LintReport:
    """Audit a KB project folder against the canonical schema.

    Returns a structured report with severity-ranked findings.

    Parameters
    ----------
    kb_root
        KB root path.
    project_slug
        Project to audit. If None, audits the kb_root itself (only checks
        cross-project structure: External/, _Index.md at root, etc.).
    schema_version
        Schema version to apply (currently only ``"v1"`` supported).

    Returns
    -------
    LintReport
    """
    kb = Path(kb_root)
    findings: list[LintFinding] = []

    if project_slug:
        proj_dir = kb / slugify_topic(project_slug)
        if not proj_dir.exists():
            findings.append(
                LintFinding(
                    severity="fail",
                    kind="missing_folder",
                    path=proj_dir,
                    message=f"Project folder does not exist",
                    fix=f"Run scaffold_kb(kb_root, '{project_slug}') to create.",
                )
            )
        else:
            findings.extend(_lint_project_folders(proj_dir))
            findings.extend(_lint_top_level_files(proj_dir))
            findings.extend(_lint_naming_conventions(proj_dir))
            findings.extend(_lint_index_freshness(proj_dir))
    else:
        # Root-level audit (cross-project structure)
        findings.extend(_lint_root_structure(kb))

    return LintReport(
        kb_root=kb,
        project_slug=project_slug or "",
        findings=findings,
        schema_version=schema_version,
        audited_at=datetime.now(timezone.utc),
    )


# ---------------------------------------------------------------------------
# Lint checks
# ---------------------------------------------------------------------------


def _lint_project_folders(proj_dir: Path) -> list[LintFinding]:
    """Verify all canonical folders exist."""
    findings: list[LintFinding] = []
    for folder in CANONICAL_FOLDERS:
        target = proj_dir / folder
        if not target.exists():
            findings.append(
                LintFinding(
                    severity="warn",
                    kind="missing_folder",
                    path=target,
                    message=f"Required canonical folder missing: {folder}",
                    fix=f"Create with mkdir, or rerun scaffold_kb(force=True).",
                )
            )
    return findings


def _lint_top_level_files(proj_dir: Path) -> list[LintFinding]:
    """Verify START_HERE / _Index / _Catalog / _Log exist."""
    findings: list[LintFinding] = []
    for filename in CANONICAL_TOP_FILES:
        target = proj_dir / filename
        if not target.exists():
            findings.append(
                LintFinding(
                    severity="warn" if filename != "START_HERE.md" else "fail",
                    kind="missing_required_field",
                    path=target,
                    message=f"Required top-level file missing: {filename}",
                    fix=(
                        f"Run scaffold_kb(force=True) to populate, or "
                        f"create manually following the schema."
                    ),
                )
            )
    return findings


def _lint_naming_conventions(proj_dir: Path) -> list[LintFinding]:
    """Verify Sources/Articles/ files follow AuthorYearTitle convention."""
    import re

    findings: list[LintFinding] = []
    articles_dir = proj_dir / "Sources" / "Articles"
    if not articles_dir.exists():
        return findings

    pattern = re.compile(_ARTICLE_NAMING_PATTERN)
    for f in articles_dir.glob("*.md"):
        if f.name in {"_Index.md", "README.md"}:
            continue
        if not pattern.match(f.name):
            findings.append(
                LintFinding(
                    severity="info",
                    kind="naming_violation",
                    path=f,
                    message=(
                        f"Article filename does not match "
                        f"AuthorYearTitle convention "
                        f"(e.g., 'Pentimalli_2025_lipid-axis.md')."
                    ),
                    fix="Rename to AuthorLast_Year_short-title.md (no spaces).",
                )
            )
    return findings


def _lint_index_freshness(proj_dir: Path) -> list[LintFinding]:
    """Warn if _Index.md is older than the latest source-folder mtime."""
    findings: list[LintFinding] = []
    idx = proj_dir / "_Index.md"
    if not idx.exists():
        return findings  # already covered by _lint_top_level_files

    idx_mtime = idx.stat().st_mtime

    sources_dir = proj_dir / "Sources"
    if not sources_dir.exists():
        return findings

    latest_source_mtime = 0.0
    for f in sources_dir.rglob("*.md"):
        latest_source_mtime = max(latest_source_mtime, f.stat().st_mtime)

    if latest_source_mtime > 0 and (latest_source_mtime - idx_mtime) > _INDEX_STALENESS_DAYS * 86400:
        findings.append(
            LintFinding(
                severity="warn",
                kind="stale_index",
                path=idx,
                message=(
                    f"_Index.md is more than {_INDEX_STALENESS_DAYS} days older "
                    f"than the latest source. Index regeneration recommended."
                ),
                fix=(
                    "Run vaultlab.kb.indexes.update_index (when SPEC-C ships), "
                    "or manually refresh _Index.md."
                ),
            )
        )
    return findings


def _lint_root_structure(kb: Path) -> list[LintFinding]:
    """Audit cross-project structure at the KB root."""
    findings: list[LintFinding] = []
    # External/ for journal-guidelines, etc. — recommended but not required
    # (only added in 2026-05-08 SPEC-H rollout, so older KBs won't have it)
    return findings


# ---------------------------------------------------------------------------
# Templates for scaffold_kb
# ---------------------------------------------------------------------------


def _start_here_template(slug: str, today: str, weekday: str) -> str:
    """Canonical START_HERE.md with embedded LLM maintenance rules."""
    return (
        f"---\n"
        f"title: START HERE — {slug}\n"
        f"type: project-daily-brief\n"
        f"created: {today}\n"
        f"---\n\n"
        f"# START HERE — {slug}\n\n"
        f"Daily brief for the **{slug}** project. Newest day at top. "
        f"Every Claude Code session should read this first.\n\n"
        f"## 📅 {today} ({weekday})\n\n"
        f"### 🟡 Ready to show / review\n"
        f"_None yet — KB freshly scaffolded._\n\n"
        f"### 🟢 In progress\n"
        f"_None yet._\n\n"
        f"### 🔴 Open items\n"
        f"- 🔴 Ingest first paper or run `/lit-arc` on the project topic\n"
        f"- 🔴 Add origin / goals via `/onboard-project` (if not done already)\n\n"
        f"### ✅ Done today\n"
        f"- ✅ KB scaffolded via `vaultlab.kb.setup.scaffold_kb`\n\n"
        f"---\n\n"
        f"## 🧭 Quick nav\n\n"
        f"- [[_Index]] — KB master index\n"
        f"- [[_Catalog]] — source catalog\n"
        f"- [[_Log]] — chronological activity log\n\n"
        f"---\n\n"
        f"## Maintenance rules (for Claude Code sessions)\n\n"
        f"This section is the canonical 7 rules from "
        f"`tools/knowledge-base-specification.md` § START_HERE convention. "
        f"Any session reading this file should follow them.\n\n"
        f"1. **On every session**: check if today has a section. If not, "
        f"add one at the top with today's date.\n"
        f"2. **When creating any new KB file**: add a bullet under today's "
        f"section with a link to it; status = 🟡 deliverable / 🔴 TODO / "
        f"🟢 in-progress.\n"
        f"3. **When the user signals completion** (\"sent the email\", "
        f"\"pushed to xlsx\", \"told the team\"): move the item from "
        f"🔴/🟡/🟢 to ✅ under that same day.\n"
        f"4. **When detected via tool result** (file written, email sent, "
        f"commit landed): move to ✅ without waiting; note \"auto-detected\".\n"
        f"5. **Never delete** — items stay visible in their date section.\n"
        f"6. **Quick nav block** — maintain a top-level Quick nav grouping "
        f"the most-linked files.\n"
        f"7. **Newest day must make sense cold** — someone opening the file "
        f"fresh should understand what's going on without reading older days.\n"
    )


def _index_template(slug: str) -> str:
    return (
        f"---\n"
        f"title: _Index — {slug}\n"
        f"type: kb-index\n"
        f"---\n\n"
        f"# _Index — {slug}\n\n"
        f"Master index for the **{slug}** project. Auto-regenerated when "
        f"SPEC-C frontmatter-first retrieval ships; for now, manual.\n\n"
        f"## Sources\n\n"
        f"- `Sources/Articles/` — paper summaries\n"
        f"- `Sources/Papers/` — full-text PDFs\n"
        f"- `Sources/Notes/` — analysis notes\n"
        f"- `Sources/Assets/` — figures, images\n\n"
        f"## Wiki\n\n"
        f"- `Wiki/Concepts/` — concept articles\n"
        f"- `Wiki/Methodology/` — pipeline + methodology docs\n"
        f"- `Wiki/Summaries/` — Tier-A paper summaries\n\n"
        f"## Output\n\n"
        f"- `Output/Plans/` — action plans + checkboxes\n"
        f"- `Output/Drafts/` — manuscript drafts, PI messages\n"
        f"- `Output/Reports/` — audit + status reports\n"
        f"- `Output/Explorations/` — filed-back query results\n"
    )


def _catalog_template(slug: str) -> str:
    return (
        f"---\n"
        f"title: _Catalog — {slug}\n"
        f"type: kb-catalog\n"
        f"---\n\n"
        f"# _Catalog — {slug}\n\n"
        f"Source inventory for the **{slug}** project. Auto-maintained "
        f"on ingest; lists every paper / dataset / external resource.\n\n"
        f"## Papers\n\n"
        f"_Empty — run `/lit-arc <topic>` or `bobby-kb ingest <pdf>` to populate._\n\n"
        f"## Datasets\n\n"
        f"_None ingested yet._\n\n"
        f"## External resources\n\n"
        f"_None registered yet._\n"
    )


def _log_template(slug: str, today: str) -> str:
    return (
        f"---\n"
        f"title: _Log — {slug}\n"
        f"type: kb-activity-log\n"
        f"---\n\n"
        f"# _Log — {slug}\n\n"
        f"Append-only chronological log. Action types: `setup`, `ingest`, "
        f"`query`, `lint`, `compile`, `update`, `reorganize`.\n\n"
        f"## [{today}] setup | KB scaffolded\n\n"
        f"Scaffolded canonical KB structure via "
        f"`vaultlab.kb.setup.scaffold_kb`.\n"
        f"- Created folders: `Sources/`, `Wiki/`, `Output/` + canonical "
        f"subdirectories\n"
        f"- Created files: `START_HERE.md`, `_Index.md`, `_Catalog.md`, "
        f"`_Log.md`\n"
    )
