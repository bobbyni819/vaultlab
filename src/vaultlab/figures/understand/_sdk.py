"""SDK-backed figure-understand callbacks (Anthropic Messages API + vision).

Production callbacks for the 4-step figure-understanding pipeline that
DON'T require running inside Claude Code. These call the Anthropic
Messages API directly via the ``anthropic`` SDK and use the vision
content blocks (``{"type": "image", "source": {...}}``) so the model can
actually look at the figure.

For Claude-Code-mode (no API key required), use the prepare/render
helpers in :mod:`vaultlab.figures.understand._tasks` directly — the
slash command body inside Claude Code IS the LLM via Read tool.

Public surface:

- :func:`describe_via_sdk` — Step 1 callback (image -> description)
- :func:`match_via_sdk` — Step 3 callback (description + regions -> matches)
- :func:`verify_via_sdk` — Step 4 callback (annotated image -> verdict)
- :func:`understand_figure_via_sdk` — high-level wrapper that wires all
  three SDK callbacks into the orchestrator
  :func:`vaultlab.figures.understand.understand_figure`

The SDK calls re-use :func:`vaultlab.research.summarize.load_anthropic_api_key`
so credential precedence stays consistent across the codebase
(env var > config file). The model defaults to
:data:`DEFAULT_VISION_MODEL` (vision-capable Sonnet).

NOTE: This module imports ``anthropic`` lazily inside the SDK functions
so importing :mod:`vaultlab.figures.understand` itself doesn't fail on a
fresh install before the user has run ``pip install vaultlab[research]``.
"""

from __future__ import annotations

import base64
import json
import logging
import mimetypes
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from vaultlab.figures.understand._tasks import (
    DescribeFigureTask,
    MatchElementsTask,
    VerifyAnnotationTask,
    prepare_describe_task,
    prepare_match_task,
    prepare_verify_task,
    render_describe_from_response,
    render_match_from_response,
    render_verify_from_response,
)
from vaultlab.figures.understand.color_motif import ColorMotif, Region
from vaultlab.figures.understand.models import (
    ElementAnnotation,
    FigureUnderstandLog,
    VerificationIteration,
)

logger = logging.getLogger(__name__)


__all__ = [
    "DEFAULT_VISION_MODEL",
    "describe_via_sdk",
    "match_via_sdk",
    "verify_via_sdk",
    "understand_figure_via_sdk",
]


DEFAULT_VISION_MODEL = "claude-sonnet-4-6"
"""Vision-capable Sonnet — same default the rest of vaultlab uses."""

_DEFAULT_MAX_TOKENS = 4096


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _resolve_api_key(explicit: str | None) -> str:
    """Reuse the centralized auth resolver from research.summarize."""
    from vaultlab.research.summarize import load_anthropic_api_key

    return load_anthropic_api_key(explicit)


def _make_client(api_key: str | None):
    """Build an ``anthropic.Anthropic`` client, deferring the import."""
    import anthropic  # noqa: PLC0415 — deferred so the package stays light to import

    key = _resolve_api_key(api_key)
    return anthropic.Anthropic(api_key=key)


def _image_block(image_path: Path) -> dict[str, Any]:
    """Encode an image file as an Anthropic vision content block."""
    if not image_path.exists():
        raise FileNotFoundError(f"figure not found: {image_path}")
    mime, _ = mimetypes.guess_type(str(image_path))
    if mime is None or not mime.startswith("image/"):
        suffix = image_path.suffix.lower().lstrip(".")
        mime = f"image/{suffix or 'png'}"
    if mime == "image/jpg":
        mime = "image/jpeg"
    data = image_path.read_bytes()
    return {
        "type": "image",
        "source": {
            "type": "base64",
            "media_type": mime,
            "data": base64.standard_b64encode(data).decode("ascii"),
        },
    }


def _extract_text(response: Any) -> str:
    """Concatenate text blocks from an Anthropic Messages response."""
    chunks: list[str] = []
    for block in getattr(response, "content", []) or []:
        if getattr(block, "type", "") == "text":
            chunks.append(getattr(block, "text", "") or "")
    return "\n".join(chunks).strip()


def _extract_json(text: str) -> dict[str, Any] | None:
    """Pull a JSON object out of an LLM reply, tolerating preambles / fences.

    Returns ``None`` if no valid JSON object can be parsed — callers feed
    that to the render_* helpers, which produce safe defaults rather than
    crashing.
    """
    if not text:
        return None
    s = text.strip()
    if s.startswith("```"):
        first_newline = s.find("\n")
        if first_newline != -1:
            s = s[first_newline + 1:]
        if s.endswith("```"):
            s = s[:-3].rstrip()
    start = s.find("{")
    if start == -1:
        logger.warning("_extract_json: no JSON object found in reply: %r", s[:200])
        return None
    depth = 0
    in_str = False
    esc = False
    for i in range(start, len(s)):
        ch = s[i]
        if esc:
            esc = False
            continue
        if ch == "\\" and in_str:
            esc = True
            continue
        if ch == '"':
            in_str = not in_str
            continue
        if in_str:
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                blob = s[start:i + 1]
                try:
                    parsed = json.loads(blob)
                    return parsed if isinstance(parsed, dict) else None
                except json.JSONDecodeError as exc:
                    logger.warning("_extract_json: failed to parse: %s", exc)
                    return None
    logger.warning("_extract_json: unbalanced braces in reply")
    return None


def _call_messages(
    *,
    client,
    model: str,
    system: str,
    user_blocks: list[dict[str, Any]],
    max_tokens: int = _DEFAULT_MAX_TOKENS,
) -> dict[str, Any] | None:
    """One Anthropic call with vision-capable content blocks."""
    response = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user_blocks}],
    )
    text = _extract_text(response)
    return _extract_json(text)


# ---------------------------------------------------------------------------
# Public SDK callbacks
# ---------------------------------------------------------------------------


def describe_via_sdk(
    task: DescribeFigureTask,
    *,
    client=None,
    model: str = DEFAULT_VISION_MODEL,
    api_key: str | None = None,
) -> str:
    """Step 1 — call Anthropic with vision; return the description text.

    Returns the string for direct use as
    :attr:`vaultlab.figures.understand.models.FigureUnderstandLog.step1_description`.
    Raises any underlying SDK / network errors so the orchestrator can
    fall back gracefully (it wraps ``describe_fn`` in a try/except and
    records the failure into the log).
    """
    cli = client or _make_client(api_key)
    blocks = [_image_block(task.figure_path), {"type": "text", "text": task.prompt}]
    parsed = _call_messages(
        client=cli, model=model, system=task.system, user_blocks=blocks
    )
    description, _ = render_describe_from_response(parsed, task)
    return description


def match_via_sdk(
    task: MatchElementsTask,
    *,
    client=None,
    model: str = DEFAULT_VISION_MODEL,
    api_key: str | None = None,
) -> list[dict[str, Any]]:
    """Step 3 — call Anthropic with the figure + regions; return match list.

    Returns the list of match dicts in the shape the orchestrator expects
    (``element_name`` / ``matched_region_id`` / ``rationale`` / ``confidence``).
    """
    cli = client or _make_client(api_key)
    blocks: list[dict[str, Any]] = [_image_block(task.figure_path)]
    if task.annotated_preview_path is not None and task.annotated_preview_path.exists():
        blocks.append(_image_block(task.annotated_preview_path))
    blocks.append({"type": "text", "text": task.prompt})
    parsed = _call_messages(
        client=cli, model=model, system=task.system, user_blocks=blocks
    )
    return render_match_from_response(parsed, task)


def verify_via_sdk(
    task: VerifyAnnotationTask,
    *,
    client=None,
    model: str = DEFAULT_VISION_MODEL,
    api_key: str | None = None,
) -> VerificationIteration:
    """Step 4 — call Anthropic with the annotated image; return verdict."""
    cli = client or _make_client(api_key)
    blocks = [
        _image_block(task.annotated_image_path),
        {"type": "text", "text": task.prompt},
    ]
    parsed = _call_messages(
        client=cli, model=model, system=task.system, user_blocks=blocks
    )
    return render_verify_from_response(parsed, task)


# ---------------------------------------------------------------------------
# High-level wrapper
# ---------------------------------------------------------------------------


def understand_figure_via_sdk(
    figure_path: str | Path,
    motifs: Sequence[ColorMotif],
    *,
    paper_doi: str,
    paper_tldr: str = "",
    figure_id: str | None = None,
    annotated_png_path: str | Path | None = None,
    client=None,
    model: str = DEFAULT_VISION_MODEL,
    api_key: str | None = None,
    dilation_px: int = 8,
    max_iterations: int = 5,
    skip_verify: bool = False,
) -> tuple[list[ElementAnnotation], FigureUnderstandLog]:
    """Run the full 4-step pipeline using SDK-backed callbacks.

    This is the high-level entry point for "I have an Anthropic API key
    and want to run figure-understanding without spawning a Claude Code
    session."

    Parameters
    ----------
    figure_path
        Source figure (PNG/JPG/etc).
    motifs
        Color motifs for Step 2 localization.
    paper_doi
        DOI of the source paper. Used to slug the reasoning-log directory
        and to give context to the LLM.
    paper_tldr
        Optional context for the LLM (paper TL;DR / one-line description).
    figure_id
        Override the default figure id (``figure_path.name``).
    annotated_png_path
        Where the rendered annotated PNG should land. Required for the
        verify step (it reads this file). When ``None``, defaults to
        ``<figure_path-stem>.annotated.png`` next to the source figure.
    client
        Optional pre-built ``anthropic.Anthropic`` client. When ``None``,
        one is built from ``api_key`` / env / config.
    model
        Anthropic vision-capable model id.
    api_key
        Optional explicit API key. ``None`` -> resolves via env / config.
    dilation_px
        Forwarded to :func:`vaultlab.figures.understand.merge_regions`.
    max_iterations
        Verify-loop cap. ``0`` or ``skip_verify=True`` skips Step 4.
    skip_verify
        When True, do not run Step 4 even if there are annotations to
        verify. Useful for quick smoke tests where the annotated PNG
        hasn't been rendered yet.

    Returns
    -------
    (annotations, log)
        Same shape as :func:`vaultlab.figures.understand.understand_figure`.
    """
    # Local import to avoid a circular import via the package __init__.
    from vaultlab.figures.understand import understand_figure
    from vaultlab.figures.understand.render import render_debug_overlay

    figure_path = Path(figure_path)
    if annotated_png_path is None:
        annotated_png_path = figure_path.with_suffix(".annotated.png")
    annotated_png_path = Path(annotated_png_path)

    cli = client or _make_client(api_key)

    # Track elements named in Step 1 so verify can echo them.
    described_elements_holder: dict[str, list[str]] = {"value": []}
    description_holder: dict[str, str] = {"value": ""}

    def describe_fn(image_path: Path) -> str:
        task = prepare_describe_task(
            image_path, paper_doi=paper_doi, paper_tldr=paper_tldr
        )
        # Inline the SDK call so we can also capture the elements list,
        # which the SDK callback signature (str return) wouldn't expose.
        blocks = [_image_block(task.figure_path), {"type": "text", "text": task.prompt}]
        parsed = _call_messages(
            client=cli, model=model, system=task.system, user_blocks=blocks
        )
        description, elements = render_describe_from_response(parsed, task)
        description_holder["value"] = description
        described_elements_holder["value"] = elements
        return description

    def match_fn(_description: str, regions: list[Region]) -> list[dict[str, Any]]:
        task = prepare_match_task(
            figure_path,
            description=description_holder["value"],
            described_elements=described_elements_holder["value"],
            regions=regions,
        )
        return match_via_sdk(task, client=cli, model=model, api_key=api_key)

    def verify_fn(
        annotated_path: Path,
        annotations: list[ElementAnnotation],
        iteration: int,
    ) -> VerificationIteration:
        # Render fresh annotations onto the source figure before each pass
        # so the verifier sees the current state of the boxes.
        try:
            render_debug_overlay(figure_path, annotations, annotated_path)
        except Exception as exc:  # noqa: BLE001
            logger.warning("verify_fn: render_debug_overlay failed: %s", exc)
        expected = [a.label for a in annotations] or described_elements_holder["value"]
        task = prepare_verify_task(
            annotated_path, iteration=iteration, expected_elements=expected
        )
        return verify_via_sdk(task, client=cli, model=model, api_key=api_key)

    return understand_figure(
        figure_path,
        motifs,
        doi=paper_doi,
        figure_id=figure_id,
        annotated_png_path=annotated_png_path,
        describe_fn=describe_fn,
        match_fn=match_fn,
        verify_fn=None if skip_verify else verify_fn,
        dilation_px=dilation_px,
        max_iterations=max_iterations,
    )
