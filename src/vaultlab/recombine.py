"""Small deterministic recombination primitives.

Recombination proposes a child from two parent artifacts; verification disposes
of whether that child should be accepted.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, fields, is_dataclass
from typing import Any, Generic, TypeVar

from vaultlab.figures.contract import FigureContract
from vaultlab.figures.tournament import TournamentResult

__all__ = [
    "RecombineResult",
    "recombine",
    "recombine_figure_contracts",
    "recombine_top_two",
]

A = TypeVar("A")
B = TypeVar("B")
C = TypeVar("C")


@dataclass(frozen=True)
class RecombineResult(Generic[C]):
    """Result of combining two parents and optionally verifying the child."""

    child: C | None
    parent_a_id: str
    parent_b_id: str
    verified: bool | None
    verdict: Any | None
    rationale: str

    def to_dict(self) -> dict[str, object]:
        """Serialize the result with best-effort child/verdict conversion."""

        return {
            "child": _best_effort_value(self.child),
            "parent_a_id": self.parent_a_id,
            "parent_b_id": self.parent_b_id,
            "verified": self.verified,
            "verdict": _best_effort_value(self.verdict),
            "rationale": self.rationale,
        }


def recombine(
    parent_a: A,
    parent_b: B,
    *,
    combine_fn: Callable[[A, B], C],
    verify_fn: Callable[[C], Any] | None = None,
    parent_a_id: str = "parent_a",
    parent_b_id: str = "parent_b",
    accept_fn: Callable[[Any], bool] | None = None,
) -> RecombineResult[C]:
    """Combine two parents into a child and optionally verify the child.

    Combine, verify, and accept exceptions are captured as failed recombination
    results rather than propagated. The caller can inspect ``rationale`` for the
    failure reason.
    """

    try:
        child = combine_fn(parent_a, parent_b)
    except Exception as exc:
        return RecombineResult(
            child=None,
            parent_a_id=parent_a_id,
            parent_b_id=parent_b_id,
            verified=False,
            verdict=None,
            rationale=(
                f"Recombined {parent_a_id} + {parent_b_id}; combine failed: "
                f"{type(exc).__name__}: {exc}"
            ),
        )

    if verify_fn is None:
        return RecombineResult(
            child=child,
            parent_a_id=parent_a_id,
            parent_b_id=parent_b_id,
            verified=None,
            verdict=None,
            rationale=f"Recombined {parent_a_id} + {parent_b_id}; no verifier run.",
        )

    try:
        verdict = verify_fn(child)
        verified = bool(accept_fn(verdict)) if accept_fn is not None else _truthy_verdict(verdict)
    except Exception as exc:
        return RecombineResult(
            child=child,
            parent_a_id=parent_a_id,
            parent_b_id=parent_b_id,
            verified=False,
            verdict=None,
            rationale=(
                f"Recombined {parent_a_id} + {parent_b_id}; verification failed: "
                f"{type(exc).__name__}: {exc}"
            ),
        )

    status = "verified" if verified else "did not verify"
    return RecombineResult(
        child=child,
        parent_a_id=parent_a_id,
        parent_b_id=parent_b_id,
        verified=verified,
        verdict=verdict,
        rationale=f"Recombined {parent_a_id} + {parent_b_id}; child {status}.",
    )


def recombine_figure_contracts(a: FigureContract, b: FigureContract) -> FigureContract:
    """Merge two figure contracts into a child contract.

    The child preserves the stronger available conclusion, takes the union of
    evidence-chain panels with ``b`` winning key conflicts, and carries stricter
    export commitments such as maximum raster DPI and bounded width.
    """

    evidence_chain = dict(a.evidence_chain)
    conflicting_keys = sorted(set(a.evidence_chain).intersection(b.evidence_chain))
    evidence_chain.update(b.evidence_chain)

    return FigureContract(
        conclusion=_stronger_conclusion(a.conclusion, b.conclusion),
        evidence_chain=evidence_chain,
        archetype=b.archetype if len(b.evidence_chain) > len(a.evidence_chain) else a.archetype,
        backend=a.backend,
        width_mm=_stricter_width(a.width_mm, b.width_mm),
        height_mm=min(a.height_mm, b.height_mm),
        export_formats=_merge_export_formats(a.export_formats, b.export_formats),
        dpi=max(a.dpi, b.dpi),
        stats_block=_merge_text(a.stats_block, b.stats_block),
        image_integrity_notes=_merge_text(a.image_integrity_notes, b.image_integrity_notes),
        source_data_path=a.source_data_path if a.source_data_path is not None else b.source_data_path,
        color_policy=_merge_text(a.color_policy, b.color_policy),
        notes=_merge_notes(a.notes, b.notes, conflicting_keys),
    )


def recombine_top_two(
    tournament_result: TournamentResult,
    candidates_by_id: Mapping[str, A],
    *,
    combine_fn: Callable[[A, A], C],
    verify_fn: Callable[[C], Any] | None = None,
    accept_fn: Callable[[Any], bool] | None = None,
) -> RecombineResult[C] | None:
    """Recombine the top two ranked candidates from a tournament result."""

    if len(tournament_result.ranking) < 2:
        return None

    parent_a_id = tournament_result.ranking[0][0]
    parent_b_id = tournament_result.ranking[1][0]
    try:
        parent_a = candidates_by_id[parent_a_id]
        parent_b = candidates_by_id[parent_b_id]
    except KeyError as exc:
        missing_id = str(exc).strip("'")
        return RecombineResult(
            child=None,
            parent_a_id=parent_a_id,
            parent_b_id=parent_b_id,
            verified=False,
            verdict=None,
            rationale=(
                f"Recombined top two {parent_a_id} + {parent_b_id}; "
                f"missing candidate: {missing_id}"
            ),
        )

    return recombine(
        parent_a,
        parent_b,
        combine_fn=combine_fn,
        verify_fn=verify_fn,
        parent_a_id=parent_a_id,
        parent_b_id=parent_b_id,
        accept_fn=accept_fn,
    )


def _truthy_verdict(verdict: Any) -> bool:
    if isinstance(verdict, bool):
        return verdict
    if verdict is None:
        return False
    if isinstance(verdict, str):
        normalized = verdict.strip().lower()
        if normalized in {"pass", "passed", "ok", "true", "verified", "success"}:
            return True
        if normalized in {"fail", "failed", "error", "false", "not_verified", "reject"}:
            return False
        return bool(normalized)
    if isinstance(verdict, Mapping):
        lowered = {str(key).lower(): value for key, value in verdict.items()}
        for key in ("ok", "passed", "pass", "verified", "success"):
            if key in lowered:
                return bool(lowered[key])
        for key in ("error", "errors", "exception"):
            if lowered.get(key):
                return False
        status = lowered.get("status") or lowered.get("verdict")
        if isinstance(status, str):
            return _truthy_verdict(status)
        return bool(verdict)
    return bool(verdict)


def _stronger_conclusion(a: str, b: str) -> str:
    clean_a = a.strip()
    clean_b = b.strip()
    if not clean_a:
        return clean_b
    if not clean_b:
        return clean_a
    if clean_a == clean_b:
        return clean_a
    return clean_b if len(clean_b) > len(clean_a) else clean_a


def _stricter_width(a: float, b: float) -> float:
    nature_double_column_mm = 183.0
    return min(a, b, nature_double_column_mm)


def _merge_export_formats(
    a: tuple[str, ...],
    b: tuple[str, ...],
) -> tuple[Any, ...]:
    return tuple(dict.fromkeys((*a, *b)))


def _merge_text(a: str, b: str) -> str:
    clean_a = a.strip()
    clean_b = b.strip()
    if clean_a and clean_b and clean_a != clean_b:
        return f"{clean_a}\n{clean_b}"
    return clean_a or clean_b


def _merge_notes(a: str, b: str, conflicting_keys: list[str]) -> str:
    notes = _merge_text(a, b)
    if not conflicting_keys:
        return notes
    conflict_note = (
        "Recombined evidence_chain with parent_b winning key conflicts: "
        f"{', '.join(conflicting_keys)}."
    )
    return _merge_text(notes, conflict_note)


def _best_effort_value(value: object) -> object:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Mapping):
        return {str(key): _best_effort_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_best_effort_value(item) for item in value]
    if is_dataclass(value) and not isinstance(value, type):
        return {field.name: _best_effort_value(getattr(value, field.name)) for field in fields(value)}
    return str(value)
