"""Reviewer-perspective manuscript preflight gate."""

from __future__ import annotations

import tempfile
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from vaultlab.figures.understand.visual_qa import (
    VisualQAFinding,
    VisualQAResult,
    visual_qa_figure,
)
from vaultlab.manuscript.claim_ledger import ClaimLedger, LedgerAudit
from vaultlab.manuscript.figure_text_consistency import (
    ConsistencyReport,
    check_figure_text_consistency,
)
from vaultlab.roles._invoke import (
    AggregatedAudit,
    AuditPreparationError,
    AuditPrompt,
    aggregate_audits,
    prepare_audit,
)

FixSeverity = Literal["error", "warning", "info"]

DEFAULT_REVIEWER_ROLES: tuple[str, ...] = (
    "rigor_auditor",
    "methods_critic",
    "journal_reviewer",
    "expert_reviewer",
    "publication_guideline_compliance",
    "figure_reader",
)

_SEVERITY_RANK: dict[FixSeverity, int] = {"error": 0, "warning": 1, "info": 2}


@dataclass(frozen=True)
class FixItem:
    """One unified reviewer fix queue item."""

    source: str
    severity: FixSeverity
    message: str
    where: str | None = None
    fix: str | None = None

    def to_dict(self) -> dict[str, str]:
        payload = {
            "source": self.source,
            "severity": self.severity,
            "message": self.message,
        }
        if self.where is not None:
            payload["where"] = self.where
        if self.fix is not None:
            payload["fix"] = self.fix
        return payload


@dataclass(frozen=True)
class PreparedRolePass:
    """A reviewer-role audit prompt prepared for optional execution."""

    role_id: str
    prompt: AuditPrompt | None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "role_id": self.role_id,
            "prepared": self.prompt is not None,
            "artifact_path": str(self.prompt.artifact_path) if self.prompt is not None else None,
            "target_journal": self.prompt.target_journal if self.prompt is not None else None,
            "error": self.error,
        }


@dataclass(frozen=True)
class ManuscriptPreflightReport:
    """Combined deterministic and reviewer-role manuscript preflight result."""

    ok: bool
    fix_queue: list[FixItem]
    ledger_audit: LedgerAudit
    consistency: ConsistencyReport
    visual_qa: list[VisualQAResult]
    prepared_roles: list[PreparedRolePass]
    aggregated: AggregatedAudit | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "fix_queue": [item.to_dict() for item in self.fix_queue],
            "ledger_audit": self.ledger_audit.to_dict(),
            "consistency": self.consistency.to_dict(),
            "visual_qa": [result.to_dict() for result in self.visual_qa],
            "prepared_roles": [role.to_dict() for role in self.prepared_roles],
            "aggregated": _aggregated_to_dict(self.aggregated),
        }

    def to_markdown(self) -> str:
        counts = _counts_by_severity(self.fix_queue)
        lines = [
            "# Manuscript Preflight Report",
            "",
            f"- **Overall:** {'PASS' if self.ok else 'FIX REQUIRED'}",
            (
                "- **Fix queue:** "
                f"{counts['error']} error, {counts['warning']} warning, {counts['info']} info"
            ),
            f"- **Prepared reviewer roles:** {len(self.prepared_roles)}",
            (
                "- **Aggregated reviewer audit:** "
                + (
                    self.aggregated.aggregated_verdict
                    if self.aggregated is not None
                    else "not run"
                )
            ),
            "",
            "## Ranked fix queue",
            "",
        ]
        if self.fix_queue:
            for item in self.fix_queue:
                where = f" `{item.where}`" if item.where else ""
                fix = f" Fix: {item.fix}" if item.fix else ""
                lines.append(
                    f"- `{item.severity.upper()}` `{item.source}`{where}: {item.message}{fix}"
                )
        else:
            lines.append("- No fixes were detected by the enabled checks.")

        lines.extend(["", "## Reviewer role passes", ""])
        if self.prepared_roles:
            for role in self.prepared_roles:
                if role.prompt is None:
                    lines.append(f"- `{role.role_id}`: not prepared. {role.error}")
                else:
                    lines.append(
                        f"- `{role.role_id}`: prepared for `{role.prompt.artifact_path}` "
                        f"targeting `{role.prompt.target_journal}`."
                    )
        else:
            lines.append("- No reviewer roles were requested.")

        lines.extend(["", "## Deterministic backbone", ""])
        lines.append(f"- Claim ledger: {'pass' if self.ledger_audit.ok else 'fix required'}")
        lines.append(f"- Figure-text consistency: {'pass' if self.consistency.ok else 'fix required'}")
        lines.append(f"- Visual QA figures checked: {len(self.visual_qa)}")
        return "\n".join(lines).rstrip() + "\n"


def run_manuscript_preflight(
    manuscript_md: str,
    *,
    ledger: ClaimLedger | None = None,
    artifact_path: Path | str | None = None,
    figures_dir: Path | str | None = None,
    coverage_dir: Path | str | None = None,
    roles: list[str] | None = None,
    project_slug: str | None = None,
    target_journal: str | None = None,
    kb_root: Path | str | None = None,
    run_visual_qa: bool = False,
    executor: Callable[[AuditPrompt], Mapping[str, Any]] | None = None,
) -> ManuscriptPreflightReport:
    """Run deterministic checks and prepare optional reviewer-role passes."""

    active_ledger = ledger if ledger is not None else ClaimLedger.from_markdown(manuscript_md)
    figures_root = Path(figures_dir) if figures_dir is not None else None
    coverage_root = Path(coverage_dir) if coverage_dir is not None else None

    ledger_audit = active_ledger.audit(coverage_dir=coverage_root)
    consistency = check_figure_text_consistency(
        manuscript_md,
        ledger=active_ledger,
        figures_dir=figures_root,
        coverage_dir=coverage_root,
    )

    fix_queue: list[FixItem] = []
    fix_queue.extend(_fix_items_from_ledger(ledger_audit))
    fix_queue.extend(_fix_items_from_consistency(consistency))

    visual_results = _run_visual_qa(figures_root, run_visual_qa=run_visual_qa)
    fix_queue.extend(_fix_items_from_visual_qa(visual_results))

    role_ids = DEFAULT_REVIEWER_ROLES if roles is None else tuple(roles)
    prepared_roles, role_prepare_items, artifact = _prepare_roles(
        manuscript_md,
        artifact_path=artifact_path,
        role_ids=role_ids,
        project_slug=project_slug,
        target_journal=target_journal,
        kb_root=kb_root,
    )
    fix_queue.extend(role_prepare_items)

    aggregated: AggregatedAudit | None = None
    if executor is None:
        fix_queue.extend(
            FixItem(
                source=f"role:{prepared.role_id}",
                severity="info",
                message=f"{prepared.role_id} review prepared - run to complete preflight",
            )
            for prepared in prepared_roles
            if prepared.prompt is not None
        )
    else:
        role_reports: list[Mapping[str, Any]] = []
        for prepared in prepared_roles:
            if prepared.prompt is None:
                continue
            try:
                report = executor(prepared.prompt)
            except Exception as exc:
                fix_queue.append(
                    FixItem(
                        source=f"role:{prepared.role_id}",
                        severity="warning",
                        message=f"role {prepared.role_id} executor failed: {exc}",
                    )
                )
                continue
            role_reports.append(_with_role(report, prepared.role_id, artifact))
            fix_queue.extend(_fix_items_from_role_report(report, prepared.role_id))
        if role_reports:
            try:
                aggregated = aggregate_audits(role_reports)
            except AuditPreparationError as exc:
                fix_queue.append(
                    FixItem(
                        source="role:aggregate",
                        severity="warning",
                        message=f"role reports could not be aggregated: {exc}",
                    )
                )

    ranked_queue = _rank_fix_queue(fix_queue)
    return ManuscriptPreflightReport(
        ok=not any(item.severity == "error" for item in ranked_queue),
        fix_queue=ranked_queue,
        ledger_audit=ledger_audit,
        consistency=consistency,
        visual_qa=visual_results,
        prepared_roles=prepared_roles,
        aggregated=aggregated,
    )


def _prepare_roles(
    manuscript_md: str,
    *,
    artifact_path: Path | str | None,
    role_ids: tuple[str, ...],
    project_slug: str | None,
    target_journal: str | None,
    kb_root: Path | str | None,
) -> tuple[list[PreparedRolePass], list[FixItem], Path]:
    artifact = _ensure_artifact(manuscript_md, artifact_path)
    prepared_roles: list[PreparedRolePass] = []
    fix_items: list[FixItem] = []
    for role_id in role_ids:
        try:
            prompt = prepare_audit(
                role_id,
                artifact,
                project_slug=project_slug,
                target_journal=target_journal,
                kb_root=kb_root,
                load_kb_context=False,
            )
        except Exception as exc:
            message = f"role {role_id} could not be prepared: {exc}"
            prepared_roles.append(PreparedRolePass(role_id=role_id, prompt=None, error=str(exc)))
            fix_items.append(FixItem(source=f"role:{role_id}", severity="warning", message=message))
            continue
        prepared_roles.append(PreparedRolePass(role_id=role_id, prompt=prompt))
    return prepared_roles, fix_items, artifact


def _ensure_artifact(manuscript_md: str, artifact_path: Path | str | None) -> Path:
    if artifact_path is None:
        temp = tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            suffix=".md",
            prefix="vaultlab-preflight-",
            delete=False,
        )
        with temp:
            temp.write(manuscript_md)
        return Path(temp.name)

    artifact = Path(artifact_path)
    if artifact.exists():
        return artifact
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text(manuscript_md, encoding="utf-8")
    return artifact


def _run_visual_qa(figures_root: Path | None, *, run_visual_qa: bool) -> list[VisualQAResult]:
    if not run_visual_qa or figures_root is None or not figures_root.exists():
        return []
    results: list[VisualQAResult] = []
    for png in sorted(figures_root.glob("*.png")):
        try:
            results.append(visual_qa_figure(png, run_vision=False, write_sidecar=False))
        except Exception as exc:
            results.append(
                VisualQAResult(
                    verdict="WARN",
                    findings=[
                        VisualQAFinding(
                            source="layout",
                            severity="warn",
                            message=f"visual QA skipped: {exc}",
                            fix="Rerun visual QA after confirming the PNG can be read.",
                        )
                    ],
                    layout_severity="warn",
                    vision_ran=False,
                    png=str(png),
                )
            )
    return results


def _fix_items_from_ledger(audit: LedgerAudit) -> list[FixItem]:
    return [
        FixItem(
            source="claim_ledger",
            severity=problem.severity,
            message=problem.message,
            where=problem.claim_id,
        )
        for problem in audit.problems
    ]


def _fix_items_from_consistency(report: ConsistencyReport) -> list[FixItem]:
    return [
        FixItem(
            source="figure_text",
            severity=problem.severity,
            message=problem.message,
            where=problem.claim_id or problem.figure_id,
            fix=_fix_for_consistency(problem.kind),
        )
        for problem in report.problems
    ]


def _fix_items_from_visual_qa(results: list[VisualQAResult]) -> list[FixItem]:
    items: list[FixItem] = []
    for result in results:
        for finding in result.findings:
            items.append(
                FixItem(
                    source="visual_qa",
                    severity=_visual_severity(finding.severity),
                    message=finding.message,
                    where=result.png,
                    fix=finding.fix,
                )
            )
        if not result.findings and result.verdict != "PASS":
            items.append(
                FixItem(
                    source="visual_qa",
                    severity=_visual_severity(result.verdict),
                    message=f"visual QA reported {result.verdict}: {result.layout_severity}",
                    where=result.png,
                )
            )
    return items


def _fix_items_from_role_report(report: Mapping[str, Any], role_id: str) -> list[FixItem]:
    items: list[FixItem] = []
    for key in ("issues", "concerns", "friction_predicted", "checks"):
        raw_items = report.get(key)
        if not isinstance(raw_items, list):
            continue
        for raw_item in raw_items:
            if isinstance(raw_item, Mapping):
                items.append(_fix_item_from_role_mapping(raw_item, role_id))
            elif isinstance(raw_item, str) and raw_item.strip():
                items.append(
                    FixItem(
                        source=f"role:{role_id}",
                        severity="warning",
                        message=raw_item.strip(),
                    )
                )
    if not items:
        verdict = report.get("verdict") or report.get("verdict_journal_style")
        if verdict is not None:
            items.append(
                FixItem(
                    source=f"role:{role_id}",
                    severity="info",
                    message=f"{role_id} verdict: {verdict}",
                )
            )
    return items


def _fix_item_from_role_mapping(item: Mapping[str, Any], role_id: str) -> FixItem:
    message = _first_text(
        item,
        ("message", "issue", "concern", "friction", "check", "name", "detail", "result"),
    )
    detail = _first_optional_text(item, ("detail", "rationale", "why", "evidence"))
    if detail and detail not in message:
        message = f"{message}: {detail}"
    return FixItem(
        source=f"role:{role_id}",
        severity=_role_severity(item.get("severity") or item.get("result")),
        message=message,
        where=_optional_text(item.get("where") or item.get("location") or item.get("section")),
        fix=_optional_text(item.get("fix") or item.get("recommendation") or item.get("action")),
    )


def _with_role(report: Mapping[str, Any], role_id: str, artifact: Path) -> Mapping[str, Any]:
    copied = dict(report)
    copied.setdefault("_role", role_id)
    copied.setdefault("target_artifact", str(artifact))
    return copied


def _rank_fix_queue(items: list[FixItem]) -> list[FixItem]:
    return sorted(items, key=lambda item: (_SEVERITY_RANK[item.severity], item.source, item.message))


def _counts_by_severity(items: list[FixItem]) -> dict[FixSeverity, int]:
    return {
        "error": sum(1 for item in items if item.severity == "error"),
        "warning": sum(1 for item in items if item.severity == "warning"),
        "info": sum(1 for item in items if item.severity == "info"),
    }


def _aggregated_to_dict(aggregated: AggregatedAudit | None) -> dict[str, Any] | None:
    if aggregated is None:
        return None
    return {
        "artifact_path": str(aggregated.artifact_path),
        "per_role_verdicts": aggregated.per_role_verdicts,
        "aggregated_verdict": aggregated.aggregated_verdict,
        "aggregated_evidence_axis": aggregated.aggregated_evidence_axis,
        "issue_count": aggregated.issue_count,
        "role_count": aggregated.role_count,
    }


def _fix_for_consistency(kind: str) -> str:
    fixes = {
        "missing_figure": "Add the referenced figure file or remove the manuscript callout.",
        "cut_figure": "Either cite the figure in prose or remove it from the bundle.",
        "number_mismatch": "Update the manuscript, ledger, or source statistic so the values agree.",
        "identity_contradiction": "Resolve the label contradiction between prose and coverage metadata.",
    }
    return fixes.get(kind, "Resolve the figure-text consistency problem before submission.")


def _visual_severity(value: object) -> FixSeverity:
    normalized = str(value).strip().lower()
    if normalized in {"fail", "failed", "error"}:
        return "error"
    if normalized in {"warn", "warning"}:
        return "warning"
    return "info"


def _role_severity(value: object) -> FixSeverity:
    normalized = str(value or "").strip().lower()
    if normalized in {"fail", "failed", "error", "reject"}:
        return "error"
    if normalized in {"major", "minor", "warn", "warning", "style", "concern"}:
        return "warning"
    return "info"


def _first_text(item: Mapping[str, Any], keys: tuple[str, ...]) -> str:
    value = _first_optional_text(item, keys)
    if value is not None:
        return value
    return "role reported an issue without a message"


def _first_optional_text(item: Mapping[str, Any], keys: tuple[str, ...]) -> str | None:
    for key in keys:
        value = _optional_text(item.get(key))
        if value is not None:
            return value
    return None


def _optional_text(value: object) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    if value is not None and not isinstance(value, (dict, list, tuple, set)):
        return str(value)
    return None


__all__ = [
    "DEFAULT_REVIEWER_ROLES",
    "FixItem",
    "ManuscriptPreflightReport",
    "PreparedRolePass",
    "run_manuscript_preflight",
]
