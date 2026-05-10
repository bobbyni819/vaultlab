"""Content-aware paper picker for the literature-arc Tier-A budget.

Background
----------
The mechanical citation-graph picker in
:func:`vaultlab.research.lineage._pick_top_n_for_summarization` ranks papers
by ``(has_pdf, og_score + forward_influence)``. **It never reads any paper
content before deciding.** That works as long as the citation graph is
representative of topical importance — but for application-heavy corpora
it goes wrong: a peripheral application paper that happens to have a cached
PMC PDF can outrank a foundational paper without one. Bobby (2026-04-30):

    "I want this to be way more content aware rather than just based on
    citation scores because I don't know if those might be deceiving
    sometimes."

Fix
---
Two-stage selection:

1. **Candidate pool** — by default (``coarse_n=None``), every paper in
   the corpus is a candidate; the picker sees ALL abstracts. Pass an
   integer to restore the legacy "top-N by ``og_score + forward_influence``"
   capped pool behaviour.
2. **Fine filter (content-aware)** — each candidate's abstract is fed to
   Claude Code (or any callable matching :data:`PickerCallback`), which
   returns a ranked list of ``target_n`` (typically 8-10) DOIs along with
   a per-pick rationale. The rationales land in the project's
   ``decisions-log.md`` (or a per-run fallback file) so the audit trail
   is preserved.

This module mirrors the reader/narrator-callback pattern from
``summarize.py`` and ``lineage.py``: the picker callback receives a
:class:`PickerTask` and returns a JSON-shaped dict matching
:func:`picker_response_schema`. No SDK calls live in this module — Claude
Code IS the LLM via callback.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from vaultlab.kb.paths import (
    article_stub_path,
    ensure_parent,
    project_decisions_path,
    slugify_doi,
)

if TYPE_CHECKING:
    from vaultlab.research.corpus import Corpus

logger = logging.getLogger(__name__)

__all__ = [
    "CandidatePaper",
    "PickerCallback",
    "PickerTask",
    "build_picker_prompt",
    "load_abstract_from_kb",
    "pick_top_n_content_aware",
    "picker_response_schema",
    "prepare_picker_task",
    "render_picks_from_response",
    "write_picker_decision",
]


# ---------------------------------------------------------------------------
# Public dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CandidatePaper:
    """One row of the coarse pool fed to the content-aware picker.

    Attributes:
        doi: Lower-cased DOI.
        title: Paper title (may be empty for sparse-metadata refs).
        authors: Author list.
        year: Publication year (0 when unknown).
        journal: Journal / venue.
        abstract: Abstract text. Falls back to ``"[no abstract]"`` when
            neither the search-result metadata nor the KB stub has one.
        og_score: Citation-graph OG score (fraction of corpus papers
            citing this DOI).
        forward_influence: In-degree on the seed-x-seed subgraph.
        has_pdf: Whether a cached PDF exists (informational; the picker
            is content-first but may use this as a tie-breaker).
    """

    doi: str
    title: str
    authors: list[str]
    year: int
    journal: str
    abstract: str
    og_score: float
    forward_influence: int
    has_pdf: bool


@dataclass(frozen=True)
class PickerTask:
    """A prepared content-aware-picker task ready for a Claude Code session.

    No LLM is called when this object is built. The slash command body
    inside Claude Code (or any caller wiring a custom callback) inspects
    :attr:`candidates` + :attr:`prompt`, ranks the candidates per the
    system-prompt criteria, and returns JSON matching
    :attr:`response_schema`.

    Attributes:
        topic: The user-supplied topic (raw, not slugified).
        candidates: All corpus papers (default) or top-``coarse_n`` by
            citation-graph score (legacy capped behaviour).
        target_n: How many DOIs the picker should return (8-10 typical).
        prompt: The full user-message prompt the picker should respond to.
        system_prompt: The system-message guard rails.
        response_schema: JSON schema describing the expected response.
    """

    topic: str
    candidates: list[CandidatePaper]
    target_n: int
    prompt: str
    system_prompt: str
    response_schema: dict[str, Any]


# Type alias for the Claude-Code-side picker callback.
PickerCallback = Callable[["PickerTask"], dict[str, Any]]


# ---------------------------------------------------------------------------
# Prompt + schema
# ---------------------------------------------------------------------------


_PICKER_SYSTEM_PROMPT = (
    "You are a content-aware literature picker. You rank candidate papers "
    "by how well they support a researcher's topic — NOT by citation count "
    "alone. Read each abstract before ranking. Cover seminal old work AND "
    "state-of-the-art new work; avoid picking five papers that say the "
    "same thing. If an abstract is missing or off-topic, deprioritize that "
    "paper. Return ONLY a JSON object with a single key 'picks' containing "
    "an ordered list of {doi, rank, rationale} entries. No markdown fencing."
)


def picker_response_schema() -> dict[str, Any]:
    """Return the JSON schema for the content-aware picker response.

    The picker returns a list of picks, each with ``doi``, ``rank``
    (1-indexed), and ``rationale``. The number of picks should equal
    :attr:`PickerTask.target_n`.
    """
    return {
        "type": "object",
        "required": ["picks"],
        "properties": {
            "picks": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["doi", "rank", "rationale"],
                    "properties": {
                        "doi": {
                            "type": "string",
                            "description": "DOI of the candidate paper.",
                        },
                        "rank": {
                            "type": "integer",
                            "description": "1-indexed rank (1 = best).",
                        },
                        "rationale": {
                            "type": "string",
                            "description": ("1-3 sentence justification grounded in the abstract."),
                        },
                    },
                },
            },
        },
    }


def _truncate_abstract(text: str, *, max_chars: int = 1200) -> str:
    """Trim an abstract for prompt budget without breaking mid-word."""
    if not text:
        return "[no abstract]"
    if len(text) <= max_chars:
        return text.strip()
    cut = text[:max_chars].rsplit(" ", 1)[0]
    return cut.strip() + " …"


def build_picker_prompt(
    *,
    topic: str,
    candidates: list[CandidatePaper],
    target_n: int,
) -> str:
    """Build the user-message prompt for the content-aware picker.

    The picker is told the topic, the criteria (relevance, novelty,
    diversity, recency vs canonical balance), and the candidate list
    with abstracts. Candidates are presented in citation-graph order
    so the picker can see the mechanical baseline before overriding it.
    """
    lines: list[str] = [
        f"TOPIC: {topic}",
        "",
        f"Pick the {target_n} BEST papers from the {len(candidates)} candidates "
        "below for a literature lineage arc on this topic.",
        "",
        "RANKING CRITERIA (in order of importance):",
        "1. Topical relevance to the TOPIC — does the abstract clearly "
        "address this area, or is it tangential / off-topic?",
        "2. Likely contribution / methodological novelty — does it introduce "
        "a method, a definition, a key result, or just apply prior work?",
        "3. Coverage diversity — across your picks, do not pick five papers "
        "that say the same thing. Aim for a spread of mechanisms / methods / "
        "applications.",
        "4. Recency vs canonical-status balance — include some seminal old "
        "work AND some state-of-the-art new work.",
        "",
        "DECEPTIVE CITATION SIGNALS:",
        "- A high og_score / forward_influence does NOT mean the paper is "
        "topically relevant. If the abstract is off-topic, deprioritize it.",
        "- A cached PDF (has_pdf=True) is convenient but does NOT make a "
        "paper more topically relevant.",
        "- A low-citation paper with a clearly on-topic abstract beats a "
        "high-citation paper whose abstract is barely related.",
        "",
        f"CANDIDATES ({len(candidates)} total, ordered by citation-graph score):",
        "",
    ]
    for i, c in enumerate(candidates, 1):
        author_str = ""
        if c.authors:
            first = c.authors[0]
            if len(c.authors) > 1:
                author_str = f"{first} et al."
            else:
                author_str = first
        header = f"[{i}] {c.title or '(untitled)'}"
        meta_parts: list[str] = []
        if author_str:
            meta_parts.append(author_str)
        if c.year:
            meta_parts.append(str(c.year))
        if c.journal:
            meta_parts.append(c.journal)
        meta = " — ".join(meta_parts) if meta_parts else "(no metadata)"
        lines.append(header)
        lines.append(f"    {meta}")
        lines.append(
            f"    DOI: {c.doi}  | og_score={c.og_score:.2f}  "
            f"forward_influence={c.forward_influence}  has_pdf={c.has_pdf}"
        )
        lines.append(f"    Abstract: {_truncate_abstract(c.abstract)}")
        lines.append("")

    lines.extend(
        [
            "OUTPUT FORMAT:",
            "Return ONLY a JSON object:",
            "",
            "{",
            '  "picks": [',
            (
                '    {"doi": "<doi>", "rank": 1, "rationale": "<1-3 '
                'sentences grounded in the abstract>"},'
            ),
            '    {"doi": "<doi>", "rank": 2, "rationale": "..."},',
            "    ...",
            "  ]",
            "}",
            "",
            f"Return EXACTLY {target_n} picks. Use the candidate DOIs "
            "EXACTLY as listed above. Do NOT invent new DOIs.",
        ]
    )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Abstract resolution (KB stub > Paper.abstract > placeholder)
# ---------------------------------------------------------------------------


def load_abstract_from_kb(kb_root: Path, doi: str) -> str:
    """Return the abstract from ``Sources/Articles/<doi-slug>.md`` if present.

    Looks for the canonical ``## Abstract`` heading written by
    :func:`vaultlab.research.lineage._write_article_stub`. Returns an empty
    string when the file or the heading is missing — callers fall back to
    the search-result ``Paper.abstract`` field.
    """
    if not doi:
        return ""
    stub_path = article_stub_path(Path(kb_root), doi)
    if not stub_path.exists():
        return ""
    try:
        text = stub_path.read_text(encoding="utf-8")
    except OSError:
        return ""
    # Find "## Abstract" then read until next "## " heading or end of file.
    match = re.search(
        r"^##\s+Abstract\s*\n+(?P<body>.+?)(?=\n##\s+|\Z)",
        text,
        re.MULTILINE | re.DOTALL,
    )
    if not match:
        return ""
    return match.group("body").strip()


_AUTO_CAP_THRESHOLD: int = 500
"""When ``coarse_n=None`` and the corpus has more than this many papers,
automatically cap the candidate pool to :data:`_AUTO_CAP_DEFAULT` to
avoid blowing the picker's LLM context. Set the threshold high enough
that small/medium corpora (~250 papers from backward-only expansion)
still get the "read everything" treatment."""

_AUTO_CAP_DEFAULT: int = 200
"""When the auto-cap kicks in, this is the number of candidates kept."""


def _build_candidates(
    corpus: Corpus,
    *,
    coarse_n: int | None,
    kb_root: Path,
    pdf_cache_dir: Path | None,
) -> list[CandidatePaper]:
    """Build the candidate pool for the content-aware picker.

    When ``coarse_n`` is ``None`` (the default), every paper in the corpus
    is included as a candidate — UNLESS the corpus is large (>500 papers,
    typical when forward citation expansion is on). In that case an
    automatic cap of 200 kicks in to keep the picker's prompt under
    ~100k tokens. Pass an explicit ``coarse_n`` to override.

    When a positive int is given, the corpus is sorted by
    ``(is_seed, has_pdf, og_score + forward_influence)`` and the top-N
    are returned.

    Bug 2 fix (evening 3, 2026-04-30): Seed DOIs are ALWAYS preserved in the
    candidate pool, even when their og_score is 0 because they're not yet
    cited within the corpus.

    Hydrates each row's abstract from (in priority order):

    1. ``Sources/Articles/<doi-slug>.md`` (already-written stub)
    2. The :class:`Paper`'s ``abstract`` field
    3. ``"[no abstract]"`` placeholder
    """
    metrics = corpus.metrics
    seed_dois: set[str] = {s.doi.lower() for s in corpus.seeds if s.doi}

    if pdf_cache_dir is not None:
        from vaultlab.research.acquisition import cache_path_for

        def _has_pdf(doi: str) -> bool:
            return cache_path_for(doi, pdf_cache_dir).exists()
    else:

        def _has_pdf(doi: str) -> bool:
            return False

    if metrics is None:
        # Without metrics we can't rank; emit seeds first then everything else.
        ranked_dois = list(seed_dois) + [d for d in corpus.papers.keys() if d not in seed_dois]
    else:

        def _full_score(doi: str) -> tuple[int, int, float]:
            return (
                1 if doi in seed_dois else 0,
                1 if _has_pdf(doi) else 0,
                float(metrics.og_score.get(doi, 0.0))
                + float(metrics.forward_influence.get(doi, 0)),
            )

        ranked_dois = sorted(corpus.papers.keys(), key=_full_score, reverse=True)
        # Defensive: ensure any seed DOIs not present in corpus.papers are
        # ALSO included (they get appended to the end so they won't outrank
        # corpus papers, but they'll still be considered).
        for sd in seed_dois:
            if sd not in corpus.papers:
                ranked_dois.append(sd)
    # ``coarse_n=None`` means "no cap UNLESS the corpus is huge." The
    # auto-cap protects against context-window blow-out when forward
    # citation expansion produces a 2000+ paper corpus.
    effective_cap = coarse_n
    if effective_cap is None and len(ranked_dois) > _AUTO_CAP_THRESHOLD:
        effective_cap = _AUTO_CAP_DEFAULT
        logger.info(
            "picker auto-cap: corpus has %d papers > %d threshold; "
            "capping candidate pool to top %d",
            len(ranked_dois),
            _AUTO_CAP_THRESHOLD,
            _AUTO_CAP_DEFAULT,
        )
    if effective_cap is not None:
        ranked_dois = ranked_dois[:effective_cap]

    out: list[CandidatePaper] = []
    for doi in ranked_dois:
        paper = corpus.papers.get(doi)
        # Abstract: KB stub first, then Paper.abstract, then placeholder.
        abstract = load_abstract_from_kb(kb_root, doi)
        if not abstract and paper is not None:
            abstract = (paper.abstract or "").strip()
        if not abstract:
            abstract = "[no abstract]"
        og = float(metrics.og_score.get(doi, 0.0)) if metrics else 0.0
        fwd = int(metrics.forward_influence.get(doi, 0)) if metrics else 0
        out.append(
            CandidatePaper(
                doi=doi,
                title=(paper.title if paper else "") or "",
                authors=list(paper.authors) if paper else [],
                year=int(paper.year) if paper and paper.year else 0,
                journal=(paper.journal if paper else "") or "",
                abstract=abstract,
                og_score=og,
                forward_influence=fwd,
                has_pdf=_has_pdf(doi),
            )
        )
    return out


# ---------------------------------------------------------------------------
# Public API: prepare / render / fallback
# ---------------------------------------------------------------------------


def prepare_picker_task(
    topic: str,
    *,
    corpus: Corpus,
    target_n: int = 10,
    coarse_n: int | None = None,
    kb_root: Path,
    pdf_cache_dir: Path | None = None,
) -> PickerTask:
    """Prepare a content-aware paper-picker task. Does NOT call any LLM.

    1. Selects candidates from the corpus. **Default (``coarse_n=None``):**
       every paper in the corpus is a candidate — the picker reads ALL
       abstracts. Pass an integer to restore the legacy capped-pool behaviour
       (top-N by ``og_score + forward_influence``).
    2. For each candidate, reads the abstract from
       ``Sources/Articles/<doi>.md`` (or the in-memory
       :attr:`Paper.abstract`); falls back to ``"[no abstract]"``.
    3. Builds a system + user prompt asking the picker to rank by
       relevance / novelty / diversity / recency-vs-canonical balance.
    4. Returns the structured :class:`PickerTask`. The caller (the slash
       command body, or :func:`pick_top_n_content_aware` with a callback)
       runs the actual ranking step.

    Args:
        topic: User-supplied topic, raw.
        corpus: Built :class:`Corpus` (``compute_metrics`` already run).
        target_n: How many DOIs the picker should return (default 10).
        coarse_n: Maximum candidate-pool size. ``None`` (default) means
            no cap — every corpus paper is a candidate.
        kb_root: Vaultlab KB root.
        pdf_cache_dir: Optional ``Sources/Papers/`` directory used to
            mark candidates with cached PDFs. Informational only.

    Returns:
        A :class:`PickerTask` ready for the Claude Code session.
    """
    candidates = _build_candidates(
        corpus,
        coarse_n=coarse_n,
        kb_root=Path(kb_root),
        pdf_cache_dir=pdf_cache_dir,
    )
    prompt = build_picker_prompt(topic=topic, candidates=candidates, target_n=target_n)
    return PickerTask(
        topic=topic,
        candidates=candidates,
        target_n=target_n,
        prompt=prompt,
        system_prompt=_PICKER_SYSTEM_PROMPT,
        response_schema=picker_response_schema(),
    )


def render_picks_from_response(
    task: PickerTask,
    response_json: dict[str, Any] | None,
) -> list[str]:
    """Take Claude Code's JSON response and return an ordered DOI list.

    The picks are filtered to candidate DOIs (any picks not present in
    ``task.candidates`` are dropped — the picker is forbidden from
    inventing DOIs). Picks are sorted by ``rank`` ascending; ties fall
    back to insertion order. Missing or non-numeric ranks sort last.

    Args:
        task: The :class:`PickerTask` produced by
            :func:`prepare_picker_task`.
        response_json: Parsed JSON dict matching
            :func:`picker_response_schema`. ``None`` or empty -> ``[]``.

    Returns:
        Ordered list of DOIs (lower-cased). Length capped at
        ``task.target_n``.
    """
    if not response_json:
        return []
    raw_picks = response_json.get("picks") or []
    if not isinstance(raw_picks, list):
        return []
    valid_dois = {c.doi for c in task.candidates}
    enriched: list[tuple[int, int, str]] = []  # (rank, insertion_idx, doi)
    for idx, item in enumerate(raw_picks):
        if not isinstance(item, dict):
            continue
        raw_doi = item.get("doi")
        if not isinstance(raw_doi, str):
            continue
        doi = raw_doi.strip().lower()
        if not doi or doi not in valid_dois:
            logger.debug("picker dropped unknown DOI: %r", raw_doi)
            continue
        raw_rank = item.get("rank")
        try:
            rank = int(raw_rank)
        except (TypeError, ValueError):
            rank = 10**6  # sort missing ranks last
        enriched.append((rank, idx, doi))
    enriched.sort(key=lambda t: (t[0], t[1]))
    seen: set[str] = set()
    out: list[str] = []
    for _rank, _idx, doi in enriched:
        if doi in seen:
            continue
        seen.add(doi)
        out.append(doi)
        if len(out) >= task.target_n:
            break
    return out


def _rationales_by_doi(
    response_json: dict[str, Any] | None,
) -> dict[str, str]:
    """Build a doi -> rationale map from the picker response."""
    if not response_json:
        return {}
    raw = response_json.get("picks") or []
    if not isinstance(raw, list):
        return {}
    out: dict[str, str] = {}
    for item in raw:
        if not isinstance(item, dict):
            continue
        doi = item.get("doi")
        rationale = item.get("rationale", "")
        if isinstance(doi, str) and isinstance(rationale, str):
            out[doi.strip().lower()] = rationale.strip()
    return out


# ---------------------------------------------------------------------------
# Decisions-log writer (audit trail)
# ---------------------------------------------------------------------------


def _format_decision_block(
    *,
    topic: str,
    coarse_n: int,
    target_n: int,
    method: str,
    picks: list[str],
    rationales: dict[str, str],
    candidates_by_doi: dict[str, CandidatePaper],
    timestamp: str,
) -> str:
    """Render the markdown block appended to ``decisions-log.md``."""
    lines: list[str] = [
        "",
        f"## Picker decision — {timestamp}",
        "",
        f"Topic: {topic}",
        f"Coarse pool: {coarse_n} candidates from citation graph",
        f"Target N: {target_n}",
        f"Method: {method}",
        "",
        "### Picks",
        "",
    ]
    if not picks:
        lines.append("_(picker returned no picks)_")
        lines.append("")
        return "\n".join(lines)
    from vaultlab.kb.paths import author_year_label

    for i, doi in enumerate(picks, 1):
        cand = candidates_by_doi.get(doi)
        slug = slugify_doi(doi)
        if cand is not None:
            label = author_year_label(cand.authors, cand.year)
            stats = f"(og={cand.og_score:.2f}, fwd={cand.forward_influence})"
        else:
            label = doi
            stats = ""
        rationale = rationales.get(doi, "_(no rationale)_")
        suffix = f" {stats}" if stats else ""
        lines.append(f"{i}. [[{slug}|{label}]]{suffix} — {rationale}")
    lines.append("")
    return "\n".join(lines)


def write_picker_decision(
    *,
    kb_root: Path,
    project: str | None,
    topic: str,
    task: PickerTask,
    picks: list[str],
    rationales: dict[str, str],
    method: str,
    fallback_dir: Path | None = None,
    timestamp: str | None = None,
) -> Path | None:
    """Append the picker decision to ``decisions-log.md`` (or a fallback).

    Behaviour:

    * If ``project`` is given AND
      ``Wiki/Projects/<project>/decisions-log.md`` exists, append the
      decision block to that file.
    * Else, if ``fallback_dir`` is given, write the block to
      ``<fallback_dir>/picker-decision.md`` (overwriting any prior file
      since it's a per-run artifact).
    * Else, return ``None`` (the caller may proceed without a written
      audit trail; the picks are still returned in memory).

    Args:
        kb_root: Vaultlab KB root.
        project: Optional project slug — used to locate the canonical
            ``decisions-log.md``.
        topic: User-supplied topic.
        task: The :class:`PickerTask` (used for candidate hydration).
        picks: Ordered DOI list returned by
            :func:`render_picks_from_response`.
        rationales: ``doi -> rationale`` map.
        method: Human-readable method label
            (e.g. ``"content-aware (Claude Code in-session)"``).
        fallback_dir: Optional run directory used when no project log
            exists yet.
        timestamp: Optional ISO timestamp; defaults to ``datetime.now()``.

    Returns:
        The written path, or ``None`` if neither destination resolved.
    """
    ts = timestamp or datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    candidates_by_doi = {c.doi: c for c in task.candidates}
    block = _format_decision_block(
        topic=topic,
        coarse_n=len(task.candidates),
        target_n=task.target_n,
        method=method,
        picks=picks,
        rationales=rationales,
        candidates_by_doi=candidates_by_doi,
        timestamp=ts,
    )

    # Prefer the project-scoped log when it already exists.
    if project:
        log_path = project_decisions_path(Path(kb_root), project)
        if log_path.exists():
            with log_path.open("a", encoding="utf-8") as fh:
                fh.write(block)
                if not block.endswith("\n"):
                    fh.write("\n")
            return log_path

    # Fall back to the run directory.
    if fallback_dir is not None:
        out_path = ensure_parent(Path(fallback_dir) / "picker-decision.md")
        header = (
            f"# Picker decision — {topic}\n"
            f"\n_(no project decisions-log.md found; per-run fallback)_\n"
        )
        out_path.write_text(header + block + "\n", encoding="utf-8")
        return out_path

    logger.debug("write_picker_decision: no project log, no fallback_dir; skipping")
    return None


# ---------------------------------------------------------------------------
# Top-level orchestration
# ---------------------------------------------------------------------------


def _citation_graph_pick(
    corpus: Corpus,
    *,
    n: int,
    pdf_cache_dir: Path | None,
) -> list[str]:
    """Mechanical citation-graph pick (the previous behaviour).

    Mirrors :func:`vaultlab.research.lineage._pick_top_n_for_summarization`
    but lives here to keep the picker module self-contained for the
    ``fallback_to_citation_graph=True`` path.
    """
    metrics = corpus.metrics
    seed_dois = [s.doi.lower() for s in corpus.seeds if s.doi]
    if metrics is None:
        return seed_dois[:n]
    if pdf_cache_dir is not None:
        from vaultlab.research.acquisition import cache_path_for

        def _has_pdf(doi: str) -> bool:
            return cache_path_for(doi, pdf_cache_dir).exists()
    else:

        def _has_pdf(doi: str) -> bool:
            return False

    def _score(doi: str) -> tuple[int, float]:
        return (
            1 if _has_pdf(doi) else 0,
            float(metrics.og_score.get(doi, 0.0)) + float(metrics.forward_influence.get(doi, 0)),
        )

    ranked = sorted(corpus.papers.keys(), key=_score, reverse=True)
    return ranked[:n]


def pick_top_n_content_aware(
    topic: str,
    corpus: Corpus,
    *,
    target_n: int = 10,
    coarse_n: int | None = None,
    kb_root: Path,
    pdf_cache_dir: Path | None = None,
    picker_callback: PickerCallback | None = None,
    fallback_to_citation_graph: bool = True,
    project: str | None = None,
    fallback_dir: Path | None = None,
    log_decision: bool = True,
) -> list[str]:
    """Run the content-aware picker.

    Two execution modes:

    * **Callback given** — :func:`prepare_picker_task` builds the prompt
      with every corpus paper's abstract (``coarse_n=None``, default) or
      a top-``coarse_n`` slice (legacy mode), ``picker_callback``
      reads abstracts and returns ranked picks, and
      :func:`render_picks_from_response` produces the final DOI list.
      Optionally writes the rationale to ``decisions-log.md``.
    * **No callback** — falls back to the mechanical citation-graph pick
      (matches the prior behaviour) when
      ``fallback_to_citation_graph=True`` (default). When
      ``fallback_to_citation_graph=False`` and no callback is given,
      raises :class:`ValueError`.

    Args:
        topic: User-supplied topic.
        corpus: Built :class:`Corpus`.
        target_n: How many DOIs to return (default 10).
        coarse_n: Maximum candidate-pool size. ``None`` (default) means
            no cap — every corpus paper is a candidate.
        kb_root: Vaultlab KB root.
        pdf_cache_dir: Optional ``Sources/Papers/`` for PDF-presence hints.
        picker_callback: Optional :data:`PickerCallback` that consumes a
            :class:`PickerTask` and returns a JSON dict matching
            :func:`picker_response_schema`.
        fallback_to_citation_graph: If True (default), missing callbacks
            fall back to the mechanical pick.
        project: Optional project slug for the canonical
            ``decisions-log.md`` write.
        fallback_dir: Optional per-run directory for the
            ``picker-decision.md`` fallback artifact.
        log_decision: When False, suppress the decisions-log write
            (used in tests).

    Returns:
        Ordered list of picked DOIs, length up to ``target_n``.
    """
    if picker_callback is None:
        if not fallback_to_citation_graph:
            raise ValueError(
                "pick_top_n_content_aware requires a picker_callback when "
                "fallback_to_citation_graph=False"
            )
        return _citation_graph_pick(corpus, n=target_n, pdf_cache_dir=pdf_cache_dir)

    task = prepare_picker_task(
        topic,
        corpus=corpus,
        target_n=target_n,
        coarse_n=coarse_n,
        kb_root=Path(kb_root),
        pdf_cache_dir=pdf_cache_dir,
    )
    if not task.candidates:
        logger.warning("pick_top_n_content_aware: empty candidate pool; nothing to pick")
        return []

    response: dict[str, Any] | None
    method = "content-aware (Claude Code in-session)"
    try:
        raw_response = picker_callback(task)
    except Exception as exc:
        logger.warning("picker_callback raised: %s; falling back to citation graph", exc)
        if not fallback_to_citation_graph:
            raise
        return _citation_graph_pick(corpus, n=target_n, pdf_cache_dir=pdf_cache_dir)

    if isinstance(raw_response, dict):
        response = raw_response
    else:
        logger.warning(
            "picker_callback returned non-dict (%s); falling back",
            type(raw_response).__name__,
        )
        response = None

    picks = render_picks_from_response(task, response)
    if not picks and fallback_to_citation_graph:
        logger.warning("picker returned 0 valid picks; falling back to citation graph")
        method = "citation-graph fallback (picker returned no valid picks)"
        picks = _citation_graph_pick(corpus, n=target_n, pdf_cache_dir=pdf_cache_dir)

    rationales = _rationales_by_doi(response)

    if log_decision:
        try:
            write_picker_decision(
                kb_root=Path(kb_root),
                project=project,
                topic=topic,
                task=task,
                picks=picks,
                rationales=rationales,
                method=method,
                fallback_dir=fallback_dir,
            )
        except Exception:  # pragma: no cover — never break the run
            logger.exception("write_picker_decision failed")

    # Audit log line (info level so it's visible without DEBUG).
    for i, doi in enumerate(picks, 1):
        rat = rationales.get(doi, "")
        logger.info(
            "picker rank=%d doi=%s rationale=%s",
            i,
            doi,
            rat[:200] if rat else "(no rationale)",
        )
    return picks
