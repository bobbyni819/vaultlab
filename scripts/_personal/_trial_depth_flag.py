"""Trial harness for the ``/lit-arc`` ``depth`` flag (Task #63, 2026-04-30).

Runs ``vaultlab.research.lineage.run_lit_arc`` end-to-end on a synthetic
100-paper corpus across all four depth levels (``fast``, ``balanced``,
``thorough``, ``complete``) plus an explicit-override case.  Prints the
Tier-A budget that the orchestrator computed for each run so we can sanity
check the depth -> budget mapping without spending any real LLM tokens.

Usage::

    python scripts/_trial_depth_flag.py

Expected output::

    [trial-depth] depth=fast      n_pdfs_cached=N  budget=20
    [trial-depth] depth=balanced  n_pdfs_cached=N  budget=50
    [trial-depth] depth=thorough  n_pdfs_cached=N  budget=N
    [trial-depth] depth=complete  n_pdfs_cached=N  budget=N
    [trial-depth] explicit override max_papers_to_summarize=100 -> budget=100
"""

from __future__ import annotations

import logging
import os
import sys
import tempfile
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
except Exception:
    pass

logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")

from vaultlab.research.acquisition import AcquisitionResult  # noqa: E402
from vaultlab.research.lineage import run_lit_arc  # noqa: E402
from vaultlab.research.paper import Paper  # noqa: E402


def _synthetic_seeds(n: int) -> list[Paper]:
    return [
        Paper(
            title=f"Synthetic paper {i}",
            authors=[f"Author{i} I"],
            year=2010 + (i % 15),
            journal="Synth J",
            doi=f"10.9999/synth.{i:03d}",
            citation_count=100 - i,
            source_api="synth",
            abstract=f"Abstract for paper {i}.",
        )
        for i in range(n)
    ]


class _FakeClient:
    def __init__(self, seeds: list[Paper]) -> None:
        self._seeds = seeds

    def search(self, query: str, max_results: int = 20, sources=None):
        return list(self._seeds)


def _fake_acquire(corpus, cache_dir, **kwargs):
    """Pretend every seed acquired a PDF (n_pdfs_cached == corpus.n_papers)."""
    from vaultlab.research.acquisition import cache_path_for

    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    out: dict[str, AcquisitionResult] = {}
    for doi in sorted(corpus.papers.keys()):
        target = cache_path_for(doi, cache_dir)
        target.write_bytes(b"%PDF-1.4\n" + b"x" * 4000)
        out[doi] = AcquisitionResult(
            doi=doi, pdf_path=target, source="unpaywall", license="cc-by",
        )
    return out


def _fake_llm_summary():
    def _caller(*, pdf_bytes, prompt, api_key, model, **_):
        return (
            {
                "tldr": "[stub] s1. s2. s3.",
                "why_it_matters": ["[stub]"],
                "methods_summary": "[stub]",
                "key_findings": ["a [p1]", "b [p2]", "c [p3]"],
                "extracted_references": [],
            },
            1234,
            56,
        )

    return _caller


def _run_once(*, depth: str, max_papers: int | None, n_seeds: int) -> tuple[int, int]:
    """Return ``(n_pdfs_cached, resolved_budget)`` for a depth run.

    The budget is read off the ``depth_budget`` progress event (when depth
    derives the budget) or the provenance JSON (when an explicit override
    is in play, since no event is emitted).
    """
    seeds = _synthetic_seeds(n_seeds)
    client = _FakeClient(seeds)
    events: list[tuple[str, dict]] = []

    def _progress(*args, **kwargs):
        events.append((args[0] if args else "", dict(kwargs)))

    with tempfile.TemporaryDirectory() as td:
        kb_root = Path(td)
        result = run_lit_arc(
            "depth-trial",
            kb_root=kb_root,
            depth=depth,  # type: ignore[arg-type]
            max_seeds=n_seeds,
            max_papers_to_summarize=max_papers,
            _client=client,
            _fetch_refs=lambda d: [],
            _acquire=_fake_acquire,
            _llm_summary=_fake_llm_summary(),
            progress=_progress,
            _today="2026-04-30",
        )
        budget_events = [kw for tag, kw in events if tag == "depth_budget"]
        if budget_events:
            return budget_events[0]["n_pdfs_cached"], budget_events[0]["budget"]
        # Explicit override -> read from provenance.
        import json as _json
        rec_path = result.arc_path.with_name(
            result.arc_path.name + ".provenance.json"
        )
        rec = _json.loads(rec_path.read_text(encoding="utf-8"))
        return result.pdfs_acquired, int(rec["params"]["max_papers_to_summarize"])


def main() -> int:
    n_seeds = 100
    print(
        f"[trial-depth] synthetic corpus n_seeds={n_seeds} (every seed gets a PDF)"
    )
    print("[trial-depth] ----")
    for depth, expected in (
        ("fast", 20),
        ("balanced", 50),
        ("thorough", n_seeds),
        ("complete", n_seeds),
    ):
        n_cached, budget = _run_once(
            depth=depth, max_papers=None, n_seeds=n_seeds
        )
        marker = "OK" if budget == expected else "MISMATCH"
        print(
            f"[trial-depth] depth={depth:<10} "
            f"n_pdfs_cached={n_cached:<3} budget={budget:<3} "
            f"(expected {expected}, {marker})"
        )

    # Explicit override case: depth=fast + max_papers_to_summarize=100 -> 100.
    n_cached, budget = _run_once(
        depth="fast", max_papers=100, n_seeds=n_seeds
    )
    marker = "OK" if budget == 100 else "MISMATCH"
    print(
        f"[trial-depth] explicit override max_papers_to_summarize=100 -> "
        f"budget={budget} (expected 100, {marker})"
    )

    print(
        "[trial-depth] complete-mode interaction with acquisition retry: "
        "run_lit_arc forwards aggressive_retry=True + skip_paywalled=False to "
        "acquire_pdfs_for_corpus when depth='complete'. The acquisition fn "
        "then re-attempts paywalled tiers for any DOI whose first pass came "
        "back source='failed'. Verified by "
        "test_run_lit_arc_complete_passes_aggressive_retry + "
        "test_aggressive_retry_reattempts_failed_dois_with_paywalled."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
