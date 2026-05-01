"""Tests for multi-query expansion + unified_search fan-out."""

from __future__ import annotations

from vaultlab.research.paper import Paper
from vaultlab.research.query_expansion import (
    expand_query,
    expand_topic_deterministic,
    prepare_query_expansion_task,
    render_queries_from_response,
)
from vaultlab.research.search import unified_search


# ---------------------------------------------------------------------------
# Deterministic expansion
# ---------------------------------------------------------------------------


def test_deterministic_expansion_includes_topic_first():
    out = expand_topic_deterministic("CODEX multiplexed imaging", target_n=4)
    assert out[0] == "CODEX multiplexed imaging"
    assert len(out) == 4


def test_deterministic_expansion_produces_distinct_variants():
    out = expand_topic_deterministic("CODEX", target_n=6)
    assert len(set(out)) == 6  # all distinct


def test_deterministic_expansion_caps_at_target_n():
    out = expand_topic_deterministic("CODEX", target_n=3)
    assert len(out) == 3


def test_deterministic_expansion_handles_empty_topic():
    out = expand_topic_deterministic("", target_n=5)
    assert out == [""]


# ---------------------------------------------------------------------------
# Render from callback response
# ---------------------------------------------------------------------------


def test_render_queries_from_response_prepends_original_topic():
    """The literal topic is always the first variant."""
    response = {
        "variants": [
            "different phrasing",
            "another phrasing",
        ]
    }
    out = render_queries_from_response(
        response, topic="my topic", target_n=5
    )
    assert out[0] == "my topic"
    assert "different phrasing" in out
    assert "another phrasing" in out


def test_render_queries_dedupes_case_insensitively():
    response = {
        "variants": ["MY topic", "MY TOPIC", "actually different"]
    }
    out = render_queries_from_response(
        response, topic="my topic", target_n=10
    )
    # All three case variants of "my topic" collapse to one entry.
    assert len([x for x in out if x.lower() == "my topic"]) == 1
    assert "actually different" in out


def test_render_queries_caps_at_target_n():
    response = {"variants": [f"v{i}" for i in range(20)]}
    out = render_queries_from_response(response, topic="t", target_n=5)
    assert len(out) == 5


def test_render_queries_handles_malformed_response():
    out = render_queries_from_response({}, topic="t", target_n=5)
    assert out == ["t"]
    out2 = render_queries_from_response("not json", topic="t", target_n=5)
    assert out2 == ["t"]


def test_render_queries_handles_json_string_response():
    out = render_queries_from_response(
        '{"variants": ["a", "b"]}', topic="t", target_n=5
    )
    assert "a" in out
    assert "b" in out


# ---------------------------------------------------------------------------
# expand_query (callback or fallback)
# ---------------------------------------------------------------------------


def test_expand_query_no_callback_uses_deterministic_fallback():
    out = expand_query("CODEX", target_n=4)
    assert out[0] == "CODEX"
    assert "CODEX review" in out


def test_expand_query_with_callback_returns_callback_variants():
    captured: list = []

    def cb(task):
        captured.append(task)
        return {"variants": ["llm-generated-1", "llm-generated-2"]}

    out = expand_query("topic-X", target_n=5, callback=cb)
    assert "llm-generated-1" in out
    assert "llm-generated-2" in out
    # Callback was invoked
    assert len(captured) == 1
    # Task carries the right topic
    assert captured[0].topic == "topic-X"


def test_expand_query_callback_exception_falls_back_deterministic():
    """If the callback raises, we fall back to deterministic expansion."""

    def cb(task):
        raise RuntimeError("LLM down")

    out = expand_query("CODEX", target_n=4, callback=cb)
    # Falls back; literal topic is still first.
    assert out[0] == "CODEX"
    assert len(out) >= 1


# ---------------------------------------------------------------------------
# unified_search fan-out
# ---------------------------------------------------------------------------


class _FakeNcbi:
    """A fake source client that records every search call."""

    def __init__(self, papers_per_query: dict[str, list[Paper]]):
        self._table = papers_per_query
        self.calls: list[str] = []

    def search(self, query: str, max_results: int = 50) -> list[Paper]:
        self.calls.append(query)
        return list(self._table.get(query, []))


def _paper(*, doi: str, year: int, citations: int) -> Paper:
    return Paper(
        title=f"p-{doi}",
        year=year,
        citation_count=citations,
        doi=doi,
        source_api="pubmed",
    )


def test_unified_search_multi_query_fans_out_across_variants():
    """Each variant runs against each source; results are deduped."""
    fake = _FakeNcbi(
        {
            "topic A": [
                _paper(doi="10.1/A", year=2024, citations=10),
                _paper(doi="10.1/B", year=2018, citations=100),
            ],
            "topic B": [
                _paper(doi="10.1/B", year=2018, citations=100),  # overlaps
                _paper(doi="10.1/C", year=2025, citations=2),  # unique
            ],
        }
    )
    papers = unified_search(
        query="ignored",
        queries=["topic A", "topic B"],
        sources=["pubmed"],
        ncbi_client=fake,
    )
    # Both variants ran
    assert fake.calls == ["topic A", "topic B"]
    # Three unique DOIs survive after dedup
    dois = {p.doi for p in papers}
    assert dois == {"10.1/A", "10.1/B", "10.1/C"}


def test_unified_search_multi_query_trace_records_all_variants():
    """Trace's per_source.queries lists every variant; hits are summed."""
    fake = _FakeNcbi(
        {
            "topic A": [_paper(doi="10.1/A", year=2024, citations=5)],
            "topic B": [_paper(doi="10.1/B", year=2024, citations=5)],
        }
    )
    papers, trace = unified_search(
        query="ignored",
        queries=["topic A", "topic B"],
        sources=["pubmed"],
        ncbi_client=fake,
        return_trace=True,
    )
    ncbi_trace = trace.per_source["ncbi"]
    assert ncbi_trace.queries == ["topic A", "topic B"]
    # Hits are summed across variants (1 + 1 = 2)
    assert ncbi_trace.hits == 2
    assert trace.deduped_seeds == 2


def test_unified_search_single_query_path_unchanged():
    """When ``queries`` is None, the legacy single-query path runs once."""
    fake = _FakeNcbi(
        {"my topic": [_paper(doi="10.1/X", year=2024, citations=1)]}
    )
    papers = unified_search(
        query="my topic",
        sources=["pubmed"],
        ncbi_client=fake,
    )
    assert fake.calls == ["my topic"]
    assert len(papers) == 1


# ---------------------------------------------------------------------------
# Task structure
# ---------------------------------------------------------------------------


def test_prepare_query_expansion_task_carries_topic_and_schema():
    task = prepare_query_expansion_task("CODEX imaging", target_n=4)
    assert task.topic == "CODEX imaging"
    assert task.target_n == 4
    assert "variants" in task.response_schema["properties"]
    assert "CODEX imaging" in task.prompt
