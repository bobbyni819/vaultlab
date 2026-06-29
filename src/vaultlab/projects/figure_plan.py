"""Machine-readable figure planning contracts."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Literal, TypeVar, cast

SCHEMA = "vaultlab-figure-plan/v1"

PlanSeverity = Literal["pass", "warn", "fail"]

_SEVERITY_RANK: dict[PlanSeverity, int] = {"pass": 0, "warn": 1, "fail": 2}
_PANEL_SLOT_RE = re.compile(r"^[A-Za-z]$")
_CLAIM_ID_RE = re.compile(r"^[A-Za-z0-9_.:-]+$")

EnumT = TypeVar("EnumT", bound=Enum)


class SupportRole(str, Enum):
    """How a supplement supports a publication subpanel."""

    ROBUSTNESS = "robustness"
    ADDITIONAL_SCALE = "additional_scale"
    ADDITIONAL_CONDITION = "additional_condition"
    PARAMETER_SWEEP = "parameter_sweep"
    FULL_CATEGORY_COVERAGE = "full_category_coverage"
    NEGATIVE_CONTROL = "negative_control"
    METHOD_DIAGNOSTIC = "method_diagnostic"
    EXPLORATORY_ARCHIVE = "exploratory_archive"


class SubpanelReadiness(str, Enum):
    """Promotion rungs for a planned subpanel."""

    DISPLAY_EXISTS = "display_exists"
    PROVENANCE_VERIFIED = "provenance_verified"
    GEOMETRY_QA_PASSED = "geometry_qa_passed"
    DECK_READY = "deck_ready"
    FAILED = "failed"

    @property
    def rank(self) -> int:
        """Numeric ordering for promotion-gate comparisons."""

        return {
            SubpanelReadiness.FAILED: -1,
            SubpanelReadiness.DISPLAY_EXISTS: 0,
            SubpanelReadiness.PROVENANCE_VERIFIED: 1,
            SubpanelReadiness.GEOMETRY_QA_PASSED: 2,
            SubpanelReadiness.DECK_READY: 3,
        }[self]


@dataclass(frozen=True)
class SubpanelPlan:
    """The join object connecting a planned panel to analysis and QA sidecars."""

    subpanel_id: str
    figure_id: str
    letter: str
    concept: str
    plot_type: str
    source_result: str
    analysis_script: str
    plot_script: str
    output_figure: str
    manifest_path: str
    layout_sidecar_path: str
    visual_qa_path: str
    provenance_path: str
    panel_slot_id: str
    claim_id: str
    supplement_ids: list[str] = field(default_factory=list)
    readiness: SubpanelReadiness = SubpanelReadiness.DISPLAY_EXISTS

    def to_dict(self) -> dict[str, Any]:
        """Serialize this subpanel plan to a JSON-ready dict."""

        return {
            "subpanel_id": self.subpanel_id,
            "figure_id": self.figure_id,
            "letter": self.letter,
            "concept": self.concept,
            "plot_type": self.plot_type,
            "source_result": self.source_result,
            "analysis_script": self.analysis_script,
            "plot_script": self.plot_script,
            "output_figure": self.output_figure,
            "manifest_path": self.manifest_path,
            "layout_sidecar_path": self.layout_sidecar_path,
            "visual_qa_path": self.visual_qa_path,
            "provenance_path": self.provenance_path,
            "panel_slot_id": self.panel_slot_id,
            "claim_id": self.claim_id,
            "supplement_ids": list(self.supplement_ids),
            "readiness": self.readiness.value,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> SubpanelPlan:
        """Build a subpanel plan from parsed JSON."""

        return cls(
            subpanel_id=str(payload.get("subpanel_id", "")),
            figure_id=str(payload.get("figure_id", "")),
            letter=str(payload.get("letter", "")),
            concept=str(payload.get("concept", "")),
            plot_type=str(payload.get("plot_type", "")),
            source_result=str(payload.get("source_result", "")),
            analysis_script=str(payload.get("analysis_script", "")),
            plot_script=str(payload.get("plot_script", "")),
            output_figure=str(payload.get("output_figure", "")),
            manifest_path=str(payload.get("manifest_path", "")),
            layout_sidecar_path=str(payload.get("layout_sidecar_path", "")),
            visual_qa_path=str(payload.get("visual_qa_path", "")),
            provenance_path=str(payload.get("provenance_path", "")),
            panel_slot_id=str(payload.get("panel_slot_id", "")),
            claim_id=str(payload.get("claim_id", "")),
            supplement_ids=_string_list(payload.get("supplement_ids", [])),
            readiness=_enum_from_value(
                SubpanelReadiness,
                payload.get("readiness"),
                SubpanelReadiness.DISPLAY_EXISTS,
            ),
        )

    def validate(self) -> list[str]:
        """Return soft schema problems without touching the filesystem."""

        problems = _required_string_problems(
            "subpanel",
            self.subpanel_id,
            {
                "subpanel_id": self.subpanel_id,
                "figure_id": self.figure_id,
                "letter": self.letter,
                "concept": self.concept,
                "plot_type": self.plot_type,
                "source_result": self.source_result,
                "analysis_script": self.analysis_script,
                "plot_script": self.plot_script,
                "output_figure": self.output_figure,
                "manifest_path": self.manifest_path,
                "layout_sidecar_path": self.layout_sidecar_path,
                "visual_qa_path": self.visual_qa_path,
                "provenance_path": self.provenance_path,
                "panel_slot_id": self.panel_slot_id,
                "claim_id": self.claim_id,
            },
        )
        if self.panel_slot_id and _PANEL_SLOT_RE.fullmatch(self.panel_slot_id) is None:
            problems.append(
                f"subpanel {self.subpanel_id} has malformed panel_slot_id: {self.panel_slot_id}"
            )
        if self.claim_id and _CLAIM_ID_RE.fullmatch(self.claim_id) is None:
            problems.append(f"subpanel {self.subpanel_id} has malformed claim_id: {self.claim_id}")
        return problems

    def audit(self) -> FigurePlanAudit:
        """Validate this subpanel plan as a standalone record."""

        return _audit_from_messages(self.validate())


@dataclass(frozen=True)
class FigurePlan:
    """Top-level plan for one publication figure."""

    figure_id: str
    purpose: str
    reading_order: list[str] = field(default_factory=list)
    subpanel_ids: list[str] = field(default_factory=list)
    supplement_ids: list[str] = field(default_factory=list)
    required_analyses: list[str] = field(default_factory=list)
    open_decisions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Serialize this figure plan to a JSON-ready dict."""

        return {
            "figure_id": self.figure_id,
            "purpose": self.purpose,
            "reading_order": list(self.reading_order),
            "subpanel_ids": list(self.subpanel_ids),
            "supplement_ids": list(self.supplement_ids),
            "required_analyses": list(self.required_analyses),
            "open_decisions": list(self.open_decisions),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> FigurePlan:
        """Build a figure plan from parsed JSON."""

        return cls(
            figure_id=str(payload.get("figure_id", "")),
            purpose=str(payload.get("purpose", "")),
            reading_order=_string_list(payload.get("reading_order", [])),
            subpanel_ids=_string_list(payload.get("subpanel_ids", [])),
            supplement_ids=_string_list(payload.get("supplement_ids", [])),
            required_analyses=_string_list(payload.get("required_analyses", [])),
            open_decisions=_string_list(payload.get("open_decisions", [])),
        )

    def validate(self) -> list[str]:
        """Return standalone plan problems without dereferencing linked records."""

        return _required_string_problems(
            "figure plan",
            self.figure_id,
            {"figure_id": self.figure_id, "purpose": self.purpose},
        )

    def audit(self) -> FigurePlanAudit:
        """Validate this figure plan as a standalone record."""

        return _audit_from_messages(self.validate())


@dataclass(frozen=True)
class SupplementPlan:
    """Plan for one supplemental or archive figure linked to a subpanel."""

    supplement_id: str
    support_role: SupportRole
    output_figure: str
    manifest_path: str
    parent_subpanel_id: str | None = None
    archive_role: str | None = None
    notes: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize this supplement plan to a JSON-ready dict."""

        return {
            "supplement_id": self.supplement_id,
            "parent_subpanel_id": self.parent_subpanel_id,
            "archive_role": self.archive_role,
            "support_role": self.support_role.value,
            "output_figure": self.output_figure,
            "manifest_path": self.manifest_path,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> SupplementPlan:
        """Build a supplement plan from parsed JSON."""

        return cls(
            supplement_id=str(payload.get("supplement_id", "")),
            parent_subpanel_id=_optional_str(payload.get("parent_subpanel_id")),
            archive_role=_optional_str(payload.get("archive_role")),
            support_role=_enum_from_value(
                SupportRole,
                payload.get("support_role"),
                SupportRole.EXPLORATORY_ARCHIVE,
            ),
            output_figure=str(payload.get("output_figure", "")),
            manifest_path=str(payload.get("manifest_path", "")),
            notes=_optional_str(payload.get("notes")),
        )

    def validate(self) -> list[str]:
        """Return soft supplement schema problems."""

        problems = _required_string_problems(
            "supplement",
            self.supplement_id,
            {
                "supplement_id": self.supplement_id,
                "output_figure": self.output_figure,
                "manifest_path": self.manifest_path,
            },
        )
        if not _present(self.parent_subpanel_id) and not _present(self.archive_role):
            problems.append(
                f"supplement {self.supplement_id} is orphaned: "
                "set parent_subpanel_id or archive_role"
            )
        return problems

    def audit(self) -> FigurePlanAudit:
        """Validate this supplement plan as a standalone record."""

        return _audit_from_messages(self.validate())


@dataclass(frozen=True)
class FigurePlanProblem:
    """One structured figure-plan audit problem."""

    severity: PlanSeverity
    message: str
    field: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize this problem."""

        return {
            "severity": self.severity,
            "message": self.message,
            "field": self.field,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> FigurePlanProblem:
        """Build a problem from parsed JSON."""

        return cls(
            severity=_severity_from_value(payload.get("severity")),
            message=str(payload.get("message", "")),
            field=_optional_str(payload.get("field")),
        )


@dataclass(frozen=True)
class FigurePlanAudit:
    """Structured result from figure-plan validation."""

    overall_severity: PlanSeverity
    problems: list[FigurePlanProblem] = field(default_factory=list)

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
        """Serialize this audit."""

        return {
            "overall_severity": self.overall_severity,
            "problems": [problem.to_dict() for problem in self.problems],
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> FigurePlanAudit:
        """Build an audit from parsed JSON."""

        problems = [
            FigurePlanProblem.from_dict(item) for item in _dict_list(payload.get("problems", []))
        ]
        return cls(overall_severity=_aggregate(problems), problems=problems)


def validate_figure_plan(
    plan: FigurePlan,
    subpanels: list[SubpanelPlan],
    supplements: list[SupplementPlan],
) -> FigurePlanAudit:
    """Validate a figure-plan bundle without dereferencing path fields."""

    problems: list[FigurePlanProblem] = []
    _extend_messages(problems, plan.validate())
    for subpanel in subpanels:
        _extend_messages(problems, subpanel.validate())
    for supplement in supplements:
        _extend_messages(problems, supplement.validate())

    problems.extend(_round_trip_problems(plan, subpanels, supplements))
    problems.extend(_reference_problems(plan, subpanels, supplements))
    problems.extend(_duplicate_letter_problems(subpanels))

    return FigurePlanAudit(overall_severity=_aggregate(problems), problems=problems)


def dump_plan(
    plan: FigurePlan,
    subpanels: list[SubpanelPlan],
    supplements: list[SupplementPlan],
    path: Path | str,
) -> Path:
    """Atomically write a complete figure-plan JSON bundle."""

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_name(f".{target.name}.tmp")
    tmp.write_text(
        json.dumps(
            _bundle_to_dict(plan, subpanels, supplements),
            ensure_ascii=False,
            indent=2,
            sort_keys=False,
        )
        + "\n",
        encoding="utf-8",
    )
    os.replace(tmp, target)
    return target


def load_plan(path: Path | str) -> tuple[FigurePlan, list[SubpanelPlan], list[SupplementPlan]]:
    """Read a complete figure-plan JSON bundle."""

    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"figure plan must be a JSON object: {path}")
    if payload.get("schema") != SCHEMA:
        raise ValueError(
            f"unsupported figure plan schema: {payload.get('schema')!r}; expected {SCHEMA!r}"
        )
    return _bundle_from_dict(cast("dict[str, Any]", payload))


def _bundle_to_dict(
    plan: FigurePlan,
    subpanels: list[SubpanelPlan],
    supplements: list[SupplementPlan],
) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "figure_plan": plan.to_dict(),
        "subpanels": [subpanel.to_dict() for subpanel in subpanels],
        "supplements": [supplement.to_dict() for supplement in supplements],
    }


def _bundle_from_dict(
    payload: dict[str, Any],
) -> tuple[FigurePlan, list[SubpanelPlan], list[SupplementPlan]]:
    return (
        FigurePlan.from_dict(_dict(payload.get("figure_plan", {}))),
        [SubpanelPlan.from_dict(item) for item in _dict_list(payload.get("subpanels", []))],
        [SupplementPlan.from_dict(item) for item in _dict_list(payload.get("supplements", []))],
    )


def _round_trip_problems(
    plan: FigurePlan,
    subpanels: list[SubpanelPlan],
    supplements: list[SupplementPlan],
) -> list[FigurePlanProblem]:
    loaded_plan, loaded_subpanels, loaded_supplements = _bundle_from_dict(
        _bundle_to_dict(plan, subpanels, supplements)
    )
    if (loaded_plan, loaded_subpanels, loaded_supplements) != (plan, subpanels, supplements):
        return [FigurePlanProblem("fail", "figure plan JSON round-trip mismatch")]
    return []


def _reference_problems(
    plan: FigurePlan,
    subpanels: list[SubpanelPlan],
    supplements: list[SupplementPlan],
) -> list[FigurePlanProblem]:
    problems: list[FigurePlanProblem] = []
    subpanel_ids = {subpanel.subpanel_id for subpanel in subpanels}
    supplement_ids = {supplement.supplement_id for supplement in supplements}
    subpanels_by_id = {subpanel.subpanel_id: subpanel for subpanel in subpanels}

    for subpanel_id in plan.subpanel_ids:
        if subpanel_id not in subpanel_ids:
            problems.append(
                FigurePlanProblem("fail", f"figure plan references missing subpanel_id: {subpanel_id}")
            )

    referenced_letters = {
        subpanels_by_id[subpanel_id].letter
        for subpanel_id in plan.subpanel_ids
        if subpanel_id in subpanels_by_id
    }
    for letter in plan.reading_order:
        if letter not in referenced_letters:
            problems.append(
                FigurePlanProblem(
                    "fail",
                    f"reading_order letter not present in referenced subpanels: {letter}",
                )
            )

    for supplement_id in plan.supplement_ids:
        if supplement_id not in supplement_ids:
            problems.append(
                FigurePlanProblem(
                    "fail",
                    f"figure plan references missing supplement_id: {supplement_id}",
                )
            )

    for subpanel in subpanels:
        for supplement_id in subpanel.supplement_ids:
            if supplement_id not in supplement_ids:
                problems.append(
                    FigurePlanProblem(
                        "fail",
                        f"subpanel {subpanel.subpanel_id} references missing supplement_id: "
                        f"{supplement_id}",
                    )
                )

    for supplement in supplements:
        if _present(supplement.parent_subpanel_id) and supplement.parent_subpanel_id not in subpanel_ids:
            problems.append(
                FigurePlanProblem(
                    "fail",
                    f"supplement {supplement.supplement_id} references missing parent_subpanel_id: "
                    f"{supplement.parent_subpanel_id}",
                )
            )

    return problems


def _duplicate_letter_problems(subpanels: list[SubpanelPlan]) -> list[FigurePlanProblem]:
    problems: list[FigurePlanProblem] = []
    seen: set[tuple[str, str]] = set()
    for subpanel in subpanels:
        key = (subpanel.figure_id, subpanel.letter)
        if key in seen:
            problems.append(
                FigurePlanProblem(
                    "fail",
                    f"duplicate subpanel figure/letter pair: {subpanel.figure_id}/{subpanel.letter}",
                )
            )
        seen.add(key)
    return problems


def _audit_from_messages(messages: list[str]) -> FigurePlanAudit:
    problems = [FigurePlanProblem("fail", message) for message in messages]
    return FigurePlanAudit(overall_severity=_aggregate(problems), problems=problems)


def _extend_messages(problems: list[FigurePlanProblem], messages: list[str]) -> None:
    problems.extend(FigurePlanProblem("fail", message) for message in messages)


def _required_string_problems(
    record_name: str,
    record_id: str,
    values: dict[str, str],
) -> list[str]:
    problems: list[str] = []
    label = record_id or "<missing>"
    for field_name, value in values.items():
        if not value.strip():
            problems.append(f"{record_name} {label} missing required field: {field_name}")
    return problems


def _aggregate(problems: list[FigurePlanProblem]) -> PlanSeverity:
    if not problems:
        return "pass"
    return max((problem.severity for problem in problems), key=lambda severity: _SEVERITY_RANK[severity])


def _severity_from_value(value: Any) -> PlanSeverity:
    if value in {"pass", "warn", "fail"}:
        return cast("PlanSeverity", value)
    return "fail"


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


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


def _present(value: str | None) -> bool:
    return value is not None and bool(value.strip())


def _enum_from_value(enum_cls: type[EnumT], value: Any, default: EnumT) -> EnumT:
    if value is None:
        return default
    for member in enum_cls:
        if value == member.value or value == member.name:
            return member
    return default


__all__ = [
    "SCHEMA",
    "FigurePlan",
    "FigurePlanAudit",
    "FigurePlanProblem",
    "PlanSeverity",
    "SubpanelPlan",
    "SubpanelReadiness",
    "SupplementPlan",
    "SupportRole",
    "dump_plan",
    "load_plan",
    "validate_figure_plan",
]
