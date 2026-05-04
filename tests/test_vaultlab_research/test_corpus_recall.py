"""Tests for vaultlab.research.corpus_recall."""

from __future__ import annotations

from pathlib import Path

import pytest

from vaultlab.research.corpus_recall import (
    gather_relevant_summaries,
    merge_summary_sets,
    _default_keywords_from_topic,
)


def _write_summary(
    path: Path,
    *,
    title: str,
    tier: str = "A",
    tldr: str = "",
) -> None:
    """Helper: write a minimal-frontmatter summary markdown file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    content = (
        "---\n"
        f"title: {title}\n"
        f"tier: {tier}\n"
        "doi: 10.1000/test\n"
        "---\n\n"
        "## TL;DR\n"
        f"{tldr}\n"
    )
    path.write_text(content, encoding="utf-8")


def test_gather_returns_tier_a_matches_only_by_default(tmp_path: Path) -> None:
    summaries = tmp_path / "Wiki" / "Summaries"
    _write_summary(summaries / "tier-a-relevant.md",
                   title="CODEX multiplexed imaging in tumor immunology", tier="A")
    _write_summary(summaries / "tier-a-irrelevant.md",
                   title="Quantum computing for finance", tier="A")
    _write_summary(summaries / "tier-c-relevant.md",
                   title="CODEX phenotyping methods", tier="C")

    result = gather_relevant_summaries("CODEX multiplexed imaging", tmp_path)

    names = {p.name for p in result}
    assert "tier-a-relevant.md" in names
    assert "tier-a-irrelevant.md" not in names
    assert "tier-c-relevant.md" not in names  # tier-C excluded by default


def test_gather_includes_tier_b_when_min_tier_b(tmp_path: Path) -> None:
    summaries = tmp_path / "Wiki" / "Summaries"
    _write_summary(summaries / "tier-a.md",
                   title="CODEX antibody panels", tier="A")
    _write_summary(summaries / "tier-b.md",
                   title="CODEX protocols paper", tier="B")
    _write_summary(summaries / "tier-c.md",
                   title="CODEX in cancer", tier="C")

    result = gather_relevant_summaries(
        "CODEX",
        tmp_path,
        min_tier="B",
    )

    names = {p.name for p in result}
    assert "tier-a.md" in names
    assert "tier-b.md" in names
    assert "tier-c.md" not in names  # still excluded


def test_gather_matches_on_title_and_tldr(tmp_path: Path) -> None:
    summaries = tmp_path / "Wiki" / "Summaries"
    _write_summary(summaries / "title-match.md",
                   title="A multiplexed imaging study", tldr="other text")
    _write_summary(summaries / "tldr-match.md",
                   title="Generic title",
                   tldr="This study uses multiplexed imaging for...")
    _write_summary(summaries / "no-match.md",
                   title="Unrelated paper", tldr="Nothing relevant")

    result = gather_relevant_summaries("multiplexed imaging", tmp_path)

    names = {p.name for p in result}
    assert "title-match.md" in names
    assert "tldr-match.md" in names
    assert "no-match.md" not in names


def test_gather_with_explicit_keywords(tmp_path: Path) -> None:
    summaries = tmp_path / "Wiki" / "Summaries"
    _write_summary(summaries / "match.md", title="Highly multiplexed CODEX")
    _write_summary(summaries / "skip.md", title="t-CyCIF imaging")

    result = gather_relevant_summaries(
        "ignored topic string",
        tmp_path,
        keywords=["CODEX"],
    )

    names = {p.name for p in result}
    assert "match.md" in names
    assert "skip.md" not in names


def test_gather_returns_empty_when_no_summaries_dir(tmp_path: Path) -> None:
    # No Wiki/Summaries created
    result = gather_relevant_summaries("anything", tmp_path)
    assert result == []


def test_gather_handles_invalid_yaml_gracefully(tmp_path: Path) -> None:
    summaries = tmp_path / "Wiki" / "Summaries"
    summaries.mkdir(parents=True)
    # File with broken frontmatter
    (summaries / "broken.md").write_text(
        "---\nbroken: [unclosed\n---\nbody",
        encoding="utf-8",
    )
    # File with no frontmatter at all
    (summaries / "no-frontmatter.md").write_text("just a body", encoding="utf-8")
    # Valid match
    _write_summary(summaries / "valid.md", title="CODEX paper")

    result = gather_relevant_summaries("CODEX", tmp_path)

    names = {p.name for p in result}
    assert "valid.md" in names
    assert "broken.md" not in names
    assert "no-frontmatter.md" not in names


def test_merge_dedupes_by_filename(tmp_path: Path) -> None:
    p1 = tmp_path / "10.1000_a.md"
    p2 = tmp_path / "10.1000_b.md"
    p3 = tmp_path / "10.1000_c.md"
    for p in (p1, p2, p3):
        p.write_text("stub", encoding="utf-8")

    merged = merge_summary_sets(
        this_run_paths=[p1, p2],
        cumulative_paths=[p2, p3],  # p2 is duplicate
    )

    names = [p.name for p in merged]
    assert names == ["10.1000_a.md", "10.1000_b.md", "10.1000_c.md"]
    # No duplicate of 10.1000_b.md


def test_merge_this_run_takes_precedence(tmp_path: Path) -> None:
    """When same filename in both, this-run version comes first."""
    this_run_p = tmp_path / "this-run" / "paper.md"
    cumulative_p = tmp_path / "cumulative" / "paper.md"
    this_run_p.parent.mkdir()
    cumulative_p.parent.mkdir()
    this_run_p.write_text("new", encoding="utf-8")
    cumulative_p.write_text("old", encoding="utf-8")

    merged = merge_summary_sets([this_run_p], [cumulative_p])
    assert len(merged) == 1
    assert merged[0] == this_run_p  # this-run wins


def test_default_keywords_drops_stopwords_and_short_tokens() -> None:
    keywords = _default_keywords_from_topic(
        "CODEX multiplexed imaging in tumor microenvironment"
    )
    assert "CODEX" in keywords
    assert "multiplexed" in keywords
    assert "imaging" in keywords
    assert "tumor" in keywords
    assert "microenvironment" in keywords
    assert "in" not in keywords  # stopword
    # No 1-2 char tokens
    assert all(len(k) >= 3 for k in keywords)


def test_max_results_caps_returned_list(tmp_path: Path) -> None:
    summaries = tmp_path / "Wiki" / "Summaries"
    summaries.mkdir(parents=True)
    for i in range(50):
        _write_summary(summaries / f"paper-{i:02d}.md",
                       title=f"CODEX paper {i}")

    result = gather_relevant_summaries("CODEX", tmp_path, max_results=10)
    assert len(result) == 10
