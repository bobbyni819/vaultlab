"""Pairwise figure tournaments for prioritizing figure variants.

The tournament winner is a prioritization signal, not truth. Use it to decide
which figure variant deserves the next review pass; do not treat it as evidence
that the winning figure is scientifically correct.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path

from vaultlab.figures.understand.layout_checks import run_layout_audit

__all__ = [
    "FigureCandidate",
    "Match",
    "TournamentResult",
    "run_figure_tournament",
]


@dataclass(frozen=True)
class FigureCandidate:
    """One figure variant that can be pairwise-ranked."""

    candidate_id: str
    png_path: Path | str | None = None
    label: str = ""
    score_hint: float | None = None


@dataclass(frozen=True)
class Match:
    """One pairwise tournament result."""

    a_id: str
    b_id: str
    winner_id: str | None
    margin: float
    rationale: str
    judge: str


@dataclass(frozen=True)
class TournamentResult:
    """Aggregated pairwise ranking.

    ``winner_id`` is only a prioritization signal for follow-up figure review,
    not a claim that the selected figure is true or publication-ready.
    """

    ranking: list[tuple[str, float]]
    matches: list[Match]
    winner_id: str | None
    n_candidates: int

    def to_dict(self) -> dict[str, object]:
        """Serialize the result to a JSON-compatible dictionary."""

        return {
            "ranking": [
                {"candidate_id": candidate_id, "score": score}
                for candidate_id, score in self.ranking
            ],
            "matches": [asdict(match) for match in self.matches],
            "winner_id": self.winner_id,
            "n_candidates": self.n_candidates,
            "caveat": "The winner is a prioritization signal, not truth.",
        }

    def to_markdown(self) -> str:
        """Render the ranking table, match log, and anti-overclaim caveat."""

        lines = [
            "# Figure Tournament",
            "",
            "> Caveat: the winner is a prioritization signal, not truth. Validate the selected figure against the data, figure contract, and human review before relying on it.",
            "",
            "## Ranking",
            "",
            "| Rank | Candidate | Score |",
            "| --- | --- | ---: |",
        ]
        if self.ranking:
            for rank, (candidate_id, score) in enumerate(self.ranking, start=1):
                lines.append(f"| {rank} | `{candidate_id}` | {score:.3g} |")
        else:
            lines.append("| - | - | - |")

        lines.extend(["", "## Match Log", ""])
        if self.matches:
            for match in self.matches:
                winner = match.winner_id if match.winner_id is not None else "tie"
                lines.append(
                    f"- `{match.a_id}` vs `{match.b_id}` -> `{winner}` "
                    f"(margin {match.margin:.3g}, judge `{match.judge}`): {match.rationale}"
                )
        else:
            lines.append("- No pairwise matches were run.")
        return "\n".join(lines).rstrip() + "\n"


JudgeResult = Match | str | None
ScoreFn = Callable[[FigureCandidate], float]
JudgeFn = Callable[[FigureCandidate, FigureCandidate], JudgeResult]

_SEVERITY_SCORE = {"pass": 1.0, "warn": 0.5, "fail": 0.0}


def run_figure_tournament(
    candidates: list[FigureCandidate],
    *,
    score_fn: ScoreFn | None = None,
    judge_fn: JudgeFn | None = None,
) -> TournamentResult:
    """Round-robin rank figure variants by pairwise wins.

    The resulting winner is a prioritization signal for work planning, not truth.
    The deterministic default scorer uses the layout audit severity when a PNG is
    available and falls back to ``score_hint`` or ``0.0`` without crashing.
    """

    if len(candidates) < 2:
        ranking = [(candidate.candidate_id, 0.0) for candidate in candidates]
        winner_id = candidates[0].candidate_id if len(candidates) == 1 else None
        return TournamentResult(
            ranking=ranking,
            matches=[],
            winner_id=winner_id,
            n_candidates=len(candidates),
        )

    matches: list[Match] = []
    for i, candidate_a in enumerate(candidates):
        for candidate_b in candidates[i + 1 :]:
            matches.append(
                _run_match(candidate_a, candidate_b, score_fn=score_fn, judge_fn=judge_fn)
            )

    ranking, winner_id = _aggregate_ranking(candidates, matches)
    return TournamentResult(
        ranking=ranking,
        matches=matches,
        winner_id=winner_id,
        n_candidates=len(candidates),
    )


def _run_match(
    candidate_a: FigureCandidate,
    candidate_b: FigureCandidate,
    *,
    score_fn: ScoreFn | None,
    judge_fn: JudgeFn | None,
) -> Match:
    if judge_fn is not None:
        return _run_judged_match(candidate_a, candidate_b, judge_fn)

    scorer = score_fn if score_fn is not None else _default_score
    judge = "score_fn" if score_fn is not None else "layout_audit"
    score_a = _safe_score(scorer, candidate_a)
    score_b = _safe_score(scorer, candidate_b)
    return _match_from_scores(candidate_a, candidate_b, score_a, score_b, judge=judge)


def _run_judged_match(
    candidate_a: FigureCandidate,
    candidate_b: FigureCandidate,
    judge_fn: JudgeFn,
) -> Match:
    try:
        judged = judge_fn(candidate_a, candidate_b)
    except Exception as exc:
        return Match(
            a_id=candidate_a.candidate_id,
            b_id=candidate_b.candidate_id,
            winner_id=None,
            margin=0.0,
            rationale=f"judge failed: {exc}",
            judge="judge_fn",
        )

    if isinstance(judged, Match):
        return _normalize_match(judged, candidate_a, candidate_b)
    if isinstance(judged, str):
        if judged in {candidate_a.candidate_id, candidate_b.candidate_id}:
            return Match(
                a_id=candidate_a.candidate_id,
                b_id=candidate_b.candidate_id,
                winner_id=judged,
                margin=1.0,
                rationale=f"judge selected {judged}",
                judge="judge_fn",
            )
        return Match(
            a_id=candidate_a.candidate_id,
            b_id=candidate_b.candidate_id,
            winner_id=None,
            margin=0.0,
            rationale=f"judge returned unknown winner id: {judged}",
            judge="judge_fn",
        )
    return Match(
        a_id=candidate_a.candidate_id,
        b_id=candidate_b.candidate_id,
        winner_id=None,
        margin=0.0,
        rationale="judge returned tie",
        judge="judge_fn",
    )


def _match_from_scores(
    candidate_a: FigureCandidate,
    candidate_b: FigureCandidate,
    score_a: float,
    score_b: float,
    *,
    judge: str,
) -> Match:
    margin = _normalized_margin(score_a, score_b)
    rationale = (
        f"{candidate_a.candidate_id} score={score_a:.3g}; "
        f"{candidate_b.candidate_id} score={score_b:.3g}"
    )
    if score_a > score_b:
        winner_id = candidate_a.candidate_id
    elif score_b > score_a:
        winner_id = candidate_b.candidate_id
    else:
        winner_id = None
        margin = 0.0
        rationale = f"{rationale}; tied scores"
    return Match(
        a_id=candidate_a.candidate_id,
        b_id=candidate_b.candidate_id,
        winner_id=winner_id,
        margin=margin,
        rationale=rationale,
        judge=judge,
    )


def _aggregate_ranking(
    candidates: list[FigureCandidate],
    matches: list[Match],
) -> tuple[list[tuple[str, float]], str | None]:
    win_counts = {candidate.candidate_id: 0.0 for candidate in candidates}
    margin_sums = {candidate.candidate_id: 0.0 for candidate in candidates}
    match_counts = {candidate.candidate_id: 0 for candidate in candidates}

    for match in matches:
        match_counts[match.a_id] += 1
        match_counts[match.b_id] += 1
        margin = _clamp_margin(match.margin)
        if match.winner_id is None:
            win_counts[match.a_id] += 0.5
            win_counts[match.b_id] += 0.5
        elif match.winner_id == match.a_id:
            win_counts[match.a_id] += 1.0
            margin_sums[match.a_id] += margin
            margin_sums[match.b_id] -= margin
        elif match.winner_id == match.b_id:
            win_counts[match.b_id] += 1.0
            margin_sums[match.b_id] += margin
            margin_sums[match.a_id] -= margin
        else:
            win_counts[match.a_id] += 0.5
            win_counts[match.b_id] += 0.5

    def mean_margin(candidate_id: str) -> float:
        count = match_counts[candidate_id]
        return margin_sums[candidate_id] / count if count else 0.0

    ranking = sorted(
        win_counts.items(),
        key=lambda item: (-item[1], -mean_margin(item[0]), item[0]),
    )
    winner_id = None if all(match.winner_id is None for match in matches) else ranking[0][0]
    return ranking, winner_id


def _normalize_match(
    match: Match, candidate_a: FigureCandidate, candidate_b: FigureCandidate
) -> Match:
    pair_ids = {candidate_a.candidate_id, candidate_b.candidate_id}
    winner_id = match.winner_id if match.winner_id in pair_ids else None
    return Match(
        a_id=candidate_a.candidate_id,
        b_id=candidate_b.candidate_id,
        winner_id=winner_id,
        margin=_clamp_margin(match.margin) if winner_id is not None else 0.0,
        rationale=match.rationale,
        judge=match.judge,
    )


def _safe_score(score_fn: ScoreFn, candidate: FigureCandidate) -> float:
    try:
        return float(score_fn(candidate))
    except Exception:
        return _score_hint_or_zero(candidate)


def _default_score(candidate: FigureCandidate) -> float:
    if candidate.png_path is None:
        return _score_hint_or_zero(candidate)
    path = Path(candidate.png_path)
    if not path.exists():
        return _score_hint_or_zero(candidate)
    try:
        audit = run_layout_audit(path)
    except Exception:
        return _score_hint_or_zero(candidate)
    return _SEVERITY_SCORE.get(str(audit.overall_severity).lower(), 0.0)


def _score_hint_or_zero(candidate: FigureCandidate) -> float:
    if candidate.score_hint is None:
        return 0.0
    return float(candidate.score_hint)


def _normalized_margin(score_a: float, score_b: float) -> float:
    scale = max(abs(score_a), abs(score_b), 1.0)
    return _clamp_margin(abs(score_a - score_b) / scale)


def _clamp_margin(value: float) -> float:
    return max(0.0, min(1.0, float(value)))
