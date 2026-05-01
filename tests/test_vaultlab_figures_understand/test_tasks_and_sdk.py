"""Tests for figure-understand tasks + SDK callbacks (production wiring).

Round 3 of the figure-understand build (agent #82's framework lacked
production callsites). These tests cover:

- :mod:`vaultlab.figures.understand._tasks` — prepare/render helpers and
  task dataclasses.
- :mod:`vaultlab.figures.understand._sdk` — Anthropic SDK-backed
  callbacks. The SDK client is stubbed in every test; we never hit the
  real API in pytest. The real-API smoke test lives in
  ``scripts/_demo_understand_via_sdk_2026-04-30.py``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

# Match the gating used by tests/test_log.py — these tests build small
# synthetic figures via numpy / PIL.
np = pytest.importorskip("numpy")
pytest.importorskip("PIL")
pytest.importorskip("skimage")

from PIL import Image  # noqa: E402

from vaultlab.figures.understand import (  # noqa: E402
    ColorMotif,
    Region,
    VerificationIteration,
    prepare_describe_task,
    prepare_match_task,
    prepare_verify_task,
    render_describe_from_response,
    render_match_from_response,
    render_verify_from_response,
)
from vaultlab.figures.understand._sdk import (  # noqa: E402
    describe_via_sdk,
    match_via_sdk,
    understand_figure_via_sdk,
    verify_via_sdk,
)


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


def _synthetic_figure(tmp_path: Path) -> Path:
    """Tiny figure with one neon-green block (so localize finds 1 region)."""
    img = np.full((400, 400, 3), 255, dtype=np.uint8)
    img[100:160, 100:160] = (50, 230, 50)
    p = tmp_path / "fig.png"
    Image.fromarray(img).save(p)
    return p


class _FakeBlock:
    def __init__(self, text: str) -> None:
        self.type = "text"
        self.text = text


class _FakeResponse:
    def __init__(self, text: str) -> None:
        self.content = [_FakeBlock(text)]


class _StubAnthropicClient:
    """Stand-in for ``anthropic.Anthropic`` — never hits the network.

    Hand it a ``reply`` (string returned for every call) or a list of
    replies (consumed in order). It records each call so tests can assert
    on the prompt / model / image content.
    """

    def __init__(self, reply: str | list[str]) -> None:
        if isinstance(reply, str):
            self._replies = [reply]
            self._cycle = True
        else:
            self._replies = list(reply)
            self._cycle = False
        self.calls: list[dict[str, Any]] = []
        # ``messages`` mirrors the real SDK shape: client.messages.create(...).
        self.messages = self  # type: ignore[assignment]

    def create(self, **kwargs: Any) -> _FakeResponse:
        self.calls.append(kwargs)
        if not self._replies:
            raise AssertionError("StubAnthropicClient: out of pre-canned replies")
        if self._cycle:
            return _FakeResponse(self._replies[0])
        return _FakeResponse(self._replies.pop(0))


# ---------------------------------------------------------------------------
# prepare_* tests (no LLM at all)
# ---------------------------------------------------------------------------


def test_prepare_describe_task_includes_paper_tldr_in_prompt(tmp_path: Path) -> None:
    fig = _synthetic_figure(tmp_path)
    task = prepare_describe_task(
        fig,
        paper_doi="10.1234/foo",
        paper_tldr="This paper introduces CODEX, a multiplexed-imaging method.",
    )
    assert task.figure_path == fig
    assert task.paper_doi == "10.1234/foo"
    assert "CODEX" in task.prompt
    assert "10.1234/foo" in task.prompt
    # Schema contract is stable.
    assert task.response_schema["required"] == ["description", "elements"]
    # System prompt is non-trivial.
    assert task.system.strip()


def test_prepare_match_task_lists_region_ids_and_motifs(tmp_path: Path) -> None:
    fig = _synthetic_figure(tmp_path)
    regions = [
        Region(motif_name="neon-green", bbox_px=(100, 100, 160, 160), area_px=3600, centroid_px=(130, 130)),
        Region(motif_name="orange", bbox_px=(50, 200, 80, 230), area_px=900, centroid_px=(65, 215)),
    ]
    task = prepare_match_task(
        fig,
        description="A green square top-left and an orange square mid-left.",
        described_elements=["green square", "orange square"],
        regions=regions,
    )
    assert "r0" in task.prompt and "r1" in task.prompt
    assert "neon-green" in task.prompt
    assert "orange" in task.prompt
    assert task.response_schema["required"] == ["matches"]


def test_prepare_verify_task_carries_iteration_and_expected_elements(tmp_path: Path) -> None:
    fig = _synthetic_figure(tmp_path)
    task = prepare_verify_task(
        fig, iteration=3, expected_elements=["green square", "orange square"]
    )
    assert task.iteration == 3
    assert "green square" in task.prompt
    assert "VERIFY ITERATION: 3" in task.prompt
    assert "ACCEPT" in task.prompt and "RETRY_LOCALIZE" in task.prompt


# ---------------------------------------------------------------------------
# render_*_from_response tests
# ---------------------------------------------------------------------------


def test_render_describe_handles_dict_and_json_string(tmp_path: Path) -> None:
    fig = _synthetic_figure(tmp_path)
    task = prepare_describe_task(fig, paper_doi="10/x", paper_tldr="")
    desc, elements = render_describe_from_response(
        {"description": "A green square.", "elements": ["green square"]}, task
    )
    assert desc == "A green square."
    assert elements == ["green square"]
    desc2, elements2 = render_describe_from_response(
        '{"description": "x", "elements": ["a", "b"]}', task
    )
    assert desc2 == "x" and elements2 == ["a", "b"]
    # Bad input -> safe defaults.
    assert render_describe_from_response(None, task) == ("", [])
    assert render_describe_from_response("not json", task) == ("", [])


def test_render_match_drops_invalid_region_ids(tmp_path: Path) -> None:
    fig = _synthetic_figure(tmp_path)
    regions = [
        Region("green", (10, 10, 30, 30), 400, (20, 20)),
        Region("orange", (50, 50, 70, 70), 400, (60, 60)),
    ]
    task = prepare_match_task(
        fig, description="d", described_elements=["a", "b"], regions=regions
    )
    response = {
        "matches": [
            {"element_name": "a", "matched_region_id": "r0", "rationale": "ok", "confidence": 0.9},
            {"element_name": "b", "matched_region_id": "r99", "rationale": "wrong", "confidence": 0.5},
            {"element_name": "c", "matched_region_id": "rZ", "rationale": "fab", "confidence": 0.1},
        ]
    }
    out = render_match_from_response(response, task)
    assert len(out) == 1
    assert out[0]["matched_region_id"] == "r0"
    assert out[0]["confidence"] == pytest.approx(0.9)


def test_render_verify_invalid_decision_falls_back_to_give_up(tmp_path: Path) -> None:
    fig = _synthetic_figure(tmp_path)
    task = prepare_verify_task(fig, iteration=2, expected_elements=["x"])
    out = render_verify_from_response(
        {"annotated_image_read": "looks fine", "issues_found": [], "decision": "MAYBE"},
        task,
    )
    assert isinstance(out, VerificationIteration)
    assert out.decision == "GIVE_UP"
    assert out.iteration == 2

    # None response -> still returns a structured iteration (GIVE_UP).
    out_none = render_verify_from_response(None, task)
    assert out_none.decision == "GIVE_UP"
    assert "missing or non-JSON" in out_none.annotated_image_read


# ---------------------------------------------------------------------------
# SDK callback tests (stubbed client; never hits the network)
# ---------------------------------------------------------------------------


def test_describe_via_sdk_returns_text_for_real_image(tmp_path: Path) -> None:
    fig = _synthetic_figure(tmp_path)
    task = prepare_describe_task(fig, paper_doi="10/x", paper_tldr="ctx")
    client = _StubAnthropicClient(
        '{"description": "single green square in the upper-left", '
        '"elements": ["green square"]}'
    )
    out = describe_via_sdk(task, client=client)
    assert isinstance(out, str)
    assert "green square" in out
    # SDK was called exactly once with the figure encoded as image content.
    assert len(client.calls) == 1
    user_blocks = client.calls[0]["messages"][0]["content"]
    types = [b.get("type") for b in user_blocks]
    assert "image" in types
    assert "text" in types


def test_match_via_sdk_handles_empty_regions(tmp_path: Path) -> None:
    fig = _synthetic_figure(tmp_path)
    task = prepare_match_task(
        fig, description="nothing visible", described_elements=[], regions=[]
    )
    client = _StubAnthropicClient('{"matches": []}')
    out = match_via_sdk(task, client=client)
    assert out == []
    assert len(client.calls) == 1


def test_verify_via_sdk_returns_verification_iteration(tmp_path: Path) -> None:
    fig = _synthetic_figure(tmp_path)
    task = prepare_verify_task(fig, iteration=1, expected_elements=["green square"])
    client = _StubAnthropicClient(
        '{"annotated_image_read": "box on green square", "issues_found": [], '
        '"decision": "ACCEPT"}'
    )
    out = verify_via_sdk(task, client=client)
    assert isinstance(out, VerificationIteration)
    assert out.decision == "ACCEPT"
    assert out.iteration == 1
    assert out.issues_found == []


def test_understand_figure_via_sdk_smoke_with_stubbed_client(tmp_path: Path) -> None:
    """Full pipeline using a stubbed SDK — verifies wiring + log rendering.

    The stub returns three replies in order: describe, match, verify.
    """
    fig = _synthetic_figure(tmp_path)
    motif = ColorMotif("neon-green", (90, 145), 0.40, 0.40, 0.0001)
    annotated = tmp_path / "fig.annotated.png"

    replies = [
        # Step 1 (describe)
        '{"description": "single neon-green square upper-left", '
        '"elements": ["neon-green square"]}',
        # Step 3 (match)
        '{"matches": [{"element_name": "neon-green square", '
        '"matched_region_id": "r0", "rationale": "only green region", '
        '"confidence": 0.95}]}',
        # Step 4 (verify) — accept on first iteration
        '{"annotated_image_read": "marker on the green square", '
        '"issues_found": [], "decision": "ACCEPT"}',
    ]
    client = _StubAnthropicClient(replies)

    annotations, log = understand_figure_via_sdk(
        fig,
        [motif],
        paper_doi="10.1234/sdk.smoke",
        paper_tldr="A synthetic test figure with one green square.",
        annotated_png_path=annotated,
        client=client,
    )

    # Three SDK calls: describe + match + verify.
    assert len(client.calls) == 3
    # Pipeline produced one annotation.
    assert len(annotations) == 1
    assert annotations[0].label == "neon-green square"
    # Log captures all four steps with real content.
    assert "neon-green square" in log.step1_description
    assert log.step3_matches[0]["matched_region_id"] == "r0"
    assert log.step4_verifications[-1].decision == "ACCEPT"
    assert log.final_state == "success"
    # Annotated PNG was rendered next to the source figure.
    assert annotated.exists()


def test_understand_figure_via_sdk_skip_verify_path(tmp_path: Path) -> None:
    """When skip_verify=True, the SDK is called only twice (describe+match)."""
    fig = _synthetic_figure(tmp_path)
    motif = ColorMotif("neon-green", (90, 145), 0.40, 0.40, 0.0001)
    annotated = tmp_path / "fig.annotated.png"

    client = _StubAnthropicClient(
        [
            '{"description": "green square", "elements": ["green square"]}',
            '{"matches": [{"element_name": "green square", '
            '"matched_region_id": "r0", "rationale": "x", "confidence": 0.8}]}',
        ]
    )

    annotations, log = understand_figure_via_sdk(
        fig,
        [motif],
        paper_doi="10.1234/skip.verify",
        annotated_png_path=annotated,
        client=client,
        skip_verify=True,
    )
    # Only 2 SDK calls; no verify pass.
    assert len(client.calls) == 2
    assert len(annotations) == 1
    assert log.step4_verifications == []
    # Log honestly records "partial" because verify was skipped.
    assert log.final_state == "partial"
