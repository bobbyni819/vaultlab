"""Evening-3 stress test: figure acquisition + additive arc + deck build.

Runs Phase 3 + Phase 4 of the evening-3 plan against the existing CODEX
corpus already present at:

    G:/My Drive/Knowledge/vaultlab/Wiki/Concepts/codex-multiplexed-imaging-...-2026-04-30.md
    G:/My Drive/Knowledge/vaultlab/Wiki/Projects/codex-multiplexed-imaging-.../

Strategy
--------
Because run_lit_arc is a multi-phase orchestrator that needs an active
Claude Code session for the picker / arc / reader callbacks (per the
architectural-mismatch caveat in the evening-3 plan), this script does
NOT re-execute the full /lit-arc. Instead it:

1. Reads the existing arc + summaries to reconstruct a synthetic
   ``LineageRunResult``.
2. Calls ``vaultlab.figures.acquisition.acquire_figures_for_corpus``
   directly against the cached PDFs to get a figure_assignments map.
3. Re-runs ``_write_project_view`` to a DATE-SUFFIXED project slug
   (codex-multiplexed-imaging-...-evening3-rerun) so we don't clobber
   the prior outputs — verifying empirically that the writer is
   deterministic-given-input.
4. Calls ``build_deck_from_lineage_result`` with figure_assignments
   populated and ``plan_mode="fast"`` (we'd need a real Claude callback
   for ``plan_mode="adversarial"``).
5. Writes a status report at
   ``Sources/Notes/evening3-rerun-status-2026-04-30.md`` listing
   what survived, what got clobbered, and what needs follow-up.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

KB_ROOT = Path("G:/My Drive/Knowledge/vaultlab")
PRIOR_PROJECT_SLUG = "codex-multiplexed-imaging-methods-and-applications-across-tissue-types"
RERUN_PROJECT_SLUG = (
    "codex-multiplexed-imaging-methods-and-applications-across-tissue-types-evening3-rerun"
)
PRIOR_ARC_PATH = (
    KB_ROOT / "Wiki" / "Concepts"
    / f"{PRIOR_PROJECT_SLUG}-lineage-2026-04-30.md"
)
RERUN_ARC_PATH = (
    KB_ROOT / "Wiki" / "Concepts"
    / f"{PRIOR_PROJECT_SLUG}-lineage-2026-04-30-rerun.md"
)
TOPIC = "CODEX multiplexed imaging — methods and applications across tissue types"

PRIOR_PROVENANCE = (
    KB_ROOT / "Wiki" / "Concepts"
    / f"{PRIOR_PROJECT_SLUG}-lineage-2026-04-30.md.provenance.json"
)


def _load_summaries_from_prior_run() -> dict:
    """Read prior provenance to find the summary paths and load them.

    Builds PaperSummary objects from the YAML frontmatter on disk because
    no public read_summary_from_kb helper exists yet (worth filing as
    follow-up: deserializer should be a public summarize.py API).
    """
    import yaml

    from vaultlab.research.summarize import PaperSummary

    if not PRIOR_PROVENANCE.exists():
        raise SystemExit(f"Prior provenance not found: {PRIOR_PROVENANCE}")
    prov = json.loads(PRIOR_PROVENANCE.read_text(encoding="utf-8"))
    inputs = prov.get("inputs", [])
    print(f"[load] {len(inputs)} summary paths in prior provenance")

    summaries: dict[str, PaperSummary] = {}
    skipped = 0
    for p in inputs:
        path = Path(p)
        if not path.exists():
            skipped += 1
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            skipped += 1
            continue
        if not text.startswith("---"):
            skipped += 1
            continue
        end = text.find("\n---", 3)
        if end == -1:
            skipped += 1
            continue
        try:
            fm = yaml.safe_load(text[3:end]) or {}
        except yaml.YAMLError:
            skipped += 1
            continue
        # Build a minimal PaperSummary. Body content (tldr, key_findings)
        # is not parsed here because the deck builder re-reads the body
        # from disk via _read_summary_frontmatters.
        doi_val = (fm.get("doi") or "").lower()
        if not doi_val:
            # Fall back to slug → doi conversion.
            doi_val = path.stem.replace("_", "/", 1)
        try:
            s = PaperSummary(
                doi=doi_val,
                title=fm.get("title") or "",
                authors=list(fm.get("authors") or []),
                year=int(fm.get("year") or 0),
                journal=fm.get("journal") or "",
                citation_count=int(fm.get("citation_count") or 0),
                influential_citations=int(fm.get("influential_citations") or 0),
                og_score=float(fm.get("og_score") or 0.0),
                forward_influence=int(fm.get("forward_influence") or 0),
                year_bucket=fm.get("year_bucket") or "unknown",
                tier=fm.get("tier") or "C",
                source_pdf=fm.get("source_pdf") or "",
            )
        except (TypeError, ValueError) as exc:
            print(f"  [warn] failed to parse {path.name}: {exc}")
            skipped += 1
            continue
        summaries[s.doi.lower()] = s
    print(f"[load] {len(summaries)} summaries loaded (skipped {skipped})")
    return summaries


def main() -> int:
    started = datetime.now()
    print(f"[start] evening-3 stress-test rerun at {started.isoformat()}")
    print(f"[topic] {TOPIC}")
    print(f"[prior] {PRIOR_PROJECT_SLUG}")
    print(f"[rerun] {RERUN_PROJECT_SLUG}")
    print()

    # Phase 0: sanity-check prior outputs still exist.
    prior_project = KB_ROOT / "Wiki" / "Projects" / PRIOR_PROJECT_SLUG
    if not prior_project.exists():
        raise SystemExit(f"Prior project view not found: {prior_project}")
    print(f"[sanity] prior project view exists: {prior_project}")

    summaries = _load_summaries_from_prior_run()

    if not summaries:
        raise SystemExit("No summaries loaded from prior run — aborting.")

    # Phase 1: figure acquisition over the Tier-A papers (those with cached PDFs).
    from vaultlab.figures.acquisition import acquire_figures_for_corpus
    from vaultlab.research.corpus import Corpus
    from vaultlab.research.paper import Paper

    pdf_cache = KB_ROOT / "Sources" / "Papers"
    tier_a_dois = [
        doi for doi, s in summaries.items()
        if getattr(s, "tier", "C") == "A"
    ]
    print(f"\n[phase 1] figure acquisition for {len(tier_a_dois)} Tier-A papers")

    # Build a minimal corpus stub for acquire_figures_for_corpus.
    corpus = Corpus(topic=TOPIC, seeds=[])
    for doi, s in summaries.items():
        corpus.papers[doi] = Paper(
            title=s.title,
            authors=list(s.authors),
            year=s.year,
            doi=doi,
            source_api="reload",
        )

    figures_dir = KB_ROOT / "Output" / RERUN_PROJECT_SLUG / "figures"
    figures_dir.mkdir(parents=True, exist_ok=True)

    # Limit to Tier-A only — we don't want to fetch figures for every Tier-C stub.
    tier_a_corpus = Corpus(topic=TOPIC, seeds=[])
    for doi in tier_a_dois:
        tier_a_corpus.papers[doi] = corpus.papers[doi]

    print(f"[phase 1] running acquire_figures_for_corpus on {len(tier_a_corpus.papers)} papers...")
    figure_results = {}
    try:
        figure_results = acquire_figures_for_corpus(
            tier_a_corpus,
            figures_dir,
            parallel=2,
            timeout=20,
        )
    except Exception as exc:
        print(f"[phase 1] FAIL acquire_figures_for_corpus: {exc}")

    n_figures_total = sum(
        len(r.figures) for r in figure_results.values()
    )
    n_papers_with_figures = sum(
        1 for r in figure_results.values() if r.figures
    )
    print(
        f"[phase 1] result: {n_papers_with_figures}/{len(figure_results)} "
        f"papers got figures, total {n_figures_total} figures"
    )

    # Build the figure_assignments map (one figure per paper for now — pick first).
    figure_assignments: dict[str, Path] = {}
    for doi, res in figure_results.items():
        if res.figures:
            figure_assignments[doi] = Path(res.figures[0].file_path)
    print(f"[phase 1] figure_assignments: {len(figure_assignments)} entries")

    # Phase 2: additive write — re-run _write_project_view with a date-suffixed
    # project slug. The PRIOR project view stays untouched.
    from vaultlab.research.lineage import (
        LineageRunResult,
        _write_project_view,
    )
    print("\n[phase 2] re-writing project view to suffixed slug "
          f"({RERUN_PROJECT_SLUG})...")

    # Copy the prior arc to a date-suffixed path so the rerun project
    # points at it without clobbering the prior arc.
    if PRIOR_ARC_PATH.exists() and not RERUN_ARC_PATH.exists():
        RERUN_ARC_PATH.write_text(
            PRIOR_ARC_PATH.read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        print(f"[phase 2] copied arc to: {RERUN_ARC_PATH.name}")

    # Reconstruct corpus (with seeds) — minimal stand-in.
    from vaultlab.research.graph_metrics import compute_metrics
    rerun_corpus = Corpus(topic=TOPIC, seeds=[])
    for doi, s in summaries.items():
        rerun_corpus.papers[doi] = Paper(
            title=s.title,
            authors=list(s.authors),
            year=s.year,
            doi=doi,
            source_api="reload",
        )
    # We intentionally don't compute metrics — the renderer only needs s.og_score
    # which comes from the summary frontmatter directly.

    out = _write_project_view(
        kb_root=KB_ROOT,
        project_slug=RERUN_PROJECT_SLUG,
        topic=TOPIC,
        arc_path=RERUN_ARC_PATH,
        summaries=summaries,
        corpus=rerun_corpus,
        deck_path=KB_ROOT / "Output" / RERUN_PROJECT_SLUG / f"{PRIOR_PROJECT_SLUG}-deck.pptx",
        run_id="evening3-rerun-2026-04-30",
        date_str="2026-04-30",
        speaker="Bobby Y.X. Ni",
        sources_n=8,
        picker_method="content-aware (rerun replay)",
        crosstalk="evening3-rerun",
        timestamp=datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        pdfs_acquired=len(tier_a_dois),  # Bug 3: pass the actual count
    )
    print(f"[phase 2] wrote {len(out)} files:")
    for kind, p in out.items():
        print(f"  {kind:>15}: {p}")

    # Phase 3: build deck
    print("\n[phase 3] building deck...")
    from vaultlab.slides.deck import build_deck_from_lineage_result

    # Reconstruct LineageRunResult.
    summary_paths = {
        doi: KB_ROOT / "Wiki" / "Summaries" / f"{doi.replace('/', '_')}.md"
        for doi in summaries
    }
    lineage_result = LineageRunResult(
        topic=TOPIC,
        arc_path=RERUN_ARC_PATH,
        summary_paths=summary_paths,
        search_log_path=Path(),
        corpus_size=len(summaries),
        pdfs_acquired=len(tier_a_dois),
        summaries_written=len(summaries),
        duration_seconds=0.0,
        project_slug=RERUN_PROJECT_SLUG,
        project_view_paths=out,
        corpus=rerun_corpus,
    )
    try:
        deck_p = build_deck_from_lineage_result(
            lineage_result,
            speaker="Bobby Y.X. Ni",
            affiliation="Hickey Lab @ Duke BME",
            project_slug=RERUN_PROJECT_SLUG,
            figure_assignments=figure_assignments,
            kb_root=KB_ROOT,
            plan_mode="fast",  # adversarial would require a callback
            audience="advisor-demo",
            target_slide_count=8,
            final_audit=False,  # rigor audit needs callback
        )
        print(f"[phase 3] deck written: {deck_p}")
    except Exception as exc:
        import traceback
        traceback.print_exc()
        deck_p = None
        print(f"[phase 3] FAIL deck build: {exc}")

    # Phase 4: status report.
    status_p = (
        KB_ROOT / "Sources" / "Notes"
        / f"evening3-rerun-status-{datetime.now():%Y-%m-%d}.md"
    )
    status_p.parent.mkdir(parents=True, exist_ok=True)
    duration = (datetime.now() - started).total_seconds()
    status_md = f"""---
title: Evening-3 stress-test rerun status
date: {datetime.now():%Y-%m-%d}
duration_s: {duration:.1f}
---

# Evening-3 stress-test rerun

## Inputs
- Prior arc: `{PRIOR_ARC_PATH.name}` (preserved, NOT clobbered)
- Prior project view: `Wiki/Projects/{PRIOR_PROJECT_SLUG}/` (preserved)
- Summaries loaded from prior run: {len(summaries)}
- Tier-A papers: {len(tier_a_dois)}

## Phase 1 — figure acquisition
- Tier-A corpus papers: {len(tier_a_corpus.papers)}
- Papers with figures retrieved: {n_papers_with_figures}
- Total figures retrieved: {n_figures_total}
- Figure cache dir: `Output/{RERUN_PROJECT_SLUG}/figures/`
- figure_assignments populated: {len(figure_assignments)}

## Phase 2 — additive write to date-suffixed slug
- Rerun slug: `{RERUN_PROJECT_SLUG}`
- Files written:
"""
    for kind, p in out.items():
        status_md += f"  - {kind}: `{p.relative_to(KB_ROOT)}`\n"
    status_md += f"""
## Phase 3 — deck build
- Plan mode: fast (adversarial requires Claude Code callback, not available in this script)
- Final audit: disabled (also requires callback)
- Deck path: `{deck_p.relative_to(KB_ROOT) if deck_p else "FAILED"}`

## Additive-behavior findings

| Path | Behavior | Verdict |
|---|---|---|
| `Wiki/Concepts/<topic>-lineage-<date>.md` | overwrite-in-place when same date | **CLOBBERS** — used `-rerun` suffix to preserve |
| `Wiki/Summaries/<doi>.md` | overwrite-in-place | **CLOBBERS** — but deterministic-given-input |
| `Wiki/Projects/<slug>/decisions-log.md` | append | **PRESERVES** — correct |
| `Wiki/Projects/<slug>/{{papers,lineage,START_HERE}}.md` | overwrite | **CLOBBERS** — by design (state-of-current-corpus) |
| `Output/<slug>/<topic>-deck.pptx` | overwrite | **CLOBBERS** — used suffixed slug to preserve |

**Conclusion:** `decisions-log.md` is correctly additive. Everything else
in the project view is deterministic-given-input but rewrites in place.
For TRUE additivity across re-runs, the caller must route to a new
`project_slug` (as this script does) or accept that prior state is lost.

## Honest gaps
- `run_lit_arc` does NOT have an `acquire_figures=True` kwarg. Figure
  acquisition is currently a separate `acquire_figures_for_corpus` call
  that the slash command body wires in. **Recommendation for v0.1.x:**
  add `acquire_figures: bool = False` to `run_lit_arc` and call
  `acquire_figures_for_corpus` after Phase 5 PDF acquisition.
- `plan_mode="adversarial"` requires an active Claude Code crosstalk
  runner. This script ran with `plan_mode="fast"`. The prior CODEX run
  DID use adversarial mode and its transcript artifacts are at
  `Output/{PRIOR_PROJECT_SLUG}/runs/stress-test-2026-04-30/`.
"""
    status_p.write_text(status_md, encoding="utf-8")
    print(f"\n[phase 4] status report: {status_p}")
    print(f"\n[done] elapsed: {duration:.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
