from __future__ import annotations

from pathlib import Path


def test_tournament_score_hints_rank_clear_best_and_record_matches() -> None:
    from vaultlab.figures.tournament import FigureCandidate, run_figure_tournament

    result = run_figure_tournament(
        [
            FigureCandidate("draft", score_hint=0.5),
            FigureCandidate("winner", score_hint=0.9),
            FigureCandidate("weak", score_hint=0.2),
        ]
    )

    assert result.n_candidates == 3
    assert result.winner_id == "winner"
    assert result.ranking[0] == ("winner", 2.0)
    assert len(result.matches) == 3
    assert all(match.margin > 0 for match in result.matches)
    assert any("score" in match.rationale for match in result.matches)


def test_tournament_injected_score_fn_drives_result() -> None:
    from vaultlab.figures.tournament import FigureCandidate, run_figure_tournament

    candidates = [
        FigureCandidate("layout"),
        FigureCandidate("story"),
        FigureCandidate("style"),
    ]
    scores = {"layout": 0.2, "story": 0.95, "style": 0.6}

    result = run_figure_tournament(
        candidates,
        score_fn=lambda candidate: scores[candidate.candidate_id],
    )

    assert result.winner_id == "story"
    assert result.ranking == [("story", 2.0), ("style", 1.0), ("layout", 0.0)]
    assert {match.judge for match in result.matches} == {"score_fn"}


def test_tournament_injected_judge_fn_drives_result() -> None:
    from vaultlab.figures.tournament import FigureCandidate, Match, run_figure_tournament

    candidates = [
        FigureCandidate("a"),
        FigureCandidate("b"),
        FigureCandidate("c"),
    ]

    def judge(a: FigureCandidate, b: FigureCandidate) -> Match | str | None:
        if {a.candidate_id, b.candidate_id} == {"a", "b"}:
            return Match(a.candidate_id, b.candidate_id, "b", 0.8, "b tells the story", "test")
        if {a.candidate_id, b.candidate_id} == {"b", "c"}:
            return "b"
        return None

    result = run_figure_tournament(candidates, judge_fn=judge)

    assert result.winner_id == "b"
    assert result.ranking[0] == ("b", 2.0)
    assert any(match.winner_id is None and match.margin == 0 for match in result.matches)
    assert any(match.rationale == "b tells the story" for match in result.matches)


def test_tournament_all_equal_is_all_tie_with_no_winner() -> None:
    from vaultlab.figures.tournament import FigureCandidate, run_figure_tournament

    result = run_figure_tournament(
        [
            FigureCandidate("a", score_hint=0.5),
            FigureCandidate("b", score_hint=0.5),
            FigureCandidate("c", score_hint=0.5),
        ]
    )

    assert result.winner_id is None
    assert result.ranking == [("a", 1.0), ("b", 1.0), ("c", 1.0)]
    assert all(match.winner_id is None for match in result.matches)


def test_tournament_handles_less_than_two_candidates() -> None:
    from vaultlab.figures.tournament import FigureCandidate, run_figure_tournament

    empty = run_figure_tournament([])
    single = run_figure_tournament([FigureCandidate("only", score_hint=0.7)])

    assert empty.ranking == []
    assert empty.matches == []
    assert empty.winner_id is None
    assert single.ranking == [("only", 0.0)]
    assert single.matches == []
    assert single.winner_id == "only"


def test_tournament_markdown_and_dict_include_caveat() -> None:
    from vaultlab.figures.tournament import FigureCandidate, run_figure_tournament

    result = run_figure_tournament(
        [FigureCandidate("a", score_hint=0.8), FigureCandidate("b", score_hint=0.3)]
    )

    payload = result.to_dict()
    markdown = result.to_markdown()

    assert payload["winner_id"] == "a"
    assert payload["matches"][0]["winner_id"] == "a"
    assert "| Rank | Candidate | Score |" in markdown
    assert "prioritization signal, not truth" in markdown
    assert "## Match Log" in markdown


def test_tournament_missing_png_falls_back_without_crashing(tmp_path: Path) -> None:
    from vaultlab.figures.tournament import FigureCandidate, run_figure_tournament

    result = run_figure_tournament(
        [
            FigureCandidate("missing", png_path=tmp_path / "missing.png"),
            FigureCandidate("hinted", score_hint=0.4),
        ]
    )

    assert result.winner_id == "hinted"
    assert result.ranking[0] == ("hinted", 1.0)
