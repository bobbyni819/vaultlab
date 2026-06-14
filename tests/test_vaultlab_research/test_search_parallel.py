"""Tests for the concurrent source fan-out in ``unified_search``.

The sequential→parallel refactor (one worker thread per source) must:

1. Actually run sources CONCURRENTLY (a slow source doesn't serialize behind
   the others).
2. Keep each source single-threaded (we don't assert this directly, but the
   per-source worker design is what enforces ``requests.Session`` safety).
3. Honour ``per_source_timeout_s`` as a backstop — a hung source is recorded
   as an error and the OTHER sources still return.
4. Produce byte-for-byte identical output to the sequential (``parallel=False``)
   path: same deduped papers, same per-source trace counts.
"""

from __future__ import annotations

import threading
import time

from vaultlab.research.paper import Paper
from vaultlab.research.search import unified_search


def _paper(title: str, doi: str, *, cites: int = 1, year: int = 2020, src: str = "pubmed") -> Paper:
    return Paper(title=title, doi=doi, citation_count=cites, year=year, source_api=src)


class _SleepStub:
    """Source stub that sleeps and records concurrent-thread occupancy."""

    def __init__(self, papers: list[Paper], registry: dict, *, sleep_s: float = 0.2):
        self._papers = papers
        self._reg = registry
        self._sleep = sleep_s

    def search(self, query: str, max_results: int = 20) -> list[Paper]:
        reg = self._reg
        with reg["lock"]:
            reg["active"] += 1
            reg["max_active"] = max(reg["max_active"], reg["active"])
        try:
            time.sleep(self._sleep)
        finally:
            with reg["lock"]:
                reg["active"] -= 1
        return list(self._papers)


class _PlainStub:
    """Minimal non-sleeping source stub: returns a fixed paper list."""

    def __init__(self, papers: list[Paper]):
        self._papers = papers

    def search(self, query: str, max_results: int = 20) -> list[Paper]:
        return list(self._papers)


def _registry() -> dict:
    return {"lock": threading.Lock(), "active": 0, "max_active": 0}


class TestConcurrency:
    def test_sources_run_concurrently(self) -> None:
        reg = _registry()
        ncbi = _SleepStub([_paper("A", "10.1/a")], reg)
        s2 = _SleepStub([_paper("B", "10.1/b", src="semantic")], reg)
        cr = _SleepStub([_paper("C", "10.1/c", src="crossref")], reg)

        papers = unified_search(
            "q",
            ncbi_client=ncbi,
            semantic_client=s2,
            crossref_client=cr,
            parallel=True,
        )
        assert len(papers) == 3
        # With three sources each sleeping, a serial run would peak at 1 active
        # thread; concurrency means >= 2 were in-flight simultaneously.
        assert reg["max_active"] >= 2

    def test_sequential_mode_never_overlaps(self) -> None:
        reg = _registry()
        ncbi = _SleepStub([_paper("A", "10.1/a")], reg)
        s2 = _SleepStub([_paper("B", "10.1/b", src="semantic")], reg)

        papers = unified_search(
            "q",
            ncbi_client=ncbi,
            semantic_client=s2,
            parallel=False,
        )
        assert len(papers) == 2
        assert reg["max_active"] == 1


class TestTimeoutBackstop:
    def test_slow_source_times_out_others_survive(self) -> None:
        reg = _registry()
        fast = _SleepStub([_paper("A", "10.1/a")], reg, sleep_s=0.0)
        # 2s sleep against a 0.2s backstop → this source is abandoned.
        slow = _SleepStub([_paper("B", "10.1/b", src="semantic")], reg, sleep_s=2.0)

        started = time.time()
        papers, trace = unified_search(
            "q",
            ncbi_client=fast,
            semantic_client=slow,
            return_trace=True,
            parallel=True,
            per_source_timeout_s=0.2,
        )
        elapsed = time.time() - started

        # The fast source's paper is returned without waiting ~2s for the slow one.
        assert elapsed < 1.5
        assert [p.doi for p in papers] == ["10.1/a"]
        assert trace.per_source["ncbi"].hits == 1
        slow_trace = trace.per_source["semantic_scholar"]
        assert slow_trace.hits == 0
        assert slow_trace.errors and "timeout" in slow_trace.errors[0].lower()

    def test_global_deadline_does_not_stack_when_first_source_is_slow(self) -> None:
        """Issue-4 regression: the SLOW source is FIRST in branch order (ncbi).

        A per-future ``result(timeout=T)`` harvest loop would block T on the
        slow first source before even looking at the fast ones, and with
        multiple slow sources the budget would stack to N*T. The global
        ``as_completed`` deadline must (a) still collect the fast source and
        (b) keep total wall-time ~one budget, not stacked.
        """
        reg = _registry()
        # ncbi is registered FIRST (branch order) and is the slow/hung one.
        slow = _SleepStub([_paper("A", "10.1/a")], reg, sleep_s=2.0)
        # Two FAST later sources — would each add T to a stacked-budget harvest.
        fast1 = _SleepStub([_paper("B", "10.1/b", src="semantic")], reg, sleep_s=0.0)
        fast2 = _SleepStub([_paper("C", "10.1/c", src="crossref")], reg, sleep_s=0.0)

        started = time.time()
        papers, trace = unified_search(
            "q",
            ncbi_client=slow,
            semantic_client=fast1,
            crossref_client=fast2,
            return_trace=True,
            parallel=True,
            per_source_timeout_s=0.4,
        )
        elapsed = time.time() - started

        # Total wall ~one 0.4s budget — NOT 0.4s*3 (stacked) and NOT 2s (serial).
        assert elapsed < 1.2, f"fan-out wall-time stacked: {elapsed:.2f}s"
        # Both fast sources collected despite the slow FIRST source.
        assert {p.doi for p in papers} == {"10.1/b", "10.1/c"}
        assert trace.per_source["semantic_scholar"].hits == 1
        assert trace.per_source["crossref"].hits == 1
        # The slow first source timed out under the global deadline.
        ncbi_trace = trace.per_source["ncbi"]
        assert ncbi_trace.hits == 0
        assert ncbi_trace.errors and "timeout" in ncbi_trace.errors[0].lower()


class TestParallelEqualsSequential:
    def _build(self):
        ncbi = [
            _paper("A", "10.1/a", cites=10, year=2020),
            _paper("B", "10.1/b", cites=5, year=2019),
        ]
        # semantic shares DOI a (lower-priority source) + adds c.
        sem = [
            _paper("A", "10.1/a", cites=11, year=2020, src="semantic"),
            _paper("C", "10.1/c", cites=2, year=2018, src="semantic"),
        ]
        return ncbi, sem

    def test_same_output_both_modes_multi_query(self) -> None:
        ncbi_papers, sem_papers = self._build()

        def run(parallel: bool):
            ncbi = _PlainStub(list(ncbi_papers))
            sem = _PlainStub(list(sem_papers))
            papers, trace = unified_search(
                "ignored when queries given",
                queries=["q1", "q2"],
                ncbi_client=ncbi,
                semantic_client=sem,
                return_trace=True,
                parallel=parallel,
            )
            return [p.doi for p in papers], trace.to_dict()

        par_dois, par_trace = run(parallel=True)
        seq_dois, seq_trace = run(parallel=False)

        assert par_dois == seq_dois
        # Per-source hits + dedup distribution identical (wall_time_ms excluded —
        # it's timing-dependent).
        for key in ("ncbi", "semantic_scholar"):
            assert par_trace["per_source"][key]["hits"] == seq_trace["per_source"][key]["hits"]
            assert par_trace["per_source"][key]["errors"] == seq_trace["per_source"][key]["errors"]
        assert par_trace["deduped_seeds"] == seq_trace["deduped_seeds"]
        assert par_trace["by_source_after_dedup"] == seq_trace["by_source_after_dedup"]
