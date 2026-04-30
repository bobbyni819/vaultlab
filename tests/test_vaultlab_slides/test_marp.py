"""Tests for vaultlab.slides.marp — Marp markdown mirror.

Ported from ``bobby-tools/tests/test_bobby_slides/test_marp.py``.
"""
from __future__ import annotations

from vaultlab.slides.marp import deck_plan_to_marp, write_marp


def _basic_plan():
    return {
        "title": "Test Talk",
        "author": "Bobby Ni",
        "slides": [
            {"type": "title", "title": "Test Talk", "subtitle": "Sub", "author": "Bobby Ni"},
            {"type": "section_divider", "title": "Background"},
            {
                "type": "figure",
                "title": "Figure 1",
                "image_path": "fig1.png",
                "caption": "A test figure",
                "bullets": ["n=100", "p<0.001"],
                "citation_source": "Smith et al., 2024",
            },
            {
                "type": "multi_figure",
                "title": "Multi panels",
                "figures": [
                    {"path": "a.png", "label": "A", "caption": "Panel A"},
                    {"path": "b.png", "label": "B", "caption": "Panel B"},
                ],
            },
            {"type": "text", "title": "Methods", "bullets": ["Step 1", "Step 2"]},
            {"type": "references", "references": ["Smith et al., 2024", "Jones, 2023"]},
        ],
    }


class TestRender:
    def test_includes_marp_frontmatter(self):
        result = deck_plan_to_marp(_basic_plan())
        assert "marp: true" in result
        assert "size: 16:9" in result
        assert "paginate: true" in result

    def test_separates_slides_with_dashes(self):
        result = deck_plan_to_marp(_basic_plan())
        body = result.split("---", 2)[-1]
        assert body.count("\n---\n") == 5

    def test_renders_title_slide(self):
        result = deck_plan_to_marp(_basic_plan())
        assert "# Test Talk" in result
        assert "## Sub" in result
        assert "**Bobby Ni**" in result

    def test_renders_section_divider(self):
        result = deck_plan_to_marp(_basic_plan())
        assert "# Background" in result

    def test_renders_figure_slide(self):
        result = deck_plan_to_marp(_basic_plan())
        assert "## Figure 1" in result
        assert "![](fig1.png)" in result
        assert "*A test figure*" in result
        assert "- n=100" in result
        assert "Source: Smith et al., 2024" in result

    def test_renders_multi_figure(self):
        result = deck_plan_to_marp(_basic_plan())
        assert "## Multi panels" in result
        assert "![](a.png)" in result
        assert "![](b.png)" in result
        assert "**A**" in result
        assert "**B**" in result

    def test_renders_text_slide(self):
        result = deck_plan_to_marp(_basic_plan())
        assert "## Methods" in result
        assert "- Step 1" in result

    def test_renders_references(self):
        result = deck_plan_to_marp(_basic_plan())
        assert "## References" in result
        assert "- Smith et al., 2024" in result
        assert "- Jones, 2023" in result


class TestSpeakerNotes:
    def test_renders_speaker_notes_as_html_comment(self):
        plan = {
            "title": "T",
            "slides": [{
                "type": "text",
                "title": "Slide",
                "bullets": ["b"],
                "speaker_notes": {"hook": "H", "transition": "T"},
            }],
        }
        result = deck_plan_to_marp(plan)
        assert "<!--" in result
        assert "HOOK: H" in result
        assert "TRANSITION: T" in result
        assert "-->" in result

    def test_no_notes_no_comment(self):
        plan = {
            "title": "T",
            "slides": [{"type": "text", "title": "Slide", "bullets": ["b"]}],
        }
        result = deck_plan_to_marp(plan)
        assert "<!--" not in result


class TestWriteMarp:
    def test_writes_file(self, tmp_path):
        out = tmp_path / "deck.md"
        result = write_marp(_basic_plan(), out)
        assert result == out
        assert out.exists()
        assert "marp: true" in out.read_text(encoding="utf-8")

    def test_creates_parent_dir(self, tmp_path):
        out = tmp_path / "nested" / "deeper" / "deck.md"
        write_marp(_basic_plan(), out)
        assert out.exists()


class TestUnknownSlideType:
    def test_unknown_type_falls_back_to_text(self):
        plan = {
            "slides": [{"type": "weird_type", "title": "W", "bullets": ["b"]}],
        }
        result = deck_plan_to_marp(plan)
        assert "## W" in result
