"""End-to-end stress test of /lit-arc + /build-deck on the CODEX corpus.

Resumes from the Phase 1-5 state.pkl produced by phase_1_5.py so we don't
re-run the 9-minute deterministic search/acquire phase. Uses the
test-injection points to feed the cached client / refs / acquisition
results to ``run_lit_arc``, then chains into ``build_deck_from_lineage_result``.
"""
from __future__ import annotations

import logging
import pickle
import sys
import time
import traceback
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore
except Exception:
    pass

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("stress_test")

# Suppress 3rd-party debug noise but keep vaultlab info+
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("vaultlab.research.acquisition").setLevel(logging.WARNING)

SCRATCH = Path(__file__).parent
sys.path.insert(0, str(SCRATCH))
import callbacks  # type: ignore[import-not-found]

from vaultlab.research.lineage import run_lit_arc
from vaultlab.research.acquisition import AcquisitionResult
from vaultlab.slides import build_deck_from_lineage_result


TOPIC = "CODEX multiplexed imaging — methods and applications across tissue types"
KB_ROOT = Path("G:/My Drive/Knowledge/vaultlab")
DATE_STR = "2026-04-30"
MAX_SEEDS = 8
MAX_PAPERS_TO_SUMMARIZE = 6  # Tier-A budget — 6 PDFs we have full text for
RUN_DIR = KB_ROOT / "Output" / "codex-multiplexed-imaging-methods-and-applications-across-tissue-types" / "runs" / "stress-test-2026-04-30"


def _make_fake_client(state):
    seeds = []
    # Build minimal Paper objects from state seeds (which are inside the corpus)
    for doi in state["corpus"].seed_dois:
        if doi in state["corpus"].papers:
            seeds.append(state["corpus"].papers[doi])

    class _Client:
        def search(self, query, max_results=20, sources=None):
            return list(seeds[:max_results])
    return _Client()


def _make_fake_acquire(state):
    """Replay cached acquisition results from disk."""
    cache = {}
    for doi, info in state["acq_results"].items():
        cache[doi] = AcquisitionResult(
            doi=doi,
            pdf_path=Path(info["pdf_path"]) if info["pdf_path"] else None,
            source=info["source"] or "failed",
            license=info.get("license", ""),
            error=None,
        )

    def _acquire(corpus, pdf_cache_dir, **kwargs):
        # Just return the pre-computed dict — keys are lower-cased dois
        results = {}
        for doi in corpus.papers:
            results[doi] = cache.get(doi.lower(), AcquisitionResult(
                doi=doi, pdf_path=None, source="failed", license="", error="not in cache"))
        return results
    return _acquire


def _make_fake_fetch_refs(state):
    """Replay cached references from corpus.references — re-wrap as Reference objects."""
    from vaultlab.research.citation_lookup import Reference
    refs_map = dict(state["corpus"].references)

    def _fetch_refs(doi):
        raw = refs_map.get(doi.lower(), [])
        out = []
        for item in raw:
            if isinstance(item, str):
                out.append(Reference(doi=item))
            elif hasattr(item, "doi"):
                out.append(item)
        return out
    return _fetch_refs


def main() -> int:
    print("=" * 78)
    print("STRESS TEST  /lit-arc + /build-deck  full pipeline")
    print(f"  topic         = {TOPIC}")
    print(f"  kb_root       = {KB_ROOT}")
    print(f"  max_seeds     = {MAX_SEEDS}")
    print(f"  Tier-A budget = {MAX_PAPERS_TO_SUMMARIZE}")
    print(f"  run_dir       = {RUN_DIR}")
    print("=" * 78)
    started = time.time()

    # Load Phase 1-5 cache
    state_pkl = SCRATCH / "state.pkl"
    if not state_pkl.exists():
        print(f"ERROR: missing {state_pkl}; run phase_1_5.py first")
        return 1
    with state_pkl.open("rb") as fh:
        state = pickle.load(fh)
    print(f"\n[load] Phase 1-5 state from {state_pkl} "
          f"({state['corpus'].n_papers} papers, {state['pdfs_acquired']} PDFs cached)")

    RUN_DIR.mkdir(parents=True, exist_ok=True)

    fake_client = _make_fake_client(state)
    fake_acquire = _make_fake_acquire(state)
    fake_fetch_refs = _make_fake_fetch_refs(state)

    # ----- /lit-arc -----
    t0 = time.time()
    print("\n[/lit-arc] starting run_lit_arc with adversarial picker + arc + binner...")
    try:
        result = run_lit_arc(
            TOPIC,
            kb_root=KB_ROOT,
            depth="balanced",
            max_seeds=MAX_SEEDS,
            max_papers_to_summarize=MAX_PAPERS_TO_SUMMARIZE,
            picker_callback=callbacks.claude_code_picker,
            binner_callback=callbacks.claude_code_binner,
            reader=callbacks.claude_code_reader,
            narrator=callbacks.claude_code_narrator,
            picker_mode="adversarial",
            arc_mode="adversarial",
            crosstalk_runner=callbacks.claude_code_runner,
            crosstalk_n_rounds=3,
            run_dir=RUN_DIR,
            speaker="Bobby",
            project_slug=None,
            _client=fake_client,
            _fetch_refs=fake_fetch_refs,
            _acquire=fake_acquire,
            _today=DATE_STR,
        )
    except Exception as exc:
        print(f"\nERROR: run_lit_arc raised: {exc!r}")
        traceback.print_exc()
        return 2
    print(f"\n[/lit-arc] complete in {time.time() - t0:.1f}s")
    print(f"  arc_path           = {result.arc_path}")
    print(f"  search_log_path    = {result.search_log_path}")
    print(f"  corpus_size        = {result.corpus_size}")
    print(f"  pdfs_acquired      = {result.pdfs_acquired}")
    print(f"  summaries_written  = {result.summaries_written}")
    print(f"  project_slug       = {result.project_slug}")
    print(f"  project_view_paths = {list(result.project_view_paths.keys())}")
    print(f"  corpus carried     = {result.corpus is not None}")

    # Reset runner call counters between meetings — picker meeting consumed
    # 3 rounds of "picker", arc consumed 3 rounds of "arc"; deck-plan + audit
    # are fresh.
    callbacks._RUNNER_CALL_COUNTS.clear()

    # ----- /build-deck -----
    t0 = time.time()
    print("\n[/build-deck] starting build_deck_from_lineage_result with adversarial plan + audit...")
    try:
        deck_path = build_deck_from_lineage_result(
            result,
            speaker="Bobby Y.X. Ni",
            affiliation="Hickey Lab @ Duke BME",
            project_slug=result.project_slug,
            figure_assignments={},  # no figures acquired in this run
            kb_root=KB_ROOT,
            audience="journal-club",
            target_slide_count=7,
            plan_mode="adversarial",
            crosstalk_runner=callbacks.claude_code_runner,
            crosstalk_n_rounds=3,
            final_audit=True,
            audit_strict=False,
            run_dir=RUN_DIR,
        )
    except Exception as exc:
        print(f"\nERROR: build_deck_from_lineage_result raised: {exc!r}")
        traceback.print_exc()
        return 3
    print(f"\n[/build-deck] complete in {time.time() - t0:.1f}s")
    print(f"  deck_path = {deck_path}")
    print(f"  deck exists = {deck_path.exists()}")

    print(f"\nTotal stress-test wall time: {time.time() - started:.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
