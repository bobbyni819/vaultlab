"""Offline tests for the figure-vs-claim semantic verifier.

No network / API key required: the API call is exercised through an injected stub client.
Focus: schema enforcement (an out-of-contract model response is surfaced as a hard
failure, never silently coerced to a verdict) and request shape.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from vaultlab.figures.verify_semantic import (
    VERDICT_VALUES,
    SchemaViolation,
    build_request,
    validate_verdict,
    verify_figure_claim,
)

# A tiny real PNG (1x1) so build_request can base64 a genuine image off disk.
_PNG_1x1 = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
    "890000000a49444154789c6360000002000154a24f8b0000000049454e44ae426082"
)


@pytest.fixture()
def fig(tmp_path: Path) -> Path:
    p = tmp_path / "fig.png"
    p.write_bytes(_PNG_1x1)
    return p


# --- validate_verdict -------------------------------------------------------

def test_validate_verdict_accepts_valid():
    out = validate_verdict(
        {"verdict": "PARTIAL", "evidence_anchors": ["  bar ~7 on axis  ", ""], "confidence": 0.8}
    )
    assert out["verdict"] == "PARTIAL"
    assert out["evidence_anchors"] == ["bar ~7 on axis"]  # trimmed, empties dropped
    assert out["confidence"] == 0.8


@pytest.mark.parametrize(
    "bad",
    [
        {"verdict": "NOPE", "evidence_anchors": ["x"], "confidence": 0.5},          # enum
        {"verdict": "SUPPORTED", "evidence_anchors": [], "confidence": 0.5},        # empty list
        {"verdict": "SUPPORTED", "evidence_anchors": ["", "  "], "confidence": 0.5},  # all blank
        {"verdict": "SUPPORTED", "evidence_anchors": ["x"], "confidence": 1.5},     # > 1
        {"verdict": "SUPPORTED", "evidence_anchors": ["x"], "confidence": -0.1},    # < 0
        {"verdict": "SUPPORTED", "evidence_anchors": ["x"], "confidence": "hi"},    # non-numeric
        {"verdict": "SUPPORTED", "evidence_anchors": ["x"], "confidence": True},    # bool not number
        ["not", "a", "dict"],                                                       # not an object
    ],
)
def test_validate_verdict_rejects(bad):
    with pytest.raises(SchemaViolation):
        validate_verdict(bad)


def test_all_verdict_values_present():
    assert VERDICT_VALUES == ["SUPPORTED", "PARTIAL", "UNSUPPORTED", "FABRICATED"]


# --- build_request ----------------------------------------------------------

def test_build_request_shape(fig: Path):
    req = build_request("the bar is tall", fig, source_pdf=None)
    assert req["model"] == "claude-sonnet-4-6"
    content = req["messages"][0]["content"]
    assert content[0]["type"] == "image"
    assert content[0]["source"]["media_type"] == "image/png"
    assert "the bar is tall" in content[1]["text"]
    # structured-output constraint present; verdict enum is in the schema
    schema = req["output_config"]["format"]["schema"]
    assert schema["properties"]["verdict"]["enum"] == VERDICT_VALUES


def test_build_request_rejects_bad_extension(tmp_path: Path):
    p = tmp_path / "fig.bmp"
    p.write_bytes(_PNG_1x1)
    with pytest.raises(ValueError):
        build_request("c", p)


# --- verify_figure_claim with an injected stub client -----------------------

class _Block:
    def __init__(self, text): self.type, self.text = "text", text


class _Usage:
    input_tokens, output_tokens = 123, 45


class _Resp:
    model = "claude-sonnet-4-6"
    usage = _Usage()
    def __init__(self, text): self.content = [_Block(text)]


class _StubClient:
    """Stub mimicking anthropic.Anthropic().messages.create."""
    def __init__(self, payload_text): self._text = payload_text
    @property
    def messages(self): return self
    def create(self, **kwargs): return _Resp(self._text)


def test_verify_returns_validated_verdict(fig: Path):
    payload = json.dumps(
        {"verdict": "FABRICATED", "evidence_anchors": ["no error bars present"], "confidence": 0.9}
    )
    out = verify_figure_claim("p=0.01 claimed", fig, client=_StubClient(payload))
    assert out["verdict"] == "FABRICATED"
    assert out["evidence_anchors"] == ["no error bars present"]
    assert out["_usage"] == {"input_tokens": 123, "output_tokens": 45}


def test_verify_surfaces_schema_violation_not_silent(fig: Path):
    # Model returns a verdict outside the enum — must raise, NOT coerce to a default.
    payload = json.dumps({"verdict": "MAYBE", "evidence_anchors": ["x"], "confidence": 0.5})
    with pytest.raises(SchemaViolation):
        verify_figure_claim("claim", fig, client=_StubClient(payload))


def test_verify_surfaces_non_json(fig: Path):
    with pytest.raises(SchemaViolation):
        verify_figure_claim("claim", fig, client=_StubClient("I think it is supported."))
