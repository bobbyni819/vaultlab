"""Durable manuscript lifecycle state built from existing manuscript gates."""

from __future__ import annotations

import json
import os
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, cast

from vaultlab.citations import Citation
from vaultlab.manuscript.citation_gate import PromotionAction, run_citation_gate
from vaultlab.manuscript.claim_ledger import ClaimLedger, LedgerProblem
from vaultlab.manuscript.preflight import FixItem, FixSeverity, run_manuscript_preflight
from vaultlab.roles._invoke import AuditPrompt

SCHEMA = "vaultlab-manuscript-state/v1"

_SEVERITY_RANK: dict[FixSeverity, int] = {"error": 0, "warning": 1, "info": 2}
_ACCEPTABLE_REVIEWER_VERDICTS = {"ship", "pass", "passed", "acceptable", "approved"}


class ManuscriptStage(Enum):
    """Ordered lifecycle stages for a manuscript."""

    DRAFTING = 0
    EVIDENCE_LINKED = 1
    FIGURE_SYNCED = 2
    CITATION_TIERED = 3
    REVIEWER_AUDITED = 4
    SUBMISSION_READY = 5

    @property
    def rank(self) -> int:
        """Numeric ordering for strict-ladder comparisons."""
        return int(self.value)


@dataclass(frozen=True)
class StageGate:
    """One advancement gate and its blocking reasons."""

    stage: ManuscriptStage
    passed: bool
    blockers: list[str]

    def to_dict(self) -> dict[str, Any]:
        """Serialize the gate to a JSON-ready dict."""
        return {
            "stage": self.stage.name,
            "passed": self.passed,
            "blockers": list(self.blockers),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> StageGate:
        """Build a gate from a JSON payload."""
        return cls(
            stage=_stage_from_payload(payload.get("stage")),
            passed=bool(payload.get("passed", False)),
            blockers=_string_list(payload.get("blockers")),
        )


@dataclass
class ManuscriptState:
    """Persistable manuscript lifecycle dashboard."""

    current_stage: ManuscriptStage
    gates: list[StageGate]
    fix_queue: list[FixItem]
    n_claims: int
    n_blocked_citations: int
    timestamp: str | None = None
    title: str | None = None

    def gate_for(self, stage: ManuscriptStage) -> StageGate:
        """Return the gate associated with ``stage``."""
        for gate in self.gates:
            if gate.stage is stage:
                return gate
        raise KeyError(f"stage has no gate: {stage.name}")

    def to_dict(self) -> dict[str, Any]:
        """Serialize the state to a JSON-ready dict."""
        return {
            "schema": SCHEMA,
            "current_stage": self.current_stage.name,
            "gates": [gate.to_dict() for gate in self.gates],
            "fix_queue": [item.to_dict() for item in self.fix_queue],
            "n_claims": self.n_claims,
            "n_blocked_citations": self.n_blocked_citations,
            "timestamp": self.timestamp,
            "title": self.title,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> ManuscriptState:
        """Build a manuscript state from a JSON payload."""
        return cls(
            current_stage=_stage_from_payload(payload.get("current_stage")),
            gates=[
                StageGate.from_dict(item)
                for item in _mapping_list(payload.get("gates"))
            ],
            fix_queue=[
                _fix_item_from_dict(item)
                for item in _mapping_list(payload.get("fix_queue"))
            ],
            n_claims=int(payload.get("n_claims", 0)),
            n_blocked_citations=int(payload.get("n_blocked_citations", 0)),
            timestamp=_optional_str(payload.get("timestamp")),
            title=_optional_str(payload.get("title")),
        )

    def to_json(self, path: Path | str) -> Path:
        """Atomically write this state as JSON."""
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_name(f".{target.name}.tmp")
        tmp.write_text(
            json.dumps(self.to_dict(), ensure_ascii=False, indent=2, sort_keys=False) + "\n",
            encoding="utf-8",
        )
        os.replace(tmp, target)
        return target

    @classmethod
    def read_json(cls, path: Path | str) -> ManuscriptState:
        """Read a manuscript state from JSON."""
        return read_json(path)

    def to_markdown(self) -> str:
        """Render a compact lifecycle dashboard."""
        lines = [
            "# Manuscript State Dashboard",
            "",
            f"- **Current stage:** `{self.current_stage.name}`",
            f"- **Claims:** {self.n_claims}",
            f"- **Blocked citations:** {self.n_blocked_citations}",
        ]
        if self.title is not None:
            lines.append(f"- **Title:** {self.title}")
        if self.timestamp is not None:
            lines.append(f"- **Timestamp:** {self.timestamp}")

        lines.extend(["", "## Lifecycle gates", ""])
        for gate in self.gates:
            status = "pass" if gate.passed else "✗"
            checkbox = "x" if gate.passed else " "
            lines.append(f"- [{checkbox}] {gate.stage.name}: {status}")
            for blocker in gate.blockers:
                lines.append(f"  - blocker: {blocker}")

        lines.extend(["", "## Ranked fix queue", ""])
        if not self.fix_queue:
            lines.append("- No fixes are currently queued.")
        else:
            for item in self.fix_queue:
                where = f" `{item.where}`" if item.where else ""
                fix = f" Fix: {item.fix}" if item.fix else ""
                lines.append(
                    f"- `{item.severity.upper()}` `{item.source}`{where}: {item.message}{fix}"
                )
        return "\n".join(lines).rstrip() + "\n"


def assess_manuscript(
    manuscript_md: str,
    *,
    ledger: ClaimLedger | None = None,
    figures_dir: Path | str | None = None,
    coverage_dir: Path | str | None = None,
    citations: list[Citation] | None = None,
    roles: list[str] | None = None,
    run_visual_qa: bool = False,
    executor: Callable[[AuditPrompt], Mapping[str, Any]] | None = None,
    title: str | None = None,
    timestamp: str | None = None,
) -> ManuscriptState:
    """Assess a manuscript and return its strict lifecycle state.

    The function delegates all deterministic checks to
    :func:`run_manuscript_preflight` and citation tiering to
    :func:`run_citation_gate`; this module only derives the durable dashboard.
    """
    active_ledger = ledger if ledger is not None else ClaimLedger.from_markdown(manuscript_md)
    preflight = run_manuscript_preflight(
        manuscript_md,
        ledger=active_ledger,
        figures_dir=figures_dir,
        coverage_dir=coverage_dir,
        roles=roles,
        run_visual_qa=run_visual_qa,
        executor=executor,
    )
    citation_report = (
        run_citation_gate(citations=citations)
        if citations is not None
        else run_citation_gate(ledger=active_ledger)
    )

    evidence_gate = _evidence_gate(preflight.ledger_audit.problems)
    figure_gate = StageGate(
        ManuscriptStage.FIGURE_SYNCED,
        preflight.consistency.ok,
        [problem.message for problem in preflight.consistency.problems],
    )
    citation_gate = StageGate(
        ManuscriptStage.CITATION_TIERED,
        citation_report.ok,
        [f"{status.citation_key} needs Tier-3" for status in citation_report.blocked],
    )
    reviewer_gate = _reviewer_gate(preflight.fix_queue, preflight.aggregated, executor)
    submission_gate = StageGate(
        ManuscriptStage.SUBMISSION_READY,
        all(
            gate.passed
            for gate in (evidence_gate, figure_gate, citation_gate, reviewer_gate)
        ),
        _submission_blockers(evidence_gate, figure_gate, citation_gate, reviewer_gate),
    )
    gates = [evidence_gate, figure_gate, citation_gate, reviewer_gate, submission_gate]

    return ManuscriptState(
        current_stage=_current_stage(gates),
        gates=gates,
        fix_queue=_rank_fix_queue(
            preflight.fix_queue + _fix_items_from_promotions(citation_report.promotion_queue)
        ),
        n_claims=len(active_ledger.claims),
        n_blocked_citations=len(citation_report.blocked),
        timestamp=timestamp,
        title=title,
    )


def read_json(path: Path | str) -> ManuscriptState:
    """Read a manuscript lifecycle state from JSON."""
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"manuscript state must be a JSON object: {path}")
    return ManuscriptState.from_dict(cast("dict[str, Any]", payload))


def _evidence_gate(problems: list[LedgerProblem]) -> StageGate:
    blockers = [
        problem.message
        for problem in problems
        if _is_missing_evidence_problem(problem.message)
    ]
    return StageGate(ManuscriptStage.EVIDENCE_LINKED, not blockers, blockers)


def _reviewer_gate(
    fix_queue: list[FixItem],
    aggregated: object,
    executor: Callable[[AuditPrompt], Mapping[str, Any]] | None,
) -> StageGate:
    blockers = [
        item.message
        for item in fix_queue
        if item.severity == "error"
    ]
    if executor is None:
        blockers.append("reviewer role passes prepared but not executed")
    elif aggregated is None:
        blockers.append("reviewer role passes did not produce an aggregated verdict")
    else:
        verdict = getattr(aggregated, "aggregated_verdict", "unknown")
        if not _is_acceptable_verdict(verdict):
            blockers.append(f"aggregated reviewer verdict is {verdict}")
    return StageGate(ManuscriptStage.REVIEWER_AUDITED, not blockers, blockers)


def _submission_blockers(*gates: StageGate) -> list[str]:
    return [
        f"{gate.stage.name}: {blocker}"
        for gate in gates
        if not gate.passed
        for blocker in gate.blockers
    ]


def _current_stage(gates: list[StageGate]) -> ManuscriptStage:
    current = ManuscriptStage.DRAFTING
    for gate in gates:
        if not gate.passed:
            break
        current = gate.stage
    return current


def _fix_items_from_promotions(actions: list[PromotionAction]) -> list[FixItem]:
    return [
        FixItem(
            source="citation_gate",
            severity="error",
            message=f"{action.citation_key} needs Tier-3",
            where=action.citation_key,
            fix=action.action,
        )
        for action in actions
    ]


def _rank_fix_queue(items: list[FixItem]) -> list[FixItem]:
    return sorted(items, key=lambda item: (_SEVERITY_RANK[item.severity], item.source, item.message))


def _is_missing_evidence_problem(message: str) -> bool:
    return "missing figure link" in message or "missing numeric link" in message


def _is_acceptable_verdict(verdict: object) -> bool:
    return str(verdict).strip().lower() in _ACCEPTABLE_REVIEWER_VERDICTS


def _stage_from_payload(value: object) -> ManuscriptStage:
    if isinstance(value, str):
        if value in ManuscriptStage.__members__:
            return ManuscriptStage[value]
        for stage in ManuscriptStage:
            if value == str(stage.value):
                return stage
    if isinstance(value, int):
        return ManuscriptStage(value)
    raise ValueError(f"unknown manuscript stage: {value!r}")


def _fix_item_from_dict(payload: Mapping[str, Any]) -> FixItem:
    return FixItem(
        source=str(payload.get("source", "")),
        severity=_severity_from_payload(payload.get("severity")),
        message=str(payload.get("message", "")),
        where=_optional_str(payload.get("where")),
        fix=_optional_str(payload.get("fix")),
    )


def _severity_from_payload(value: object) -> FixSeverity:
    if value in {"error", "warning", "info"}:
        return cast("FixSeverity", value)
    raise ValueError(f"unknown fix severity: {value!r}")


def _mapping_list(value: object) -> list[Mapping[str, Any]]:
    if not isinstance(value, list):
        return []
    return [cast("Mapping[str, Any]", item) for item in value if isinstance(item, Mapping)]


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    return str(value)


__all__ = [
    "ManuscriptStage",
    "ManuscriptState",
    "StageGate",
    "assess_manuscript",
    "read_json",
]
