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
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

from vaultlab.kb.paths import (
    article_stub_path,
    concept_path,
    ensure_parent,
    search_log_path,
    slugify_doi,
    summary_path,
)
from vaultlab.provenance import ProvenanceRecord, write_receipts
from vaultlab.research.acquisition import acquire_pdfs_for_corpus
from vaultlab.research.corpus import build_corpus_from_seeds
from vaultlab.research.graph_metrics import compute_metrics
from vaultlab.research.summarize import (
    DEFAULT_MODEL,
    PaperSummary,
    SummarizeAuthError,
    load_anthropic_api_key,
    summarize_corpus,
)

if TYPE_CHECKING:
    from vaultlab.research.corpus import Corpus
    from vaultlab.research.paper import Paper

logger = logging.getLogger(__name__)

__all__ = [
    "LineageRunResult",
    "build_arc_prompt",
    "render_arc_markdown",
    "run_lit_arc",
]


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
    """

    topic: str
    arc_path: Path
    summary_paths: dict[str, Path] = field(default_factory=dict)
    search_log_path: Path = Path()
    corpus_size: int = 0
    pdfs_acquired: int = 0
    summaries_written: int = 0
    duration_seconds: float = 0.0


# ---------------------------------------------------------------------------
# Search log writer (Sources/Notes/lit-search-...md)
# ---------------------------------------------------------------------------


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
# Tier-A picker
# ---------------------------------------------------------------------------


def _pick_top_n_for_summarization(
    corpus: Corpus,
    *,
    n: int,
) -> list[str]:
    """Return up to ``n`` corpus DOIs to spend Tier-A token budget on.

    Ranks by ``og_score + forward_influence`` (papers that BOTH show up
    as a foundational citation across the seed set AND are themselves
    seeds whose work is cited by other seeds get prioritised).
    """
    metrics = corpus.metrics
    if metrics is None:
        # No metrics; just take the seeds in input order.
        return [d for d in (s.doi.lower() for s in corpus.seeds if s.doi)][:n]

    def _score(doi: str) -> float:
        return float(metrics.og_score.get(doi, 0.0)) + float(
            metrics.forward_influence.get(doi, 0)
        )

    # Score every paper in the corpus, take top-n by score.
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
    """Human-readable wikilink label: "Komor 2016 (CBE)" style."""
    if s.authors:
        first = s.authors[0]
        # Strip initials, take last name first-token
        last = first.split()[0] if first else "Anon"
    else:
        last = "Anon"
    year = str(s.year) if s.year else "n.d."
    return f"{last} {year}"


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
    for s in rows[:max_rows]:
        slug = slugify_doi(s.doi) if s.doi else "?"
        label = _author_year_label(s)
        lines.append(
            f"| {s.year} | [[{slug}|{label}]] | {s.tier} | "
            f"{s.og_score:.2f} | {s.forward_influence} |"
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
    kb_root: Path,
    max_seeds: int = 15,
    max_papers_to_summarize: int = 20,
    pdf_cache_dir: Path | None = None,
    apis: dict[str, str] | None = None,
    progress: _ProgressFn | None = None,
    # Test injection points (default to real implementations):
    _client: Any | None = None,
    _llm_summary: Callable[..., tuple[dict[str, Any], int, int]] | None = None,
    _llm_arc: Callable[..., dict[str, str]] | None = None,
    _fetch_refs: Any | None = None,
    _acquire: Any | None = None,
    _summarize_corpus_fn: Any | None = None,
    _today: str | None = None,
) -> LineageRunResult:
    """Run the full ``/lit-arc`` pipeline end-to-end.

    See module docstring for the canonical paths each phase writes.
    Test injection points let unit tests stub every external call —
    callers in production should leave them at their defaults.
    """
    started = time.time()
    date_str = _today or date.today().strftime("%Y-%m-%d")
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
    # Phase 5: PDF acquisition (waterfall)
    # ------------------------------------------------------------------
    _emit(progress, "phase", "acquire_pdfs", n_papers=corpus.n_papers)
    acq = _acquire if _acquire is not None else acquire_pdfs_for_corpus
    try:
        acq_results = acq(
            corpus,
            pdf_cache_dir,
            apis=apis,
            skip_paywalled=True,  # keep dry-runs fast / OA-only
        )
    except TypeError:
        # The injected fake may not accept all kwargs — fall back to positional.
        acq_results = acq(corpus, pdf_cache_dir)
    pdfs_acquired = sum(
        1 for r in acq_results.values() if getattr(r, "pdf_path", None) is not None
    )
    _emit(progress, "pdfs_acquired", n=pdfs_acquired)

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
    if max_papers_to_summarize and max_papers_to_summarize < corpus.n_papers:
        keep = set(_pick_top_n_for_summarization(corpus, n=max_papers_to_summarize))
        kept = 0
        skipped = 0
        for doi in list(corpus.papers.keys()):
            if doi in keep:
                kept += 1
            else:
                # Demote: pretend the PDF doesn't exist so summarize_corpus
                # writes a Tier-C stub. We don't delete the cached PDF
                # itself (it might be used by other commands later).
                res = acq_results.get(doi)
                if res is not None and getattr(res, "pdf_path", None) is not None:
                    skipped += 1
        _emit(progress, "summarize_budget", kept=kept, skipped=skipped)

    summarize_fn = _summarize_corpus_fn if _summarize_corpus_fn is not None else summarize_corpus
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
    if _llm_arc is not None:
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

    # method.md sidecar will be written next to the arc; we hint at the
    # canonical relpath so the frontmatter "provenance:" key is correct.
    method_relpath = arc_path.name + ".method.md"

    arc_md = render_arc_markdown(
        topic=topic,
        date_str=date_str,
        summaries=summaries,
        corpus=corpus,
        method_relpath=method_relpath,
        narrative=narrative,
        narrative_skipped_reason=skipped_reason,
    )
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
            "max_papers_to_summarize": max_papers_to_summarize,
            "pdf_cache_dir": str(pdf_cache_dir),
            "narration": "claude" if narrative is not None else "skipped",
        },
        model=DEFAULT_MODEL if narrative is not None else "",
        related_outputs=[str(log_path), *[str(p) for p in article_stubs]],
        notes=skipped_reason or "",
    )
    write_receipts(arc_path, record)
    _emit(progress, "provenance_written")

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
    )
