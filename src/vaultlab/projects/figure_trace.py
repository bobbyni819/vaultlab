"""Bridge planned subpanels to existing figure QA sidecars."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, cast

from vaultlab.figures.layout_sidecar import audit_layout_sidecar
from vaultlab.figures.publication.coverage import CoverageManifest
from vaultlab.projects.figure_plan import SubpanelPlan, SubpanelReadiness
from vaultlab.projects.readiness import (
    PromotionGate,
    ProvenanceScan,
    evaluate_promotion,
    scan_provenance_text,
)
from vaultlab.slides.panel_contract import PanelLayoutContract

TraceSeverity = Literal["pass", "warn", "fail"]

_SEVERITY_RANK: dict[TraceSeverity, int] = {"pass": 0, "warn": 1, "fail": 2}


@dataclass(frozen=True)
class SubpanelTrace:
    """Summary of loaded QA evidence and computed readiness for one subpanel."""

    subpanel_id: str
    figure_id: str
    letter: str
    computed_readiness: SubpanelReadiness
    promotion_gate: PromotionGate
    problems: list[str] = field(default_factory=list)
    coverage_severity: TraceSeverity = "fail"
    layout_severity: TraceSeverity = "fail"
    panel_severity: TraceSeverity = "warn"
    provenance_scan: ProvenanceScan = field(
        default_factory=lambda: ProvenanceScan(
            matched_markers=[],
            placeholder_counts={},
            text_length=0,
        )
    )

    @property
    def overall_severity(self) -> TraceSeverity:
        """Aggregate trace severity from IO problems and loaded audit severities."""

        if self.problems:
            return "fail"
        return _aggregate([self.coverage_severity, self.layout_severity, self.panel_severity])

    def ok(self) -> bool:
        """Return True when the trace has no IO problems and the promotion passed."""

        return not self.problems and self.promotion_gate.passed

    @property
    def n_fail(self) -> int:
        """Number of failing trace-level checks."""

        count = 1 if self.problems else 0
        return count + sum(
            1
            for severity in [self.coverage_severity, self.layout_severity, self.panel_severity]
            if severity == "fail"
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize this trace to a JSON-ready dict."""

        return {
            "subpanel_id": self.subpanel_id,
            "figure_id": self.figure_id,
            "letter": self.letter,
            "computed_readiness": self.computed_readiness.value,
            "promotion_gate": self.promotion_gate.to_dict(),
            "problems": list(self.problems),
            "coverage_severity": self.coverage_severity,
            "layout_severity": self.layout_severity,
            "panel_severity": self.panel_severity,
            "provenance_scan": self.provenance_scan.to_dict(),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> SubpanelTrace:
        """Build a trace from parsed JSON."""

        return cls(
            subpanel_id=str(payload.get("subpanel_id", "")),
            figure_id=str(payload.get("figure_id", "")),
            letter=str(payload.get("letter", "")),
            computed_readiness=_readiness_from_value(
                payload.get("computed_readiness"),
                SubpanelReadiness.DISPLAY_EXISTS,
            ),
            promotion_gate=PromotionGate.from_dict(_dict(payload.get("promotion_gate", {}))),
            problems=_string_list(payload.get("problems", [])),
            coverage_severity=_severity_from_value(payload.get("coverage_severity")),
            layout_severity=_severity_from_value(payload.get("layout_severity")),
            panel_severity=_severity_from_value(payload.get("panel_severity")),
            provenance_scan=ProvenanceScan.from_dict(_dict(payload.get("provenance_scan", {}))),
        )

    def validate(self) -> list[str]:
        """Return soft trace-record problems."""

        problems: list[str] = []
        if not self.subpanel_id.strip():
            problems.append("trace missing subpanel_id")
        if not self.figure_id.strip():
            problems.append("trace missing figure_id")
        if not self.letter.strip():
            problems.append("trace missing letter")
        problems.extend(self.promotion_gate.validate())
        problems.extend(self.provenance_scan.validate())
        return problems

    def audit(self) -> SubpanelTraceAudit:
        """Audit this trace record."""

        trace_problems = [
            SubpanelTraceProblem("fail", message) for message in self.validate()
        ]
        return SubpanelTraceAudit(
            overall_severity=_aggregate_problems(trace_problems),
            problems=trace_problems,
        )


@dataclass(frozen=True)
class SubpanelTraceProblem:
    """One structured subpanel-trace audit problem."""

    severity: TraceSeverity
    message: str

    def to_dict(self) -> dict[str, str]:
        """Serialize this trace problem."""

        return {"severity": self.severity, "message": self.message}

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> SubpanelTraceProblem:
        """Build a trace problem from parsed JSON."""

        return cls(
            severity=_severity_from_value(payload.get("severity")),
            message=str(payload.get("message", "")),
        )


@dataclass(frozen=True)
class SubpanelTraceAudit:
    """Structured validation result for a trace record."""

    overall_severity: TraceSeverity
    problems: list[SubpanelTraceProblem] = field(default_factory=list)

    @property
    def n_fail(self) -> int:
        """Number of failing checks."""

        return sum(1 for problem in self.problems if problem.severity == "fail")

    @property
    def n_warn(self) -> int:
        """Number of warning checks."""

        return sum(1 for problem in self.problems if problem.severity == "warn")

    def ok(self) -> bool:
        """Return True when no failing checks are present."""

        return self.n_fail == 0

    def to_dict(self) -> dict[str, Any]:
        """Serialize this trace audit."""

        return {
            "overall_severity": self.overall_severity,
            "problems": [problem.to_dict() for problem in self.problems],
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> SubpanelTraceAudit:
        """Build a trace audit from parsed JSON."""

        problems = [
            SubpanelTraceProblem.from_dict(item) for item in _dict_list(payload.get("problems", []))
        ]
        return cls(overall_severity=_aggregate_problems(problems), problems=problems)


@dataclass(frozen=True)
class _SimpleAudit:
    passed: bool

    def ok(self) -> bool:
        return self.passed


def trace_subpanel(
    subpanel: SubpanelPlan,
    *,
    base_dir: Path | str | None = None,
    min_effective_font_pt: float = 5.5,
    panel_audit: Any | None = None,
) -> SubpanelTrace:
    """Load QA sidecars for one subpanel and compute its readiness.

    ``panel_audit`` is an optional slide-placement audit (e.g. the
    ``PanelLayoutAudit`` returned by ``audit_panel_layout_contract`` for the
    contract slot this subpanel fills). It is required to reach the top
    ``DECK_READY`` rung: a single subpanel plus its figure sidecars cannot prove
    panel-placement correctness on its own, so when no panel audit is supplied a
    subpanel caps at ``GEOMETRY_QA_PASSED`` and a ``DECK_READY`` claim is blocked
    with ``panel_audit_missing`` rather than silently accepted.
    """

    root = Path(base_dir) if base_dir is not None else None
    problems: list[str] = []

    coverage_audit: Any = _SimpleAudit(False)
    coverage_severity: TraceSeverity = "fail"
    manifest_path = _resolve_path(subpanel.manifest_path, root)
    if manifest_path is None or not manifest_path.exists():
        problems.append(f"missing manifest_path: {_display_path(subpanel.manifest_path)}")
    else:
        try:
            coverage_audit = CoverageManifest.read_json(manifest_path).audit()
            coverage_severity = "pass" if _audit_ok(coverage_audit) else "fail"
        except Exception as exc:
            problems.append(f"failed manifest_path: {_display_path(subpanel.manifest_path)}: {exc}")

    layout_audit: Any = _SimpleAudit(False)
    layout_severity: TraceSeverity = "fail"
    layout_path = _resolve_path(subpanel.layout_sidecar_path, root)
    if layout_path is None or not layout_path.exists():
        problems.append(f"missing layout_sidecar_path: {_display_path(subpanel.layout_sidecar_path)}")
    else:
        try:
            layout_audit = audit_layout_sidecar(
                layout_path,
                min_effective_font_pt=min_effective_font_pt,
            )
            layout_severity = _severity_from_value(
                getattr(layout_audit, "overall_severity", "fail")
            )
        except Exception as exc:
            problems.append(
                f"failed layout_sidecar_path: {_display_path(subpanel.layout_sidecar_path)}: {exc}"
            )

    provenance_scan = scan_provenance_text("")
    provenance_path = _resolve_path(subpanel.provenance_path, root)
    if provenance_path is None or not provenance_path.exists():
        problems.append(f"missing provenance_path: {_display_path(subpanel.provenance_path)}")
    else:
        try:
            provenance_scan = scan_provenance_text(provenance_path.read_text(encoding="utf-8"))
        except Exception as exc:
            problems.append(f"failed provenance_path: {_display_path(subpanel.provenance_path)}: {exc}")

    panel_severity: TraceSeverity
    if panel_audit is not None:
        panel_severity = "pass" if _audit_ok(panel_audit) else "fail"
    elif subpanel.readiness.rank >= SubpanelReadiness.DECK_READY.rank:
        panel_severity = "fail"
    else:
        panel_severity = "pass"

    gate = evaluate_promotion(
        subpanel,
        layout_audit=layout_audit,
        coverage_audit=coverage_audit,
        provenance_scan=provenance_scan,
        panel_audit=panel_audit,
    )

    return SubpanelTrace(
        subpanel_id=subpanel.subpanel_id,
        figure_id=subpanel.figure_id,
        letter=subpanel.letter,
        computed_readiness=gate.computed_readiness,
        promotion_gate=gate,
        problems=problems,
        coverage_severity=coverage_severity,
        layout_severity=layout_severity,
        panel_severity=panel_severity,
        provenance_scan=provenance_scan,
    )


def link_panel_slot_to_subpanel(
    contract: PanelLayoutContract,
    subpanels: Sequence[SubpanelPlan],
) -> dict[str, str | None]:
    """Map each panel slot letter in a contract to a matching subpanel id."""

    by_slot: dict[str, list[str]] = {}
    for subpanel in subpanels:
        by_slot.setdefault(subpanel.panel_slot_id, []).append(subpanel.subpanel_id)

    result: dict[str, str | None] = {}
    for slot in contract.panels:
        matches = by_slot.get(slot.letter, [])
        result[slot.letter] = matches[0] if len(matches) == 1 else None
    return result


def _resolve_path(raw_path: str, base_dir: Path | None) -> Path | None:
    if not raw_path.strip():
        return None
    path = Path(raw_path)
    if path.is_absolute() or base_dir is None:
        return path
    return base_dir / path


def _display_path(raw_path: str) -> str:
    return raw_path if raw_path.strip() else "<empty>"


def _audit_ok(audit: Any) -> bool:
    ok_attr = getattr(audit, "ok", None)
    if callable(ok_attr):
        return bool(ok_attr())
    if isinstance(ok_attr, bool):
        return ok_attr
    return False


def _aggregate(severities: list[TraceSeverity]) -> TraceSeverity:
    if not severities:
        return "pass"
    return max(severities, key=lambda severity: _SEVERITY_RANK[severity])


def _aggregate_problems(problems: list[SubpanelTraceProblem]) -> TraceSeverity:
    if not problems:
        return "pass"
    return max((problem.severity for problem in problems), key=lambda severity: _SEVERITY_RANK[severity])


def _severity_from_value(value: Any) -> TraceSeverity:
    if value in {"pass", "warn", "fail"}:
        return cast("TraceSeverity", value)
    return "fail"


def _readiness_from_value(value: Any, default: SubpanelReadiness) -> SubpanelReadiness:
    if value is None:
        return default
    for member in SubpanelReadiness:
        if value == member.value or value == member.name:
            return member
    return default


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def _dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return cast("dict[str, Any]", value)
    return {}


def _dict_list(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [cast("dict[str, Any]", item) for item in value if isinstance(item, dict)]


__all__ = [
    "SubpanelTrace",
    "SubpanelTraceAudit",
    "SubpanelTraceProblem",
    "TraceSeverity",
    "link_panel_slot_to_subpanel",
    "trace_subpanel",
]
