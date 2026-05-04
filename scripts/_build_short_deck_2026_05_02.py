"""Phase deck — build the short-scope deck from on-disk arc + summaries.

We synthesize a LineageRunResult instead of re-running run_lit_arc
(idempotent / reuse-policy from /build-deck.md).
"""
from __future__ import annotations
import json
import sys
from pathlib import Path
from datetime import date

# Force UTF-8 stdout for logs with unicode arrows etc.
sys.stdout.reconfigure(encoding="utf-8")

from vaultlab.research.lineage import LineageRunResult
from vaultlab.research.corpus import Corpus
from vaultlab.research.paper import Paper
from vaultlab.slides.deck import build_deck_from_lineage_result
from vaultlab.kb.paths import slugify_topic

KB_ROOT = Path("G:/My Drive/Knowledge/vaultlab")
TOPIC = "Multiscale tissue simulation for lung infectious disease"
SLUG = "multiscale-tissue-simulation-lung-infection"
PROJECT_SLUG = SLUG
WORKSPACE = KB_ROOT / "Wiki" / "Projects" / SLUG / "_short_2026_05_02_workspace"
SUMMARIES_DIR = KB_ROOT / "Wiki" / "Summaries"
PAPERS_DIR = KB_ROOT / "Sources" / "Papers"
ARC_PATH = KB_ROOT / "Wiki" / "Concepts" / f"{SLUG}-lineage-short-2026-05-02.md"
DECK_OUT = KB_ROOT / "Output" / SLUG / "short-2026-05-02.pptx"
DECK_OUT.parent.mkdir(parents=True, exist_ok=True)

picks = json.loads((WORKSPACE / "curated_picks.json").read_text(encoding="utf-8"))["picks"]
acq = {a["doi"]: a for a in json.loads((WORKSPACE / "acquisition_results.json").read_text(encoding="utf-8"))}

# Build summary_paths map
summary_paths: dict[str, Path] = {}
for p in picks:
    doi = p["doi"]
    slug = doi.replace("/", "_").lower()
    candidate = SUMMARIES_DIR / f"{slug}.md"
    if candidate.exists():
        summary_paths[doi] = candidate
        continue
    # Try uppercased variant
    candidate2 = SUMMARIES_DIR / f"{doi.replace('/', '_')}.md"
    if candidate2.exists():
        summary_paths[doi] = candidate2

print(f"Located {len(summary_paths)}/{len(picks)} summaries on disk")
for doi, p in summary_paths.items():
    print(f"  {doi} -> {p.name}")

# Build a synthetic Corpus from picks (seeds + walked refs aren't strictly needed
# for the deck builder's lineage path; what matters is corpus.papers).
papers: dict[str, Paper] = {}
for p in picks:
    papers[p["doi"]] = Paper(
        doi=p["doi"],
        title=p.get("rationale", "")[:80] or p["doi"],
        authors=[],
        year=0,
        journal="",
        abstract="",
        url="",
        pdf_url="",
        citation_count=0,
        source_api="curated-picks",
    )

corpus = Corpus(
    topic=TOPIC,
    seeds=[
        "10.1093/bioinformatics/btac049",
        "10.1038/s41586-023-05915-x",
        "10.3389/fimmu.2021.727626",
        "10.1016/j.cobme.2019.10.001",
    ],
    papers=papers,
    references={},
    cited_by={},
    metrics=None,
    preprint_pairs={},
)

# Figure assignments — try cached figure paths if any exist; otherwise empty.
figure_assignments: dict[str, Path] = {}
fig_cache_dir = KB_ROOT / "Output" / SLUG / "figures_cache"
fig_cache_dir.mkdir(parents=True, exist_ok=True)

# Try to acquire figures for cached PDFs (best-effort, graceful)
try:
    from vaultlab.figures.acquisition import acquire_figures_for_corpus
    print(f"\nAttempting figure acquisition for {len(picks)} papers...")
    fig_results = acquire_figures_for_corpus(corpus, fig_cache_dir, parallel=2, timeout=45)
    for doi, fres in fig_results.items():
        figs = getattr(fres, "figures", []) or []
        if figs:
            first = figs[0]
            path = getattr(first, "path", None)
            if path:
                figure_assignments[doi] = Path(path)
    print(f"Acquired figures for {len(figure_assignments)}/{len(picks)} papers")
except Exception as e:
    print(f"Figure acquisition skipped due to error: {e}")

# Synthesize the LineageRunResult
result = LineageRunResult(
    topic=TOPIC,
    arc_path=ARC_PATH,
    summary_paths=summary_paths,
    search_log_path=WORKSPACE / "search_log.json",
    corpus_size=len(picks),
    pdfs_acquired=sum(1 for a in acq.values() if a["pdf_path"]),
    summaries_written=len(summary_paths),
    duration_seconds=0.0,
    project_slug=PROJECT_SLUG,
    project_view_paths={},
    corpus=corpus,
    figure_assignments=figure_assignments,
    figures_acquired=len(figure_assignments),
)

print(f"\nBuilding deck -> {DECK_OUT}")
out_path = build_deck_from_lineage_result(
    result,
    speaker="Bobby Y.X. Ni",
    affiliation="Hickey Lab @ Duke BME",
    project_slug=PROJECT_SLUG,
    figure_assignments=figure_assignments,
    kb_root=KB_ROOT,
    plan_callback=None,         # use mechanical synthesis
    audience="journal-club",
    target_slide_count=7,
    plan_mode="fast",
    crosstalk_runner=None,
    final_audit=False,
    audit_strict=False,
)
print(f"Deck written: {out_path}")

# Move to the requested location if different
if Path(out_path) != DECK_OUT:
    DECK_OUT.write_bytes(Path(out_path).read_bytes())
    print(f"Copied to: {DECK_OUT}")
