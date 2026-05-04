"""Cumulative-corpus recall — turn the Wiki/Summaries folder into a real asset.

Background
----------
When ``run_lit_arc`` runs for a topic, the per-run picker selects the
top-N candidates from THIS run's search and ranks them. The narrator
then writes the arc using only those picks.

Problem (surfaced 2026-05-01 in the CODEX additive run): the picker
is per-run; it doesn't see the *cumulative* ``Wiki/Summaries/`` folder
that has accumulated Tier-A papers from prior runs on related topics.
The CODEX arc was written from 19 Tier-A picks while 30 CODEX-relevant
Tier-A summaries already existed on disk — including the namesake
Goltsev 2018 *Cell* paper, which was Tier-A from a prior run but
not in this run's top-30 picks because the picker's composite_score
weights recency and Goltsev is a 2018 paper.

Fix philosophy (Bobby's "always read more" principle, 2026-05-01):
the cumulative ``Wiki/Summaries/`` folder is an asset that grows
monotonically across all the user's research projects. Every new
arc should glob it for topic-relevant Tier-A summaries and merge
those with this-run's picks before the narrator stage.

This module provides :func:`gather_relevant_summaries` for that
purpose. The function is intentionally simple — keyword-matching over
title + TL;DR — because semantic relevance is the narrator's job;
this function just delivers candidates.

Usage from :func:`run_lit_arc`
------------------------------
After ``acquire_pdfs_for_corpus`` and before the narrator stage::

    from vaultlab.research.corpus_recall import gather_relevant_summaries

    cumulative_paths = gather_relevant_summaries(
        topic=topic,
        kb_root=kb_root,
        keywords=topic_keywords(topic),
    )
    # Merge with this-run picks (de-dup by DOI):
    merged_summaries = merge_summary_sets(this_run_picks, cumulative_paths)

The narrator's prompt then receives ``merged_summaries`` instead of
just ``this_run_picks``, and any wikilinks to cumulative-corpus papers
already resolve because the summary files exist on disk.

Usage from a slash command (Claude-Code-callable path)
------------------------------------------------------
The narrator callback in ``.claude/commands/lit-arc.md`` is expected
to call this function before composing the arc, so the same behavior
applies whether running via SDK or Claude Code.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable

import yaml


def gather_relevant_summaries(
    topic: str,
    kb_root: Path,
    keywords: Iterable[str] | None = None,
    *,
    min_tier: str = "A",
    max_results: int = 200,
) -> list[Path]:
    """Glob ``Wiki/Summaries/*.md`` for Tier-A topic-relevant papers.

    Args:
        topic: The user's topic string. Used as a fallback keyword if
            ``keywords`` is None.
        kb_root: Path to the KB root (e.g., ``G:/My Drive/Knowledge/vaultlab``).
        keywords: Optional explicit keyword list. Each summary file is
            checked for at least one keyword (case-insensitive) in its
            title or TL;DR. If None, uses a simple tokenization of
            ``topic``.
        min_tier: Minimum tier to include. Default ``"A"`` (full-text
            read). ``"B"`` would also include abstract-only summaries
            once Tier-B summarization is implemented (task #115).
        max_results: Cap on the returned list. Defaults to 200, which
            is large enough that no real-world arc will hit it.

    Returns:
        List of summary file paths (``Wiki/Summaries/<doi-slug>.md``)
        that are at-or-above ``min_tier`` AND match at least one
        keyword. Order is by file mtime (newest first) — the narrator
        is expected to do its own ranking.

    Notes:
        This function is deliberately simple. It does NOT call an LLM
        and does NOT do semantic embedding-based matching. Keyword
        matching is sufficient because:

        1. The narrator stage will re-evaluate relevance when composing
           paragraphs. False positives here just give the narrator
           more to work with.
        2. The Wiki/Summaries folder size is bounded (~100s of papers
           for typical users), so exhaustive scanning is fine.
        3. Embedding-based matching would add a dependency and a
           computation step for marginal benefit.

        For users who want stricter filtering, pass an explicit
        ``keywords`` list narrower than the default tokenization.
    """
    summaries_dir = kb_root / "Wiki" / "Summaries"
    if not summaries_dir.is_dir():
        return []

    if keywords is None:
        keywords = _default_keywords_from_topic(topic)
    keywords = [kw.lower() for kw in keywords if kw and len(kw) >= 3]
    if not keywords:
        return []

    # Tier ordering: A < B < C means A is the highest-fidelity.
    # min_tier="A" means "include only A". min_tier="B" means "A or B".
    tier_levels = {"A": 0, "B": 1, "C": 2}
    min_level = tier_levels.get(min_tier.upper(), 0)

    matches: list[tuple[float, Path]] = []
    for md_path in summaries_dir.glob("*.md"):
        try:
            content = md_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        # Quick frontmatter parse (avoid importing heavy YAML for non-frontmatter files)
        if not content.startswith("---"):
            continue
        try:
            _, frontmatter, body = content.split("---", 2)
            fm = yaml.safe_load(frontmatter) or {}
        except (ValueError, yaml.YAMLError):
            continue

        tier = str(fm.get("tier", "C")).upper().strip()
        if tier_levels.get(tier, 99) > min_level:
            continue

        title = str(fm.get("title", "")).lower()
        # Match on title OR first ~500 chars of body (TL;DR section)
        haystack = title + " " + body[:500].lower()
        if any(kw in haystack for kw in keywords):
            matches.append((md_path.stat().st_mtime, md_path))

    matches.sort(reverse=True)
    return [p for _, p in matches[:max_results]]


def _default_keywords_from_topic(topic: str) -> list[str]:
    """Tokenize a topic string into searchable keywords.

    Splits on whitespace and punctuation; drops short tokens (<3 chars)
    and a small list of stopwords. This is intentionally simple — for
    semantic relevance, callers should pass an explicit ``keywords`` list.
    """
    stopwords = {
        "the", "and", "for", "with", "from", "that", "this", "into",
        "across", "using", "via", "based", "are", "was", "were", "has",
        "have", "of", "in", "on", "an", "a", "to", "by", "at",
    }
    tokens = re.findall(r"[A-Za-z][A-Za-z0-9-]+", topic)
    return [t for t in tokens if t.lower() not in stopwords and len(t) >= 3]


def merge_summary_sets(
    this_run_paths: Iterable[Path],
    cumulative_paths: Iterable[Path],
) -> list[Path]:
    """De-duplicate and merge two sets of summary file paths.

    De-dup is by filename (i.e., by DOI-slug). The this-run set
    takes precedence when the same DOI appears in both — the
    most recent run's summary should win.

    Order: this-run paths first, then cumulative-only paths in
    file-mtime order.
    """
    seen: set[str] = set()
    out: list[Path] = []

    for p in this_run_paths:
        key = p.name.lower()
        if key not in seen:
            seen.add(key)
            out.append(p)

    for p in cumulative_paths:
        key = p.name.lower()
        if key not in seen:
            seen.add(key)
            out.append(p)

    return out


__all__ = [
    "gather_relevant_summaries",
    "merge_summary_sets",
]
