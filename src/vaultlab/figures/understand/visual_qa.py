"""Post-render visual QA for rendered PNG figures.

The deterministic backbone is :func:`run_layout_audit`. Optional vision
readback reuses the existing figure-understanding SDK verify path and is
advisory: no API key or SDK means the vision leg is skipped, not fatal.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal

from vaultlab.figures.understand._sdk import _resolve_api_key, verify_via_sdk
from vaultlab.figures.understand._tasks import (
    VERIFY_SYSTEM_PROMPT,
    VerifyAnnotationTask,
    verify_response_schema,
)
from vaultlab.figures.understand.layout_checks import AuditSeverity, run_layout_audit
from vaultlab.figures.understand.models import VerificationIteration

VisualQASource = Literal["layout", "vision"]
VisualQASeverity = Literal["pass", "warn", "fail"]
VisualQAVerdict = Literal["PASS", "WARN", "FAIL"]

_SEVERITY_RANK: dict[VisualQASeverity, int] = {"pass": 0, "warn": 1, "fail": 2}
_VERDICT_FROM_SEVERITY: dict[VisualQASeverity, VisualQAVerdict] = {
    "pass": "PASS",
    "warn": "WARN",
    "fail": "FAIL",
}


@dataclass(frozen=True)
class VisualQAFinding:
    """One deterministic or vision-derived visual QA finding."""

    source: VisualQASource
    severity: VisualQASeverity
    message: str
    fix: str | None = None


@dataclass(frozen=True)
class VisualQAResult:
    """Combined layout + optional vision QA result for one rendered PNG."""

    verdict: VisualQAVerdict
    findings: list[VisualQAFinding]
    layout_severity: str
    vision_ran: bool
    png: str

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable representation."""

        return {
            "verdict": self.verdict,
            "findings": [asdict(finding) for finding in self.findings],
            "layout_severity": self.layout_severity,
            "vision_ran": self.vision_ran,
            "png": self.png,
        }

    def to_markdown(self) -> str:
        """Render a concise reviewer-facing visual QA report."""

        lines = [
            "# Visual QA",
            "",
            f"- **PNG:** `{self.png}`",
            f"- **Verdict:** `{self.verdict}`",
            f"- **Layout severity:** `{self.layout_severity}`",
            f"- **Vision readback ran:** `{self.vision_ran}`",
            "",
            "## What to fix",
            "",
        ]
        fix_findings = [finding for finding in self.findings if finding.severity != "pass"]
        if fix_findings:
            for finding in fix_findings:
                fix = finding.fix or "Inspect the rendered PNG and adjust the figure before release."
                lines.append(
                    f"- `{finding.severity.upper()}` ({finding.source}): "
                    f"{finding.message} Fix: {fix}"
                )
        else:
            lines.append("- No required fixes were detected by the enabled checks.")
        lines.extend(["", "## Findings", ""])
        for finding in self.findings:
            suffix = f" Fix: {finding.fix}" if finding.fix else ""
            lines.append(
                f"- `{finding.severity.upper()}` ({finding.source}): "
                f"{finding.message}{suffix}"
            )
        return "\n".join(lines).rstrip() + "\n"


def visual_qa_figure(
    png_path: Path | str,
    *,
    conclusion: str | None = None,
    run_vision: bool = False,
    verify_fn: Callable[..., Any] | None = None,
    write_sidecar: bool = True,
) -> VisualQAResult:
    """Run deterministic layout QA plus optional vision readback on a PNG.

    Parameters
    ----------
    png_path
        Rendered PNG to audit.
    conclusion
        Optional intended conclusion. The vision prompt asks whether the PNG
        appears to support this conclusion; deterministic layout checks ignore it.
    run_vision
        When false, no model, network, or SDK path is touched.
    verify_fn
        Optional injected vision verifier for tests or alternate callers. It is
        called with keyword arguments and may return a
        :class:`VerificationIteration`, a dict, or a string.
    write_sidecar
        When true, write ``<png>.visual_qa.json`` and ``<png>.visual_qa.md``.
    """

    png = Path(png_path)
    layout = run_layout_audit(png)
    findings = _findings_from_layout(layout.overall_severity, layout.checks)
    vision_ran = False

    if run_vision:
        vision_findings, vision_ran = _run_vision_qa(
            png,
            conclusion=conclusion,
            verify_fn=verify_fn,
        )
        findings.extend(vision_findings)

    result = VisualQAResult(
        verdict=_verdict(findings),
        findings=findings,
        layout_severity=str(layout.overall_severity),
        vision_ran=vision_ran,
        png=str(png),
    )
    if write_sidecar:
        _write_sidecars(png, result)
    return result


def _findings_from_layout(overall: AuditSeverity, checks: list[Any]) -> list[VisualQAFinding]:
    findings = [
        VisualQAFinding(
            source="layout",
            severity=overall,
            message=f"layout audit overall severity: {overall}",
            fix=_layout_fix(overall, "overall"),
        )
    ]
    for check in checks:
        name = str(getattr(check, "name", "layout_check"))
        severity = _normalize_severity(getattr(check, "severity", "warn"))
        detail = str(getattr(check, "detail", "layout check did not report details"))
        findings.append(
            VisualQAFinding(
                source="layout",
                severity=severity,
                message=f"{name}: {detail}",
                fix=_layout_fix(severity, name),
            )
        )
    return findings


def _run_vision_qa(
    png: Path,
    *,
    conclusion: str | None,
    verify_fn: Callable[..., Any] | None,
) -> tuple[list[VisualQAFinding], bool]:
    task = _visual_verify_task(png, conclusion=conclusion)
    try:
        if verify_fn is None:
            try:
                api_key = _resolve_api_key(None)
            except Exception:
                return [
                    VisualQAFinding(
                        source="vision",
                        severity="pass",
                        message="vision QA skipped: no API key",
                    )
                ], False
            response = verify_via_sdk(task, api_key=api_key)
        else:
            response = verify_fn(task=task, png_path=png, conclusion=conclusion)
    except ImportError:
        return [
            VisualQAFinding(
                source="vision",
                severity="pass",
                message="vision QA skipped: SDK unavailable",
            )
        ], False
    except Exception as exc:
        return [
            VisualQAFinding(
                source="vision",
                severity="warn",
                message=f"vision QA skipped: verifier failed ({exc})",
                fix="Rerun with a working vision verifier if advisory readback is required.",
            )
        ], False

    return _findings_from_vision_response(response, conclusion=conclusion), True


def _visual_verify_task(png: Path, *, conclusion: str | None) -> VerifyAnnotationTask:
    conclusion_block = (
        f"\nINTENDED CONCLUSION:\n{conclusion.strip()}\n"
        if conclusion and conclusion.strip()
        else "\nNo intended conclusion was supplied.\n"
    )
    prompt = (
        "TASK:\n"
        "Read the attached rendered PNG as a scientific figure reviewer. Flag "
        "reviewer-visible defects that deterministic rcParams/layout checks may "
        "miss: illegible text, label collisions, misleading or stale labels, "
        "cropped content, confusing legends, or a visual claim that is not "
        "supported by what the PNG actually shows.\n"
        f"{conclusion_block}\n"
        "Return ONLY a JSON object matching this schema: "
        '{"annotated_image_read": "<what you saw>", '
        '"issues_found": ["<defect or mismatch>", ...], '
        '"decision": "ACCEPT"|"RETRY_LOCALIZE"|"RETRY_MATCH"|"GIVE_UP"}\n'
        "Use ACCEPT only when no reviewer-visible defects are apparent."
    )
    return VerifyAnnotationTask(
        annotated_image_path=png,
        iteration=1,
        expected_elements=[conclusion] if conclusion else [],
        system=VERIFY_SYSTEM_PROMPT,
        prompt=prompt,
        response_schema=verify_response_schema(),
    )


def _findings_from_vision_response(
    response: Any,
    *,
    conclusion: str | None,
) -> list[VisualQAFinding]:
    if isinstance(response, VerificationIteration):
        return _findings_from_verification_iteration(response)
    if isinstance(response, dict):
        if {"issues_found", "decision", "annotated_image_read"} & response.keys():
            iteration = VerificationIteration(
                iteration=1,
                annotated_image_read=str(response.get("annotated_image_read", "")),
                issues_found=_string_list(response.get("issues_found")),
                decision=str(response.get("decision", "GIVE_UP")),
            )
            return _findings_from_verification_iteration(iteration)
        findings = _findings_from_defect_dict(response)
        if conclusion and response.get("supports_conclusion") is False:
            findings.append(
                VisualQAFinding(
                    source="vision",
                    severity="fail",
                    message=f"vision readback did not support conclusion: {conclusion}",
                    fix="Revise the figure or soften the conclusion before release.",
                )
            )
        if not findings:
            findings.append(
                VisualQAFinding(
                    source="vision",
                    severity="pass",
                    message="vision QA readback found no reviewer-visible defects",
                )
            )
        return findings
    if isinstance(response, str) and response.strip():
        return [
            VisualQAFinding(
                source="vision",
                severity="warn",
                message=response.strip(),
                fix="Review the vision readback and decide whether the PNG needs revision.",
            )
        ]
    return [
        VisualQAFinding(
            source="vision",
            severity="warn",
            message="vision QA returned an empty or unrecognized response",
            fix="Rerun vision QA or manually read the PNG before release.",
        )
    ]


def _findings_from_verification_iteration(
    iteration: VerificationIteration,
) -> list[VisualQAFinding]:
    issues = [issue for issue in iteration.issues_found if issue.strip()]
    if not issues and iteration.decision == "ACCEPT":
        message = iteration.annotated_image_read or "vision QA accepted the rendered PNG"
        return [VisualQAFinding(source="vision", severity="pass", message=message)]

    severity: VisualQASeverity = "fail" if iteration.decision != "ACCEPT" else "warn"
    if not issues:
        issues = [f"vision QA decision was {iteration.decision}"]
    return [
        VisualQAFinding(
            source="vision",
            severity=severity,
            message=issue,
            fix="Inspect the PNG and rerender before release.",
        )
        for issue in issues
    ]


def _findings_from_defect_dict(response: dict[str, Any]) -> list[VisualQAFinding]:
    findings: list[VisualQAFinding] = []
    defects = response.get("defects") or response.get("findings") or []
    if isinstance(defects, list):
        for defect in defects:
            if isinstance(defect, dict):
                findings.append(
                    VisualQAFinding(
                        source="vision",
                        severity=_normalize_severity(defect.get("severity", "warn")),
                        message=str(defect.get("message", defect.get("detail", "vision defect"))),
                        fix=_optional_str(defect.get("fix")),
                    )
                )
            elif isinstance(defect, str) and defect.strip():
                findings.append(
                    VisualQAFinding(
                        source="vision",
                        severity="warn",
                        message=defect.strip(),
                        fix="Inspect the PNG and rerender if the issue is real.",
                    )
                )
    legibility = response.get("legibility")
    if isinstance(legibility, str) and _looks_like_problem(legibility):
        findings.append(
            VisualQAFinding(
                source="vision",
                severity="warn",
                message=f"legibility concern: {legibility.strip()}",
                fix="Increase label/font size, contrast, or spacing.",
            )
        )
    return findings


def _looks_like_problem(text: str) -> bool:
    lowered = text.lower()
    problem_words = ("not ", "hard", "illegible", "unreadable", "collide", "overlap", "tiny")
    return any(word in lowered for word in problem_words)


def _layout_fix(severity: VisualQASeverity, check_name: str) -> str | None:
    if severity == "pass":
        return None
    fixes = {
        "title_cutoff": "Increase top margin or use constrained layout before saving.",
        "axis_label_cutoff": "Increase left/bottom margin or use tight/constrained layout.",
        "dpi": "Export the PNG at 300 DPI or higher.",
        "empty_panel": "Confirm data were rendered and rerender from the source data.",
        "palette_accessibility": "Use a more discriminable color palette and rerender.",
    }
    return fixes.get(check_name, "Inspect the rendered PNG and adjust the layout before release.")


def _verdict(findings: list[VisualQAFinding]) -> VisualQAVerdict:
    if not findings:
        return "PASS"
    worst = max(
        (_normalize_severity(finding.severity) for finding in findings),
        key=lambda severity: _SEVERITY_RANK[severity],
    )
    return _VERDICT_FROM_SEVERITY[worst]


def _normalize_severity(value: object) -> VisualQASeverity:
    text = str(value).strip().lower()
    if text in {"pass", "passed", "ok", "accept", "accepted", "info", "none"}:
        return "pass"
    if text in {"warning", "warn", "retry", "concern"}:
        return "warn"
    if text in {"fail", "failed", "error", "reject", "give_up", "give-up"}:
        return "fail"
    return "warn"


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item.strip() for item in value if isinstance(item, str) and item.strip()]


def _optional_str(value: object) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _write_sidecars(png: Path, result: VisualQAResult) -> None:
    json_path = Path(str(png) + ".visual_qa.json")
    md_path = Path(str(png) + ".visual_qa.md")
    _atomic_write_text(json_path, json.dumps(result.to_dict(), indent=2, sort_keys=True) + "\n")
    _atomic_write_text(md_path, result.to_markdown())


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


__all__ = [
    "VisualQAFinding",
    "VisualQAResult",
    "visual_qa_figure",
]
