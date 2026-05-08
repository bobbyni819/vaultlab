"""Thin invocation wrapper for SPEC-B audit roles.

Closes the integration gap surfaced in audit-report-2026-05-08 §2.1:
the SPEC-B role prompts reference journal guidelines + KB context, but
nothing auto-loads those files into the role's context. This module is
that auto-loader.

Public API
----------
``prepare_audit(role_id, artifact_path, *, project_slug=None,
                target_journal=None, kb_root=None) -> AuditPrompt``
    Loads the role + artifact + journal guidelines + KB context (when
    available) and assembles a structured invocation bundle. Raises
    :class:`AuditPreparationError` for any blocker.

``AuditPrompt`` (dataclass) — the assembled bundle a runner / Claude Code
session can hand to the LLM as system prompt + user prompt.

``aggregate_audits(reports) -> AggregatedAudit``
    Combines verdicts from multiple audit runs (e.g. journal_reviewer +
    expert_reviewer + publication_guideline_compliance on the same
    artifact) into a single per-artifact verdict.

Lineage
-------
- virtual-lab "team_lead distributes shared context" pattern (Swanson 2025)
- OpenClaw / gstack "knowledge in instructions, LLM-driven adaptation"
- vaultlab.runner.kb_context.compose_preamble (refuse-to-proceed)
- eLife two-axis rubric (significance × evidence) — for aggregation
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Mapping, Optional

import yaml

from vaultlab.roles._loader import RoleNotFoundError, load_role
from vaultlab.runner.models import Role

logger = logging.getLogger(__name__)

__all__ = [
    "AggregatedAudit",
    "AuditPreparationError",
    "AuditPrompt",
    "JOURNAL_TARGET_DEFAULTS",
    "META_AGENT_ROLES",
    "aggregate_audits",
    "available_journal_yaml",
    "load_journal_guideline_md",
    "load_journal_guideline_yaml",
    "prepare_audit",
]


# Roles that follow the SPEC-B "audit role" contract: structured-JSON output,
# eLife verdict vocabulary, KB-context-required.
META_AGENT_ROLES: tuple[str, ...] = (
    "journal_reviewer",
    "expert_reviewer",
    "adoption_evaluator",
    "publication_guideline_compliance",
)


# Map a project's target_journal value to the YAML basename in
# ``vaultlab/data/journal_guidelines/``. Per SPEC-H, Cell-family targets
# (cell, cell-systems, cell-reports, cell-reports-methods, etc.) all
# share ``cell.yaml``; same for nature-family.
JOURNAL_TARGET_DEFAULTS: Mapping[str, str] = {
    "cell": "cell",
    "cell-systems": "cell",
    "cell-reports": "cell",
    "cell-reports-methods": "cell",
    "cell-reports-medicine": "cell",
    "chem": "cell",
    "matter": "cell",
    "immunity": "cell",
    "cancer-cell": "cell",
    "neuron": "cell",
    "nature": "nature",
    "nature-methods": "nature",
    "nature-medicine": "nature",
    "nat-biotechnol": "nature",
    "elife": "elife",
    "biorxiv": "biorxiv",
}


_DEFAULT_TARGET_JOURNAL = "cell"  # most-common default for biology projects


class AuditPreparationError(RuntimeError):
    """Raised when an audit prompt can't be assembled (missing role,
    missing artifact, missing journal yaml, etc.)."""


@dataclass(frozen=True)
class AuditPrompt:
    """Assembled invocation bundle for a SPEC-B audit role.

    Attributes
    ----------
    role
        The loaded :class:`Role`.
    artifact_text
        Full text content of the artifact being audited.
    artifact_path
        Resolved path to the artifact (for logging + provenance).
    journal_yaml
        Loaded journal guideline rules dict (parsed from
        ``vaultlab/data/journal_guidelines/<basename>.yaml``).
    common_yaml
        Loaded ``_common.yaml`` (cross-cutting palette + accessibility
        rules), or empty dict if missing.
    journal_prose
        Verbatim journal-guideline prose excerpt (loaded from
        ``<kb_root>/External/journal-guidelines/<basename>.md``), or
        empty string if KB-side prose isn't available.
    target_journal
        The resolved journal slug (e.g. ``"cell-systems"``).
    project_slug
        The resolved project slug (or empty if not in a project context).
    kb_context
        Optional :class:`KbContextBundle` from
        :func:`vaultlab.runner.kb_context.compose_preamble`. ``None``
        when the project hasn't been onboarded yet.
    """

    role: Role
    artifact_text: str
    artifact_path: Path
    journal_yaml: dict
    common_yaml: dict
    journal_prose: str
    target_journal: str
    project_slug: str
    kb_context: object | None = None

    def assembled_user_prompt(self) -> str:
        """Render the user-prompt that the LLM should see.

        Concatenates the artifact + journal guideline excerpts + KB
        context preamble in the order the role's TASKS contract expects.
        Returns a single string ready to feed to the LLM.
        """
        parts: list[str] = []

        if self.kb_context is not None:
            preamble = getattr(self.kb_context, "as_text", None)
            if callable(preamble):
                parts.append("# Project KB context\n\n" + preamble())
            else:
                # KbContextBundle dataclass — render its key fields explicitly
                start_here = getattr(self.kb_context, "start_here_text", "")
                decisions = getattr(self.kb_context, "decisions_text", "")
                if start_here:
                    parts.append("# Project START_HERE\n\n" + start_here.strip())
                if decisions:
                    parts.append("# Recent decisions log\n\n" + decisions.strip())

        if self.journal_prose:
            parts.append(
                f"# Journal guidelines — {self.target_journal} (verbatim excerpt)\n\n"
                + self.journal_prose.strip()
            )

        if self.journal_yaml:
            parts.append(
                f"# Journal enforceable rules — {self.target_journal} (yaml)\n\n"
                + yaml.safe_dump(self.journal_yaml, sort_keys=False)
            )

        if self.common_yaml:
            parts.append(
                "# Cross-journal common rules (accessibility + palette)\n\n"
                + yaml.safe_dump(self.common_yaml, sort_keys=False)
            )

        parts.append(
            f"# Artifact under audit ({self.artifact_path.name})\n\n"
            + self.artifact_text
        )

        parts.append(
            "# Your task\n\n"
            f"Apply the {self.role.name} TASKS contract to the artifact above. "
            "Output ONLY the structured JSON specified by the role's "
            "output_format — no prose, no markdown fencing, no preamble."
        )

        return "\n\n---\n\n".join(parts)


@dataclass(frozen=True)
class AggregatedAudit:
    """Combined verdict across multiple audit roles on the same artifact.

    Attributes
    ----------
    artifact_path
        Path to the audited artifact.
    per_role_verdicts
        Map from role_id → verdict string (the role's own verdict field).
    aggregated_verdict
        Worst-case verdict across all roles, mapped to a common scale.
    aggregated_evidence_axis
        Worst-case evidence axis (``inadequate < incomplete < solid <
        convincing < compelling < exceptional``).
    issue_count
        Counts of issues by severity, summed across roles.
    role_count
        Number of roles aggregated.
    """

    artifact_path: Path
    per_role_verdicts: dict[str, str]
    aggregated_verdict: str
    aggregated_evidence_axis: str
    issue_count: dict[str, int]
    role_count: int


# --- Public API --------------------------------------------------------------


def prepare_audit(
    role_id: str,
    artifact_path: Path | str,
    *,
    project_slug: str | None = None,
    target_journal: str | None = None,
    kb_root: Path | str | None = None,
    load_kb_context: bool = True,
) -> AuditPrompt:
    """Assemble a complete audit-prompt bundle for a SPEC-B role.

    Parameters
    ----------
    role_id
        One of :data:`META_AGENT_ROLES`. Other role ids are accepted but
        will not have access to the SPEC-B's structured-JSON contract.
    artifact_path
        Path to the artifact being audited (deck markdown, concept doc,
        manuscript section, recipe-rendered figure, etc.).
    project_slug
        Project slug to load KB context for. If ``None``, attempts to
        resolve from the current working directory's ``.vaultlab-project.json``.
    target_journal
        Override the project's target journal. If ``None``, reads from
        the project config; falls back to ``"cell"`` for biology defaults.
    kb_root
        KB root path. If ``None``, resolved via
        :func:`vaultlab.context.resolve_kb_root`.
    load_kb_context
        Whether to attempt loading the KB context preamble. When
        ``False`` (e.g. for unit tests), returns the prompt without it.

    Returns
    -------
    AuditPrompt
        Assembled bundle ready to invoke. Use :meth:`AuditPrompt.assembled_user_prompt`
        to get the user-prompt text.

    Raises
    ------
    AuditPreparationError
        Role doesn't exist, artifact unreadable, or no journal guideline
        is available for the target journal.
    """
    artifact = Path(artifact_path)
    if not artifact.exists():
        raise AuditPreparationError(
            f"Artifact not found: {artifact_path}"
        )

    try:
        role = load_role(role_id)
    except RoleNotFoundError as exc:
        raise AuditPreparationError(f"Role not found: {role_id!r}") from exc

    artifact_text = _read_artifact(artifact)

    resolved_journal = (
        target_journal
        or _resolve_target_journal(project_slug)
        or _DEFAULT_TARGET_JOURNAL
    )
    yaml_basename = JOURNAL_TARGET_DEFAULTS.get(
        resolved_journal, resolved_journal
    )

    journal_yaml = load_journal_guideline_yaml(yaml_basename)
    common_yaml = load_journal_guideline_yaml("_common")

    # KB-side prose is keyed by display name (cell-press, nature, elife)
    prose_basename = (
        "cell-press" if yaml_basename == "cell" else yaml_basename
    )
    journal_prose = ""
    resolved_kb_root = _resolve_kb_root(kb_root)
    if resolved_kb_root is not None:
        journal_prose = load_journal_guideline_md(
            kb_root=resolved_kb_root,
            basename=prose_basename,
        )

    kb_ctx = None
    resolved_slug = project_slug or ""
    if load_kb_context and resolved_slug and resolved_kb_root is not None:
        try:
            from vaultlab.runner.kb_context import compose_preamble
            kb_ctx = compose_preamble(
                resolved_slug,
                kb_root=resolved_kb_root,
                role=role,
                return_bundle=True,
            )
        except Exception as exc:
            # KB context is best-effort; downstream role can refuse if
            # it requires preamble. Log + continue.
            logger.warning(
                "KB context preamble unavailable for project %s: %s",
                resolved_slug,
                exc,
            )

    return AuditPrompt(
        role=role,
        artifact_text=artifact_text,
        artifact_path=artifact.resolve(),
        journal_yaml=journal_yaml,
        common_yaml=common_yaml,
        journal_prose=journal_prose,
        target_journal=resolved_journal,
        project_slug=resolved_slug,
        kb_context=kb_ctx,
    )


def aggregate_audits(reports: Iterable[Mapping]) -> AggregatedAudit:
    """Combine verdicts from multiple audit reports on the same artifact.

    Each report is the parsed JSON output of a SPEC-B role. The
    aggregator computes the worst-case verdict across all roles and
    sums issue counts by severity.

    Parameters
    ----------
    reports
        Iterable of dicts, each shaped like a SPEC-B role's JSON output.
        Must contain a top-level ``"verdict"`` (or ``"would_signoff_for_paper"``
        for expert_reviewer) and either ``"issues"``, ``"concerns"``, or
        ``"friction_predicted"``. ``"evidence_axis"`` is optional.

    Returns
    -------
    AggregatedAudit

    Raises
    ------
    AuditPreparationError
        If reports is empty or no report contains an artifact reference.
    """
    reports_list = list(reports)
    if not reports_list:
        raise AuditPreparationError("aggregate_audits requires ≥1 report")

    artifact_paths = {
        Path(r["figure_path"]) for r in reports_list if "figure_path" in r
    }
    artifact_paths.update(
        Path(r["target_artifact"]) for r in reports_list if "target_artifact" in r
    )
    artifact_path = (
        next(iter(artifact_paths)) if artifact_paths else Path("<unknown>")
    )

    per_role: dict[str, str] = {}
    issue_count: dict[str, int] = {"fail": 0, "major": 0, "minor": 0, "style": 0}
    evidence_axes: list[str] = []

    for r in reports_list:
        role_label = (
            r.get("_role")
            or r.get("role")
            or r.get("verdict_source")
            or "unknown"
        )

        # Verdict can come from any of these keys depending on the role
        verdict = (
            r.get("verdict")
            or r.get("verdict_journal_style")
            or _expert_reviewer_verdict(r)
            or "unknown"
        )
        per_role[role_label] = verdict

        # Collect issues from any of the known list-keys
        for key in ("issues", "concerns", "friction_predicted", "checks"):
            for issue in r.get(key, []) or []:
                if not isinstance(issue, dict):
                    continue
                # publication_guideline_compliance uses "result" instead of "severity"
                sev = (issue.get("severity") or issue.get("result") or "").lower()
                if sev == "fail":
                    issue_count["fail"] += 1
                elif sev == "major":
                    issue_count["major"] += 1
                elif sev == "warn":
                    issue_count["minor"] += 1
                elif sev == "minor":
                    issue_count["minor"] += 1
                elif sev == "style":
                    issue_count["style"] += 1

        if "evidence_axis" in r:
            evidence_axes.append(str(r["evidence_axis"]).lower())

    aggregated_verdict = _worst_case_verdict(per_role.values(), issue_count)
    aggregated_evidence = (
        _worst_case_evidence(evidence_axes) if evidence_axes else "n/a"
    )

    return AggregatedAudit(
        artifact_path=artifact_path,
        per_role_verdicts=per_role,
        aggregated_verdict=aggregated_verdict,
        aggregated_evidence_axis=aggregated_evidence,
        issue_count=issue_count,
        role_count=len(reports_list),
    )


def available_journal_yaml() -> list[str]:
    """List the journal yaml basenames available in the bundle."""
    return sorted(p.stem for p in _journal_yaml_dir().glob("*.yaml"))


def load_journal_guideline_yaml(basename: str) -> dict:
    """Load ``vaultlab/data/journal_guidelines/<basename>.yaml`` as dict.

    Returns an empty dict if the file is missing.
    """
    path = _journal_yaml_dir() / f"{basename}.yaml"
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        loaded = yaml.safe_load(f) or {}
    return loaded if isinstance(loaded, dict) else {}


def load_journal_guideline_md(
    *,
    kb_root: Path,
    basename: str,
) -> str:
    """Load ``<kb_root>/External/journal-guidelines/<basename>.md`` as text.

    Returns an empty string if the file is missing (KB may not have the
    External docs synced yet — that's fine, the yaml rules are
    sufficient for deterministic checks).
    """
    path = Path(kb_root) / "External" / "journal-guidelines" / f"{basename}.md"
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


# --- Internals ---------------------------------------------------------------


def _journal_yaml_dir() -> Path:
    """Resolve the bundled journal-guidelines yaml directory."""
    # vaultlab/src/vaultlab/roles/_invoke.py → ../data/journal_guidelines/
    return Path(__file__).resolve().parent.parent / "data" / "journal_guidelines"


def _read_artifact(artifact: Path) -> str:
    """Read an artifact for audit. PDFs / pptx / images return a marker."""
    suffix = artifact.suffix.lower()
    if suffix in (".md", ".txt", ".yaml", ".yml", ".json", ".py"):
        return artifact.read_text(encoding="utf-8")
    if suffix in (".png", ".jpg", ".jpeg", ".pdf", ".pptx", ".docx", ".eps", ".tiff"):
        # Image / binary artifact — runner needs to handle vision / parse
        return (
            f"<binary-artifact path={artifact} suffix={suffix}>\n"
            f"Auditor must use vision / binary-aware tools to read this."
        )
    # Unknown text format — best-effort text read
    try:
        return artifact.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return f"<binary-artifact path={artifact} suffix={suffix}>"


def _resolve_target_journal(project_slug: str | None) -> str | None:
    """Best-effort resolve target_journal from the project config.

    Returns None if config can't be located (caller falls back to
    :data:`_DEFAULT_TARGET_JOURNAL`).
    """
    if not project_slug:
        return None
    try:
        from vaultlab.onboarding.config import load_project_config_from_cwd
    except ImportError:
        return None

    try:
        cfg = load_project_config_from_cwd()
    except Exception:
        return None

    if cfg is None:
        return None
    extras = getattr(cfg, "voice", None) or {}
    if isinstance(extras, dict):
        candidate = extras.get("target_journal")
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip().lower()
    return None


def _resolve_kb_root(kb_root: Path | str | None) -> Path | None:
    """Best-effort resolve KB root."""
    if kb_root is not None:
        return Path(kb_root)
    try:
        from vaultlab.context import resolve_kb_root
    except ImportError:
        return None
    try:
        return resolve_kb_root()
    except Exception:
        return None


def _expert_reviewer_verdict(report: Mapping) -> str | None:
    """Synthesize an expert-reviewer verdict from its two-axis bool fields."""
    g = report.get("would_signoff_for_grant")
    p = report.get("would_signoff_for_paper")
    if g is None and p is None:
        return None
    if g and p:
        return "ship"
    if g and not p:
        return "ship_with_revisions"
    return "needs_major_revision"


# Worst-case ordering for verdict + evidence axis. Ordered worst → best
# so :func:`_worst_case` picks the lowest-ranked entry.
_VERDICT_RANK = {
    "reject": 0,
    "fail": 1,
    "bounce_risk": 1,
    "needs_major_revision": 2,
    "needs_minor_revision": 3,
    "ship_with_revisions": 4,
    "ship": 5,
    "unknown": 0,
}

_EVIDENCE_RANK = {
    "inadequate": 0,
    "incomplete": 1,
    "solid": 2,
    "convincing": 3,
    "compelling": 4,
    "exceptional": 5,
    "n/a": 6,
}


def _worst_case_verdict(
    verdicts: Iterable[str],
    issue_count: dict[str, int],
) -> str:
    """Pick the lowest-ranked verdict across roles, with issue-count override.

    If the per-role verdicts all say "ship" but the issue counts contain
    a fail or major issue, downgrade — this catches roles that report
    issues but mis-rate their own verdict.
    """
    worst = "ship"
    worst_rank = _VERDICT_RANK[worst]
    for v in verdicts:
        v_low = v.lower() if v else "unknown"
        rank = _VERDICT_RANK.get(v_low, 0)
        if rank < worst_rank:
            worst = v_low
            worst_rank = rank

    # Issue-count override
    if issue_count.get("fail", 0) > 0 and worst_rank > _VERDICT_RANK["needs_major_revision"]:
        return "needs_major_revision"
    if issue_count.get("major", 0) > 0 and worst_rank > _VERDICT_RANK["needs_minor_revision"]:
        return "needs_minor_revision"
    return worst


def _worst_case_evidence(axes: Iterable[str]) -> str:
    """Pick the lowest-ranked evidence axis (closer to "inadequate")."""
    worst = "exceptional"
    worst_rank = _EVIDENCE_RANK[worst]
    for a in axes:
        a_low = a.lower() if a else "n/a"
        rank = _EVIDENCE_RANK.get(a_low, 6)
        if rank < worst_rank:
            worst = a_low
            worst_rank = rank
    return worst
