"""Deterministic lane handoff and read-receipt contracts."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Literal, TypeVar, cast

SCHEMA = "vaultlab-lane-log/v1"

LaneSeverity = Literal["pass", "warn", "fail"]

_SEVERITY_RANK: dict[LaneSeverity, int] = {"pass": 0, "warn": 1, "fail": 2}

EnumT = TypeVar("EnumT", bound=Enum)


class Lane(str, Enum):
    """Project-work lane that can hand off artifacts to another lane."""

    FIGURES = "figures"
    STORYLINE = "storyline"
    COMPUTE = "compute"
    REVIEW = "review"
    SANDBOX = "sandbox"


@dataclass(frozen=True)
class ReadReceipt:
    """Record that a role read specific project context before acting."""

    file_path: str
    role: str
    sections_read: list[str]
    key_facts: list[str]
    timestamp: str

    def to_dict(self) -> dict[str, Any]:
        """Serialize this read receipt."""

        return {
            "file_path": self.file_path,
            "role": self.role,
            "sections_read": list(self.sections_read),
            "key_facts": list(self.key_facts),
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> ReadReceipt:
        """Build a read receipt from parsed JSON."""

        return cls(
            file_path=str(payload.get("file_path", "")),
            role=str(payload.get("role", "")),
            sections_read=_string_list(payload.get("sections_read", [])),
            key_facts=_string_list(payload.get("key_facts", [])),
            timestamp=str(payload.get("timestamp", "")),
        )

    def validate(self) -> list[str]:
        """Return soft read-receipt problems."""

        problems = _required_string_problems(
            "read receipt",
            self.file_path,
            {
                "file_path": self.file_path,
                "role": self.role,
                "timestamp": self.timestamp,
            },
        )
        if not self.sections_read:
            problems.append(f"read receipt {self.file_path or '<missing>'} missing sections_read")
        if not self.key_facts:
            problems.append(f"read receipt {self.file_path or '<missing>'} missing key_facts")
        return problems

    def audit(self) -> LaneLogAudit:
        """Audit this read receipt."""

        return _audit_from_messages(self.validate())


@dataclass(frozen=True)
class LaneHandoff:
    """One handoff from a source lane to a target lane."""

    source: Lane
    target: Lane
    status: str
    artifacts: list[str] = field(default_factory=list)
    verification: list[str] = field(default_factory=list)
    downstream_request: str | None = None
    open_decisions: list[str] = field(default_factory=list)
    read_receipts: list[ReadReceipt] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Serialize this lane handoff."""

        return {
            "schema": SCHEMA,
            "source": self.source.value,
            "target": self.target.value,
            "status": self.status,
            "artifacts": list(self.artifacts),
            "verification": list(self.verification),
            "downstream_request": self.downstream_request,
            "open_decisions": list(self.open_decisions),
            "read_receipts": [receipt.to_dict() for receipt in self.read_receipts],
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> LaneHandoff:
        """Build a lane handoff from parsed JSON."""

        return cls(
            source=_enum_from_value(Lane, payload.get("source"), Lane.SANDBOX),
            target=_enum_from_value(Lane, payload.get("target"), Lane.REVIEW),
            status=str(payload.get("status", "")),
            artifacts=_string_list(payload.get("artifacts", [])),
            verification=_string_list(payload.get("verification", [])),
            downstream_request=_optional_str(payload.get("downstream_request")),
            open_decisions=_string_list(payload.get("open_decisions", [])),
            read_receipts=[
                ReadReceipt.from_dict(item) for item in _dict_list(payload.get("read_receipts", []))
            ],
        )

    def validate(self) -> list[str]:
        """Return intrinsic handoff problems (status/verification consistency).

        This checks only what the handoff can self-assess. Required-read
        enforcement is a caller-supplied policy: pass the read set to
        :func:`validate_handoff` as ``required_reads=...`` to flag missing
        receipts. ``validate()`` / ``audit()`` here do not know which reads a
        given handoff required, so they never raise a missing-read problem.
        """

        return validate_handoff(self)

    def audit(self) -> LaneLogAudit:
        """Audit this lane handoff."""

        return _audit_from_messages(self.validate())


@dataclass(frozen=True)
class LanePairStatus:
    """Merged status for handoffs sharing one source-target lane pair."""

    source: Lane
    target: Lane
    handoff_count: int
    latest_status: str
    artifacts: list[str] = field(default_factory=list)
    verification: list[str] = field(default_factory=list)
    open_decisions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Serialize this lane-pair status."""

        return {
            "source": self.source.value,
            "target": self.target.value,
            "handoff_count": self.handoff_count,
            "latest_status": self.latest_status,
            "artifacts": list(self.artifacts),
            "verification": list(self.verification),
            "open_decisions": list(self.open_decisions),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> LanePairStatus:
        """Build lane-pair status from parsed JSON."""

        return cls(
            source=_enum_from_value(Lane, payload.get("source"), Lane.SANDBOX),
            target=_enum_from_value(Lane, payload.get("target"), Lane.REVIEW),
            handoff_count=int(payload.get("handoff_count", 0)),
            latest_status=str(payload.get("latest_status", "")),
            artifacts=_string_list(payload.get("artifacts", [])),
            verification=_string_list(payload.get("verification", [])),
            open_decisions=_string_list(payload.get("open_decisions", [])),
        )

    def validate(self) -> list[str]:
        """Return soft lane-pair status problems."""

        problems: list[str] = []
        if self.handoff_count < 0:
            problems.append(
                f"lane pair {self.source.value}->{self.target.value} "
                "handoff_count must be non-negative"
            )
        if not self.latest_status.strip() and self.handoff_count > 0:
            problems.append(
                f"lane pair {self.source.value}->{self.target.value} "
                "missing latest_status"
            )
        return problems

    def audit(self) -> LaneLogAudit:
        """Audit this lane-pair status."""

        return _audit_from_messages(self.validate())


@dataclass(frozen=True)
class LaneStatusReport:
    """Merged report keyed by source-target lane pairs."""

    lane_pairs: dict[tuple[Lane, Lane], LanePairStatus] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize this lane status report."""

        return {
            "schema": SCHEMA,
            "lane_pairs": [
                status.to_dict()
                for _, status in sorted(
                    self.lane_pairs.items(),
                    key=lambda item: (item[0][0].value, item[0][1].value),
                )
            ],
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> LaneStatusReport:
        """Build a lane status report from parsed JSON."""

        lane_pairs: dict[tuple[Lane, Lane], LanePairStatus] = {}
        for item in _dict_list(payload.get("lane_pairs", [])):
            status = LanePairStatus.from_dict(item)
            lane_pairs[(status.source, status.target)] = status
        return cls(lane_pairs=lane_pairs)

    def validate(self) -> list[str]:
        """Return soft lane-status report problems."""

        problems: list[str] = []
        for key, status in self.lane_pairs.items():
            if key != (status.source, status.target):
                problems.append(
                    f"lane pair key mismatch: {key[0].value}->{key[1].value} "
                    f"contains {status.source.value}->{status.target.value}"
                )
            problems.extend(status.validate())
        return problems

    def audit(self) -> LaneLogAudit:
        """Audit this lane status report."""

        return _audit_from_messages(self.validate())


@dataclass(frozen=True)
class LaneLogProblem:
    """One structured lane-log audit problem."""

    severity: LaneSeverity
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
    def from_dict(cls, payload: dict[str, Any]) -> LaneLogProblem:
        """Build a lane-log problem from parsed JSON."""

        return cls(
            severity=_severity_from_value(payload.get("severity")),
            message=str(payload.get("message", "")),
            field=_optional_str(payload.get("field")),
        )


@dataclass(frozen=True)
class LaneLogAudit:
    """Structured result from lane-log validation."""

    overall_severity: LaneSeverity
    problems: list[LaneLogProblem] = field(default_factory=list)

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
    def from_dict(cls, payload: dict[str, Any]) -> LaneLogAudit:
        """Build a lane-log audit from parsed JSON."""

        problems = [
            LaneLogProblem.from_dict(item) for item in _dict_list(payload.get("problems", []))
        ]
        return cls(overall_severity=_aggregate(problems), problems=problems)


def validate_handoff(
    handoff: LaneHandoff,
    *,
    required_reads: Sequence[str] = (),
) -> list[str]:
    """Validate handoff receipts and verification strings without opening files."""

    problems: list[str] = []
    label = f"{handoff.source.value}->{handoff.target.value}"
    if not handoff.status.strip():
        problems.append(f"handoff {label} missing required field: status")
    if handoff.status.strip().lower() != "draft" and not _non_empty_strings(handoff.verification):
        problems.append(
            f"handoff {label} missing verification for non-draft status: {handoff.status}"
        )
    for receipt in handoff.read_receipts:
        problems.extend(receipt.validate())
    receipt_paths = {receipt.file_path for receipt in handoff.read_receipts}
    for required_read in required_reads:
        if required_read not in receipt_paths:
            problems.append(f"handoff {label} missing required read receipt: {required_read}")
    return problems


def merge_handoffs(handoffs: Sequence[LaneHandoff]) -> LaneStatusReport:
    """Merge handoffs into a report keyed by ``(source, target)`` lane pairs."""

    grouped: dict[tuple[Lane, Lane], list[LaneHandoff]] = {}
    for handoff in handoffs:
        grouped.setdefault((handoff.source, handoff.target), []).append(handoff)

    lane_pairs: dict[tuple[Lane, Lane], LanePairStatus] = {}
    for key, group in grouped.items():
        source, target = key
        lane_pairs[key] = LanePairStatus(
            source=source,
            target=target,
            handoff_count=len(group),
            latest_status=group[-1].status,
            artifacts=_unique_strings(item for handoff in group for item in handoff.artifacts),
            verification=_unique_strings(
                item for handoff in group for item in handoff.verification
            ),
            open_decisions=_unique_strings(
                item for handoff in group for item in handoff.open_decisions
            ),
        )
    return LaneStatusReport(lane_pairs=lane_pairs)


def _audit_from_messages(messages: list[str]) -> LaneLogAudit:
    problems = [LaneLogProblem("fail", message) for message in messages]
    return LaneLogAudit(overall_severity=_aggregate(problems), problems=problems)


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


def _non_empty_strings(values: list[str]) -> bool:
    return any(value.strip() for value in values)


def _unique_strings(values: Iterable[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def _aggregate(problems: list[LaneLogProblem]) -> LaneSeverity:
    if not problems:
        return "pass"
    return max((problem.severity for problem in problems), key=lambda severity: _SEVERITY_RANK[severity])


def _severity_from_value(value: Any) -> LaneSeverity:
    if value in {"pass", "warn", "fail"}:
        return cast("LaneSeverity", value)
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


def _enum_from_value(enum_cls: type[EnumT], value: Any, default: EnumT) -> EnumT:
    if value is None:
        return default
    for member in enum_cls:
        if value == member.value or value == member.name:
            return member
    return default


__all__ = [
    "SCHEMA",
    "Lane",
    "LaneHandoff",
    "LaneLogAudit",
    "LaneLogProblem",
    "LanePairStatus",
    "LaneSeverity",
    "LaneStatusReport",
    "ReadReceipt",
    "merge_handoffs",
    "validate_handoff",
]
