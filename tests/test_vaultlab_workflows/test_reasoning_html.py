"""Tests for vaultlab.workflows.reasoning_html — reasoning-chain HTML."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from vaultlab.workflows.reasoning_html import (
    build_reasoning_report_html,
    write_reasoning_report,
)


@pytest.fixture
def sample_result() -> dict:
    return {
        "purpose": "rigor-audit",
        "crosstalk_status": "complete",
        "runtime_seconds": 42.7,
        "rounds": [
            {
                "role_id": "data_analyst",
                "prompt": "Audit the deck for rigor.",
                "output": "Found 3 issues in slides 2 and 3.",
            },
            {
                "role_id": "literature_critic",
                "prompt": "Are the claims supported?",
                "output": "Claim on slide 5 is overclaimed.",
            },
            {
                "role_id": "synthesizer",
                "prompt": "Integrate.",
                "output": json.dumps(
                    {"passed": False, "issues": [{"loc": "Slide 2", "severity": "major"}]}
                ),
            },
        ],
        "final_output": {
            "passed": False,
            "issues": [
                {"loc": "Slide 2", "severity": "major", "fix": "Cite source"},
            ],
        },
    }


def test_renders_basic_report(sample_result):
    html = build_reasoning_report_html(sample_result, topic="multi-lung audit")
    assert "<!doctype html>" in html
    assert "multi-lung audit" in html
    assert "3 turns" in html
    assert "rigor-audit" in html


def test_renders_status_chips(sample_result):
    html = build_reasoning_report_html(sample_result)
    assert ">complete<" in html
    assert "42.7s" in html or "42.7" in html


def test_renders_per_round_with_role_chips(sample_result):
    html = build_reasoning_report_html(sample_result)
    assert "data_analyst" in html
    assert "literature_critic" in html
    assert "synthesizer" in html
    # Role-attribution stat line should also include the counts.
    assert "× 1" in html


def test_last_round_is_open_by_default(sample_result):
    html = build_reasoning_report_html(sample_result)
    # The last <details> in the rounds section should have the open attribute
    # (we check both that *some* details are open and that the synthesizer
    # output appears).
    assert " open>" in html
    assert "passed" in html  # synthesizer JSON content


def test_synthesizer_json_pretty_printed(sample_result):
    html = build_reasoning_report_html(sample_result)
    # JSON quotes are HTML-escaped after pretty-printing.
    assert "&quot;passed&quot;: false" in html
    assert "&quot;severity&quot;" in html


def test_final_output_block_present(sample_result):
    html = build_reasoning_report_html(sample_result)
    assert "Final synthesized output" in html
    assert "Cite source" in html


def test_handles_dataclass_input():
    """Should accept any object exposing `rounds`, `final_output`, etc."""

    class FakeResult:
        rounds = [{"role_id": "x", "prompt": "p", "output": "o"}]
        final_output = {"k": "v"}
        crosstalk_status = "complete"
        purpose = "test"
        runtime_seconds = 0.0

    html = build_reasoning_report_html(FakeResult())
    assert "<!doctype html>" in html
    assert ">x<" in html or "&gt;x&lt;" in html


def test_handles_empty_rounds():
    html = build_reasoning_report_html({"rounds": [], "final_output": {}, "purpose": "x"})
    assert "No rounds recorded" in html


def test_xss_safe_against_evil_output():
    result = {
        "purpose": "x",
        "crosstalk_status": "complete",
        "rounds": [
            {
                "role_id": "data_analyst",
                "prompt": "<script>alert(1)</script>",
                "output": "<img src=x onerror=alert(1)>",
            }
        ],
        "final_output": {},
    }
    html = build_reasoning_report_html(result)
    assert "<script>alert(1)</script>" not in html
    assert "<img src=x onerror" not in html
    assert "&lt;script&gt;" in html


def test_write_reasoning_report(tmp_path: Path, sample_result):
    out = tmp_path / "reasoning.html"
    written = write_reasoning_report(out, sample_result)
    assert written == out
    assert out.exists()


def test_handles_non_json_output_as_prose():
    result = {
        "purpose": "x",
        "crosstalk_status": "complete",
        "rounds": [
            {"role_id": "narrator", "prompt": "p", "output": "Just prose, not JSON."},
        ],
        "final_output": {},
    }
    html = build_reasoning_report_html(result)
    assert "Just prose, not JSON." in html
    # Should NOT have <pre> for prose
    assert "background:#" in html  # the prose div uses inline bg style


def test_role_color_attribution(sample_result):
    """Different roles get different colors. data_analyst (blue) vs synthesizer (purple)."""
    html = build_reasoning_report_html(sample_result)
    # data_analyst should use the blue-ish color
    assert "#0369a1" in html  # data_analyst fg
    # synthesizer uses purple
    assert "#5b21b6" in html
    # literature_critic uses rose
    assert "#9f1239" in html
