"""End-to-end ``/lit-arc`` orchestrator: search → corpus → PDFs → summaries → arc.

This module wires the four phases of the literature-search v2 pipeline
into a single :func:`run_lit_arc` call so the ``/lit-arc <topic>`` slash
command (and other callers) get a single entry point that produces:

    Sources/Notes/lit-search-<topic>-<date>.md       (search log)
    Sources/Articles/<doi-slug>.md                   (one stub per seed)
    Sources/Papers/<doi-slug>.pdf                    (downloaded full-text)
    Wiki/Summaries/<doi-slug>.md                     (per-paper summaries)
    Wiki/Concepts/<topic-slug>-lineage-<date>.md     (the lineage arc)
    <arc>.provenance.json + <arc>.method.md          (provenance receipts)

Phase boundaries
----------------
1. **Search** — :class:`vaultlab.research.ResearchClient` over PubMed/S2/etc.
2. **Search log** — markdown record in ``Sources/Notes/`` so the user
   can trace what query produced what corpus.
3. **Article stubs** — one ``Sources/Articles/<doi>.md`` per seed. We
   write our own stub here (rather than calling ``download.save_to_kb``)
   so the filename routes through :func:`vaultlab.kb.paths.article_stub_path`
   and stays consistent with every other path in the KB.
4. **Corpus + metrics** — :func:`build_corpus_from_seeds` walks one
   layer of CrossRef references; :func:`compute_metrics` produces
   og_score / forward_influence / co-citation pairs / year buckets.
5. **PDF acquisition** — :func:`acquire_pdfs_for_corpus` (waterfall).
6. **Summaries (Tier A vs C)** — :func:`summarize_corpus`. Papers with
   PDFs get full Claude reads; the rest are Tier C stubs. Top-N (by
   combined ``og_score + forward_influence``) get prioritised.
7. **Lineage arc** — :func:`_render_arc` writes the cross-source
   narrative + structured tables to ``Wiki/Concepts/``. The narrative
   paragraphs are LLM-generated when ``ANTHROPIC_API_KEY`` is set;
   otherwise the structured tables are emitted with a "narrative skipped"
   note.
8. **Provenance** — :func:`vaultlab.provenance.write_receipts` drops
   the JSON + method.md sidecars next to the arc.

Authentication
--------------
The lineage-narrative LLM call uses the same auth resolver as
``summarize.py`` (:func:`load_anthropic_api_key`). If no key is found
we fall back to "structured tables only" — never raise — so dry-runs
without keys still produce a fully-routed arc file.

LLM-driven binning (recommended)
--------------------------------
After :func:`compute_metrics` runs, the deterministic year-quartile
``year_buckets`` can leave the HISTORY bucket EMPTY on corpora where
every paper is recent (Bobby's L4 CODEX bug, 2026-04-30). Pass
``binner_callback`` to ``run_lit_arc`` and the orchestrator routes the
corpus through :func:`vaultlab.research.binning.assign_buckets_with_llm`
between phases 4 and 6 — the LLM reads each abstract, decides whether
the paper is HISTORY / DEVELOPMENT / SOTA *for the topic's lineage*,
and the resulting buckets OVERRIDE
``corpus.metrics.year_buckets`` (mutated in place) so summaries, arc
narration, and slides all see the LLM-driven assignment. Without a
callback, the deterministic year-quartile buckets are kept as the
fallback path.

Two execution modes
-------------------
Like ``summarize.py``, this module exposes two parallel paths:

1. **SDK path** (:func:`run_lit_arc` with no ``reader`` / ``narrator``
   args, or :func:`_call_anthropic_arc`) — calls the Anthropic API
   directly via an API key.
2. **Claude-Code-callable path** (:func:`prepare_arc_task` +
   :func:`render_arc_from_response`, plus ``run_lit_arc(reader=...,
   narrator=...)``) — does NOT call any LLM. The slash command body
   inside Claude Code reads PDFs / generates arc paragraphs in-session
   and feeds the JSON back through the render functions.

Use the Claude-Code-callable path from ``.claude/commands/lit-arc.md``
so users without an Anthropic API key can still run the full pipeline.
"""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Literal

from vaultlab.kb.paths import (
    article_stub_path,
    concept_path,
    ensure_parent,
    project_decisions_path,
    project_lineage_pointer_path,
    project_papers_path,
    project_state_path,
    search_log_path,
    slugify_doi,
    slugify_topic,
    summary_path,
)
from vaultlab.provenance import ProvenanceRecord, write_receipts
from vaultlab.research.acquisition import acquire_pdfs_for_corpus
from vaultlab.research.binning import (
    BinningCallback,
    BinningTask,
    assign_buckets_with_llm,
)
from vaultlab.research.corpus import build_corpus_from_seeds
from vaultlab.research.graph_metrics import compute_metrics
from vaultlab.research.picker import (
    PickerCallback,
    pick_top_n_content_aware,
    write_picker_decision,
)
from vaultlab.research.summarize import (
    DEFAULT_MODEL,
    PaperSummary,
    SummarizeAuthError,
    SummaryReader,
    load_anthropic_api_key,
    summarize_corpus,
)

if TYPE_CHECKING:
    from vaultlab.research.corpus import Corpus
    from vaultlab.research.paper import Paper

logger = logging.getLogger(__name__)

__all__ = [
    "ArcNarrator",
    "ArcTask",
    "DepthLevel",
    "LineageRunResult",
    "arc_response_schema",
    "build_arc_prompt",
    "prepare_arc_task",
    "render_arc_from_response",
    "render_arc_markdown",
    "run_lit_arc",
]


# ---------------------------------------------------------------------------
# Depth control (Task #63, 2026-04-30)
# ---------------------------------------------------------------------------

DepthLevel = Literal["fast", "balanced", "thorough", "complete"]
"""Depth knob exposed by ``/lit-arc`` so users can dial Tier-A read budget
to match how much wall-clock time they have. Mapped to a Tier-A budget by
:func:`_derive_max_papers` once PDF acquisition has finished (so the
ceiling is the actual count of cached PDFs).

* ``fast`` — ~20 Tier-A papers, ~15 min. Quick scoping.
* ``balanced`` — ~50 Tier-A papers, ~30 min. Daily literature review (default).
* ``thorough`` — read every cached PDF, ~60 min. Deep review.
* ``complete`` — read every cached PDF AND retry paywalled-acquisition
  once more before deciding the budget, ~90 min. Publication-grade.
"""

# Soft thresholds the orchestrator uses to derive the Tier-A budget when
# ``max_papers_to_summarize`` is left at its default (None). Kept module-level
# so tests / docs don't drift from runtime behaviour.
_DEPTH_CAP_FAST = 20
_DEPTH_CAP_BALANCED = 50
_LARGE_CORPUS_WARNING_THRESHOLD = 200


def _derive_max_papers(
    depth: DepthLevel,
    n_pdfs_cached: int,
    corpus_size: int,
) -> int:
    """Map ``depth`` -> Tier-A paper budget.

    Args:
        depth: One of ``"fast" | "balanced" | "thorough" | "complete"``.
        n_pdfs_cached: How many corpus papers ended up with a usable PDF
            after the acquisition phase (the ceiling for read-everything
            depth modes — there's no point budgeting for papers we can't
            full-text read).
        corpus_size: Total papers in the corpus (search seeds + walked refs).
            Currently informational, but kept in the signature so future
            extensions can use it (e.g. abstract-only fallback for Tier-C).

    Returns:
        Tier-A paper budget (an int >= 0).
    """
    del corpus_size  # kept for forward compatibility; not used today
    n_pdfs_cached = max(0, int(n_pdfs_cached))
    if depth == "fast":
        return min(_DEPTH_CAP_FAST, n_pdfs_cached)
    if depth == "balanced":
        return min(_DEPTH_CAP_BALANCED, n_pdfs_cached)
    if depth == "thorough":
        return n_pdfs_cached
    if depth == "complete":
        # The aggressive_retry happens at acquisition time, so by the time
        # we get here ``n_pdfs_cached`` already reflects the retried count.
        return n_pdfs_cached
    raise ValueError(
        f"unknown depth: {depth!r} (expected one of "
        f"'fast', 'balanced', 'thorough', 'complete')"
    )


# ---------------------------------------------------------------------------
# Same-day arc collision detection (Fix 3, 2026-04-30 evening-4)
# ---------------------------------------------------------------------------


def _resolve_arc_path_with_collision(
    base_path: Path,
    *,
    expected_content: str | None = None,
) -> Path:
    """Pick an arc path that does NOT clobber an existing same-day arc.

    Same-day re-runs of ``/lit-arc`` previously overwrote
    ``Wiki/Concepts/<topic>-lineage-<date>.md`` (and its
    ``.method.md`` + ``.provenance.json`` sidecars) every time the user
    re-ran the pipeline on the same date. That wiped the prior arc with
    no warning. This helper preserves the prior arc by picking
    ``<topic>-lineage-<date>-rerun-1.md`` (and ``-rerun-2.md`` etc.) on
    collision.

    Args:
        base_path: The desired path
            (``Wiki/Concepts/<topic>-lineage-<date>.md``).
        expected_content: When given, compare the existing file's text
            against this. Identical content (deterministic re-run with
            same inputs) means the rerun is idempotent — return
            ``base_path`` unchanged so the on-disk file is left alone.
            When the existing content differs, walk the rerun-N suffix
            until a free slot is found.

    Returns:
        The resolved path. The file at ``base_path`` is **never** touched
        by this helper; the caller writes to the returned path.
    """
    base_path = Path(base_path)
    if not base_path.exists():
        return base_path
    if expected_content is not None:
        try:
            existing = base_path.read_text(encoding="utf-8")
        except OSError:
            existing = ""
        if existing == expected_content:
            # Idempotent re-run with identical content — keep the existing
            # path, no rename needed.
            return base_path
    # Walk rerun-1, rerun-2, ... until a free slot exists.
    parent = base_path.parent
    stem = base_path.stem  # e.g. "topic-lineage-2026-04-30"
    suffix = base_path.suffix  # ".md"
    n = 1
    while True:
        candidate = parent / f"{stem}-rerun-{n}{suffix}"
        if not candidate.exists():
            return candidate
        n += 1


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------


@dataclass
class LineageRunResult:
    """Output of a :func:`run_lit_arc` call.

    Attributes:
        topic: The user-supplied topic (raw, not slugified).
        arc_path: Path to ``Wiki/Concepts/<topic>-lineage-<date>.md``.
        summary_paths: Mapping ``doi -> Wiki/Summaries/<doi>.md`` for
            every paper that received a summary file (Tier A or C).
        search_log_path: Path to ``Sources/Notes/lit-search-<query>-<date>.md``.
        corpus_size: Number of papers in the corpus (seeds + walked refs).
        pdfs_acquired: Count of papers with a successful PDF acquisition
            (or cache hit) — these are the Tier A candidates.
        summaries_written: Count of summary markdown files actually written.
        duration_seconds: Wall-clock time of the full run.
        project_slug: The slug used for ``Wiki/Projects/<slug>/`` (either
            an explicit override or ``slugify_topic(topic)``).
        project_view_paths: Mapping of project-view file kind
            (``start_here``, ``papers``, ``lineage``, ``decisions_log``)
            to the file path written by Phase 8.
        corpus: The live :class:`Corpus` produced by Phase 4 (corpus +
            metrics). Carried so downstream consumers (e.g. the
            adversarial deck-plan path) can read
            ``corpus.metrics.co_citation_pairs`` / ``corpus.seeds`` /
            ``corpus.references`` without reconstructing a synthetic
            corpus from on-disk frontmatters (F-13 in the
            pipeline-integration-map audit). May be ``None`` for callers
            that only need paths.
        figure_assignments: Mapping ``doi -> figure_path`` populated when
            ``run_lit_arc(..., acquire_figures=True)`` ran the
            figure-acquisition phase between PDF acquisition and
            summarization. Empty dict otherwise. The deck builder reads
            this directly via ``build_deck_from_lineage_result(...,
            figure_assignments=result.figure_assignments)`` so the
            slash-command body no longer has to call
            ``acquire_figures_for_corpus`` itself.
        figures_acquired: Count of papers with at least one figure on
            disk after Phase 4b. ``0`` when ``acquire_figures`` was False.
    """

    topic: str
    arc_path: Path
    summary_paths: dict[str, Path] = field(default_factory=dict)
    search_log_path: Path = Path()
    corpus_size: int = 0
    pdfs_acquired: int = 0
    summaries_written: int = 0
    duration_seconds: float = 0.0
    project_slug: str = ""
    project_view_paths: dict[str, Path] = field(default_factory=dict)
    corpus: "Corpus | None" = None
    figure_assignments: dict[str, Path] = field(default_factory=dict)
    figures_acquired: int = 0


# ---------------------------------------------------------------------------
# Search log writer (Sources/Notes/lit-search-...md)
# ---------------------------------------------------------------------------


def _search_trace_path(kb_root: Path, topic: str, date_str: str) -> Path:
    """Sidecar JSON path for ``_write_search_log``.

    Mirrors the markdown log filename — ``lit-search-<topic>-<date>.md``
    becomes ``lit-search-<topic>-<date>.search-trace.json``. This keeps
    the trace co-located with the human-readable record so a decisions-log
    reader can find both with one ``ls``.
    """
    md = search_log_path(Path(kb_root), topic, date_str)
    return md.with_suffix("").with_name(md.stem + ".search-trace.json")


def _write_search_trace(
    *,
    kb_root: Path,
    topic: str,
    date_str: str,
    trace: Any,
) -> Path | None:
    """Persist a :class:`SearchTrace` next to the markdown search log.

    Returns the path that was written, or ``None`` when the trace object
    can't be serialized (e.g. an injected fake search client returned a
    plain list and the orchestrator built no trace). Failure is silent —
    the trace is observability, not load-bearing data.
    """
    if trace is None:
        return None
    try:
        payload = trace.to_dict()
    except Exception:  # pragma: no cover — defensive
        logger.exception("search trace failed to serialize")
        return None
    path = ensure_parent(_search_trace_path(Path(kb_root), topic, date_str))
    try:
        path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    except OSError:  # pragma: no cover — disk failure shouldn't kill run
        logger.exception("failed to write search trace at %s", path)
        return None
    return path


def _write_pdf_acquisition_trace(
    *,
    acq_results: dict[str, Any],
    run_dir: Path | None,
    kb_root: Path,
    topic: str,
    date_str: str,
) -> Path | None:
    """Persist a per-DOI PDF acquisition trace (Gap 2 — observability).

    Shape::

        {
          "run_id": "...",
          "per_doi": {
            "10.x/y": {
              "tried": ["unpaywall", "pmc", ...],
              "succeeded": "pmc" | null,
              "errors": {"unpaywall": "404", ...},
              "result_path": "<kb>/Sources/Papers/...",
              "wall_time_ms": 1234
            }
          },
          "summary": {"total_dois": N, "succeeded": M,
                      "fail_reasons": {...}}
        }

    Writes to ``<run_dir>/pdf-acquisition-trace.json`` when ``run_dir``
    is provided (so it lands inside the run-archived directory).
    Otherwise falls back to
    ``<kb>/Sources/Notes/pdf-acquisition-trace-<topic>-<date>.json`` so
    callers without a run_dir still get the sidecar.
    """
    if not acq_results:
        return None

    per_doi: dict[str, Any] = {}
    fail_reasons: dict[str, int] = {}
    succeeded = 0
    for doi, res in acq_results.items():
        path = getattr(res, "pdf_path", None)
        source = getattr(res, "source", "")
        is_success = path is not None and source not in ("failed", "")
        if is_success:
            succeeded += 1
        else:
            reason = getattr(res, "error", None) or "unknown"
            fail_reasons[reason] = fail_reasons.get(reason, 0) + 1
        per_doi[doi] = {
            "tried": list(getattr(res, "tried", ()) or ()),
            "succeeded": source if is_success else None,
            "errors": dict(getattr(res, "tier_errors", {}) or {}),
            "result_path": str(path) if path is not None else None,
            "wall_time_ms": int(getattr(res, "wall_time_ms", 0) or 0),
            "license": getattr(res, "license", None),
        }

    payload = {
        "run_id": (run_dir.name if run_dir is not None else f"{slugify_topic(topic)}-{date_str}"),
        "topic": topic,
        "date": date_str,
        "per_doi": per_doi,
        "summary": {
            "total_dois": len(per_doi),
            "succeeded": succeeded,
            "failed": len(per_doi) - succeeded,
            "fail_reasons": fail_reasons,
        },
    }

    if run_dir is not None:
        target = ensure_parent(Path(run_dir) / "pdf-acquisition-trace.json")
    else:
        target = ensure_parent(
            Path(kb_root)
            / "Sources"
            / "Notes"
            / f"pdf-acquisition-trace-{slugify_topic(topic)}-{date_str}.json"
        )
    try:
        target.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    except OSError:  # pragma: no cover — defensive
        logger.exception("failed to write pdf acquisition trace at %s", target)
        return None
    return target


def _write_search_log(
    *,
    kb_root: Path,
    topic: str,
    seeds: list[Paper],
    date_str: str,
) -> Path:
    """Drop a markdown record of the search query + the seed papers.

    This is the audit trail: "what did the user ask, what did the search
    engine return". Lives in ``Sources/`` because it's an immutable
    record, not LLM-synthesized content.
    """
    path = ensure_parent(search_log_path(Path(kb_root), topic, date_str))
    lines: list[str] = [
        "---",
        f"query: {topic}",
        f"date: {date_str}",
        f"n_seeds: {len(seeds)}",
        "generated_by: vaultlab.research.lineage.run_lit_arc",
        "---",
        "",
        f"# Lit-search log: {topic}",
        "",
        f"Date: {date_str}",
        f"Seeds returned: {len(seeds)}",
        "",
        "## Seeds",
        "",
    ]
    for i, seed in enumerate(seeds, 1):
        title = seed.title or "(untitled)"
        year = seed.year or "?"
        journal = seed.journal or ""
        doi = seed.doi or ""
        line = f"{i}. **{title}** ({year}) — {journal}"
        if doi:
            line += f" [DOI: {doi}]"
        lines.append(line)
        if seed.authors:
            authors = ", ".join(seed.authors[:5])
            if len(seed.authors) > 5:
                authors += ", ..."
            lines.append(f"   - Authors: {authors}")
        if seed.citation_count:
            lines.append(f"   - Cited by: {seed.citation_count}")
    lines.append("")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Article-stub writer (Sources/Articles/<doi>.md, canonical paths)
# ---------------------------------------------------------------------------


def _write_article_stub(kb_root: Path, paper: Paper) -> Path | None:
    """Write a single seed's metadata stub to ``Sources/Articles/<doi>.md``.

    Returns ``None`` (without writing) when the paper has no DOI — those
    seeds can't be routed canonically and stay only in the search log.
    """
    if not paper.doi:
        return None
    path = ensure_parent(article_stub_path(Path(kb_root), paper.doi))
    lines: list[str] = ["---"]
    title = (paper.title or "").replace('"', '\\"')
    lines.append(f'title: "{title}"')
    if paper.authors:
        lines.append("authors:")
        for a in paper.authors:
            esc = a.replace('"', '\\"')
            lines.append(f'  - "{esc}"')
    if paper.year:
        lines.append(f"year: {paper.year}")
    if paper.journal:
        j = paper.journal.replace('"', '\\"')
        lines.append(f'journal: "{j}"')
    lines.append(f'doi: "{paper.doi}"')
    if paper.pmid:
        lines.append(f'pmid: "{paper.pmid}"')
    if paper.citation_count:
        lines.append(f"citation_count: {paper.citation_count}")
    if paper.source_api:
        lines.append(f'source: "{paper.source_api}"')
    lines.append(f"created: {date.today().isoformat()}")
    lines.append("tags: [article, literature, lit-arc-seed]")
    lines.append("---")
    lines.append("")
    lines.append(f"# {paper.title or paper.doi}")
    lines.append("")
    if paper.authors:
        lines.append(f"**Authors:** {', '.join(paper.authors)}")
        lines.append("")
    if paper.journal and paper.year:
        lines.append(f"**Published in:** {paper.journal} ({paper.year})")
        lines.append("")
    if paper.doi:
        lines.append(f"**DOI:** [{paper.doi}](https://doi.org/{paper.doi})")
        lines.append("")
    if paper.abstract:
        lines.append("## Abstract")
        lines.append("")
        lines.append(paper.abstract)
        lines.append("")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Project-view writer (Wiki/Projects/<slug>/{START_HERE,papers,lineage,decisions-log}.md)
# ---------------------------------------------------------------------------


# Regex to parse Tier rows in a sibling project's papers.md, e.g.
#   | [[10.1126_science.1225829\|Jinek 2012]] | 2012 | 0.66 | 2 | — |
# We match the wikilink slug only (column 1), since "Also in" needs no other data.
_SIBLING_WIKILINK_RE = re.compile(
    r"\[\[([A-Za-z0-9._\-+/]+)(?:\\?\|[^\]]*)?\]\]"
)


def _scan_sibling_project_dois(
    kb_root: Path,
    *,
    exclude_slug: str,
) -> dict[str, list[str]]:
    """Return ``{doi-slug: [project-slug, ...]}`` from sibling projects' papers.md.

    Walks ``Wiki/Projects/*/papers.md`` and extracts the wikilink slugs out
    of every paper row. Used to populate the "Also in" column when a paper
    is referenced by multiple projects. The current project's own slug is
    excluded so we never list it as "also in" itself.
    """
    membership: dict[str, list[str]] = {}
    projects_root = Path(kb_root) / "Wiki" / "Projects"
    if not projects_root.exists():
        return membership
    for child in sorted(projects_root.iterdir()):
        if not child.is_dir():
            continue
        sibling_slug = child.name
        if sibling_slug == exclude_slug:
            continue
        papers_md = child / "papers.md"
        if not papers_md.exists():
            continue
        try:
            text = papers_md.read_text(encoding="utf-8")
        except OSError:
            continue
        # Track which slugs we've already attributed to this sibling so we
        # don't duplicate them when the same DOI appears in both Tier-A and
        # Tier-C blocks (shouldn't happen, but be defensive).
        seen: set[str] = set()
        for m in _SIBLING_WIKILINK_RE.finditer(text):
            doi_slug = m.group(1)
            # Skip non-DOI wikilinks (e.g. local "papers" / "decisions-log"
            # navigation links). Heuristic: real DOI slugs always contain a
            # dot AND an underscore (the slugified "/" separator).
            if "." not in doi_slug or "_" not in doi_slug:
                continue
            if doi_slug in seen:
                continue
            seen.add(doi_slug)
            membership.setdefault(doi_slug, []).append(sibling_slug)
    return membership


def _project_view_label(s: PaperSummary) -> str:
    """Author-Year label used in Wiki/Projects/<slug>/papers.md wikilinks.

    Delegates surname extraction to :func:`vaultlab.kb.paths.author_year_label`
    so OpenAlex's ``F. Last`` format (e.g. ``J. Kennedy-Darling``) renders
    as ``Kennedy-Darling 2020`` instead of ``J. 2020``.
    """
    from vaultlab.kb.paths import author_year_label

    return author_year_label(s.authors, s.year)


def _render_project_papers_md(
    *,
    project_slug: str,
    topic: str,
    summaries: dict[str, PaperSummary],
    arc_path: Path,
    deck_path: Path | None,
    also_in: dict[str, list[str]],
    date_str: str,
) -> str:
    """Render the body of ``Wiki/Projects/<slug>/papers.md``.

    Tier-A papers go in a sortable table; Tier-C papers go in a
    space-efficient comma-separated wikilink list (5 per line). The
    ``also_in`` map is keyed by DOI-slug.
    """
    rows: list[tuple[PaperSummary, str]] = []
    for doi, s in summaries.items():
        slug = slugify_doi(doi) if doi else slugify_doi(s.doi or "unknown")
        rows.append((s, slug))

    tier_a = [(s, slug) for s, slug in rows if s.tier == "A"]
    tier_c = [(s, slug) for s, slug in rows if s.tier != "A"]

    # Tier-A: rank by og_score + forward_influence/10 (matches backfill script).
    tier_a.sort(
        key=lambda pair: -(pair[0].og_score + pair[0].forward_influence / 10)
    )
    # Tier-C: by year descending, with year=0 sinking to the bottom.
    tier_c.sort(key=lambda pair: -(pair[0].year or 0))

    deck_line = (
        f"**Slide deck:** `Output/{project_slug}/{deck_path.name}`"
        if deck_path is not None
        else "**Slide deck:** _(none — lit-arc only)_"
    )

    lines: list[str] = [
        "---",
        f"project: {project_slug}",
        f"topic: {topic}",
        f"updated: {date_str}",
        f"total_corpus: {len(rows)}",
        f"tier_a_count: {len(tier_a)}",
        f"tier_c_count: {len(tier_c)}",
        "kind: project-papers",
        "---",
        "",
        f"# Papers — {project_slug}",
        "",
        f"This project read the following papers for the lineage arc *{topic}*. ",
        "Each `[[wikilink]]` resolves to the **global** per-paper summary at "
        "`Wiki/Summaries/<doi-slug>.md`. Papers also surfaced by other projects ",
        "are noted in the *Also in* column.",
        "",
        f"**Lineage arc:** [[{arc_path.stem}]]",
        deck_line,
        "",
        "## Tier A — full text read by Claude Code",
        "",
        "Papers with cached PDFs read end-to-end and rendered as "
        "`Wiki/Summaries/<doi>.md` with TL;DR, methods, key findings (with "
        "`[p<N>]` page markers), and connections.",
        "",
    ]

    if tier_a:
        lines.append("| Paper | Year | OG | Forward | Also in |")
        lines.append("|---|---|---|---|---|")
        for s, slug in tier_a:
            label = _project_view_label(s)
            also = ", ".join(f"`{x}`" for x in also_in.get(slug, [])) or "—"
            lines.append(
                f"| [[{slug}\\|{label}]] | {s.year or '?'} "
                f"| {s.og_score:.2f} | {s.forward_influence} | {also} |"
            )
    else:
        lines.append("_(no Tier-A papers — none had a cached PDF)_")

    lines.extend([
        "",
        "## Tier C — citation-stat-only stubs",
        "",
        "Papers cited via the corpus's citation graph but not read full-text. "
        "Frontmatter has citation metrics; LLM-written content sections are "
        "empty. Linked here so the citation network is navigable in "
        "Obsidian's graph view.",
        "",
    ])
    if tier_c:
        chunks = [
            f"[[{slug}\\|{_project_view_label(s)}]]"
            for s, slug in tier_c
        ]
        # 5 per line for readability — same as the backfill script.
        for i in range(0, len(chunks), 5):
            lines.append(" · ".join(chunks[i:i + 5]))
    else:
        lines.append("_(no Tier-C papers in this corpus)_")

    return "\n".join(lines) + "\n"


def _render_project_lineage_pointer(
    *,
    project_slug: str,
    topic: str,
    arc_path: Path,
    date_str: str,
) -> str:
    """Render ``Wiki/Projects/<slug>/lineage.md`` — short pointer page."""
    return (
        "---\n"
        f"project: {project_slug}\n"
        f"topic: {topic}\n"
        f"updated: {date_str}\n"
        "kind: lineage-pointer\n"
        "---\n\n"
        f"# Lineage — {project_slug}\n\n"
        f"The full lineage arc for this project lives at: [[{arc_path.stem}]]\n\n"
        f"Generated {date_str} by `vaultlab.research.lineage.run_lit_arc`.\n"
    )


def _render_project_start_here(
    *,
    project_slug: str,
    topic: str,
    summaries: dict[str, PaperSummary],
    arc_path: Path,
    deck_path: Path | None,
    date_str: str,
) -> str:
    """Render ``Wiki/Projects/<slug>/START_HERE.md`` — landing page."""
    n_total = len(summaries)
    n_tier_a = sum(1 for s in summaries.values() if s.tier == "A")
    n_tier_c = n_total - n_tier_a
    deck_line = (
        f"- **Slide deck:** `Output/{project_slug}/{deck_path.name}`"
        if deck_path is not None
        else "- **Slide deck:** _(none — lit-arc only)_"
    )
    return (
        "---\n"
        f"project: {project_slug}\n"
        f"topic: {topic}\n"
        f"updated: {date_str}\n"
        "kind: project-start-here\n"
        "---\n\n"
        f"# {topic}\n\n"
        f"Project slug: `{project_slug}`\n\n"
        "## What this is\n\n"
        f"VaultLab project for a literature lineage arc on **{topic}**. "
        f"Generated/updated {date_str} via `/lit-arc` "
        "(`vaultlab.research.lineage.run_lit_arc`).\n\n"
        "## What's in the corpus\n\n"
        f"- **{n_total} papers** total across the citation-graph corpus\n"
        f"- **{n_tier_a} Tier-A** papers read full-text (TL;DRs in `Wiki/Summaries/`)\n"
        f"- **{n_tier_c} Tier-C** papers cited for citation-graph metrics only\n\n"
        "## Where to look\n\n"
        f"- **The lineage narrative:** [[{arc_path.stem}|→ open arc]]\n"
        "- **Per-paper manifest:** [[papers|→ open papers list]]\n"
        "- **Decisions log:** [[decisions-log|→ open log]]\n"
        f"{deck_line}\n\n"
        "## Last updated\n\n"
        f"{date_str}\n"
    )


def _render_decisions_log_entry(
    *,
    topic: str,
    speaker: str,
    seeds_n: int,
    sources_n: int,
    corpus_size: int,
    tier_a_n: int,
    pdfs_acquired: int,
    picker_method: str,
    crosstalk: str,
    run_id: str | None,
    output_slug: str,
    deck_path: Path | None,
    timestamp: str,
) -> str:
    """Render one append-only entry for ``decisions-log.md``."""
    pct = (
        f"{(pdfs_acquired / max(corpus_size, 1)) * 100:.0f}%"
        if corpus_size
        else "0%"
    )
    deck_line = (
        f"- **Output deck:** {deck_path}"
        if deck_path is not None
        else "- **Output deck:** none — lit-arc only"
    )
    run_line = (
        f"- **Run ID:** {run_id} (`Output/{output_slug}/runs/{run_id}/`)"
        if run_id
        else "- **Run ID:** none (no run_dir provided)"
    )
    return (
        f"## {timestamp} — lit-arc run\n"
        f"- **Topic:** {topic}\n"
        f"- **Speaker:** {speaker}\n"
        f"- **Search:** {seeds_n} seeds, {sources_n} sources\n"
        f"- **Corpus size:** {corpus_size} papers (1 layer of CrossRef refs)\n"
        f"- **Tier-A picks:** {tier_a_n} (picker_method=`{picker_method}`)\n"
        f"- **PDFs acquired:** {pdfs_acquired} ({pct} success rate)\n"
        f"- **Multi-agent crosstalk:** {crosstalk}\n"
        f"{run_line}\n"
        f"{deck_line}\n"
    )


def _decisions_log_header(*, project_slug: str, topic: str) -> str:
    """Return the frontmatter + H1 used at the top of a fresh decisions-log.md."""
    return (
        "---\n"
        f"project: {project_slug}\n"
        f"topic: {topic}\n"
        "kind: decisions-log\n"
        "---\n\n"
        f"# Decisions log — {project_slug}\n\n"
    )


# Frontmatter signal that ``START_HERE.md`` was written by the onboarding
# orchestrator (``vaultlab.onboarding.project_init``) and should NOT be
# clobbered by the lit-arc project-view writer. The onboarding template
# emits ``schema: vaultlab-start-here/v1`` and
# ``managed_by: vaultlab.onboarding.project_init`` in its frontmatter — we
# look for either signal so the detection is robust to small format drift.
_ONBOARDING_START_HERE_SIGNALS: tuple[str, ...] = (
    "managed_by: vaultlab.onboarding.project_init",
    "schema: vaultlab-start-here/v1",
)


def _safe_merge_start_here(
    *,
    start_here_path: Path,
    lineage_body: str,
    project_slug: str,
    topic: str,
    arc_path: Path,
    date_str: str,
    n_total: int,
    n_tier_a: int,
    n_tier_c: int,
    deck_path: Path | None,
) -> None:
    """Write the lineage START_HERE without clobbering an onboarding START_HERE.

    Detection: if ``start_here_path`` already exists and its frontmatter
    carries one of the :data:`_ONBOARDING_START_HERE_SIGNALS` markers
    (i.e. it was written by ``vaultlab.onboarding.project_init``), append
    a "## Lineage runs" section to the existing body instead of
    overwriting it. The onboarding-side content (Topic / Goals / Folder
    inventory / etc.) stays intact so users keep one canonical landing
    page per project (F-2 in the pipeline-integration-map audit).

    When the existing file was written by lit-arc itself (no onboarding
    signal), the original overwrite-with-current-state behaviour is
    preserved — we want refreshes of the live Tier-A / Tier-C counts.
    """
    existing: str | None = None
    if start_here_path.exists():
        try:
            existing = start_here_path.read_text(encoding="utf-8")
        except OSError:
            existing = None

    is_onboarding = bool(
        existing
        and existing.startswith("---")
        and any(sig in existing for sig in _ONBOARDING_START_HERE_SIGNALS)
    )

    def _emit_receipt() -> None:
        """Best-effort sidecar receipt for the START_HERE update (F-7)."""
        try:
            record = ProvenanceRecord(
                generated_by="vaultlab.research.lineage._write_project_view",
                project=project_slug,
                topic=topic,
                kind="project_start_here",
                inputs=[str(arc_path)] if arc_path else [],
                params={
                    "slug": project_slug,
                    "date": date_str,
                    "n_total": n_total,
                    "n_tier_a": n_tier_a,
                    "n_tier_c": n_tier_c,
                    "merged_with_onboarding": is_onboarding,
                },
                tags=["lit-arc", "project-view", "start-here"],
                notes=(
                    "Refreshed via lit-arc Phase 9. "
                    "Merged with onboarding START_HERE."
                    if is_onboarding else
                    "Refreshed via lit-arc Phase 9 (overwrite)."
                ),
            )
            write_receipts(start_here_path, record)
        except Exception:
            logger.exception(
                "write_receipts failed for project START_HERE %s",
                start_here_path,
            )

    if not is_onboarding:
        # Either no file or a previous lit-arc render — overwrite with
        # the live state so Tier counts refresh.
        start_here_path.write_text(lineage_body, encoding="utf-8")
        _emit_receipt()
        return

    # Onboarding-managed file: preserve it and append (or refresh) a
    # "## Lineage runs" section that lit-arc owns.
    deck_line = (
        f"- **Slide deck:** `Output/{project_slug}/{deck_path.name}`"
        if deck_path is not None
        else "- **Slide deck:** _(none — lit-arc only)_"
    )
    new_section = "\n".join([
        "## Lineage runs",
        "",
        f"- **Last run:** {date_str}",
        f"- **Topic:** {topic}",
        f"- **Corpus:** {n_total} papers ({n_tier_a} Tier-A, {n_tier_c} Tier-C)",
        f"- **Lineage arc:** [[{arc_path.stem}|→ open arc]]",
        "- **Per-paper manifest:** [[papers|→ open papers list]]",
        "- **Decisions log:** [[decisions-log|→ open log]]",
        deck_line,
        "",
    ])

    if "## Lineage runs" in existing:
        # Refresh the existing section in place so we don't accumulate
        # one block per run. Find the next H2 (or EOF) and replace.
        start = existing.find("## Lineage runs")
        # Find next "\n## " after start (a sibling H2). If none, replace
        # to end of file.
        next_h2 = existing.find("\n## ", start + 1)
        prefix = existing[:start]
        if next_h2 == -1:
            merged = prefix + new_section
        else:
            merged = prefix + new_section + "\n" + existing[next_h2 + 1:]
    else:
        if not existing.endswith("\n"):
            existing += "\n"
        merged = existing + "\n" + new_section

    start_here_path.write_text(merged, encoding="utf-8")
    _emit_receipt()


def _write_project_view(
    *,
    kb_root: Path,
    project_slug: str,
    topic: str,
    arc_path: Path,
    summaries: dict[str, PaperSummary],
    corpus: Corpus,
    deck_path: Path | None = None,
    run_id: str | None = None,
    date_str: str | None = None,
    speaker: str = "Bobby",
    sources_n: int = 0,
    picker_method: str = "citation-graph",
    crosstalk: str = "none",
    timestamp: str | None = None,
    pdfs_acquired: int | None = None,
) -> dict[str, Path]:
    """Write ``Wiki/Projects/<slug>/{START_HERE,papers,lineage,decisions-log}.md``.

    Idempotent: re-running for the same project APPENDS a new entry to
    ``decisions-log.md`` while OVERWRITING ``papers.md``, ``lineage.md``,
    and ``START_HERE.md`` (these reflect current state).

    The "Also in" column in ``papers.md`` is computed live by scanning
    sibling project directories' ``papers.md`` files — no in-memory state
    survives between runs.

    Args:
        kb_root: Vaultlab KB root.
        project_slug: Pre-slugified project identifier (e.g. ``codex-cn-test``).
            Used verbatim — the path helpers re-slugify defensively but
            already-slugified inputs are stable.
        topic: User-supplied topic (raw, not slugified) for display.
        arc_path: Path to the lineage arc Markdown that this project view
            points to.
        summaries: Mapping of doi -> :class:`PaperSummary` (the same map
            already written under ``Wiki/Summaries/``).
        corpus: The :class:`Corpus` produced by the run (currently used
            only for parity with :func:`run_lit_arc`'s other helpers; the
            paper data flows from ``summaries``).
        deck_path: Path to the deck file in Output/, or None if no deck.
        run_id: Optional run identifier (timestamped folder under runs/).
        date_str: ISO-format date used in frontmatter; defaults to today.
        speaker: Author / driver of the run, recorded in the decisions log.
        sources_n: Number of search sources hit (NCBI/S2/etc).
        picker_method: ``"citation-graph"`` or ``"content-aware"``.
        crosstalk: Free-form note for the decisions log.
        timestamp: Full timestamp for the decisions-log entry; defaults
            to ``YYYY-MM-DDTHH:MM:SS`` for now.

    Returns:
        ``{"start_here": Path, "papers": Path, "lineage": Path,
        "decisions_log": Path}`` — the four files written.
    """
    if date_str is None:
        date_str = date.today().strftime("%Y-%m-%d")
    if timestamp is None:
        timestamp = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

    # Cross-project "Also in" detection — scan sibling project papers.md
    # at write time so refreshes stay current.
    sibling_membership = _scan_sibling_project_dois(
        kb_root, exclude_slug=project_slug
    )

    # Resolve output paths via vaultlab.kb.paths (autonomous routing rule).
    start_here_p = ensure_parent(project_state_path(kb_root, project_slug))
    papers_p = ensure_parent(project_papers_path(kb_root, project_slug))
    lineage_p = ensure_parent(project_lineage_pointer_path(kb_root, project_slug))
    decisions_p = ensure_parent(project_decisions_path(kb_root, project_slug))

    # 1. papers.md — overwrite
    papers_p.write_text(
        _render_project_papers_md(
            project_slug=project_slug,
            topic=topic,
            summaries=summaries,
            arc_path=arc_path,
            deck_path=deck_path,
            also_in=sibling_membership,
            date_str=date_str,
        ),
        encoding="utf-8",
    )

    # 2. lineage.md — overwrite (pointer page; cheap to regenerate)
    lineage_p.write_text(
        _render_project_lineage_pointer(
            project_slug=project_slug,
            topic=topic,
            arc_path=arc_path,
            date_str=date_str,
        ),
        encoding="utf-8",
    )

    # 3. START_HERE.md — overwrite ONLY if not onboarding-managed.
    # Per F-2 in the pipeline-integration-map audit, when
    # ``init_project_from_intake`` already wrote an onboarding START_HERE,
    # we must not clobber it. ``_safe_merge_start_here`` detects that case
    # and appends a "## Lineage runs" section instead.
    n_total_for_view = len(summaries)
    n_tier_a_for_view = sum(1 for s in summaries.values() if s.tier == "A")
    n_tier_c_for_view = n_total_for_view - n_tier_a_for_view
    _safe_merge_start_here(
        start_here_path=start_here_p,
        lineage_body=_render_project_start_here(
            project_slug=project_slug,
            topic=topic,
            summaries=summaries,
            arc_path=arc_path,
            deck_path=deck_path,
            date_str=date_str,
        ),
        project_slug=project_slug,
        topic=topic,
        arc_path=arc_path,
        date_str=date_str,
        n_total=n_total_for_view,
        n_tier_a=n_tier_a_for_view,
        n_tier_c=n_tier_c_for_view,
        deck_path=deck_path,
    )

    # 4. decisions-log.md — APPEND new entry (or seed file with header).
    # Bug 3 fix (evening 3, 2026-04-30): use the caller-supplied `pdfs_acquired`
    # (actual successful acquisition count from `LineageRunResult.pdfs_acquired`)
    # rather than conflating with the Tier-A bucket count. The two can diverge
    # — e.g. a paper can be Tier A from cache without a fresh acquisition.
    n_tier_a = sum(1 for s in summaries.values() if s.tier == "A")
    pdfs_acquired_for_log = pdfs_acquired if pdfs_acquired is not None else n_tier_a
    new_entry = _render_decisions_log_entry(
        topic=topic,
        speaker=speaker,
        seeds_n=len(corpus.seeds),
        sources_n=sources_n,
        corpus_size=len(summaries),
        tier_a_n=n_tier_a,
        pdfs_acquired=pdfs_acquired_for_log,
        picker_method=picker_method,
        crosstalk=crosstalk,
        run_id=run_id,
        output_slug=project_slug,
        deck_path=deck_path,
        timestamp=timestamp,
    )
    if decisions_p.exists():
        existing = decisions_p.read_text(encoding="utf-8")
        # Append a blank line + new entry. Header already in place.
        if not existing.endswith("\n"):
            existing += "\n"
        decisions_p.write_text(existing + "\n" + new_entry, encoding="utf-8")
    else:
        decisions_p.write_text(
            _decisions_log_header(project_slug=project_slug, topic=topic)
            + new_entry,
            encoding="utf-8",
        )

    return {
        "start_here": start_here_p,
        "papers": papers_p,
        "lineage": lineage_p,
        "decisions_log": decisions_p,
    }


# ---------------------------------------------------------------------------
# Tier-A picker
# ---------------------------------------------------------------------------


def _pick_top_n_for_summarization(
    corpus: Corpus,
    *,
    n: int,
    pdf_cache_dir: Path | None = None,
) -> list[str]:
    """Return up to ``n`` corpus DOIs to spend Tier-A token budget on.

    Ranks by ``has_pdf, og_score + forward_influence`` — papers WITH a
    cached PDF are prioritized over papers without (per L4-CODEX bug #2:
    spending Tier-A budget on papers we can't full-text-read is wasted).

    Within each tier (has_pdf vs not), rank by ``og_score +
    forward_influence`` so the most central papers come first.
    """
    metrics = corpus.metrics
    seed_dois = [d for d in (s.doi.lower() for s in corpus.seeds if s.doi)]
    if metrics is None:
        # No metrics; fall back to seeds in input order.
        return seed_dois[:n]

    # Detect which DOIs have cached PDFs (if pdf_cache_dir given).
    if pdf_cache_dir is not None:
        from vaultlab.research.acquisition import cache_path_for

        def _has_pdf(doi: str) -> bool:
            return cache_path_for(doi, pdf_cache_dir).exists()
    else:
        def _has_pdf(doi: str) -> bool:
            return False  # treat all equally

    def _score(doi: str) -> tuple[int, float]:
        # Primary: 1 if has_pdf, 0 otherwise (so PDFs sort first).
        # Secondary: og_score + forward_influence.
        return (
            1 if _has_pdf(doi) else 0,
            float(metrics.og_score.get(doi, 0.0)) + float(
                metrics.forward_influence.get(doi, 0)
            ),
        )

    ranked = sorted(corpus.papers.keys(), key=_score, reverse=True)
    return ranked[:n]


# ---------------------------------------------------------------------------
# Lineage-arc prompt (LLM input)
# ---------------------------------------------------------------------------


_ARC_SYSTEM_PROMPT = (
    "You are writing a lineage section for a researcher's knowledge base. "
    "Be faithful — only use the per-paper TL;DR / key findings provided in the "
    "user message. Do not invent facts. Cite each paper with a wikilink in the "
    "form [[<doi-slug>|Author Year]] using the slugs provided. "
    "Return ONLY a JSON object with three keys: 'history', 'development', 'sota'. "
    "Each value is a single paragraph (3-6 sentences). No markdown fencing."
)


def _bucket_summaries(
    summaries: dict[str, PaperSummary],
) -> dict[str, list[PaperSummary]]:
    """Group summaries by year_bucket (history / development / sota / unknown)."""
    out: dict[str, list[PaperSummary]] = {
        "history": [],
        "development": [],
        "sota": [],
        "unknown": [],
    }
    for s in summaries.values():
        out.setdefault(s.year_bucket, []).append(s)
    return out


def _author_year_label(s: PaperSummary) -> str:
    """Human-readable wikilink label: "Komor 2016 (CBE)" style.

    Delegates to :func:`vaultlab.kb.paths.author_year_label`. That helper
    handles every author-name format we've seen in the wild (NCBI's
    "Goltsev Y" / OpenAlex's "J. Kennedy-Darling" / CrossRef's
    "First Last" / Vancouver "Last, First"), so the same surname falls
    out of all of them. Pre-evening-5 (2026-04-30) this used a naive
    ``authors[0].split()[0]`` which produced ``J. 2020`` for OpenAlex
    backfills.
    """
    from vaultlab.kb.paths import author_year_label

    return author_year_label(s.authors, s.year)


def build_arc_prompt(
    *,
    topic: str,
    summaries: dict[str, PaperSummary],
    top_og: list[tuple[str, float]],
    top_co_citation: list[tuple[str, str, int]],
) -> str:
    """Build the user-message text for the lineage-arc LLM call.

    The prompt feeds Claude:
    * the topic
    * per-paper TL;DRs + first 2 key findings, bucketed by year
    * the top-OG list (so Claude can lean on the "always-cited" papers)
    * top co-citation pairs (so Claude can spot tightly coupled lineages)

    Each paper is identified by ``[[<doi-slug>|Author Year]]`` so the
    model has the exact wikilink target it must emit.
    """
    buckets = _bucket_summaries(summaries)

    def _render_bucket(name: str, items: list[PaperSummary]) -> str:
        if not items:
            return f"({name}: no papers in this bucket)\n"
        # Sort by year ascending for narrative flow.
        items = sorted(items, key=lambda s: (s.year or 0))
        lines = [f"### {name} bucket ({len(items)} papers)"]
        for s in items[:25]:  # cap to keep prompt manageable
            slug = slugify_doi(s.doi) if s.doi else "?"
            label = _author_year_label(s)
            tldr = (s.tldr or "_(no full-text available — Tier C stub)_").strip()
            findings_preview = "; ".join(
                (s.key_findings or [])[:2]
            ) or "_(no findings extracted)_"
            lines.append(
                f"- [[{slug}|{label}]] ({s.year}) — {tldr} "
                f"Findings: {findings_preview}"
            )
        return "\n".join(lines)

    history = _render_bucket("history", buckets.get("history", []))
    development = _render_bucket("development", buckets.get("development", []))
    sota = _render_bucket("sota", buckets.get("sota", []))

    og_lines = []
    for doi, score in top_og[:8]:
        s = summaries.get(doi)
        label = _author_year_label(s) if s else doi
        slug = slugify_doi(doi)
        og_lines.append(f"- [[{slug}|{label}]] — og_score={score:.2f}")
    og_block = "\n".join(og_lines) if og_lines else "(none)"

    cocite_lines = []
    for a, b, n in top_co_citation[:5]:
        sa = summaries.get(a)
        sb = summaries.get(b)
        la = _author_year_label(sa) if sa else a
        lb = _author_year_label(sb) if sb else b
        cocite_lines.append(
            f"- [[{slugify_doi(a)}|{la}]] + [[{slugify_doi(b)}|{lb}]] — "
            f"co-cited by {n} papers"
        )
    cocite_block = "\n".join(cocite_lines) if cocite_lines else "(none)"

    return f"""\
TOPIC: {topic}

You are writing the History / Development / State-of-the-art narrative
arc for this topic. The corpus has been bucketed by publication-year
quartile within the corpus itself. Use the bucketed summaries below.

CITATION RULES:
- Each paragraph must cite 3-5 papers via wikilinks of the form
  [[<doi-slug>|Author Year]]. Use the EXACT slugs and labels given below.
- Lean on the "Top OG papers" list when describing foundational work.
- Lean on "Top co-citation pairs" to spot pairs that often appear together.
- Never invent a citation that's not in the lists below.

PER-PAPER SUMMARIES (bucketed):

{history}

{development}

{sota}

TOP OG PAPERS (most-cited in our seed set):
{og_block}

TOP CO-CITATION PAIRS:
{cocite_block}

OUTPUT FORMAT:
Return ONLY a JSON object:

{{
  "history": "<3-6 sentence paragraph for the history bucket, with [[wikilinks]]>",
  "development": "<3-6 sentence paragraph for the development bucket, with [[wikilinks]]>",
  "sota": "<3-6 sentence paragraph for the state-of-the-art bucket, with [[wikilinks]]>"
}}

Now write the JSON.
"""


# ---------------------------------------------------------------------------
# Lineage-arc LLM call (with import-locality on anthropic)
# ---------------------------------------------------------------------------


def _call_anthropic_arc(
    *,
    prompt: str,
    api_key: str,
    model: str,
    max_tokens: int = 3000,
) -> dict[str, str]:
    """Invoke Claude for the lineage-narrative paragraphs.

    Returns ``{"history": str, "development": str, "sota": str}``.
    Raises on auth / parse errors; the caller decides whether to fall
    back to the "narration skipped" path.
    """
    import anthropic

    from vaultlab.research.summarize import _extract_json

    client = anthropic.Anthropic(api_key=api_key)
    response = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=_ARC_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )
    # Concat any text blocks.
    text_chunks = []
    for block in response.content:
        if getattr(block, "type", "") == "text":
            text_chunks.append(block.text)
    full = "\n".join(text_chunks).strip()
    parsed = _extract_json(full)
    return {
        "history": str(parsed.get("history", "")).strip(),
        "development": str(parsed.get("development", "")).strip(),
        "sota": str(parsed.get("sota", "")).strip(),
    }


# ---------------------------------------------------------------------------
# Claude-Code-callable arc preparation + render
# ---------------------------------------------------------------------------


def arc_response_schema() -> dict[str, Any]:
    """Return the JSON schema for the lineage-arc LLM response.

    Mirrors the format described in :data:`_ARC_SYSTEM_PROMPT` and
    :func:`build_arc_prompt`.
    """
    return {
        "type": "object",
        "required": ["history", "development", "sota"],
        "properties": {
            "history": {
                "type": "string",
                "description": (
                    "3-6 sentence paragraph for the history bucket, "
                    "with [[wikilinks]] using the provided slugs."
                ),
            },
            "development": {
                "type": "string",
                "description": "3-6 sentence paragraph for the development bucket.",
            },
            "sota": {
                "type": "string",
                "description": "3-6 sentence paragraph for the state-of-the-art bucket.",
            },
        },
    }


@dataclass(frozen=True)
class ArcTask:
    """A prepared lineage-arc task ready for a Claude Code session to execute.

    No LLM is called when this object is built. The slash command body
    inside Claude Code reads ``summaries`` (already on disk under
    ``Wiki/Summaries/<doi>.md``), generates the three narrative
    paragraphs in-session, and feeds the response back through
    :func:`render_arc_from_response`.

    Attributes:
        topic: The user-supplied topic (raw, not slugified).
        date_str: ISO-format date for the arc filename.
        summaries: Mapping of doi -> :class:`PaperSummary`.
        output_path: Canonical destination for the arc markdown
            (``Wiki/Concepts/<topic-slug>-lineage-<date>.md``).
        method_relpath: Relative path used in frontmatter for the
            method.md sidecar.
        prompt: The full user-message prompt Claude should respond to.
        system_prompt: The system message Claude should be given.
        response_schema: JSON schema describing the expected response
            shape.
        top_og: Top OG-score papers (for provenance / re-emission).
        top_co_citation: Top co-citation pairs.
    """

    topic: str
    date_str: str
    summaries: dict[str, PaperSummary]
    output_path: Path
    method_relpath: str
    prompt: str
    system_prompt: str
    response_schema: dict[str, Any]
    top_og: list[tuple[str, float]] = field(default_factory=list)
    top_co_citation: list[tuple[str, str, int]] = field(default_factory=list)


# Type alias for the Claude-Code-side arc narrator callback.
ArcNarrator = Callable[["ArcTask"], dict[str, str]]


def prepare_arc_task(
    *,
    topic: str,
    corpus: Corpus,
    summaries: dict[str, PaperSummary],
    kb_root: Path,
    date_str: str | None = None,
) -> ArcTask:
    """Prepare a lineage-arc task. Does NOT call any LLM.

    Returns the structured task with prompt + expected response schema.
    The Claude Code session reads the per-paper summaries, generates
    the three narrative paragraphs, and feeds them back through
    :func:`render_arc_from_response`.

    For plain-Python callers with an Anthropic API key, the
    :func:`run_lit_arc` orchestrator handles SDK calls automatically.

    Args:
        topic: The user-supplied topic (raw).
        corpus: Built :class:`Corpus` with ``compute_metrics`` already
            run.
        summaries: Mapping of doi -> :class:`PaperSummary`.
        kb_root: Vaultlab KB root.
        date_str: Optional ISO date; defaults to today.

    Returns:
        An :class:`ArcTask` ready for the Claude Code narrator.
    """
    if date_str is None:
        date_str = date.today().strftime("%Y-%m-%d")
    metrics = corpus.metrics
    top_og: list[tuple[str, float]] = (
        sorted(metrics.og_score.items(), key=lambda kv: kv[1], reverse=True)[:10]
        if metrics is not None
        else []
    )
    top_co: list[tuple[str, str, int]] = (
        list(metrics.co_citation_pairs[:10]) if metrics is not None else []
    )
    prompt = build_arc_prompt(
        topic=topic,
        summaries=summaries,
        top_og=top_og,
        top_co_citation=top_co,
    )
    output_path = ensure_parent(concept_path(Path(kb_root), topic, "lineage", date_str))
    method_relpath = output_path.name + ".method.md"
    return ArcTask(
        topic=topic,
        date_str=date_str,
        summaries=dict(summaries),
        output_path=output_path,
        method_relpath=method_relpath,
        prompt=prompt,
        system_prompt=_ARC_SYSTEM_PROMPT,
        response_schema=arc_response_schema(),
        top_og=top_og,
        top_co_citation=top_co,
    )


def render_arc_from_response(
    task: ArcTask,
    response_json: dict[str, Any],
    corpus: Corpus,
    *,
    write: bool = True,
) -> Path:
    """Render the arc markdown from Claude's response and write to ``Wiki/Concepts``.

    Args:
        task: The :class:`ArcTask` produced by :func:`prepare_arc_task`.
        response_json: Parsed JSON dict matching ``task.response_schema``.
            Pass an empty dict (or ``None``-valued keys) to emit the
            structured tables without prose.
        corpus: Same :class:`Corpus` used in the prepare step. Re-passed
            because tables are derived from the citation graph.
        write: If True, write the rendered markdown to ``task.output_path``.
            If False, the file is not written but the path is still
            returned for use by the caller.

    Returns:
        Path to ``task.output_path`` (whether or not it was written).
    """
    narrative: dict[str, str] | None = None
    if response_json:
        cleaned = {
            "history": str(response_json.get("history", "")).strip(),
            "development": str(response_json.get("development", "")).strip(),
            "sota": str(response_json.get("sota", "")).strip(),
        }
        if any(cleaned.values()):
            narrative = cleaned
    arc_md = render_arc_markdown(
        topic=task.topic,
        date_str=task.date_str,
        summaries=task.summaries,
        corpus=corpus,
        method_relpath=task.method_relpath,
        narrative=narrative,
        narrative_skipped_reason=(
            "" if narrative is not None else "no narrative provided"
        ),
    )
    if write:
        task.output_path.write_text(arc_md, encoding="utf-8")
    return task.output_path


# ---------------------------------------------------------------------------
# Lineage-arc renderer (markdown body)
# ---------------------------------------------------------------------------


def _bucket_year_range(
    summaries: dict[str, PaperSummary],
    bucket: str,
) -> tuple[int | None, int | None]:
    """Return (min_year, max_year) for ``bucket``. ``(None, None)`` when empty."""
    years = [s.year for s in summaries.values() if s.year_bucket == bucket and s.year]
    if not years:
        return None, None
    return min(years), max(years)


def _bucket_papers_table(
    summaries: dict[str, PaperSummary],
    bucket: str,
    max_rows: int = 25,
) -> str:
    rows = sorted(
        [s for s in summaries.values() if s.year_bucket == bucket],
        key=lambda s: (s.year or 0, s.doi),
    )
    if not rows:
        return "_(no papers in this bucket)_\n"
    lines = ["| Year | Paper | Tier | OG | Forward |", "|---|---|---|---|---|"]
    n_skipped_anon = 0
    for s in rows[:max_rows]:
        slug = slugify_doi(s.doi) if s.doi else "?"
        # Bug 5: when authors are completely missing AND year is unknown, the
        # wikilink would render as "[[<slug>|Anon n.d.]]" — uninformative and
        # noisy. Emit a plain DOI-only row with a footnote rather than a
        # named wikilink, and tally the count for the table footer.
        from vaultlab.research.corpus import has_anonymous_author
        if has_anonymous_author(s.authors) and not s.year:
            lines.append(
                f"| ? | _(metadata-only stub: {s.doi})_ | {s.tier} | "
                f"{s.og_score:.2f} | {s.forward_influence} |"
            )
            n_skipped_anon += 1
            continue
        label = _author_year_label(s)
        lines.append(
            f"| {s.year} | [[{slug}|{label}]] | {s.tier} | "
            f"{s.og_score:.2f} | {s.forward_influence} |"
        )
    if n_skipped_anon:
        lines.append(
            f"\n_(skipped {n_skipped_anon} wikilink(s) for "
            "metadata-only stubs without authors or year)_"
        )
    return "\n".join(lines) + "\n"


def render_arc_markdown(
    *,
    topic: str,
    date_str: str,
    summaries: dict[str, PaperSummary],
    corpus: Corpus,
    method_relpath: str,
    narrative: dict[str, str] | None,
    narrative_skipped_reason: str = "",
) -> str:
    """Render the lineage-arc markdown.

    When ``narrative`` is ``None`` we emit the structured tables only,
    plus a "narrative skipped" note that mentions ``narrative_skipped_reason``.
    """
    metrics = corpus.metrics
    n_papers = len(summaries)
    n_full_text = sum(1 for s in summaries.values() if s.tier == "A")

    # Bucket year ranges (used in section headers).
    h_min, h_max = _bucket_year_range(summaries, "history")
    d_min, d_max = _bucket_year_range(summaries, "development")
    s_min, s_max = _bucket_year_range(summaries, "sota")

    def _hdr(label: str, lo: int | None, hi: int | None) -> str:
        if lo is None or hi is None:
            return f"## {label} (no papers)"
        if lo == hi:
            return f"## {label} ({lo})"
        return f"## {label} ({lo}-{hi})"

    fm_lines = [
        "---",
        f"topic: {topic}",
        f"date: {date_str}",
        f"seeds: {len(corpus.seeds)}",
        f"corpus_size: {n_papers}",
        f"papers_with_full_text: {n_full_text}",
        "generated_by: vaultlab.research.lineage.run_lit_arc",
        f"provenance: {method_relpath}",
        # Bug 6: surface the og_score definition in the document itself so a
        # reviewer who lands on the arc without reading the methodology page
        # still understands what the score means.
        'og_score_methodology: "og_score: Kessler 1963 bibliographic '
        "coupling — fraction of seed papers that cite each candidate.\"",
        "---",
    ]

    body: list[str] = []
    body.append(f"# Lineage: {topic}")
    body.append("")
    body.append(
        f"Corpus: {n_papers} papers ({n_full_text} with full-text Tier-A summaries; "
        f"the rest are Tier-C stubs grounded in citation metrics). "
        f"Seeds: {len(corpus.seeds)}. Date: {date_str}."
    )
    body.append("")
    # Bug 6: one-line citation methodology in the first section so the reader
    # doesn't have to chase frontmatter or the docs/methodology.md page.
    body.append(
        "> **og_score:** Kessler 1963 bibliographic coupling — fraction of "
        "seed papers that cite each candidate. See "
        "`vaultlab/docs/methodology.md` for the full definition + "
        "edge cases."
    )
    body.append("")

    if narrative is None:
        body.append("> _LLM narration was skipped._")
        if narrative_skipped_reason:
            body.append(f"> Reason: {narrative_skipped_reason}")
        body.append(
            "> The structured tables below still show the bucketed corpus and "
            "rankings; rerun with ``ANTHROPIC_API_KEY`` set to add the prose."
        )
        body.append("")

    # ---- History section ----
    body.append(_hdr("History", h_min, h_max))
    body.append("")
    if narrative and narrative.get("history"):
        body.append(narrative["history"])
        body.append("")
    body.append(_bucket_papers_table(summaries, "history"))
    body.append("")

    # ---- Development section ----
    body.append(_hdr("Development", d_min, d_max))
    body.append("")
    if narrative and narrative.get("development"):
        body.append(narrative["development"])
        body.append("")
    body.append(_bucket_papers_table(summaries, "development"))
    body.append("")

    # ---- SOTA section ----
    body.append(_hdr("State of the art", s_min, s_max))
    body.append("")
    if narrative and narrative.get("sota"):
        body.append(narrative["sota"])
        body.append("")
    body.append(_bucket_papers_table(summaries, "sota"))
    body.append("")

    # ---- Top OG papers ----
    body.append("## Top OG papers (cross-corpus citation frequency)")
    body.append("")
    if metrics is not None and metrics.og_score:
        body.append("| OG-score | Paper | Year |")
        body.append("|---|---|---|")
        top_og = sorted(metrics.og_score.items(), key=lambda kv: kv[1], reverse=True)[
            :10
        ]
        for doi, score in top_og:
            s = summaries.get(doi)
            label = _author_year_label(s) if s else doi
            year = s.year if s else 0
            slug = slugify_doi(doi)
            body.append(f"| {score:.2f} | [[{slug}|{label}]] | {year} |")
        body.append("")
    else:
        body.append("_(no metrics available)_")
        body.append("")

    # ---- Top co-citation pairs ----
    body.append("## Top co-citation pairs")
    body.append("")
    if metrics is not None and metrics.co_citation_pairs:
        for i, (a, b, n) in enumerate(metrics.co_citation_pairs[:10], 1):
            sa = summaries.get(a)
            sb = summaries.get(b)
            la = _author_year_label(sa) if sa else a
            lb = _author_year_label(sb) if sb else b
            body.append(
                f"{i}. [[{slugify_doi(a)}|{la}]] + [[{slugify_doi(b)}|{lb}]] "
                f"— co-cited by {n} papers"
            )
        body.append("")
    else:
        body.append("_(no co-citation pairs above threshold)_")
        body.append("")

    return "\n".join(fm_lines) + "\n\n" + "\n".join(body).rstrip() + "\n"


# ---------------------------------------------------------------------------
# Public orchestrator
# ---------------------------------------------------------------------------


_ProgressFn = Callable[..., None]


def _emit(progress: _ProgressFn | None, *args: Any, **kwargs: Any) -> None:
    if progress is None:
        return
    try:
        progress(*args, **kwargs)
    except Exception:  # pragma: no cover — never break a run on a callback
        logger.debug("progress callback raised", exc_info=True)


def run_lit_arc(
    topic: str,
    *,
    kb_root: Path | None = None,
    depth: DepthLevel = "balanced",
    max_seeds: int = 15,
    max_papers_to_summarize: int | None = None,
    pdf_cache_dir: Path | None = None,
    apis: dict[str, str] | None = None,
    progress: _ProgressFn | None = None,
    reader: SummaryReader | None = None,
    narrator: ArcNarrator | None = None,
    picker_callback: PickerCallback | None = None,
    binner_callback: BinningCallback | None = None,
    binner_max_candidates: int = 200,
    picker_coarse_n: int | None = None,
    picker_mode: str = "fast",
    arc_mode: str = "fast",
    crosstalk_runner: Any | None = None,
    crosstalk_n_rounds: int = 3,
    project: str | None = None,
    project_slug: str | None = None,
    run_dir: Path | None = None,
    deck_path: Path | None = None,
    speaker: str = "Bobby",
    acquire_figures: bool = False,
    figure_cache_dir: Path | None = None,
    # Test injection points (default to real implementations):
    _client: Any | None = None,
    _llm_summary: Callable[..., tuple[dict[str, Any], int, int]] | None = None,
    _llm_arc: Callable[..., dict[str, str]] | None = None,
    _fetch_refs: Any | None = None,
    _acquire: Any | None = None,
    _acquire_figures: Any | None = None,
    _summarize_corpus_fn: Any | None = None,
    _today: str | None = None,
    _now: str | None = None,
) -> LineageRunResult:
    """Run the full ``/lit-arc`` pipeline end-to-end.

    See module docstring for the canonical paths each phase writes.

    Two execution modes:

    * **SDK mode (default)** — phases 6 and 7 call the Anthropic API
      via an API key for per-paper summaries and the lineage-arc
      narration.
    * **Claude-Code mode** (``reader`` and/or ``narrator`` given) —
      phases 6 / 7 delegate to the supplied callbacks. The slash command
      body inside Claude Code provides callbacks that read PDFs / write
      paragraphs using the active Claude session, so no Anthropic API
      key is required.

    The two modes can be mixed (e.g. SDK summaries + Claude-Code
    narrator) by passing only one of the callbacks.

    **Content-aware Tier-A picker.** Pass ``picker_callback`` to swap the
    mechanical citation-graph picker for a content-aware one that reads
    candidate abstracts before deciding (see
    :mod:`vaultlab.research.picker`). When ``picker_callback`` is
    ``None``, the previous citation-graph behaviour is preserved. The
    coarse-pool size is controlled by ``picker_coarse_n``: the default
    ``None`` means no cap — the picker reads every corpus paper's abstract.
    Pass an int to restore the legacy capped-pool behaviour.

    The ``project`` and ``run_dir`` arguments steer the picker's
    audit-trail output: when ``project`` is given AND
    ``Wiki/Projects/<project>/decisions-log.md`` already exists, the
    pick rationales are appended there. Otherwise, when ``run_dir`` is
    given, the rationales are written to ``<run_dir>/picker-decision.md``
    instead. Both can be ``None`` (rationales then live only in logs).

    **Phase 9: project view.** Every run also writes the project view layer
    at ``Wiki/Projects/<project_slug>/`` (``START_HERE.md``, ``papers.md``,
    ``lineage.md``, append to ``decisions-log.md``). When ``project_slug``
    is ``None``, it defaults to ``slugify_topic(topic)``. Pass an explicit
    short slug (e.g. ``project_slug="codex-cn-test"``) when the project's
    canonical folder name should diverge from the topic.

    **Depth control (Task #63, 2026-04-30).** ``depth`` is the user-facing
    knob for "how aggressively should the LLM read this corpus". When
    ``max_papers_to_summarize`` is left at its default (``None``), the
    Tier-A budget is derived from ``depth`` AFTER PDF acquisition finishes,
    using :func:`_derive_max_papers` (so the ceiling is the actual count of
    cached PDFs):

    * ``"fast"`` — cap at 20 Tier-A papers (~15 min). Quick scoping.
    * ``"balanced"`` — cap at 50 Tier-A papers (~30 min). Default.
    * ``"thorough"`` — read every cached PDF (~60 min).
    * ``"complete"`` — read every cached PDF AND retry paywalled
      acquisition once more before computing the budget (~90 min).
      Forwards ``aggressive_retry=True`` and ``skip_paywalled=False`` to
      :func:`acquire_pdfs_for_corpus`.

    Pass ``max_papers_to_summarize=N`` (an explicit int) to override the
    depth-derived budget — the explicit value always wins.

    **Figure acquisition (Fix 1, 2026-04-30 evening-4).** Pass
    ``acquire_figures=True`` to fetch native-resolution figures + captions
    for the corpus between Phase 5 (PDF acquisition) and Phase 6
    (summarization) via the API waterfall in
    :mod:`vaultlab.figures.acquisition` (PMC OA tar → Elsevier
    ScienceDirect XML → Springer OA JSON). The resulting ``figure_assignments``
    map travels on the LineageRunResult so
    :func:`vaultlab.slides.deck.build_deck_from_lineage_result` can
    populate figure-slides directly. Cache directory defaults to
    ``<kb_root>/Sources/Figures/`` and may be overridden via
    ``figure_cache_dir``.

    **Same-day rerun collision detection (Fix 3, 2026-04-30 evening-4).**
    When ``Wiki/Concepts/<topic>-lineage-<date>.md`` already exists from
    an earlier run on the same date AND its content differs from the
    new arc text, the orchestrator picks
    ``<topic>-lineage-<date>-rerun-1.md`` (then ``-rerun-2.md`` etc.) and
    keeps the suffix consistent across the arc + ``.method.md`` +
    ``.provenance.json`` triplet. Idempotent re-runs (identical text)
    are detected and the path is left unchanged.

    Test injection points (``_client``, ``_llm_summary``, ``_llm_arc``,
    ``_acquire_figures``, etc.) take precedence over both modes; callers
    in production should leave them at their defaults. ``_now`` overrides
    the timestamp used in the decisions-log entry (test only).
    """
    # Validate depth eagerly so callers get a clean error.
    if depth not in ("fast", "balanced", "thorough", "complete"):
        raise ValueError(
            f"unknown depth: {depth!r} (expected one of "
            f"'fast', 'balanced', 'thorough', 'complete')"
        )

    # G-2 fix (option b): if project_slug wasn't threaded explicitly, walk
    # up from cwd looking for ``.vaultlab-project.json`` and adopt its
    # slug. Aligns with the "state-aware, additive, read-before-write"
    # memory rule — explicit kwarg still wins, but a forgetful slash-
    # command body no longer creates a parallel ``Wiki/Projects/<slug>/``.
    if project_slug is None:
        try:
            from vaultlab.onboarding import load_project_config_from_cwd
            _cfg = load_project_config_from_cwd()
        except Exception:  # pragma: no cover — never break a run
            logger.exception("load_project_config_from_cwd failed")
            _cfg = None
        if _cfg is not None and getattr(_cfg, "slug", ""):
            project_slug = _cfg.slug
            logger.info(
                "auto-discovered project_slug=%s from "
                ".vaultlab-project.json (cwd=%s)",
                project_slug,
                Path.cwd(),
            )

    started = time.time()
    date_str = _today or date.today().strftime("%Y-%m-%d")
    # Multi-tenant KB-root resolution (Layer A, 2026-04-30):
    # callers no longer have to pre-resolve kb_root. When omitted, walk the
    # env-var → vaultlab config → bobby_kb compat → first-run prompt chain.
    if kb_root is None:
        from vaultlab.context.locations import resolve_kb_root

        kb_root = resolve_kb_root()
    kb_root = Path(kb_root)

    # Resolve PDF cache dir default.
    if pdf_cache_dir is None:
        pdf_cache_dir = kb_root / "Sources" / "Papers"
    pdf_cache_dir = Path(pdf_cache_dir)
    pdf_cache_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Phase 1: search
    # ------------------------------------------------------------------
    _emit(progress, "phase", "search", topic=topic, max_seeds=max_seeds)
    if _client is None:
        from vaultlab.research import ResearchClient

        client = ResearchClient()
    else:
        client = _client
    # Prefer ``search_with_trace`` so we can emit a per-source trace
    # sidecar; fall back to the plain ``search`` path for fakes/legacy
    # injection points that don't expose the trace API.
    search_trace = None
    if hasattr(client, "search_with_trace"):
        try:
            raw_seeds, search_trace = client.search_with_trace(
                topic, max_results=max_seeds
            )
        except Exception:  # pragma: no cover — defensive
            logger.exception(
                "search_with_trace failed; falling back to plain client.search"
            )
            raw_seeds = client.search(topic, max_results=max_seeds)
    else:
        raw_seeds = client.search(topic, max_results=max_seeds)
    # Drop seeds without DOIs — we can't put them in the citation graph.
    seeds = [s for s in raw_seeds if s.doi][:max_seeds]
    _emit(progress, "seeds", n=len(seeds))

    # ------------------------------------------------------------------
    # Phase 2: search log
    # ------------------------------------------------------------------
    log_path = _write_search_log(
        kb_root=kb_root, topic=topic, seeds=seeds, date_str=date_str
    )
    _emit(progress, "search_log", path=str(log_path))
    # Side-by-side per-source trace (Gap 1 — observability). Failure here
    # is logged-and-ignored: the markdown log + decisions log already
    # carry enough to land the run, the trace is purely diagnostic.
    if search_trace is not None:
        trace_path = _write_search_trace(
            kb_root=kb_root,
            topic=topic,
            date_str=date_str,
            trace=search_trace,
        )
        if trace_path is not None:
            _emit(progress, "search_trace", path=str(trace_path))

    # ------------------------------------------------------------------
    # Phase 3: article stubs (one per seed with DOI)
    # ------------------------------------------------------------------
    article_stubs: list[Path] = []
    for seed in seeds:
        p = _write_article_stub(kb_root, seed)
        if p is not None:
            article_stubs.append(p)
    _emit(progress, "article_stubs", n=len(article_stubs))

    # ------------------------------------------------------------------
    # Phase 4: corpus + metrics
    # ------------------------------------------------------------------
    _emit(progress, "phase", "corpus", n_seeds=len(seeds))
    corpus = build_corpus_from_seeds(
        seeds,
        topic=topic,
        fetch_refs=_fetch_refs,
    )
    compute_metrics(corpus)
    _emit(
        progress,
        "corpus",
        n_papers=corpus.n_papers,
        n_edges=corpus.n_edges,
    )

    # ------------------------------------------------------------------
    # Phase 4b: LLM-driven year-bucket assignment (recommended)
    # ------------------------------------------------------------------
    # Replace the deterministic year-quartile buckets with LLM-driven
    # conceptual bucketing when a binner_callback is supplied. The LLM
    # reads each paper's abstract and decides history/development/sota
    # FOR THIS TOPIC — fixing the empty-history-bin failure mode that
    # year quartiles produced on recent corpora (Bobby's L4 CODEX
    # 2026-04-30 complaint). Without a callback, year quartiles stand.
    if binner_callback is not None and corpus.metrics is not None:
        _emit(progress, "phase", "binning", n_papers=corpus.n_papers)
        binning_result = assign_buckets_with_llm(
            corpus,
            topic,
            binner_callback=binner_callback,
            max_candidates=binner_max_candidates,
            fallback_to_deterministic=True,
        )
        # OVERRIDE corpus.metrics.year_buckets in place so all downstream
        # consumers (summarize_corpus, prepare_arc_task, slides, etc.)
        # see the LLM's conceptual buckets.
        corpus.metrics.year_buckets.update(binning_result.bucket_by_doi)
        _emit(
            progress,
            "binning",
            history=binning_result.coverage_summary.get("history", 0),
            development=binning_result.coverage_summary.get("development", 0),
            sota=binning_result.coverage_summary.get("sota", 0),
        )

    # ------------------------------------------------------------------
    # Phase 5: PDF acquisition (waterfall)
    # ------------------------------------------------------------------
    _emit(progress, "phase", "acquire_pdfs", n_papers=corpus.n_papers)
    acq = _acquire if _acquire is not None else acquire_pdfs_for_corpus
    # Depth=complete: try paywalled tiers AND retry hard before deciding
    # the Tier-A budget. Other depths stick with the OA-only fast path.
    skip_paywalled_arg = depth != "complete"
    aggressive_retry_arg = depth == "complete"
    try:
        acq_results = acq(
            corpus,
            pdf_cache_dir,
            apis=apis,
            skip_paywalled=skip_paywalled_arg,
            aggressive_retry=aggressive_retry_arg,
        )
    except TypeError:
        # The injected fake may not accept all kwargs — fall back through a
        # cascade so we tolerate older injection points (tests) and still
        # honor depth in real runs.
        try:
            acq_results = acq(
                corpus,
                pdf_cache_dir,
                apis=apis,
                skip_paywalled=skip_paywalled_arg,
            )
        except TypeError:
            acq_results = acq(corpus, pdf_cache_dir)
    pdfs_acquired = sum(
        1 for r in acq_results.values() if getattr(r, "pdf_path", None) is not None
    )
    _emit(progress, "pdfs_acquired", n=pdfs_acquired)
    # Per-DOI trace sidecar (Gap 2). Lives next to the run if available
    # so the decisions log can answer "which sources did we try for
    # 10.x/y, which one won, and why did the others fail".
    trace_path_pdf = _write_pdf_acquisition_trace(
        acq_results=acq_results,
        run_dir=run_dir,
        kb_root=kb_root,
        topic=topic,
        date_str=date_str,
    )
    if trace_path_pdf is not None:
        _emit(progress, "pdf_acquisition_trace", path=str(trace_path_pdf))

    # ------------------------------------------------------------------
    # Phase 5b: figure acquisition (opt-in)
    # ------------------------------------------------------------------
    # When ``acquire_figures=True`` is passed, fetch native-resolution
    # figures + captions for every paper in the corpus via the API
    # waterfall in :mod:`vaultlab.figures.acquisition` (PMC OA tar →
    # Elsevier ScienceDirect XML → Springer OA JSON). The resulting
    # ``figure_assignments`` map (one figure path per DOI) is carried
    # on the LineageRunResult so ``build_deck_from_lineage_result`` can
    # populate figure-slides without a second acquisition pass.
    figure_assignments: dict[str, Path] = {}
    figures_acquired = 0
    if acquire_figures:
        _emit(
            progress,
            "phase",
            "acquire_figures",
            n_papers=corpus.n_papers,
        )
        if figure_cache_dir is None:
            figure_cache_dir_resolved = kb_root / "Sources" / "Figures"
        else:
            figure_cache_dir_resolved = Path(figure_cache_dir)
        figure_cache_dir_resolved.mkdir(parents=True, exist_ok=True)
        if _acquire_figures is not None:
            acq_fig = _acquire_figures
        else:
            from vaultlab.figures.acquisition import acquire_figures_for_corpus
            acq_fig = acquire_figures_for_corpus
        try:
            fig_results = acq_fig(
                corpus,
                figure_cache_dir_resolved,
                apis=apis,
            )
        except TypeError:
            # Tolerate stubs that don't accept ``apis=`` kwarg.
            try:
                fig_results = acq_fig(corpus, figure_cache_dir_resolved)
            except Exception as exc:  # pragma: no cover — never break run
                logger.exception("acquire_figures_for_corpus raised: %s", exc)
                fig_results = {}
        except Exception as exc:  # pragma: no cover — never break run
            logger.exception("acquire_figures_for_corpus raised: %s", exc)
            fig_results = {}
        for doi, res in (fig_results or {}).items():
            figs = getattr(res, "figures", None) or []
            if not figs:
                continue
            # Pick the largest figure on disk as the default assignment so
            # the bucket picker has the best representative on hand. The
            # deck-side picker can override per-bucket if multiple figures
            # are needed (Fix 2).
            best_path: Path | None = None
            best_size = -1
            for f in figs:
                fpath = Path(getattr(f, "file_path", "") or "")
                if not fpath or not fpath.exists():
                    continue
                try:
                    size = fpath.stat().st_size
                except OSError:
                    size = 0
                if size > best_size:
                    best_size = size
                    best_path = fpath
            if best_path is not None:
                figure_assignments[doi] = best_path
        figures_acquired = len(figure_assignments)
        _emit(
            progress,
            "figures_acquired",
            n_papers=figures_acquired,
            cache_dir=str(figure_cache_dir_resolved),
        )

    # ------------------------------------------------------------------
    # Resolve the Tier-A budget: explicit override > depth-derived.
    # We do this AFTER acquisition so depth=thorough/complete can use the
    # actual cached-PDF count as the ceiling (we only spend Tier-A budget
    # on papers we can full-text read — L4-CODEX bug #2 lesson).
    # ------------------------------------------------------------------
    if max_papers_to_summarize is None:
        resolved_max_papers = _derive_max_papers(
            depth, n_pdfs_cached=pdfs_acquired, corpus_size=corpus.n_papers
        )
        _emit(
            progress,
            "depth_budget",
            depth=depth,
            n_pdfs_cached=pdfs_acquired,
            budget=resolved_max_papers,
        )
    else:
        resolved_max_papers = int(max_papers_to_summarize)

    # Corpus-size warning for read-everything depths on big corpora.
    if (
        max_papers_to_summarize is None
        and depth in ("thorough", "complete")
        and corpus.n_papers > _LARGE_CORPUS_WARNING_THRESHOLD
    ):
        # Rough wall-time guess: 60-90 min for ~150 PDFs read.
        wall_estimate = "60-90 minutes" if depth == "thorough" else "90-120 minutes"
        logger.warning(
            "[lit-arc] depth=%s on a %d-paper corpus. "
            "Estimated runtime: ~%s. ~%d PDFs will be read.",
            depth,
            corpus.n_papers,
            wall_estimate,
            pdfs_acquired,
        )
        _emit(
            progress,
            "large_corpus_warning",
            depth=depth,
            corpus_size=corpus.n_papers,
            n_pdfs_cached=pdfs_acquired,
        )

    # ------------------------------------------------------------------
    # Phase 6: summaries (Tier A vs C, top-N gets prioritised by ranking)
    # ------------------------------------------------------------------
    _emit(progress, "phase", "summarize", n_papers=corpus.n_papers)
    # We don't actually slice the corpus — summarize_corpus writes one
    # entry per paper and Tier-A vs Tier-C is decided by whether a PDF
    # is in the cache. The ``max_papers_to_summarize`` knob lets callers
    # decide how many of the top-ranked papers to keep PDFs for; we
    # delete cached PDFs for everything below the cutoff so those papers
    # become Tier-C without an LLM call.
    # L4-CODEX bug #1+#2 fix: explicitly track tier_a_dois (which papers
    # we WANT the reader to summarize) and pass to summarize_corpus.
    # Picker now also biases toward papers WITH cached PDFs.
    tier_a_dois: set[str] | None = None
    picker_method: str = "citation-graph"
    crosstalk_picker_result = None
    if resolved_max_papers and resolved_max_papers < corpus.n_papers:
        # Adversarial crosstalk path — only when explicitly enabled AND a
        # crosstalk_runner is available. Falls through to single-shot
        # picker_callback / mechanical pick on any failure.
        if (
            picker_mode == "adversarial"
            and crosstalk_runner is not None
        ):
            from vaultlab.research.picker import _build_candidates  # type: ignore[attr-defined]
            from vaultlab.workflows.crosstalk import (
                adversarial_picker_meeting,
                write_crosstalk_artifacts,
            )

            candidates = _build_candidates(
                corpus,
                coarse_n=picker_coarse_n,
                kb_root=Path(kb_root),
                pdf_cache_dir=pdf_cache_dir,
            )
            abstracts_md = "\n\n".join(
                f"[{i + 1}] {c.doi} — {c.title or '(untitled)'}\n"
                f"  Abstract: {c.abstract[:600]}"
                for i, c in enumerate(candidates)
            ) or "(no candidates)"
            ct_result = adversarial_picker_meeting(
                topic=topic,
                candidates=candidates,
                target_n=resolved_max_papers,
                abstracts_md=abstracts_md,
                n_rounds=crosstalk_n_rounds,
                runner_callback=crosstalk_runner,
            )
            crosstalk_picker_result = ct_result
            if run_dir is not None:
                try:
                    write_crosstalk_artifacts(ct_result, run_dir=Path(run_dir))
                except Exception:
                    logger.exception("write_crosstalk_artifacts (picker) failed")
            picks = (ct_result.final_output or {}).get("picks") or []
            valid_dois = {c.doi for c in candidates}
            keep_list = []
            for item in picks:
                if not isinstance(item, dict):
                    continue
                d = (item.get("doi") or "").strip().lower()
                if d in valid_dois and d not in keep_list:
                    keep_list.append(d)
                if len(keep_list) >= resolved_max_papers:
                    break
            if keep_list:
                picker_method = "adversarial"
            else:
                # Fallback to mechanical pick if synthesizer produced nothing.
                logger.warning(
                    "adversarial picker meeting returned no usable picks; "
                    "falling back to citation graph"
                )
                keep_list = _pick_top_n_for_summarization(
                    corpus,
                    n=resolved_max_papers,
                    pdf_cache_dir=pdf_cache_dir,
                )
                picker_method = (
                    "citation-graph (adversarial picker fallback)"
                )
                # Bug #5: when adversarial synth output is unusable and we
                # fall through to the mechanical picker, the audit trail
                # would otherwise be empty. Write a decision-log entry with
                # the mechanical picks + a synthetic rationale so the run
                # is still traceable.
                try:
                    from vaultlab.research.picker import PickerTask
                    fallback_task = PickerTask(
                        topic=topic,
                        candidates=candidates,
                        target_n=resolved_max_papers,
                        prompt="(adversarial picker fallback)",
                        system_prompt="(adversarial picker fallback)",
                        response_schema={},
                    )
                    fallback_rationales = {
                        d: "adversarial picker fallback after empty/invalid synthesizer output"
                        for d in keep_list
                    }
                    write_picker_decision(
                        kb_root=Path(kb_root),
                        project=project,
                        topic=topic,
                        task=fallback_task,
                        picks=keep_list,
                        rationales=fallback_rationales,
                        method=picker_method,
                        fallback_dir=run_dir,
                    )
                except Exception:  # pragma: no cover — never break the run
                    logger.exception(
                        "write_picker_decision (adversarial fallback) failed"
                    )
        elif picker_callback is not None:
            keep_list = pick_top_n_content_aware(
                topic,
                corpus,
                target_n=resolved_max_papers,
                coarse_n=picker_coarse_n,
                kb_root=kb_root,
                pdf_cache_dir=pdf_cache_dir,
                picker_callback=picker_callback,
                fallback_to_citation_graph=True,
                project=project,
                fallback_dir=run_dir,
            )
            picker_method = "content-aware"
        else:
            keep_list = _pick_top_n_for_summarization(
                corpus,
                n=resolved_max_papers,
                pdf_cache_dir=pdf_cache_dir,
            )
        keep = set(keep_list)
        tier_a_dois = keep
        _emit(
            progress,
            "summarize_budget",
            kept=len(keep),
            total=corpus.n_papers,
            method=picker_method,
        )

    summarize_fn = _summarize_corpus_fn if _summarize_corpus_fn is not None else summarize_corpus
    if reader is not None:
        # Claude-Code mode: reader replaces the SDK call. Pass it through
        # to summarize_corpus, which routes Tier A papers through the
        # reader and Tier C papers through the no-LLM stub.
        summaries = summarize_fn(
            corpus,
            pdf_cache_dir=pdf_cache_dir,
            kb_root=kb_root,
            parallel=1,  # reader mode is sequential
            overwrite=True,
            reader=reader,
            tier_a_dois=tier_a_dois,
        )
    else:
        summaries = summarize_fn(
            corpus,
            pdf_cache_dir=pdf_cache_dir,
            kb_root=kb_root,
            parallel=2,
            overwrite=True,
            _llm=_llm_summary,
        )

    # Compute the per-doi summary path map.
    summary_paths: dict[str, Path] = {
        doi: summary_path(kb_root, doi)
        for doi in summaries
    }
    summaries_written = sum(1 for p in summary_paths.values() if p.exists())
    _emit(
        progress,
        "summaries",
        total=len(summaries),
        written=summaries_written,
    )

    # ------------------------------------------------------------------
    # Phase 7: lineage arc (LLM narration optional)
    # ------------------------------------------------------------------
    _emit(progress, "phase", "arc")
    arc_path = ensure_parent(concept_path(kb_root, topic, "lineage", date_str))

    metrics = corpus.metrics
    top_og = (
        sorted(metrics.og_score.items(), key=lambda kv: kv[1], reverse=True)[:10]
        if metrics is not None
        else []
    )
    top_co = metrics.co_citation_pairs[:10] if metrics is not None else []

    narrative: dict[str, str] | None = None
    skipped_reason = ""
    crosstalk_arc_result = None
    if (
        arc_mode == "adversarial"
        and crosstalk_runner is not None
        and _llm_arc is None
    ):
        # Adversarial crosstalk path for arc generation.
        from vaultlab.workflows.crosstalk import (
            adversarial_arc_meeting,
            write_crosstalk_artifacts,
        )

        ct_arc = adversarial_arc_meeting(
            topic=topic,
            summaries=summaries,
            metrics=metrics,
            n_rounds=crosstalk_n_rounds,
            runner_callback=crosstalk_runner,
        )
        crosstalk_arc_result = ct_arc
        if run_dir is not None:
            try:
                write_crosstalk_artifacts(ct_arc, run_dir=Path(run_dir))
            except Exception:
                logger.exception("write_crosstalk_artifacts (arc) failed")
        cleaned = {
            "history": str(ct_arc.final_output.get("history", "")).strip(),
            "development": str(
                ct_arc.final_output.get("development", "")
            ).strip(),
            "sota": str(ct_arc.final_output.get("sota", "")).strip(),
        }
        if any(cleaned.values()):
            narrative = cleaned
        else:
            skipped_reason = (
                "adversarial arc meeting returned no narrative paragraphs"
            )
            narrative = None

    if narrative is not None:
        # Adversarial path already produced narrative — skip remaining paths.
        pass
    elif _llm_arc is not None:
        # Test injection: never hit the real API.
        prompt = build_arc_prompt(
            topic=topic,
            summaries=summaries,
            top_og=top_og,
            top_co_citation=top_co,
        )
        try:
            narrative = _llm_arc(prompt=prompt, api_key="test", model=DEFAULT_MODEL)
        except Exception as exc:
            skipped_reason = f"injected LLM raised: {exc}"
            narrative = None
    elif narrator is not None:
        # Claude-Code mode: hand the structured task to the slash-command
        # narrator, which produces the JSON in-session (no API key).
        arc_task = prepare_arc_task(
            topic=topic,
            corpus=corpus,
            summaries=summaries,
            kb_root=kb_root,
            date_str=date_str,
        )
        try:
            response = narrator(arc_task) or {}
            cleaned = {
                "history": str(response.get("history", "")).strip(),
                "development": str(response.get("development", "")).strip(),
                "sota": str(response.get("sota", "")).strip(),
            }
            narrative = cleaned if any(cleaned.values()) else None
            if narrative is None:
                skipped_reason = "narrator returned no narrative paragraphs"
        except Exception as exc:
            skipped_reason = f"narrator raised: {exc}"
            narrative = None
    else:
        try:
            api_key = load_anthropic_api_key(None)
        except SummarizeAuthError as exc:
            skipped_reason = str(exc).splitlines()[0]
            api_key = None

        if api_key:
            prompt = build_arc_prompt(
                topic=topic,
                summaries=summaries,
                top_og=top_og,
                top_co_citation=top_co,
            )
            try:
                narrative = _call_anthropic_arc(
                    prompt=prompt, api_key=api_key, model=DEFAULT_MODEL
                )
            except Exception as exc:
                skipped_reason = f"anthropic call raised: {exc}"
                narrative = None

    # Render the arc text first (without method_relpath) so we can detect
    # whether this is an idempotent rerun (same text, same date) vs a
    # genuine new run that would otherwise clobber the prior arc.
    # Fix 3 (2026-04-30 evening-4): same-day re-runs previously
    # overwrote ``Wiki/Concepts/<topic>-lineage-<date>.md`` along with
    # its method.md + provenance.json sidecars. We now walk the rerun-N
    # suffix on collision so prior runs survive.
    provisional_method_relpath = arc_path.name + ".method.md"
    arc_md_provisional = render_arc_markdown(
        topic=topic,
        date_str=date_str,
        summaries=summaries,
        corpus=corpus,
        method_relpath=provisional_method_relpath,
        narrative=narrative,
        narrative_skipped_reason=skipped_reason,
    )
    resolved_arc_path = _resolve_arc_path_with_collision(
        arc_path, expected_content=arc_md_provisional
    )
    if resolved_arc_path != arc_path:
        # Collision: re-render with the corrected method.md relpath so
        # the arc's frontmatter "provenance:" key matches the suffixed
        # sidecar that will actually be written.
        method_relpath = resolved_arc_path.name + ".method.md"
        arc_md = render_arc_markdown(
            topic=topic,
            date_str=date_str,
            summaries=summaries,
            corpus=corpus,
            method_relpath=method_relpath,
            narrative=narrative,
            narrative_skipped_reason=skipped_reason,
        )
        arc_path = resolved_arc_path
    else:
        method_relpath = provisional_method_relpath
        arc_md = arc_md_provisional
    arc_path.write_text(arc_md, encoding="utf-8")
    _emit(progress, "arc_written", path=str(arc_path))

    # ------------------------------------------------------------------
    # Phase 8: provenance receipts
    # ------------------------------------------------------------------
    record = ProvenanceRecord(
        generated_by="vaultlab.research.lineage.run_lit_arc",
        project="lit-arc",
        topic=topic,
        kind="lineage_arc",
        inputs=[str(p) for p in summary_paths.values()],
        params={
            "max_seeds": max_seeds,
            "depth": depth,
            "max_papers_to_summarize": resolved_max_papers,
            "max_papers_to_summarize_explicit": max_papers_to_summarize,
            "pdf_cache_dir": str(pdf_cache_dir),
            "narration": "claude" if narrative is not None else "skipped",
        },
        model=DEFAULT_MODEL if narrative is not None else "",
        related_outputs=[str(log_path), *[str(p) for p in article_stubs]],
        notes=skipped_reason or "",
    )
    write_receipts(arc_path, record)
    _emit(progress, "provenance_written")

    # ------------------------------------------------------------------
    # Phase 9: project view (Wiki/Projects/<slug>/)
    # ------------------------------------------------------------------
    # Resolve the slug: explicit override beats topic-derived default.
    resolved_slug = (
        project_slug.strip() if project_slug and project_slug.strip()
        else slugify_topic(topic)
    )
    # Resolve a run_id suitable for the decisions-log entry: prefer the
    # caller-supplied run_dir.name, fall back to None (entry says so).
    run_id_for_log: str | None = None
    if run_dir is not None:
        try:
            run_id_for_log = Path(run_dir).name or None
        except Exception:
            run_id_for_log = None

    # Decide the multi-agent crosstalk descriptor for the decisions log.
    crosstalk_parts: list[str] = []
    if picker_mode == "adversarial" and crosstalk_picker_result is not None:
        crosstalk_parts.append(
            f"picker:adversarial({crosstalk_picker_result.crosstalk_status})"
        )
    elif picker_callback is not None:
        crosstalk_parts.append("picker")
    if arc_mode == "adversarial" and crosstalk_arc_result is not None:
        crosstalk_parts.append(
            f"arc:adversarial({crosstalk_arc_result.crosstalk_status})"
        )
    elif narrator is not None or _llm_arc is not None:
        crosstalk_parts.append("arc")
    crosstalk = "+".join(crosstalk_parts) if crosstalk_parts else "none"

    project_view_paths = _write_project_view(
        kb_root=kb_root,
        project_slug=resolved_slug,
        topic=topic,
        arc_path=arc_path,
        summaries=summaries,
        corpus=corpus,
        deck_path=deck_path,
        run_id=run_id_for_log,
        date_str=date_str,
        speaker=speaker,
        sources_n=len(seeds),  # rough proxy: distinct seed count
        picker_method=picker_method,
        crosstalk=crosstalk,
        timestamp=_now,
        pdfs_acquired=pdfs_acquired,
    )
    _emit(
        progress,
        "project_view_written",
        slug=resolved_slug,
        files=len(project_view_paths),
    )

    duration = time.time() - started
    return LineageRunResult(
        topic=topic,
        arc_path=arc_path,
        summary_paths=summary_paths,
        search_log_path=log_path,
        corpus_size=corpus.n_papers,
        pdfs_acquired=pdfs_acquired,
        summaries_written=summaries_written,
        duration_seconds=duration,
        project_slug=resolved_slug,
        project_view_paths=project_view_paths,
        # F-13: carry the live corpus so the deck builder can read
        # ``corpus.metrics.co_citation_pairs`` etc. without rebuilding a
        # synthetic stand-in from on-disk frontmatters.
        corpus=corpus,
        # Fix 1 (2026-04-30 evening-4): figure acquisition is now an
        # optional phase wired into run_lit_arc — when enabled, the
        # resulting DOI -> figure_path map travels with the result so
        # the deck builder can plumb it directly without a second pass.
        figure_assignments=figure_assignments,
        figures_acquired=figures_acquired,
    )
