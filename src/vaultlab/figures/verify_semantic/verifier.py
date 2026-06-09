"""Figure-vs-claim semantic verifier (prototype).

Given a ``(claim, figure_image, source_pdf?)`` triple, ask a vision-capable Claude
model whether the figure *visually supports* the claim, and return a structured
verdict::

    {"verdict": "SUPPORTED|PARTIAL|UNSUPPORTED|FABRICATED",
     "evidence_anchors": [<concrete figure elements>],
     "confidence": 0.0..1.0}

This is the **semantic** layer of figure verification. It complements — and does NOT
duplicate — the deterministic verifiers already on ``feat/lab-dashboard``
(``enforce_hedge``, ``verify_numeric``, ``compare_two_groups``), which catch lexical
and numeric lies in *text*. This catches semantic mismatch between a claim and what a
figure actually *shows*: wrong-panel references, fabricated quantification, numeric
drift away from a plotted bar, and partial-truth overreach.

Lineage (see ``INSPIRATIONS.md``): promotes the ``methods_critic`` semantic-figure-audit
pattern (the K=100-vs-K=25 argmax inversion; the fig5C +0.32→+0.38 drift documented in
``Output/round15-vaultlab-pipeline-vetting/semantic-figure-audit-2026-05-11.md``) into a
measurable primitive. The prompt text lives in the sibling ``prompt.md`` (META PRINCIPLE
#1 — no triple-quoted prompts in ``.py``).

Design notes
------------
* The prompt is loaded from ``prompt.md`` at call time.
* Structured output is requested via the Messages API ``output_config.format``
  json-schema. JSON-schema structured outputs do NOT enforce numeric ranges, so
  ``confidence ∈ [0, 1]`` and ``evidence_anchors`` non-emptiness are validated
  CLIENT-SIDE in :func:`validate_verdict` (an out-of-schema response is a hard failure,
  surfaced — never silently coerced).
* The model id is pinned (``claude-sonnet-4-6``) but overridable per call.
* The API call is isolated in :func:`verify_figure_claim`; request-building
  (:func:`build_request`) and validation (:func:`validate_verdict`) are pure and unit
  testable without network or an API key.
"""

from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any

# Pinned via the claude-api skill (current vision-capable, cost-efficient tier).
# Overridable per call for an accuracy/cost sweep (e.g. "claude-opus-4-8").
DEFAULT_MODEL = "claude-sonnet-4-6"

VERDICT_VALUES = ["SUPPORTED", "PARTIAL", "UNSUPPORTED", "FABRICATED"]

# Fixed output schema. ``enum`` and ``additionalProperties:false`` ARE enforced by the
# API's structured-outputs layer; the numeric range on ``confidence`` and the
# non-emptiness of ``evidence_anchors`` are NOT (json-schema structured outputs drop
# numeric/length constraints) — validate_verdict enforces those client-side.
VERDICT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "verdict": {"type": "string", "enum": VERDICT_VALUES},
        "evidence_anchors": {"type": "array", "items": {"type": "string"}},
        "confidence": {"type": "number"},
    },
    "required": ["verdict", "evidence_anchors", "confidence"],
    "additionalProperties": False,
}

_MEDIA_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
}


class SchemaViolation(ValueError):
    """Raised when a model response does not satisfy the verdict contract.

    Surfaced loudly (never swallowed): an unparseable or out-of-contract verdict is a
    benchmark *failure*, not something to coerce into a default.
    """


def _load_prompt() -> str:
    return (Path(__file__).parent / "prompt.md").read_text(encoding="utf-8")


def _media_type(figure_path: str | Path) -> str:
    ext = Path(figure_path).suffix.lower()
    if ext not in _MEDIA_TYPES:
        raise ValueError(
            f"unsupported image extension {ext!r}; expected one of {sorted(_MEDIA_TYPES)}"
        )
    return _MEDIA_TYPES[ext]


def build_request(
    claim: str,
    figure_path: str | Path,
    source_pdf: str | None = None,
    *,
    model: str = DEFAULT_MODEL,
) -> dict[str, Any]:
    """Build the Messages-API request body for one figure/claim verification.

    Pure: reads the image off disk and base64-encodes it, but performs no network I/O.
    """
    figure_path = Path(figure_path)
    media_type = _media_type(figure_path)
    image_b64 = base64.standard_b64encode(figure_path.read_bytes()).decode("utf-8")

    claim_block = (
        f"CLAIM TO VERIFY:\n{claim}\n\n"
        f"source_pdf: {source_pdf or 'none provided — judge the claim against the figure only'}"
    )

    return {
        "model": model,
        "max_tokens": 1024,
        "system": _load_prompt(),
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": image_b64,
                        },
                    },
                    {"type": "text", "text": claim_block},
                ],
            }
        ],
        "output_config": {"format": {"type": "json_schema", "schema": VERDICT_SCHEMA}},
    }


def validate_verdict(obj: Any) -> dict[str, Any]:
    """Validate a parsed model response against the fixed verdict contract.

    Enforces what json-schema structured outputs cannot: verdict ∈ enum,
    evidence_anchors is a non-empty list of non-empty strings, confidence ∈ [0, 1].
    Raises :class:`SchemaViolation` on any breach. Returns a normalized dict on success.
    """
    if not isinstance(obj, dict):
        raise SchemaViolation(f"response is not a JSON object: {type(obj).__name__}")

    verdict = obj.get("verdict")
    if verdict not in VERDICT_VALUES:
        raise SchemaViolation(f"verdict {verdict!r} not in {VERDICT_VALUES}")

    anchors = obj.get("evidence_anchors")
    if not isinstance(anchors, list) or not anchors:
        raise SchemaViolation("evidence_anchors must be a non-empty list")
    cleaned = [a.strip() for a in anchors if isinstance(a, str) and a.strip()]
    if not cleaned:
        raise SchemaViolation("evidence_anchors must contain at least one non-empty string")

    confidence = obj.get("confidence")
    if isinstance(confidence, bool) or not isinstance(confidence, (int, float)):
        raise SchemaViolation(f"confidence {confidence!r} must be a number")
    if not (0.0 <= float(confidence) <= 1.0):
        raise SchemaViolation(f"confidence {confidence!r} out of range [0, 1]")

    return {
        "verdict": verdict,
        "evidence_anchors": cleaned,
        "confidence": float(confidence),
    }


def _extract_text(resp: Any) -> str:
    for block in resp.content:
        if getattr(block, "type", None) == "text":
            return block.text
    raise SchemaViolation("model response contained no text block")


def verify_figure_claim(
    claim: str,
    figure_path: str | Path,
    source_pdf: str | None = None,
    *,
    model: str = DEFAULT_MODEL,
    client: Any | None = None,
) -> dict[str, Any]:
    """Verify one figure/claim pair. Returns a validated verdict dict.

    ``client`` may be injected (a stub) for offline tests; otherwise a real
    ``anthropic.Anthropic()`` is constructed (reads ``ANTHROPIC_API_KEY`` from env).

    On success the returned dict also carries ``_usage`` (input/output token counts) so
    callers can tally per-call cost for the invocation-path recommendation.
    """
    if client is None:
        import anthropic

        client = anthropic.Anthropic()

    request = build_request(claim, figure_path, source_pdf, model=model)
    try:
        resp = client.messages.create(**request)
    except Exception as exc:  # noqa: BLE001 — fall back if output_config unsupported
        # Some SDK/model combos reject output_config; the prompt also self-instructs
        # JSON-only, so retry without the structured-output constraint rather than fail.
        if "output_config" not in str(exc):
            raise
        request.pop("output_config", None)
        resp = client.messages.create(**request)

    text = _extract_text(resp)
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise SchemaViolation(f"model response was not valid JSON: {exc}") from exc

    verdict = validate_verdict(parsed)
    usage = getattr(resp, "usage", None)
    verdict["_usage"] = {
        "input_tokens": getattr(usage, "input_tokens", None),
        "output_tokens": getattr(usage, "output_tokens", None),
    }
    verdict["_model"] = getattr(resp, "model", model)
    return verdict


__all__ = [
    "DEFAULT_MODEL",
    "VERDICT_VALUES",
    "VERDICT_SCHEMA",
    "SchemaViolation",
    "build_request",
    "validate_verdict",
    "verify_figure_claim",
]
