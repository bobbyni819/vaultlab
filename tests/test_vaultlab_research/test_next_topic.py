"""Tests for /lit-arc-next propose-next-topic module (#112)."""

from __future__ import annotations

from pathlib import Path

from vaultlab.research.next_topic import (
    NextTopicProposal,
    NextTopicTask,
    PriorTopicRecord,
    next_topic_response_schema,
    prepare_next_topic_task,
    propose_next_topics,
    read_open_questions,
    read_prior_topics,
    render_topics_from_response,
)


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


def _make_kb_with_decisions_log(
    tmp_path: Path, project_slug: str, log_text: str
) -> Path:
    """Create a KB structure + write decisions-log.md for a project."""
    kb = tmp_path / "kb"
    project_dir = kb / "Wiki" / "Projects" / project_slug
    project_dir.mkdir(parents=True)
    (project_dir / "decisions-log.md").write_text(log_text, encoding="utf-8")
    return kb


# ---------------------------------------------------------------------------
# read_prior_topics
# ---------------------------------------------------------------------------


def test_read_prior_topics_returns_empty_when_log_missing(tmp_path: Path):
    kb = tmp_path / "kb"
    out = read_prior_topics(kb, "no-such-project")
    assert out == []


def test_read_prior_topics_parses_real_log_shape(tmp_path: Path):
    log = """\
# decisions-log

## 2026-04-30T19:02:59 — lit-arc run
- **Topic:** CODEX multiplexed imaging — methods and applications across tissue types
- **Speaker:** Bobby
- **Search:** 0 seeds, 8 sources
- **Corpus size:** 236 papers (1 layer of CrossRef refs)
- **Tier-A picks:** 3 (picker_method=`content-aware`)
- **PDFs acquired:** 3 (1% success rate)
- **Run ID:** evening4-regen-2026-04-30

## 2026-05-01T10:00:00 — lit-arc run
- **Topic:** spatial transcriptomics tumor microenvironment
- **Search:** 0 seeds, 6 sources
- **Corpus size:** 180 papers (1 layer of CrossRef refs)
- **Tier-A picks:** 5 (picker_method=`content-aware`)
- **Run ID:** spatial-tx-001
"""
    kb = _make_kb_with_decisions_log(tmp_path, "test-proj", log)
    out = read_prior_topics(kb, "test-proj")
    assert len(out) == 2
    assert out[0].timestamp == "2026-04-30T19:02:59"
    assert "CODEX" in out[0].topic
    assert out[0].corpus_size == 236
    assert out[0].tier_a_picks == 3
    assert out[0].run_id == "evening4-regen-2026-04-30"
    assert out[1].topic == "spatial transcriptomics tumor microenvironment"
    assert out[1].corpus_size == 180


def test_read_prior_topics_handles_missing_optional_fields(tmp_path: Path):
    """When a log block has Topic but no Corpus size / Tier-A, defaults are 0."""
    log = """\
## 2026-05-01T10:00:00 — lit-arc run
- **Topic:** minimal log entry
- **Run ID:** abc
"""
    kb = _make_kb_with_decisions_log(tmp_path, "p", log)
    [r] = read_prior_topics(kb, "p")
    assert r.topic == "minimal log entry"
    assert r.corpus_size == 0
    assert r.tier_a_picks == 0


def test_read_prior_topics_skips_blocks_without_topic(tmp_path: Path):
    """Picker-decision blocks shouldn't be confused with lit-arc-run blocks."""
    log = """\
## 2026-04-30T19:00:00 — lit-arc run
- **Topic:** real-topic
- **Run ID:** r1

## 2026-04-30T19:30:00 — picker decision
Coarse pool: 30 candidates from citation graph
Picks: ...
"""
    kb = _make_kb_with_decisions_log(tmp_path, "p", log)
    out = read_prior_topics(kb, "p")
    assert len(out) == 1
    assert out[0].topic == "real-topic"


# ---------------------------------------------------------------------------
# read_open_questions
# ---------------------------------------------------------------------------


def test_read_open_questions_returns_empty_when_no_concepts(tmp_path: Path):
    out = read_open_questions(tmp_path / "kb", "p")
    assert out == []


def test_read_open_questions_extracts_section_body(tmp_path: Path):
    kb = tmp_path / "kb"
    concepts = kb / "Wiki" / "Concepts"
    concepts.mkdir(parents=True)
    (concepts / "topic-x-lineage-2026-05-01.md").write_text(
        "# arc\n\n"
        "## History\n\nbody of history.\n\n"
        "## Open questions\n\n"
        "How does X interact with Y under high-stress conditions?\n\n"
        "## SOTA\n\nbody of sota.\n",
        encoding="utf-8",
    )
    out = read_open_questions(kb, "p")
    assert len(out) == 1
    assert "high-stress" in out[0]


def test_read_open_questions_recognizes_alternate_headings(tmp_path: Path):
    """'Limitations & future directions' (REVIEW_PAPER) and 'Future directions'
    are also recognized as open-question sections."""
    kb = tmp_path / "kb"
    concepts = kb / "Wiki" / "Concepts"
    concepts.mkdir(parents=True)
    (concepts / "a-lineage-1.md").write_text(
        "## Limitations & future directions\n\nLimitation A.\n",
        encoding="utf-8",
    )
    (concepts / "b-lineage-2.md").write_text(
        "## Future directions\n\nFuture direction B.\n",
        encoding="utf-8",
    )
    out = read_open_questions(kb, "p")
    assert len(out) == 2
    bodies = " ".join(out)
    assert "Limitation A" in bodies
    assert "Future direction B" in bodies


# ---------------------------------------------------------------------------
# prepare_next_topic_task
# ---------------------------------------------------------------------------


def test_prepare_task_includes_prior_topics_in_prompt(tmp_path: Path):
    log = """\
## 2026-05-01T10:00:00 — lit-arc run
- **Topic:** CODEX imaging
- **Run ID:** r1
"""
    kb = _make_kb_with_decisions_log(tmp_path, "test-proj", log)
    task = prepare_next_topic_task(
        kb_root=kb, project_slug="test-proj", target_n=5
    )
    assert "CODEX imaging" in task.prompt
    assert task.target_n == 5
    assert task.prior_topics[0].topic == "CODEX imaging"


def test_prepare_task_signals_no_prior_runs_when_log_missing(tmp_path: Path):
    """When no decisions log exists, prompt clearly says 'this would be first run'."""
    task = prepare_next_topic_task(
        kb_root=tmp_path / "kb", project_slug="fresh", target_n=3
    )
    assert "first lit-arc" in task.prompt
    assert task.prior_topics == []


def test_prepare_task_target_n_caps_proposals_in_schema(tmp_path: Path):
    task = prepare_next_topic_task(
        kb_root=tmp_path / "kb", project_slug="p", target_n=3
    )
    schema = task.response_schema
    assert schema["properties"]["proposals"]["maxItems"] == 3


# ---------------------------------------------------------------------------
# render_topics_from_response
# ---------------------------------------------------------------------------


def _minimal_task(tmp_path: Path) -> NextTopicTask:
    return prepare_next_topic_task(
        kb_root=tmp_path / "kb", project_slug="p", target_n=5
    )


def test_render_returns_proposals_in_response_order(tmp_path: Path):
    task = _minimal_task(tmp_path)
    response = {
        "proposals": [
            {"topic": "Topic A", "rationale": "extends prior X"},
            {"topic": "Topic B", "rationale": "addresses gap Y"},
        ]
    }
    out = render_topics_from_response(response, task)
    assert [p.topic for p in out] == ["Topic A", "Topic B"]
    assert [p.priority_rank for p in out] == [1, 2]


def test_render_dedupes_duplicate_topics(tmp_path: Path):
    task = _minimal_task(tmp_path)
    response = {
        "proposals": [
            {"topic": "Same Topic", "rationale": "first"},
            {"topic": "SAME TOPIC", "rationale": "second (case dup)"},
            {"topic": "Different", "rationale": "third"},
        ]
    }
    out = render_topics_from_response(response, task)
    topics = [p.topic for p in out]
    assert "Same Topic" in topics
    assert "SAME TOPIC" not in topics
    assert "Different" in topics


def test_render_drops_proposals_with_empty_topic_or_rationale(tmp_path: Path):
    task = _minimal_task(tmp_path)
    response = {
        "proposals": [
            {"topic": "", "rationale": "no topic"},
            {"topic": "X", "rationale": ""},
            {"topic": "Y", "rationale": "good"},
        ]
    }
    out = render_topics_from_response(response, task)
    assert len(out) == 1
    assert out[0].topic == "Y"


def test_render_returns_empty_for_malformed_response(tmp_path: Path):
    task = _minimal_task(tmp_path)
    assert render_topics_from_response(None, task) == []
    assert render_topics_from_response({"unexpected": "shape"}, task) == []


def test_render_caps_at_target_n(tmp_path: Path):
    task = prepare_next_topic_task(
        kb_root=tmp_path / "kb", project_slug="p", target_n=2
    )
    response = {
        "proposals": [
            {"topic": f"Topic {i}", "rationale": "r"} for i in range(10)
        ]
    }
    out = render_topics_from_response(response, task)
    assert len(out) == 2


def test_render_extracts_builds_on_and_addresses_question(tmp_path: Path):
    task = _minimal_task(tmp_path)
    response = {
        "proposals": [
            {
                "topic": "X",
                "rationale": "r",
                "builds_on": ["Prior A", "Prior B"],
                "addresses_question": "How does Y work?",
            }
        ]
    }
    [p] = render_topics_from_response(response, task)
    assert p.builds_on == ["Prior A", "Prior B"]
    assert p.addresses_question == "How does Y work?"


# ---------------------------------------------------------------------------
# propose_next_topics (high-level helper)
# ---------------------------------------------------------------------------


def test_propose_returns_empty_when_no_callback(tmp_path: Path):
    out = propose_next_topics(
        kb_root=tmp_path / "kb", project_slug="p", callback=None
    )
    assert out == []


def test_propose_uses_callback_and_returns_proposals(tmp_path: Path):
    captured: list = []

    def cb(task: NextTopicTask):
        captured.append(task)
        return {
            "proposals": [
                {"topic": "From callback", "rationale": "r"},
            ]
        }

    out = propose_next_topics(
        kb_root=tmp_path / "kb",
        project_slug="p",
        callback=cb,
    )
    assert len(captured) == 1
    assert len(out) == 1
    assert out[0].topic == "From callback"


def test_propose_callback_exception_returns_empty(tmp_path: Path):
    def cb(task):
        raise RuntimeError("oops")

    out = propose_next_topics(
        kb_root=tmp_path / "kb", project_slug="p", callback=cb
    )
    assert out == []
