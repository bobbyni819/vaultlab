"""Tests for vaultlab.workflows.deck_plan — content-aware deck-plan generator.

Validates:

* :func:`prepare_deck_plan_task` produces a typed task without HTTP/LLM.
* :func:`render_plan_from_response` parses valid JSON correctly.
* :func:`render_plan_from_response` drops invalid slides + populates
  missing fields gracefully.
* :func:`generate_deck_plan` falls back to mechanical when callback None.
* :func:`generate_deck_plan` propagates callback's plan when provided.
* End-to-end: synthetic corpus + summaries + figure_assignments + stub
  callback that returns 3-slide plan -> verify .pptx generated with the
  LLM-picked slides.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from vaultlab.research.corpus import Corpus
from vaultlab.research.graph_metrics import CorpusMetrics
from vaultlab.research.paper import Paper
from vaultlab.research.summarize import PaperSummary
from vaultlab.workflows.deck_plan import (
    DeckPlanTask,
    deck_plan_response_schema,
    generate_deck_plan,
    prepare_deck_plan_task,
    render_plan_from_response,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_summary(
    doi: str,
    *,
    year: int,
    bucket: str,
    title: str,
    tier: str = "A",
    og_score: float = 0.3,
    forward_influence: int = 5,
) -> PaperSummary:
    return PaperSummary(
        doi=doi,
        title=title,
        authors=[f"Smith {year}", f"Doe {year}"],
        year=year,
        journal="J. Synthetic Sci.",
        og_score=og_score,
        forward_influence=forward_influence,
        year_bucket=bucket,
        tier=tier,
        tldr=f"This paper from {year} shows that {title.lower()}.",
        key_findings=[
            f"Found mechanism A at {year}",
            f"Showed application B at {year}",
            f"Demonstrated effect C at {year}",
        ],
    )


def _make_corpus(summaries: dict[str, PaperSummary]) -> Corpus:
    papers: dict[str, Paper] = {}
    og_score: dict[str, float] = {}
    forward_influence: dict[str, int] = {}
    year_buckets: dict[str, str] = {}
    for doi, s in summaries.items():
        key = doi.lower()
        papers[key] = Paper(
            doi=doi,
            title=s.title,
            authors=list(s.authors),
            year=s.year,
            journal=s.journal,
        )
        og_score[key] = s.og_score
        forward_influence[key] = s.forward_influence
        year_buckets[key] = s.year_bucket
    metrics = CorpusMetrics(
        og_score=og_score,
        forward_influence=forward_influence,
        co_citation_pairs=[
            ("10.1/foundations-1990", "10.1/scaffolding-2002", 4),
        ],
        year_buckets=year_buckets,
    )
    return Corpus(
        topic="trial topic",
        seeds=[],
        papers=papers,
        references={},
        metrics=metrics,
    )


@pytest.fixture
def synth_summaries() -> dict[str, PaperSummary]:
    return {
        "10.1/foundations-1990": _make_summary(
            "10.1/foundations-1990",
            year=1990,
            bucket="history",
            title="Foundational discovery",
            og_score=0.6,
            forward_influence=20,
        ),
        "10.1/scaffolding-2002": _make_summary(
            "10.1/scaffolding-2002",
            year=2002,
            bucket="history",
            title="Scaffolding the field",
        ),
        "10.1/breakthrough-2014": _make_summary(
            "10.1/breakthrough-2014",
            year=2014,
            bucket="development",
            title="Breakthrough method",
            og_score=0.4,
            forward_influence=12,
        ),
        "10.1/refinement-2019": _make_summary(
            "10.1/refinement-2019",
            year=2019,
            bucket="development",
            title="Methodological refinement",
        ),
        "10.1/sota-2024": _make_summary(
            "10.1/sota-2024",
            year=2024,
            bucket="sota",
            title="State-of-the-art system",
            og_score=0.2,
            forward_influence=3,
        ),
    }


@pytest.fixture
def synth_corpus(synth_summaries) -> Corpus:
    return _make_corpus(synth_summaries)


@pytest.fixture
def fig_assignments(tmp_path) -> dict[str, Path]:
    p1 = tmp_path / "fig_history.png"
    p2 = tmp_path / "fig_dev.png"
    p3 = tmp_path / "fig_sota.png"
    for p in (p1, p2, p3):
        p.write_bytes(b"\x89PNG\r\n\x1a\n")  # minimal PNG header
    return {
        "10.1/foundations-1990": p1,
        "10.1/breakthrough-2014": p2,
        "10.1/sota-2024": p3,
    }


# ---------------------------------------------------------------------------
# prepare_deck_plan_task
# ---------------------------------------------------------------------------


class TestPrepareDeckPlanTask:
    def test_returns_deck_plan_task_no_llm_call(
        self, synth_corpus, synth_summaries, fig_assignments, tmp_path
    ):
        """Pure function — no HTTP, no LLM, no API key."""
        task = prepare_deck_plan_task(
            topic="trial topic",
            corpus=synth_corpus,
            summaries=synth_summaries,
            figure_assignments=fig_assignments,
            speaker="Bobby Ni",
            affiliation="Hickey Lab",
            kb_root=tmp_path,
        )
        assert isinstance(task, DeckPlanTask)
        assert task.topic == "trial topic"
        assert task.speaker == "Bobby Ni"
        assert task.affiliation == "Hickey Lab"
        assert task.target_slide_count == 7  # default
        assert task.audience == "journal-club"  # default

    def test_corpus_summaries_only_tier_a(self, synth_corpus, synth_summaries, tmp_path):
        # Mark one as Tier-C — should be dropped from prompt content
        synth_summaries["10.1/sota-2024"].tier = "C"
        synth_summaries["10.1/sota-2024"].tldr = ""
        synth_summaries["10.1/sota-2024"].key_findings = []
        task = prepare_deck_plan_task(
            topic="trial topic",
            corpus=synth_corpus,
            summaries=synth_summaries,
            kb_root=tmp_path,
        )
        dois = {s["doi"] for s in task.corpus_summaries}
        assert "10.1/sota-2024" not in dois
        assert "10.1/foundations-1990" in dois

    def test_corpus_metrics_populated(self, synth_corpus, synth_summaries, tmp_path):
        task = prepare_deck_plan_task(
            topic="trial topic",
            corpus=synth_corpus,
            summaries=synth_summaries,
            kb_root=tmp_path,
        )
        m = task.corpus_metrics
        assert "top_og" in m
        assert "top_co_citation" in m
        assert "year_buckets" in m
        assert m["n_total_papers"] == 5
        assert m["n_tier_a"] == 5  # all Tier-A in fixture
        # Top OG should be ordered by score desc; foundations-1990 is highest
        assert m["top_og"][0][0] == "10.1/foundations-1990"

    def test_prompt_contains_all_buckets(
        self, synth_corpus, synth_summaries, fig_assignments, tmp_path
    ):
        task = prepare_deck_plan_task(
            topic="trial topic",
            corpus=synth_corpus,
            summaries=synth_summaries,
            figure_assignments=fig_assignments,
            kb_root=tmp_path,
        )
        prompt = task.prompt
        assert "history bucket" in prompt
        assert "development bucket" in prompt
        assert "sota bucket" in prompt
        assert "AVAILABLE FIGURES" in prompt
        assert "TOP CO-CITATION PAIRS" in prompt
        # Each Tier-A summary's TL;DR should appear
        assert "Foundational discovery" in prompt or "foundational discovery" in prompt

    def test_no_figures_uses_text_only_instruction(self, synth_corpus, synth_summaries, tmp_path):
        task = prepare_deck_plan_task(
            topic="trial topic",
            corpus=synth_corpus,
            summaries=synth_summaries,
            figure_assignments=None,
            kb_root=tmp_path,
        )
        assert "no figures available" in task.prompt
        assert task.figure_assignments == {}

    def test_response_schema_validates_basic_shape(self, synth_corpus, synth_summaries, tmp_path):
        task = prepare_deck_plan_task(
            topic="trial topic",
            corpus=synth_corpus,
            summaries=synth_summaries,
            kb_root=tmp_path,
        )
        schema = task.response_schema
        assert schema["type"] == "object"
        assert "slides" in schema["required"]
        slide_one_of = schema["properties"]["slides"]["items"]["oneOf"]
        types_seen = {item["properties"]["type"]["const"] for item in slide_one_of}
        assert {"title", "section_divider", "figure", "multi_figure", "text"} <= types_seen


# ---------------------------------------------------------------------------
# render_plan_from_response
# ---------------------------------------------------------------------------


class TestRenderPlanFromResponse:
    def test_parses_valid_three_slide_response(
        self, synth_corpus, synth_summaries, fig_assignments, tmp_path
    ):
        task = prepare_deck_plan_task(
            topic="trial topic",
            corpus=synth_corpus,
            summaries=synth_summaries,
            figure_assignments=fig_assignments,
            speaker="Bobby Ni",
            kb_root=tmp_path,
        )
        response = {
            "story_arc_summary": "History -> SOTA arc.",
            "slides": [
                {
                    "type": "title",
                    "title": "Trial topic",
                    "subtitle": "Journal club",
                    "author": "Bobby Ni",
                },
                {
                    "type": "figure",
                    "title": "Foundational figure",
                    "image_path": str(fig_assignments["10.1/foundations-1990"]),
                    "claim_paper_doi": "10.1/foundations-1990",
                    "figure_paper_doi": "10.1/foundations-1990",
                    "caption": "The 1990 foundation.",
                    "bullets": ["Showed mechanism A"],
                },
                {
                    "type": "text",
                    "title": "What's next",
                    "bullets": ["See [[doi-slug|Smith 2024]]"],
                    "citations": ["10.1/sota-2024"],
                },
            ],
        }
        plan = render_plan_from_response(task, response)
        assert plan["title"] == "trial topic"
        assert plan["author"] == "Bobby Ni"
        # 3 LLM slides + auto-appended references slide = 4
        assert len(plan["slides"]) == 4
        assert plan["slides"][0]["type"] == "title"
        assert plan["slides"][1]["type"] == "figure"
        assert plan["slides"][2]["type"] == "text"
        assert plan["slides"][-1]["type"] == "references"
        assert plan["story_arc_summary"] == "History -> SOTA arc."

    def test_drops_unknown_slide_type(self, synth_corpus, synth_summaries, tmp_path):
        task = prepare_deck_plan_task(
            topic="trial topic",
            corpus=synth_corpus,
            summaries=synth_summaries,
            kb_root=tmp_path,
        )
        response = {
            "slides": [
                {"type": "title", "title": "Trial"},
                {"type": "bogus_kind", "title": "Should be dropped"},
                {"type": "text", "title": "Real slide", "bullets": ["a"]},
            ],
        }
        plan = render_plan_from_response(task, response)
        types = [s["type"] for s in plan["slides"]]
        assert "bogus_kind" not in types
        assert "text" in types

    def test_drops_figure_slide_with_invalid_image_path(
        self, synth_corpus, synth_summaries, fig_assignments, tmp_path
    ):
        task = prepare_deck_plan_task(
            topic="trial topic",
            corpus=synth_corpus,
            summaries=synth_summaries,
            figure_assignments=fig_assignments,
            kb_root=tmp_path,
        )
        response = {
            "slides": [
                {"type": "title", "title": "Trial"},
                {
                    "type": "figure",
                    "title": "Bogus figure",
                    "image_path": "/does/not/exist.png",
                    "claim_paper_doi": "10.1/foundations-1990",
                },
                {"type": "text", "title": "Real", "bullets": ["yes"]},
            ],
        }
        plan = render_plan_from_response(task, response)
        figure_titles = [s.get("title") for s in plan["slides"] if s.get("type") == "figure"]
        assert "Bogus figure" not in figure_titles

    def test_inserts_title_slide_if_missing(self, synth_corpus, synth_summaries, tmp_path):
        task = prepare_deck_plan_task(
            topic="my topic",
            corpus=synth_corpus,
            summaries=synth_summaries,
            speaker="Alice",
            kb_root=tmp_path,
        )
        response = {
            "slides": [
                {"type": "text", "title": "First content", "bullets": ["a"]},
            ],
        }
        plan = render_plan_from_response(task, response)
        assert plan["slides"][0]["type"] == "title"
        assert plan["slides"][0]["title"] == "my topic"
        assert plan["slides"][0]["author"] == "Alice"

    def test_appends_references_slide_from_cited_dois(
        self, synth_corpus, synth_summaries, fig_assignments, tmp_path
    ):
        task = prepare_deck_plan_task(
            topic="trial",
            corpus=synth_corpus,
            summaries=synth_summaries,
            figure_assignments=fig_assignments,
            kb_root=tmp_path,
        )
        response = {
            "slides": [
                {"type": "title", "title": "Trial"},
                {
                    "type": "figure",
                    "title": "Foundational",
                    "image_path": str(fig_assignments["10.1/foundations-1990"]),
                    "claim_paper_doi": "10.1/foundations-1990",
                },
                {
                    "type": "text",
                    "title": "SOTA",
                    "bullets": ["the latest"],
                    "citations": ["10.1/sota-2024"],
                },
            ],
        }
        plan = render_plan_from_response(task, response)
        refs_slide = [s for s in plan["slides"] if s.get("type") == "references"]
        assert len(refs_slide) == 1
        refs = refs_slide[0]["references"]
        # Should contain both cited DOIs
        text = "\n".join(refs)
        assert "Foundational discovery" in text
        assert "State-of-the-art system" in text

    def test_substituted_figure_tracks_both_dois(
        self, synth_corpus, synth_summaries, fig_assignments, tmp_path
    ):
        """When claim_paper_doi != figure_paper_doi, both go into refs."""
        task = prepare_deck_plan_task(
            topic="trial",
            corpus=synth_corpus,
            summaries=synth_summaries,
            figure_assignments=fig_assignments,
            kb_root=tmp_path,
        )
        response = {
            "slides": [
                {"type": "title", "title": "Trial"},
                {
                    "type": "figure",
                    "title": "Substituted",
                    "image_path": str(fig_assignments["10.1/breakthrough-2014"]),
                    "claim_paper_doi": "10.1/scaffolding-2002",
                    "figure_paper_doi": "10.1/breakthrough-2014",
                    "caption": "Sub'd from breakthrough",
                },
            ],
        }
        plan = render_plan_from_response(task, response)
        refs_slide = [s for s in plan["slides"] if s.get("type") == "references"]
        text = "\n".join(refs_slide[0]["references"])
        assert "Scaffolding" in text
        assert "Breakthrough" in text

    def test_normalize_figure_slide_composes_substitution_caption(
        self, synth_corpus, synth_summaries, fig_assignments, tmp_path
    ):
        """Regression for L4 audit bug #2: when claim_doi != figure_doi,
        the caption MUST be prefixed with ``Substituted figure from
        [[<slug>|Author Year]]:`` so the audience sees the attribution
        flag. Before the fix, the LLM-supplied caption was used verbatim
        and the figure looked like it came from the claim paper.
        """
        task = prepare_deck_plan_task(
            topic="trial",
            corpus=synth_corpus,
            summaries=synth_summaries,
            figure_assignments=fig_assignments,
            kb_root=tmp_path,
        )
        response = {
            "slides": [
                {"type": "title", "title": "Trial"},
                {
                    "type": "figure",
                    "title": "Substituted figure",
                    "image_path": str(fig_assignments["10.1/breakthrough-2014"]),
                    "claim_paper_doi": "10.1/scaffolding-2002",
                    "figure_paper_doi": "10.1/breakthrough-2014",
                    "caption": "Original caption text",
                },
                {
                    "type": "figure",
                    "title": "Non-substituted figure",
                    "image_path": str(fig_assignments["10.1/foundations-1990"]),
                    "claim_paper_doi": "10.1/foundations-1990",
                    "figure_paper_doi": "10.1/foundations-1990",
                    "caption": "Same-paper caption",
                },
            ],
        }
        plan = render_plan_from_response(task, response)
        figure_slides = [s for s in plan["slides"] if s.get("type") == "figure"]
        assert len(figure_slides) == 2

        sub_slide = next(s for s in figure_slides if s["title"] == "Substituted figure")
        cap = sub_slide["caption"]
        # The substitution prefix must be present and lead the caption.
        assert cap.startswith("Substituted figure from "), (
            f"caption did not get the substitution prefix: {cap!r}"
        )
        # The wikilink slug must come from slugify_doi (so it resolves to
        # the actual Wiki/Summaries/<slug>.md file).
        from vaultlab.kb.paths import slugify_doi

        expected_slug = slugify_doi("10.1/breakthrough-2014")
        assert f"[[{expected_slug}|" in cap, (
            f"caption is missing wikilink to figure source: {cap!r}"
        )
        # The original caption text must be preserved after the prefix.
        assert "Original caption text" in cap

        # Non-substituted figure (claim == figure) must NOT get the prefix.
        non_sub_slide = next(s for s in figure_slides if s["title"] == "Non-substituted figure")
        assert "Substituted figure from" not in non_sub_slide["caption"]

    def test_speaker_notes_dual_format_preserved(self, synth_corpus, synth_summaries, tmp_path):
        task = prepare_deck_plan_task(
            topic="trial",
            corpus=synth_corpus,
            summaries=synth_summaries,
            kb_root=tmp_path,
        )
        response = {
            "slides": [
                {"type": "title", "title": "Trial"},
                {
                    "type": "text",
                    "title": "Real",
                    "bullets": ["yes"],
                    "speaker_notes": {
                        "mental_map": {
                            "hook": "Open with a hook",
                            "key_claim": "The claim",
                        },
                        "detailed_script": "Hello, today...",
                    },
                },
            ],
        }
        plan = render_plan_from_response(task, response)
        text_slide = [s for s in plan["slides"] if s.get("type") == "text"][0]
        notes = text_slide["speaker_notes"]
        assert notes is not None
        assert notes.get("hook") == "Open with a hook"
        assert "Hello, today" in notes.get("detailed_script", "")

    def test_empty_response_yields_minimum_legal_plan(
        self, synth_corpus, synth_summaries, tmp_path
    ):
        task = prepare_deck_plan_task(
            topic="trial",
            corpus=synth_corpus,
            summaries=synth_summaries,
            kb_root=tmp_path,
        )
        plan = render_plan_from_response(task, {})
        # Should still have a title slide and not crash
        assert plan["slides"]
        assert plan["slides"][0]["type"] == "title"


# ---------------------------------------------------------------------------
# generate_deck_plan
# ---------------------------------------------------------------------------


class TestGenerateDeckPlan:
    def test_falls_back_to_mechanical_when_no_callback(
        self, synth_corpus, synth_summaries, tmp_path
    ):
        plan = generate_deck_plan(
            topic="trial",
            corpus=synth_corpus,
            summaries=synth_summaries,
            speaker="Bobby Ni",
            kb_root=tmp_path,
            plan_callback=None,
        )
        assert plan["title"] == "Lineage: trial"
        assert plan["author"] == "Bobby Ni"
        # Should have title + section_divider(s) + content + refs
        types = [s["type"] for s in plan["slides"]]
        assert "title" in types
        assert "section_divider" in types
        assert "Mechanical" in plan.get("story_arc_summary", "")

    def test_propagates_callback_response(
        self, synth_corpus, synth_summaries, fig_assignments, tmp_path
    ):
        captured: list[DeckPlanTask] = []

        def stub_callback(task: DeckPlanTask) -> dict:
            captured.append(task)
            return {
                "story_arc_summary": "Stubbed arc",
                "slides": [
                    {"type": "title", "title": "Stubbed", "author": "Stub"},
                    {
                        "type": "text",
                        "title": "Stub bullets",
                        "bullets": ["one", "two"],
                        "citations": ["10.1/foundations-1990"],
                    },
                ],
            }

        plan = generate_deck_plan(
            topic="trial",
            corpus=synth_corpus,
            summaries=synth_summaries,
            figure_assignments=fig_assignments,
            speaker="Bobby Ni",
            kb_root=tmp_path,
            plan_callback=stub_callback,
        )
        assert len(captured) == 1
        assert captured[0].topic == "trial"
        assert plan["story_arc_summary"] == "Stubbed arc"
        # title + text + auto-references = 3
        types = [s["type"] for s in plan["slides"]]
        assert types == ["title", "text", "references"]

    def test_raises_when_no_callback_and_fallback_disabled(
        self, synth_corpus, synth_summaries, tmp_path
    ):
        with pytest.raises(ValueError):
            generate_deck_plan(
                topic="trial",
                corpus=synth_corpus,
                summaries=synth_summaries,
                kb_root=tmp_path,
                plan_callback=None,
                fallback_to_mechanical=False,
            )


# ---------------------------------------------------------------------------
# End-to-end: stub callback -> build_from_plan -> .pptx exists
# ---------------------------------------------------------------------------


class TestEndToEnd:
    def test_stub_callback_to_pptx(self, synth_corpus, synth_summaries, fig_assignments, tmp_path):
        """Synthetic corpus + stub plan_callback -> build_from_plan -> .pptx."""
        pytest.importorskip("PIL")
        pptx = pytest.importorskip("pptx")
        from PIL import Image

        # Make the fig_assignments actual real PNGs (the fixture only writes
        # PNG headers; build_from_plan's renderer needs decodable images).
        for p in fig_assignments.values():
            Image.new("RGB", (200, 150), "red").save(str(p))

        def stub_callback(task: DeckPlanTask) -> dict:
            # Pick 5 papers, 7-slide arc.
            return {
                "story_arc_summary": "Arc through five papers.",
                "slides": [
                    {
                        "type": "title",
                        "title": "Trial topic",
                        "subtitle": "Smoke",
                        "author": task.speaker or "Bobby",
                    },
                    {"type": "section_divider", "title": "Background"},
                    {
                        "type": "figure",
                        "title": "Foundational",
                        "image_path": str(fig_assignments["10.1/foundations-1990"]),
                        "claim_paper_doi": "10.1/foundations-1990",
                        "figure_paper_doi": "10.1/foundations-1990",
                        "caption": "The 1990 foundation.",
                        "bullets": ["Established mechanism A"],
                    },
                    {"type": "section_divider", "title": "SOTA"},
                    {
                        "type": "figure",
                        "title": "Modern system",
                        "image_path": str(fig_assignments["10.1/sota-2024"]),
                        "claim_paper_doi": "10.1/sota-2024",
                        "figure_paper_doi": "10.1/sota-2024",
                        "caption": "The 2024 SOTA.",
                        "bullets": ["Refined mechanism A"],
                    },
                    {
                        "type": "text",
                        "title": "Conclusions",
                        "bullets": ["Long arc", "Three eras"],
                        "citations": ["10.1/breakthrough-2014"],
                    },
                ],
            }

        plan = generate_deck_plan(
            topic="trial topic",
            corpus=synth_corpus,
            summaries=synth_summaries,
            figure_assignments=fig_assignments,
            speaker="Bobby Ni",
            affiliation="Hickey Lab",
            kb_root=tmp_path,
            plan_callback=stub_callback,
        )
        # Slide titles in order
        slide_titles = [s.get("title") for s in plan["slides"]]
        assert "Trial topic" in slide_titles
        assert "Foundational" in slide_titles
        assert "Modern system" in slide_titles
        assert "References" in slide_titles

        # Render to .pptx
        from vaultlab.slides.template import lab_template_path

        if lab_template_path() is None:
            pytest.skip("Hickey Lab template not bundled")

        from vaultlab.slides import build_from_plan

        out = tmp_path / "deck.pptx"
        result = build_from_plan(plan, out, write_marp=False)
        assert result["pptx"] == out
        assert out.exists()
        assert out.stat().st_size > 0

        prs = pptx.Presentation(str(out))
        # 6 LLM slides + 1 references = 7
        assert len(prs.slides) == 7


# ---------------------------------------------------------------------------
# Schema function
# ---------------------------------------------------------------------------


def test_deck_plan_response_schema_is_dict():
    schema = deck_plan_response_schema()
    assert isinstance(schema, dict)
    assert schema["type"] == "object"
    assert "slides" in schema["required"]


def test_deck_plan_response_schema_has_no_references_type():
    """References slide is auto-generated; LLM should not emit one."""
    schema = deck_plan_response_schema()
    one_of = schema["properties"]["slides"]["items"]["oneOf"]
    type_consts = {item["properties"]["type"]["const"] for item in one_of}
    assert "references" not in type_consts
