"""Tests for vaultlab.report — HTML primitive + 15 components.

These are deterministic string-level tests. No browser rendering. Visual
verification is a manual step (Bobby opens the file).
"""

from __future__ import annotations

import html.parser
from pathlib import Path

import pytest

from vaultlab.report import components as c
from vaultlab.report import render_report, write_report


class _Validator(html.parser.HTMLParser):
    """Minimal HTML parser to verify output is well-formed enough to parse
    without raising. Doesn't enforce strict XHTML — just makes sure there
    are no broken tags."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tag_depth = 0
        self.errors: list[str] = []

    def handle_starttag(self, tag: str, attrs):
        if tag not in ("br", "hr", "img", "meta", "link", "input", "circle", "line"):
            self.tag_depth += 1

    def handle_endtag(self, tag: str):
        self.tag_depth -= 1
        if self.tag_depth < 0:
            self.errors.append(f"Unmatched end tag: {tag}")


def _parses(html_str: str) -> bool:
    v = _Validator()
    v.feed(html_str)
    return not v.errors


# ---------------------------------------------------------------------------
# render_report


def test_render_report_minimal():
    out = render_report(title="Test", sections=["<p>hello</p>"])
    assert out.startswith("<!doctype html>")
    assert "<title>Test</title>" in out
    assert "<h1>Test</h1>" in out
    assert "<p>hello</p>" in out
    assert "vaultlab.report · generated" in out
    assert _parses(out)


def test_render_report_escapes_title():
    out = render_report(title="<script>x</script>", sections=[])
    assert "<script>x</script>" not in out
    assert "&lt;script&gt;" in out


def test_render_report_with_all_options():
    out = render_report(
        title="Full report",
        sections=["<section>a</section>"],
        eyebrow="vaultlab · audit",
        subtitle="Run 2026-05-12",
        meta="meta band",
        theme="dark",
        footer="custom footer",
    )
    assert 'data-theme="dark"' in out
    # eyebrow seeds the breadcrumb trail (split on the · / separators)
    assert 'class="breadcrumb"' in out
    assert ">audit<" in out
    assert "Run 2026-05-12" in out
    assert "meta band" in out
    assert "custom footer" in out


def test_render_report_omits_js_when_disabled():
    out = render_report(title="static", sections=[], include_js=False)
    assert "<script>" not in out


def test_write_report(tmp_path: Path):
    p = tmp_path / "sub" / "out.html"
    written = write_report(p, title="W", sections=["<p>x</p>"])
    assert written == p
    assert p.exists()
    text = p.read_text(encoding="utf-8")
    assert "<title>W</title>" in text


# ---------------------------------------------------------------------------
# Component primitives


def test_status_chip():
    # legacy good/bad normalise to the colorblind-safe pass/fail levels
    assert 'class="vl-chip pass"' in c.status_chip("ok", "good")
    assert 'class="vl-chip fail"' in c.status_chip("fail", "bad")
    assert 'class="vl-chip info"' in c.status_chip("review", "info")
    # every chip carries a glyph
    assert "vl-chip__g" in c.status_chip("ok", "pass")
    # XSS guard
    assert "<script>" not in c.status_chip("<script>x</script>")


def test_tldr_box_list():
    out = c.tldr_box(["a", "b", "c"])
    assert "<ul>" in out
    assert "<li>a</li>" in out
    assert "vl-tldr" in out


def test_tldr_box_string():
    out = c.tldr_box("first para\n\nsecond para")
    assert "<p>first para</p>" in out
    assert "<p>second para</p>" in out


def test_severity_card():
    out = c.severity_card(
        "Slide 3",
        body="overflow warning",
        severity="warn",
        badges=[("title", "warn")],
        actions=[("Copy", "x"), ("Open", "y")],
        filter_key="warn",
    )
    assert "severity-warn" in out
    assert 'data-filter-key="warn"' in out
    assert 'data-copy="x"' in out
    assert 'data-copy="y"' in out
    assert "Slide 3" in out


def test_severity_card_thumbnail():
    out = c.severity_card("S1", thumbnail="thumb.png")
    assert '<img class="thumb" src="thumb.png"' in out


def test_card_grid():
    cards = [c.severity_card(f"S{i}") for i in range(3)]
    out = c.card_grid(cards)
    # Three individual cards inside the wrapper. Match the exact card class.
    assert out.count('class="vl-card"') == 3
    assert "vl-cards" in out


def test_matrix_table():
    out = c.matrix_table(["A", "B"], [["1", "2"], ["3", "4"]])
    assert "<th>A</th>" in out
    assert "<td>1</td>" in out
    assert "<td>4</td>" in out


def test_compare_panel():
    out = c.compare_panel("L", "<p>left</p>", "R", "<p>right</p>")
    assert "vl-compare" in out
    assert "<p>left</p>" in out
    assert "<p>right</p>" in out


def test_collapsible_step():
    out = c.collapsible_step(
        "Step 1", "<p>body</p>", file_path="x.py", line=42, open_by_default=True
    )
    assert "<details" in out
    assert " open" in out
    assert "x.py:42" in out
    assert "<p>body</p>" in out


def test_tabbed_block():
    out = c.tabbed_block({"Python": "<code>py</code>", "YAML": "<code>yml</code>"})
    assert "vl-tabs" in out
    assert "Python" in out
    assert "YAML" in out
    assert out.count("vl-tab-pane") >= 2


def test_timeline_tuple_input():
    out = c.timeline([("12:00", "Start", "started"), ("12:05", "End", "ended")])
    assert "12:00" in out
    assert "Start" in out
    assert "started" in out


def test_timeline_event_input():
    out = c.timeline([c.TimelineEvent("t1", "L", "B")])
    assert "t1" in out
    assert "L" in out


def test_svg_arg_graph():
    nodes = [
        {"id": "a", "x": 100, "y": 100, "label": "A"},
        {"id": "b", "x": 200, "y": 100, "label": "B"},
    ]
    edges = [("a", "b")]
    out = c.svg_arg_graph(nodes, edges, hot_path=["a", "b"])
    assert "<svg" in out
    assert "<circle" in out
    assert "edge hot" in out
    assert ">A<" in out


def test_kanban_board():
    out = c.kanban_board(
        ["Now", "Next", "Later", "Cut"],
        {"Now": ["fix bug", "ship"], "Next": ["polish"]},
    )
    assert "vl-kanban" in out
    assert "vl-col" in out
    assert "fix bug" in out
    assert "Copy as markdown" in out
    assert "Copy as JSON" in out


def test_template_editor():
    out = c.template_editor(
        template="Hello {{name}}, you are {{role}}.",
        samples=[{"name": "Bobby", "role": "PhD"}, {"name": "Ana", "role": "MD"}],
        sample_titles=["S1", "S2"],
    )
    assert "<textarea>" in out
    assert "Hello {{name}}" in out
    assert "data-context" in out


def test_margin_glossary():
    out = c.margin_glossary("Tier-A", "Full-text PDF read with synthesis")
    assert "Tier-A" in out
    assert "synthesis" in out
    assert "vl-gloss" in out


def test_keynav_deck():
    out = c.keynav_deck([("Slide 1", "<p>a</p>"), ("Slide 2", "<p>b</p>")])
    assert 'class="vl-deck"' in out
    assert "Slide 1" in out
    assert "Slide 2" in out
    assert "Prev" in out
    assert "Next" in out
    assert "1 / 2" in out


def test_filter_bar():
    out = c.filter_bar(
        [("All", "all"), ("Errors", "bad")],
        target_selector=".vl-cards .vl-card",
    )
    assert "vl-filter" in out
    assert 'data-target=".vl-cards .vl-card"' in out
    assert 'data-filter="all"' in out


def test_section_wrapper():
    out = c.section("Title", "<p>a</p>", "<p>b</p>")
    assert "<h2>Title</h2>" in out
    assert "<p>a</p>" in out
    assert "<p>b</p>" in out


def test_section_no_title():
    out = c.section(None, "<p>a</p>")
    assert "<h2>" not in out
    assert "<p>a</p>" in out


# ---------------------------------------------------------------------------
# Integration: full report renders cleanly


def test_full_report_round_trip():
    sections = [
        c.tldr_box(["A", "B", "C"]),
        c.section(
            "Cards",
            c.filter_bar([("All", "all"), ("Warn", "warn")], target_selector=".vl-cards .vl-card"),
            c.card_grid(
                [
                    c.severity_card(
                        f"Item {i}",
                        body="body",
                        severity="warn",
                        filter_key="warn",
                    )
                    for i in range(3)
                ]
            ),
        ),
        c.section(
            "Compare",
            c.compare_panel("L", "<pre>old</pre>", "R", "<pre>new</pre>"),
        ),
        c.section(
            "Editor",
            c.template_editor(
                template="Hi {{x}}",
                samples=[{"x": "a"}, {"x": "b"}],
            ),
        ),
        c.section("Deck", c.keynav_deck([("a", "1"), ("b", "2")])),
    ]
    html_str = render_report(title="Integration", sections=sections)
    assert _parses(html_str)
    # Sanity: all major components made it into the output.
    for needle in (
        "vl-tldr",
        "vl-cards",
        "vl-card",
        "vl-filter",
        "vl-compare",
        "vl-editor",
        "vl-deck",
    ):
        assert needle in html_str


def test_no_external_assets():
    """Output is self-contained — no remote URLs, no @import, no <link href=>."""
    html_str = render_report(title="x", sections=[])
    forbidden = ["cdn.", "jsdelivr", "unpkg", "@import", "<link href"]
    for needle in forbidden:
        assert needle not in html_str, f"unexpected external asset: {needle}"


def test_print_friendly_css_present():
    html_str = render_report(title="x", sections=[])
    assert "@media print" in html_str


def test_mobile_responsive_css_present():
    html_str = render_report(title="x", sections=[])
    assert "@media (max-width: 720px)" in html_str
