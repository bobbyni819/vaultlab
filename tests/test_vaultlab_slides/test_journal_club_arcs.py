"""Tests for vaultlab.slides.journal_club_arcs — paper-type arc templates."""

from __future__ import annotations

import pytest

from vaultlab.slides.journal_club_arcs import (
    JOURNAL_CLUB_ARCS,
    arc_to_slide_plan,
    classify_paper_type,
    get_arc,
)

# ---------------------------------------------------------------------------
# Registry shape


def test_registry_has_expected_slugs():
    assert {
        "discovery",
        "methods",
        "dataset",
        "clinical",
        "materials",
        "review",
        "journal_club_default",
    } <= set(JOURNAL_CLUB_ARCS)


def test_every_arc_has_required_fields():
    for slug, arc in JOURNAL_CLUB_ARCS.items():
        assert arc["slug"] == slug, slug
        assert arc["name"]
        assert "slides" in arc
        assert (
            len(arc["slides"]) >= 5
        )  # at minimum: context + claim + method + evidence + conclusion
        for slide in arc["slides"]:
            assert slide["title"]
            assert slide["purpose"]
            assert slide["type"] in {"bullets", "figure", "title", "section"}


def test_every_slide_has_unique_title_within_arc():
    for slug, arc in JOURNAL_CLUB_ARCS.items():
        titles = [s["title"] for s in arc["slides"]]
        assert len(titles) == len(set(titles)), f"duplicate titles in {slug}"


# ---------------------------------------------------------------------------
# get_arc


def test_get_arc_returns_deep_copy():
    arc1 = get_arc("discovery")
    arc2 = get_arc("discovery")
    arc1["slides"][0]["title"] = "MUTATED"
    assert arc2["slides"][0]["title"] != "MUTATED"


def test_get_arc_unknown_slug_raises():
    with pytest.raises(KeyError, match="Unknown paper-type slug"):
        get_arc("not_a_real_type")


def test_get_arc_english_default():
    arc = get_arc("methods")
    assert arc["language"] == "en"
    assert "current bottleneck" in arc["slides"][0]["title"].lower()


def test_get_arc_chinese_variant_translates_titles():
    arc = get_arc("methods", language="zh-CN")
    assert arc["language"] == "zh-CN"
    # The first slide of methods is "The current bottleneck" → "当前技术瓶颈"
    assert arc["slides"][0]["title"] == "当前技术瓶颈"


def test_get_arc_chinese_falls_through_untranslated():
    """If a title isn't in the translation table, it stays as-is."""
    arc = get_arc("journal_club_default", language="zh-CN")
    # All titles for journal_club_default are in the translation table,
    # but the function shouldn't blow up if any aren't.
    assert arc["language"] == "zh-CN"


# ---------------------------------------------------------------------------
# arc_to_slide_plan


def test_arc_to_slide_plan_inserts_title_slide():
    arc = get_arc("dataset")
    plan = arc_to_slide_plan(
        arc, deck_title="Tabula Sapiens 2.0", deck_subtitle="Atlas of 200 organs"
    )
    assert plan["title"] == "Tabula Sapiens 2.0"
    assert plan["subtitle"] == "Atlas of 200 organs"
    assert plan["arc_slug"] == "dataset"
    assert plan["arc_logic"] == "workflow-to-validation"
    # First slide should be the title slide
    assert plan["slides"][0]["type"] == "title"
    assert plan["slides"][0]["title"] == "Tabula Sapiens 2.0"
    # Subsequent slides come from the arc
    assert plan["slides"][1]["title"] == "Why this resource was needed"


def test_arc_to_slide_plan_preserves_purpose_metadata():
    arc = get_arc("discovery")
    plan = arc_to_slide_plan(arc)
    purposes = [s.get("_purpose") for s in plan["slides"][1:]]
    assert "context" in purposes
    assert "claim" in purposes
    assert "evidence" in purposes


def test_arc_to_slide_plan_with_chinese_arc():
    arc = get_arc("review", language="zh-CN")
    plan = arc_to_slide_plan(arc, deck_title="2026年X领域综述")
    assert plan["language"] == "zh-CN"
    assert plan["slides"][1]["title"] == "为什么这个话题现在重要"


# ---------------------------------------------------------------------------
# classify_paper_type


def test_classify_explicit_paper_type():
    assert classify_paper_type({"paper_type": "methods"}) == "methods"
    assert classify_paper_type({"paper_type": "Discovery"}) == "discovery"


def test_classify_dataset_paper():
    assert classify_paper_type({"title": "A spatial atlas of mouse organs"}) == "dataset"
    assert classify_paper_type({"abstract": "We present a benchmark for X."}) == "dataset"


def test_classify_clinical_paper():
    assert (
        classify_paper_type({"abstract": "A randomized phase III trial of drug X."}) == "clinical"
    )


def test_classify_methods_paper():
    assert classify_paper_type({"title": "X: a deep learning framework for Y"}) == "methods"


def test_classify_materials_paper():
    assert (
        classify_paper_type({"abstract": "Synthesis and characterization of a new alloy."})
        == "materials"
    )


def test_classify_review_paper():
    assert classify_paper_type({"title": "Review of X in 2026"}) == "review"
    assert classify_paper_type({"abstract": "We present a perspective on Y."}) == "review"


def test_classify_discovery_paper():
    assert classify_paper_type({"abstract": "We discover a novel mechanism."}) == "discovery"


def test_classify_falls_back_to_default():
    assert (
        classify_paper_type({"title": "Some neutral paper title", "abstract": "blah."})
        == "journal_club_default"
    )


def test_classify_explicit_overrides_keyword():
    """Explicit paper_type overrides keyword detection."""
    md = {
        "paper_type": "methods",
        "abstract": "A randomized phase III clinical trial.",  # would otherwise classify as clinical
    }
    assert classify_paper_type(md) == "methods"


# ---------------------------------------------------------------------------
# Conclusion-first title rule (sanity)


def test_titles_are_conclusion_like_not_section_labels():
    """No arc should have a slide titled "Background", "Discussion",
    "Conclusion" or other section-label headings — titles should describe
    what the slide claims, not what section of the paper it's from.
    """
    forbidden = {"background", "discussion", "conclusion", "methods", "results", "introduction"}
    for slug, arc in JOURNAL_CLUB_ARCS.items():
        for slide in arc["slides"]:
            title = slide["title"].strip().lower()
            assert title not in forbidden, (
                f"{slug} has bare section-label title: {slide['title']!r}"
            )
