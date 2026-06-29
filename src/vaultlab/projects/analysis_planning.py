"""Deterministic analysis-opportunity planning."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Literal, cast

from vaultlab.projects.data_inventory import AccessStatus, DataInventory
from vaultlab.projects.figure_plan import FigurePlan, SubpanelPlan, SupplementPlan, SupportRole

SCHEMA = "vaultlab-analysis-opportunity/v1"

AnalysisSeverity = Literal["pass", "warn", "fail"]

_SEVERITY_RANK: dict[AnalysisSeverity, int] = {"pass": 0, "warn": 1, "fail": 2}
_DONOR_SUPPORT_ROLES = {SupportRole.ROBUSTNESS, SupportRole.FULL_CATEGORY_COVERAGE}


@dataclass(frozen=True)
class AnalysisOpportunity:
    """One deterministic opportunity to strengthen a planned analysis."""

    opportunity_id: str
    question: str
    claim_supported: str | None
    data_needed: list[str]
    data_status: str
    method: str
    rigor_note: str
    failure_mode_controlled: str
    figure_destination: str | None
    supplement_destination: str | None
    compute_estimate: str | None
    risk: str
    priority: int

    def to_dict(self) -> dict[str, Any]:
        """Serialize this opportunity to a JSON-ready dict."""

        return {
            "schema": SCHEMA,
            "opportunity_id": self.opportunity_id,
            "question": self.question,
            "claim_supported": self.claim_supported,
            "data_needed": list(self.data_needed),
            "data_status": self.data_status,
            "method": self.method,
            "rigor_note": self.rigor_note,
            "failure_mode_controlled": self.failure_mode_controlled,
            "figure_destination": self.figure_destination,
            "supplement_destination": self.supplement_destination,
            "compute_estimate": self.compute_estimate,
            "risk": self.risk,
            "priority": self.priority,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> AnalysisOpportunity:
        """Build an analysis opportunity from parsed JSON."""

        return cls(
            opportunity_id=str(payload.get("opportunity_id", "")),
            question=str(payload.get("question", "")),
            claim_supported=_optional_str(payload.get("claim_supported")),
            data_needed=_string_list(payload.get("data_needed", [])),
            data_status=str(payload.get("data_status", "")),
            method=str(payload.get("method", "")),
            rigor_note=str(payload.get("rigor_note", "")),
            failure_mode_controlled=str(payload.get("failure_mode_controlled", "")),
            figure_destination=_optional_str(payload.get("figure_destination")),
            supplement_destination=_optional_str(payload.get("supplement_destination")),
            compute_estimate=_optional_str(payload.get("compute_estimate")),
            risk=str(payload.get("risk", "")),
            priority=int(payload.get("priority", 0)),
        )

    def validate(self) -> list[str]:
        """Return soft opportunity-record problems."""

        problems = _required_string_problems(
            "analysis opportunity",
            self.opportunity_id,
            {
                "opportunity_id": self.opportunity_id,
                "question": self.question,
                "data_status": self.data_status,
                "method": self.method,
                "rigor_note": self.rigor_note,
                "failure_mode_controlled": self.failure_mode_controlled,
                "risk": self.risk,
            },
        )
        if self.priority < 0:
            problems.append(
                f"analysis opportunity {self.opportunity_id or '<missing>'} "
                "priority must be non-negative"
            )
        if not _present(self.figure_destination) and not _present(self.supplement_destination):
            problems.append(
                f"analysis opportunity {self.opportunity_id or '<missing>'} "
                "needs figure_destination or supplement_destination"
            )
        return problems

    def audit(self) -> AnalysisOpportunityAudit:
        """Audit this opportunity record."""

        return _audit_from_messages(self.validate())


@dataclass(frozen=True)
class AnalysisOpportunityProblem:
    """One structured analysis-opportunity audit problem."""

    severity: AnalysisSeverity
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
    def from_dict(cls, payload: dict[str, Any]) -> AnalysisOpportunityProblem:
        """Build an analysis-opportunity problem from parsed JSON."""

        return cls(
            severity=_severity_from_value(payload.get("severity")),
            message=str(payload.get("message", "")),
            field=_optional_str(payload.get("field")),
        )


@dataclass(frozen=True)
class AnalysisOpportunityAudit:
    """Structured result from analysis-opportunity validation."""

    overall_severity: AnalysisSeverity
    problems: list[AnalysisOpportunityProblem] = field(default_factory=list)

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
    def from_dict(cls, payload: dict[str, Any]) -> AnalysisOpportunityAudit:
        """Build an analysis-opportunity audit from parsed JSON."""

        problems = [
            AnalysisOpportunityProblem.from_dict(item)
            for item in _dict_list(payload.get("problems", []))
        ]
        return cls(overall_severity=_aggregate(problems), problems=problems)


def find_coverage_gaps(
    plan: FigurePlan,
    subpanels: list[SubpanelPlan],
    supplements: list[SupplementPlan],
    inventory: DataInventory,
) -> list[AnalysisOpportunity]:
    """Find deterministic analysis opportunities from plan and inventory coverage."""

    opportunities: list[AnalysisOpportunity] = []
    selected_subpanels = _selected_subpanels(plan, subpanels)

    opportunities.extend(_missing_dataset_opportunities(selected_subpanels, inventory))
    if not any(supplement.support_role is SupportRole.NEGATIVE_CONTROL for supplement in supplements):
        data_needed = ["negative_control_dataset"]
        opportunities.append(
            AnalysisOpportunity(
                opportunity_id=f"{_slug(plan.figure_id)}-negative-control",
                question=f"Add a negative-control supplement for {plan.figure_id}.",
                claim_supported=None,
                data_needed=data_needed,
                data_status=_data_status(data_needed, inventory),
                method="negative control supplement",
                rigor_note="Controls whether the planned pattern appears under a null condition.",
                failure_mode_controlled="missing_negative_control",
                figure_destination=plan.figure_id,
                supplement_destination="negative_control",
                compute_estimate="undecided",
                risk="high",
                priority=20,
            )
        )

    if selected_subpanels:
        for subpanel in selected_subpanels:
            if not _has_donor_support(subpanel, supplements):
                data_needed = [subpanel.source_result] if subpanel.source_result.strip() else []
                opportunities.append(
                    AnalysisOpportunity(
                        opportunity_id=(
                            f"{_slug(subpanel.subpanel_id)}-donor-aware-support"
                        ),
                        question=(
                            f"Add donor-aware support for "
                            f"{subpanel.figure_id}/{subpanel.letter}."
                        ),
                        claim_supported=subpanel.claim_id,
                        data_needed=data_needed,
                        data_status=_data_status(data_needed, inventory),
                        method="donor-stratified robustness check",
                        rigor_note="Controls donor-level replication before promotion.",
                        failure_mode_controlled="donor_confounding",
                        figure_destination=f"{subpanel.figure_id}/{subpanel.letter}",
                        supplement_destination="donor_aware_support",
                        compute_estimate="undecided",
                        risk="medium",
                        priority=30,
                    )
                )
    elif not _has_any_donor_support(supplements):
        opportunities.append(
            AnalysisOpportunity(
                opportunity_id=f"{_slug(plan.figure_id)}-donor-aware-support",
                question=f"Add donor-aware support for {plan.figure_id}.",
                claim_supported=None,
                data_needed=[],
                data_status="available",
                method="donor-stratified robustness check",
                rigor_note="Controls donor-level replication before promotion.",
                failure_mode_controlled="donor_confounding",
                figure_destination=plan.figure_id,
                supplement_destination="donor_aware_support",
                compute_estimate="undecided",
                risk="medium",
                priority=30,
            )
        )

    return sorted(opportunities, key=lambda item: (item.priority, item.opportunity_id))


def _selected_subpanels(plan: FigurePlan, subpanels: list[SubpanelPlan]) -> list[SubpanelPlan]:
    if not plan.subpanel_ids:
        return [subpanel for subpanel in subpanels if subpanel.figure_id == plan.figure_id]
    wanted = set(plan.subpanel_ids)
    return [subpanel for subpanel in subpanels if subpanel.subpanel_id in wanted]


def _missing_dataset_opportunities(
    subpanels: list[SubpanelPlan],
    inventory: DataInventory,
) -> list[AnalysisOpportunity]:
    opportunities: list[AnalysisOpportunity] = []
    known_ids = {dataset.dataset_id for dataset in inventory.datasets}
    seen_missing: set[str] = set()
    for subpanel in subpanels:
        dataset_id = subpanel.source_result
        if not dataset_id.strip() or dataset_id in known_ids or dataset_id in seen_missing:
            continue
        seen_missing.add(dataset_id)
        opportunities.append(
            AnalysisOpportunity(
                opportunity_id=f"missing-dataset-{_slug(dataset_id)}",
                question=f"Add dataset {dataset_id} needed by {subpanel.figure_id}/{subpanel.letter}.",
                claim_supported=subpanel.claim_id,
                data_needed=[dataset_id],
                data_status="needs_collection",
                method="stage or collect missing dataset",
                rigor_note="Planning cannot verify coverage for absent inputs.",
                failure_mode_controlled="missing_input_data",
                figure_destination=f"{subpanel.figure_id}/{subpanel.letter}",
                supplement_destination=None,
                compute_estimate="undecided",
                risk="high",
                priority=10,
            )
        )
    return opportunities


def _has_donor_support(subpanel: SubpanelPlan, supplements: list[SupplementPlan]) -> bool:
    linked_supplements = [
        supplement
        for supplement in supplements
        if supplement.parent_subpanel_id == subpanel.subpanel_id
        or supplement.supplement_id in subpanel.supplement_ids
    ]
    return any(supplement.support_role in _DONOR_SUPPORT_ROLES for supplement in linked_supplements)


def _has_any_donor_support(supplements: list[SupplementPlan]) -> bool:
    return any(supplement.support_role in _DONOR_SUPPORT_ROLES for supplement in supplements)


def _data_status(data_needed: list[str], inventory: DataInventory) -> str:
    if not data_needed:
        return "available"

    by_id = {dataset.dataset_id: dataset for dataset in inventory.datasets}
    statuses: list[AccessStatus] = []
    for dataset_id in data_needed:
        dataset = by_id.get(dataset_id)
        if dataset is None:
            return "needs_collection"
        statuses.append(dataset.access)

    if any(status is AccessStatus.NEEDS_COLLECTION for status in statuses):
        return "needs_collection"
    if any(status is AccessStatus.RESTRICTED for status in statuses):
        return "restricted"
    if any(status is AccessStatus.STAGED for status in statuses):
        return "staged"
    return "available"


def _audit_from_messages(messages: list[str]) -> AnalysisOpportunityAudit:
    problems = [AnalysisOpportunityProblem("fail", message) for message in messages]
    return AnalysisOpportunityAudit(overall_severity=_aggregate(problems), problems=problems)


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


def _aggregate(problems: list[AnalysisOpportunityProblem]) -> AnalysisSeverity:
    if not problems:
        return "pass"
    return max((problem.severity for problem in problems), key=lambda severity: _SEVERITY_RANK[severity])


def _severity_from_value(value: Any) -> AnalysisSeverity:
    if value in {"pass", "warn", "fail"}:
        return cast("AnalysisSeverity", value)
    return "fail"


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def _dict_list(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [cast("dict[str, Any]", item) for item in value if isinstance(item, dict)]


def _present(value: str | None) -> bool:
    return value is not None and bool(value.strip())


def _slug(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "-", value.strip()).strip("-").lower()
    return slug or "missing"


__all__ = [
    "SCHEMA",
    "AnalysisOpportunity",
    "AnalysisOpportunityAudit",
    "AnalysisOpportunityProblem",
    "AnalysisSeverity",
    "find_coverage_gaps",
]

