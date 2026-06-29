"""Deterministic compute planning contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Literal, TypeVar, cast

SCHEMA = "vaultlab-compute-plan/v1"

ComputeSeverity = Literal["pass", "warn", "fail"]

_SEVERITY_RANK: dict[ComputeSeverity, int] = {"pass": 0, "warn": 1, "fail": 2}
_BYTES_PER_GIB = 1024.0**3

EnumT = TypeVar("EnumT", bound=Enum)


class ComputeTarget(str, Enum):
    """Where an analysis should run."""

    LOCAL = "local"
    REMOTE_CLUSTER = "remote_cluster"
    UNDECIDED = "undecided"


@dataclass(frozen=True)
class ResourceHints:
    """Lightweight arithmetic hints for deterministic compute classification."""

    n_rows: int | None = None
    n_units: int | None = None
    input_bytes: int | None = None
    per_row_bytes: float | None = None
    prior_peak_ram_gb: float | None = None
    prior_runtime_min: float | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize this resource hint record to a JSON-ready dict."""

        return {
            "n_rows": self.n_rows,
            "n_units": self.n_units,
            "input_bytes": self.input_bytes,
            "per_row_bytes": self.per_row_bytes,
            "prior_peak_ram_gb": self.prior_peak_ram_gb,
            "prior_runtime_min": self.prior_runtime_min,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> ResourceHints:
        """Build resource hints from parsed JSON."""

        return cls(
            n_rows=_optional_int(payload.get("n_rows")),
            n_units=_optional_int(payload.get("n_units")),
            input_bytes=_optional_int(payload.get("input_bytes")),
            per_row_bytes=_optional_float(payload.get("per_row_bytes")),
            prior_peak_ram_gb=_optional_float(payload.get("prior_peak_ram_gb")),
            prior_runtime_min=_optional_float(payload.get("prior_runtime_min")),
        )

    def validate(self) -> list[str]:
        """Return soft schema problems without touching any runtime system."""

        problems: list[str] = []
        _append_non_negative_int(problems, "n_rows", self.n_rows)
        _append_non_negative_int(problems, "n_units", self.n_units)
        _append_non_negative_int(problems, "input_bytes", self.input_bytes)
        _append_non_negative_float(problems, "per_row_bytes", self.per_row_bytes)
        _append_non_negative_float(problems, "prior_peak_ram_gb", self.prior_peak_ram_gb)
        _append_non_negative_float(problems, "prior_runtime_min", self.prior_runtime_min)
        return problems

    def audit(self) -> ComputePlanAudit:
        """Audit this resource-hint record."""

        return _audit_from_messages(self.validate())


@dataclass(frozen=True)
class ComputePlan:
    """Machine-readable plan for where and how one analysis should run."""

    analysis_id: str
    target: ComputeTarget
    est_ram_gb: float | None
    est_walltime_min: float | None
    cpu: int = 1
    gpu: int = 0
    partition: str | None = None
    account: str | None = None
    job_array_shape: str | None = None
    checkpoint_strategy: str | None = None
    smoke_run_cmd: str | None = None
    full_run_cmd: str | None = None
    sync_back: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Serialize this compute plan to a JSON-ready dict."""

        return {
            "schema": SCHEMA,
            "analysis_id": self.analysis_id,
            "target": self.target.value,
            "est_ram_gb": self.est_ram_gb,
            "est_walltime_min": self.est_walltime_min,
            "cpu": self.cpu,
            "gpu": self.gpu,
            "partition": self.partition,
            "account": self.account,
            "job_array_shape": self.job_array_shape,
            "checkpoint_strategy": self.checkpoint_strategy,
            "smoke_run_cmd": self.smoke_run_cmd,
            "full_run_cmd": self.full_run_cmd,
            "sync_back": self.sync_back,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> ComputePlan:
        """Build a compute plan from parsed JSON."""

        return cls(
            analysis_id=str(payload.get("analysis_id", "")),
            target=_enum_from_value(
                ComputeTarget,
                payload.get("target"),
                ComputeTarget.UNDECIDED,
            ),
            est_ram_gb=_optional_float(payload.get("est_ram_gb")),
            est_walltime_min=_optional_float(payload.get("est_walltime_min")),
            cpu=int(payload.get("cpu", 1)),
            gpu=int(payload.get("gpu", 0)),
            partition=_optional_str(payload.get("partition")),
            account=_optional_str(payload.get("account")),
            job_array_shape=_optional_str(payload.get("job_array_shape")),
            checkpoint_strategy=_optional_str(payload.get("checkpoint_strategy")),
            smoke_run_cmd=_optional_str(payload.get("smoke_run_cmd")),
            full_run_cmd=_optional_str(payload.get("full_run_cmd")),
            sync_back=bool(payload.get("sync_back", False)),
        )

    def validate(self) -> list[str]:
        """Return soft schema problems without Slurm, SSH, or filesystem access."""

        problems = _required_string_problems(
            "compute plan",
            self.analysis_id,
            {"analysis_id": self.analysis_id},
        )
        if self.est_ram_gb is not None and self.est_ram_gb < 0:
            problems.append(f"compute plan {self.analysis_id or '<missing>'} est_ram_gb must be non-negative")
        if self.est_walltime_min is not None and self.est_walltime_min < 0:
            problems.append(
                f"compute plan {self.analysis_id or '<missing>'} "
                "est_walltime_min must be non-negative"
            )
        if self.cpu < 1:
            problems.append(f"compute plan {self.analysis_id or '<missing>'} cpu must be >= 1")
        if self.gpu < 0:
            problems.append(f"compute plan {self.analysis_id or '<missing>'} gpu must be non-negative")
        if self.target is ComputeTarget.REMOTE_CLUSTER:
            if not _present(self.smoke_run_cmd):
                problems.append(
                    f"compute plan {self.analysis_id or '<missing>'} "
                    "remote target missing smoke_run_cmd"
                )
            if not _present(self.checkpoint_strategy):
                problems.append(
                    f"compute plan {self.analysis_id or '<missing>'} "
                    "remote target missing checkpoint_strategy"
                )
        return problems

    def audit(self) -> ComputePlanAudit:
        """Audit this compute plan."""

        return _audit_from_messages(self.validate())


@dataclass(frozen=True)
class ComputePlanProblem:
    """One structured compute-plan audit problem."""

    severity: ComputeSeverity
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
    def from_dict(cls, payload: dict[str, Any]) -> ComputePlanProblem:
        """Build a compute-plan problem from parsed JSON."""

        return cls(
            severity=_severity_from_value(payload.get("severity")),
            message=str(payload.get("message", "")),
            field=_optional_str(payload.get("field")),
        )


@dataclass(frozen=True)
class ComputePlanAudit:
    """Structured result from compute-plan validation."""

    overall_severity: ComputeSeverity
    problems: list[ComputePlanProblem] = field(default_factory=list)

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
    def from_dict(cls, payload: dict[str, Any]) -> ComputePlanAudit:
        """Build an audit from parsed JSON."""

        problems = [
            ComputePlanProblem.from_dict(item) for item in _dict_list(payload.get("problems", []))
        ]
        return cls(overall_severity=_aggregate(problems), problems=problems)


def classify_compute_target(
    hints: ResourceHints,
    *,
    analysis_id: str = "unassigned-analysis",
    local_ram_gb: float = 16.0,
    local_runtime_min: float = 30.0,
) -> ComputePlan:
    """Classify a compute target using deterministic arithmetic only.

    ``analysis_id`` names the resulting plan; pass it so callers do not have to
    rebuild the frozen ``ComputePlan`` just to label it.
    """

    est_ram_gb = _estimate_ram_gb(hints)
    est_walltime_min = _estimate_walltime_min(hints)

    ram_exceeds = est_ram_gb is not None and est_ram_gb > local_ram_gb
    walltime_exceeds = est_walltime_min is not None and est_walltime_min > local_runtime_min
    if ram_exceeds or walltime_exceeds:
        # A known estimate over the local budget forces remote even if the other
        # estimate is unknown -- a 64 GB job needs a cluster regardless of walltime.
        target = ComputeTarget.REMOTE_CLUSTER
    elif est_ram_gb is None or est_walltime_min is None:
        # Under budget on what we know, but missing one estimate: cannot confirm local.
        target = ComputeTarget.UNDECIDED
    else:
        target = ComputeTarget.LOCAL

    return ComputePlan(
        analysis_id=analysis_id,
        target=target,
        est_ram_gb=est_ram_gb,
        est_walltime_min=est_walltime_min,
    )


def _estimate_ram_gb(hints: ResourceHints) -> float | None:
    if hints.prior_peak_ram_gb is not None:
        return hints.prior_peak_ram_gb
    if hints.n_rows is not None and hints.per_row_bytes is not None:
        return (float(hints.n_rows) * hints.per_row_bytes) / _BYTES_PER_GIB
    if hints.input_bytes is not None:
        return float(hints.input_bytes) / _BYTES_PER_GIB
    return None


def _estimate_walltime_min(hints: ResourceHints) -> float | None:
    if hints.prior_runtime_min is not None:
        return hints.prior_runtime_min
    if hints.n_rows is not None and hints.n_units is not None:
        return max(1.0, (float(hints.n_rows) * max(float(hints.n_units), 1.0)) / 1_000_000.0)
    return None


def _audit_from_messages(messages: list[str]) -> ComputePlanAudit:
    problems = [ComputePlanProblem("fail", message) for message in messages]
    return ComputePlanAudit(overall_severity=_aggregate(problems), problems=problems)


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


def _append_non_negative_int(problems: list[str], field_name: str, value: int | None) -> None:
    if value is not None and value < 0:
        problems.append(f"resource hints {field_name} must be non-negative")


def _append_non_negative_float(problems: list[str], field_name: str, value: float | None) -> None:
    if value is not None and value < 0:
        problems.append(f"resource hints {field_name} must be non-negative")


def _aggregate(problems: list[ComputePlanProblem]) -> ComputeSeverity:
    if not problems:
        return "pass"
    return max((problem.severity for problem in problems), key=lambda severity: _SEVERITY_RANK[severity])


def _severity_from_value(value: Any) -> ComputeSeverity:
    if value in {"pass", "warn", "fail"}:
        return cast("ComputeSeverity", value)
    return "fail"


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    return int(value)


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    return float(value)


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
    "ComputePlan",
    "ComputePlanAudit",
    "ComputePlanProblem",
    "ComputeSeverity",
    "ComputeTarget",
    "ResourceHints",
    "classify_compute_target",
]

