"""Filesystem-free data inventory contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Literal, TypeVar, cast

SCHEMA = "vaultlab-data-inventory/v1"

InventorySeverity = Literal["pass", "warn", "fail"]

_SEVERITY_RANK: dict[InventorySeverity, int] = {"pass": 0, "warn": 1, "fail": 2}

EnumT = TypeVar("EnumT", bound=Enum)


class AccessStatus(str, Enum):
    """Current access state for a dataset."""

    AVAILABLE = "available"
    STAGED = "staged"
    NEEDS_COLLECTION = "needs_collection"
    RESTRICTED = "restricted"


@dataclass(frozen=True)
class DatasetRecord:
    """One dataset needed by a planned analysis or figure."""

    dataset_id: str
    modality: str
    scale: str
    unit_coverage: list[str]
    replication_unit: str
    location: str
    fmt: str
    size_bytes: int | None
    processing_stage: str
    access: AccessStatus
    caveats: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Serialize this dataset record to a JSON-ready dict."""

        return {
            "dataset_id": self.dataset_id,
            "modality": self.modality,
            "scale": self.scale,
            "unit_coverage": list(self.unit_coverage),
            "replication_unit": self.replication_unit,
            "location": self.location,
            "fmt": self.fmt,
            "size_bytes": self.size_bytes,
            "processing_stage": self.processing_stage,
            "access": self.access.value,
            "caveats": list(self.caveats),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> DatasetRecord:
        """Build a dataset record from parsed JSON."""

        return cls(
            dataset_id=str(payload.get("dataset_id", "")),
            modality=str(payload.get("modality", "")),
            scale=str(payload.get("scale", "")),
            unit_coverage=_string_list(payload.get("unit_coverage", [])),
            replication_unit=str(payload.get("replication_unit", "")),
            location=str(payload.get("location", "")),
            fmt=str(payload.get("fmt", "")),
            size_bytes=_optional_int(payload.get("size_bytes")),
            processing_stage=str(payload.get("processing_stage", "")),
            access=_enum_from_value(
                AccessStatus,
                payload.get("access"),
                AccessStatus.NEEDS_COLLECTION,
            ),
            caveats=_string_list(payload.get("caveats", [])),
        )

    def validate(self) -> list[str]:
        """Return soft record problems without dereferencing the location string."""

        problems = _required_string_problems(
            "dataset",
            self.dataset_id,
            {
                "dataset_id": self.dataset_id,
                "modality": self.modality,
                "scale": self.scale,
                "replication_unit": self.replication_unit,
                "location": self.location,
                "fmt": self.fmt,
                "processing_stage": self.processing_stage,
            },
        )
        if not self.unit_coverage:
            problems.append(f"dataset {self.dataset_id or '<missing>'} missing required field: unit_coverage")
        if self.size_bytes is not None and self.size_bytes < 0:
            problems.append(f"dataset {self.dataset_id or '<missing>'} size_bytes must be non-negative")
        return problems

    def audit(self) -> DataInventoryAudit:
        """Audit this dataset record."""

        return _audit_from_messages(self.validate())


@dataclass(frozen=True)
class DataInventory:
    """Collection of dataset records for deterministic planning."""

    datasets: list[DatasetRecord] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Serialize this inventory to a JSON-ready dict."""

        return {
            "schema": SCHEMA,
            "datasets": [dataset.to_dict() for dataset in self.datasets],
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> DataInventory:
        """Build an inventory from parsed JSON."""

        return cls(
            datasets=[
                DatasetRecord.from_dict(item) for item in _dict_list(payload.get("datasets", []))
            ]
        )

    def validate(self) -> list[str]:
        """Return soft inventory problems."""

        problems: list[str] = []
        seen: set[str] = set()
        for dataset in self.datasets:
            problems.extend(dataset.validate())
            if dataset.dataset_id in seen:
                problems.append(f"duplicate dataset_id: {dataset.dataset_id}")
            if dataset.dataset_id:
                seen.add(dataset.dataset_id)
        return problems

    def summarize(self) -> InventorySummary:
        """Partition datasets by available/staged, needs-collection, and restricted status."""

        available_or_staged: list[str] = []
        needs_collection: list[str] = []
        restricted: list[str] = []
        for dataset in self.datasets:
            if dataset.access in {AccessStatus.AVAILABLE, AccessStatus.STAGED}:
                available_or_staged.append(dataset.dataset_id)
            elif dataset.access is AccessStatus.NEEDS_COLLECTION:
                needs_collection.append(dataset.dataset_id)
            elif dataset.access is AccessStatus.RESTRICTED:
                restricted.append(dataset.dataset_id)
        return InventorySummary(
            n_total=len(self.datasets),
            available_or_staged=available_or_staged,
            needs_collection=needs_collection,
            restricted=restricted,
        )

    def audit(self) -> DataInventoryAudit:
        """Audit this data inventory."""

        return _audit_from_messages(self.validate())


@dataclass(frozen=True)
class InventorySummary:
    """Small deterministic summary of inventory availability."""

    n_total: int
    available_or_staged: list[str] = field(default_factory=list)
    needs_collection: list[str] = field(default_factory=list)
    restricted: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Serialize this inventory summary."""

        return {
            "n_total": self.n_total,
            "available_or_staged": list(self.available_or_staged),
            "needs_collection": list(self.needs_collection),
            "restricted": list(self.restricted),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> InventorySummary:
        """Build an inventory summary from parsed JSON."""

        return cls(
            n_total=int(payload.get("n_total", 0)),
            available_or_staged=_string_list(payload.get("available_or_staged", [])),
            needs_collection=_string_list(payload.get("needs_collection", [])),
            restricted=_string_list(payload.get("restricted", [])),
        )

    def validate(self) -> list[str]:
        """Return soft summary-record problems."""

        problems: list[str] = []
        if self.n_total < 0:
            problems.append("inventory summary n_total must be non-negative")
        observed = len(self.available_or_staged) + len(self.needs_collection) + len(self.restricted)
        if observed != self.n_total:
            problems.append(
                f"inventory summary partition counts ({observed}) do not sum to n_total "
                f"({self.n_total})"
            )
        return problems

    def audit(self) -> DataInventoryAudit:
        """Audit this inventory summary."""

        return _audit_from_messages(self.validate())


@dataclass(frozen=True)
class DataInventoryProblem:
    """One structured data-inventory audit problem."""

    severity: InventorySeverity
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
    def from_dict(cls, payload: dict[str, Any]) -> DataInventoryProblem:
        """Build an inventory problem from parsed JSON."""

        return cls(
            severity=_severity_from_value(payload.get("severity")),
            message=str(payload.get("message", "")),
            field=_optional_str(payload.get("field")),
        )


@dataclass(frozen=True)
class DataInventoryAudit:
    """Structured result from data-inventory validation."""

    overall_severity: InventorySeverity
    problems: list[DataInventoryProblem] = field(default_factory=list)

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
    def from_dict(cls, payload: dict[str, Any]) -> DataInventoryAudit:
        """Build an inventory audit from parsed JSON."""

        problems = [
            DataInventoryProblem.from_dict(item) for item in _dict_list(payload.get("problems", []))
        ]
        return cls(overall_severity=_aggregate(problems), problems=problems)


def _audit_from_messages(messages: list[str]) -> DataInventoryAudit:
    problems = [DataInventoryProblem("fail", message) for message in messages]
    return DataInventoryAudit(overall_severity=_aggregate(problems), problems=problems)


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


def _aggregate(problems: list[DataInventoryProblem]) -> InventorySeverity:
    if not problems:
        return "pass"
    return max((problem.severity for problem in problems), key=lambda severity: _SEVERITY_RANK[severity])


def _severity_from_value(value: Any) -> InventorySeverity:
    if value in {"pass", "warn", "fail"}:
        return cast("InventorySeverity", value)
    return "fail"


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    return int(value)


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def _dict_list(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [cast("dict[str, Any]", item) for item in value if isinstance(item, dict)]


def _enum_from_value(enum_cls: type[EnumT], value: Any, default: EnumT) -> EnumT:
    if value is None:
        return default
    for member in enum_cls:
        if value == member.value or value == member.name:
            return member
    return default


__all__ = [
    "SCHEMA",
    "AccessStatus",
    "DataInventory",
    "DataInventoryAudit",
    "DataInventoryProblem",
    "DatasetRecord",
    "InventorySeverity",
    "InventorySummary",
]

