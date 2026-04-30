"""Dual-format speaker notes: mental map + detailed script.

Bobby's 2026-04-29 grill answer: every slide should have BOTH a mental-map
section (for fluent presenters who don't need a script) AND a detailed
word-for-word script (for first-time / nervous presenters), separated by a
visible divider.

Mental-map sections (matching ``bobby_slides._speaker`` convention):

- HOOK - one phrase to open with
- KEY CLAIM - one sentence stating the slide's takeaway
- EVIDENCE - pointer to figure / data on the slide
- KEY TERMS - exact terms to pronounce correctly
- CLICK - animation cue
- TRANSITION - one-sentence bridge to next slide

Detailed script: full first-person paragraphs, hedged voice maintained.
Length: 200-400 words default; flex by slide complexity.

Examples
--------

>>> from vaultlab.slides.notes import dual_format
>>> notes_string = dual_format(
...     mental_map={
...         "hook": "We engineer T cells in three architectural flavors.",
...         "key_claim": "TCR, TAA, and CAR therapies differ in MHC-dependence.",
...         "evidence": "Three-panel BioRender comparison in this slide.",
...         "key_terms": ["scFv", "ITAM", "ζ-chain"],
...         "click": "First click reveals annotations 1-4 (panel a).",
...         "transition": "Next slide: how we engineer the CAR construct.",
...     },
...     detailed_script=(
...         "These three panels show the three ways an engineered T cell "
...         "recognizes a tumor antigen. In panel a, the introduced TCR "
...         "competes with the endogenous TCR for MHC-presented peptide. "
...         "..."
...     ),
... )
>>> # Drop into slide.notes_slide.notes_text_frame.text = notes_string
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

# Section labels uppercase per Bobby's convention - visual scannability on stage.
_LABELS: dict[str, str] = {
    "hook": "HOOK",
    "key_claim": "KEY CLAIM",
    "evidence": "EVIDENCE",
    "key_terms": "KEY TERMS",
    "click": "CLICK",
    "transition": "TRANSITION",
}

_MENTAL_MAP_ORDER: list[str] = ["hook", "key_claim", "evidence", "key_terms", "click", "transition"]

DIVIDER = "\n\n--- DETAILED SCRIPT ---\n"


def dual_format(
    *,
    mental_map: dict[str, Any] | None = None,
    detailed_script: str = "",
) -> str:
    """Render a dual-format speaker-notes string.

    Parameters
    ----------
    mental_map
        Dict with optional keys ``hook``, ``key_claim``, ``evidence``, ``key_terms``,
        ``click``, ``transition``. Missing keys are skipped. ``key_terms`` may be
        a list (joined with commas) or a string.
    detailed_script
        Free-form paragraph(s). Recommended length 200-400 words.

    Returns
    -------
    str
        Mental map (formatted as ``- LABEL: value`` lines) + divider +
        detailed script. Either side may be empty.
    """
    map_text = _render_mental_map(mental_map) if mental_map else ""
    script_text = detailed_script.strip()

    if map_text and script_text:
        return f"{map_text}{DIVIDER}{script_text}"
    if map_text:
        return map_text
    if script_text:
        return script_text
    return ""


def parse_dual_format(notes_text: str) -> tuple[dict[str, Any], str]:
    """Split a dual-format string back into its mental-map dict + script.

    Inverse of :func:`dual_format`. Used when reading existing notes (e.g.,
    Bobby edits a slide directly and we want to merge his changes back into
    the structured mental_map for re-rendering).
    """
    if "--- DETAILED SCRIPT ---" in notes_text:
        head, _, tail = notes_text.partition("--- DETAILED SCRIPT ---")
        map_dict = _parse_mental_map(head)
        return map_dict, tail.strip()
    return _parse_mental_map(notes_text), ""


# ---------------------------------------------------------------------------
# Internal
# ---------------------------------------------------------------------------


def _render_mental_map(notes: dict[str, Any]) -> str:
    lines: list[str] = []
    for key in _MENTAL_MAP_ORDER:
        val = notes.get(key)
        if not val:
            continue
        label = _LABELS[key]
        if isinstance(val, list):
            joined = ", ".join(str(v) for v in val)
            lines.append(f"- {label}: {joined}")
        else:
            lines.append(f"- {label}: {val}")
    return "\n".join(lines)


def _parse_mental_map(text: str) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("- "):
            continue
        body = stripped[2:]
        if ":" not in body:
            continue
        label, _, value = body.partition(":")
        key = _label_to_key(label.strip())
        if key is not None:
            out[key] = value.strip()
    return out


def _label_to_key(label: str) -> str | None:
    upper = label.upper().strip()
    for key, lab in _LABELS.items():
        if lab == upper:
            return key
    return None


def required_mental_map_keys() -> Iterable[str]:
    """The full ordered set of mental-map keys.

    Useful for Claude / other LLMs generating speaker notes - this is the
    contract the dual_format renderer expects.
    """
    return tuple(_MENTAL_MAP_ORDER)


# ---------------------------------------------------------------------------
# Compat layer: bobby_slides._speaker public surface
# ---------------------------------------------------------------------------
#
# These three functions were lifted from ``bobby_slides._speaker`` (2026-04)
# so callers that worked with the bobby_slides API (and the lifted
# ``vaultlab.slides.marp`` renderer + plan builders) keep working without
# rewriting. The dual-format API above is the recommended new path; the
# names below are the older mental-map-only surface.
#
# Detailed-script support (the divider section): callers can still pass a
# ``"script"`` key in the notes dict to format_speaker_notes; we route it
# through the divider for backwards compat with bobby_slides.


def format_speaker_notes(notes: dict[str, Any] | None) -> str:
    """Render a structured notes dict as a mental-map string.

    Lifted from ``bobby_slides._speaker.format_speaker_notes``. If the dict
    contains a ``"script"`` key, its value is appended after the
    ``--- DETAILED SCRIPT ---`` divider — same dual-format output as
    :func:`dual_format`.

    Args:
        notes: dict with optional keys ``hook``, ``key_claim``, ``evidence``,
            ``key_terms`` (list or string), ``click``, ``transition``, and
            optional ``script``. Missing keys are skipped. ``None`` or empty
            dict yields ``""``.

    Returns:
        A formatted multi-line string ready to drop into a slide's notes.
    """
    if not notes:
        return ""

    map_text = _render_mental_map(notes)
    script = notes.get("script")
    if script:
        return f"{map_text}{DIVIDER}{str(script).strip()}" if map_text else str(script).strip()
    return map_text


def parse_speaker_notes(text: str) -> dict[str, Any]:
    """Reverse of :func:`format_speaker_notes` — parse mental-map back to dict.

    Lifted from ``bobby_slides._speaker.parse_speaker_notes``. ``KEY TERMS``
    values are returned as a list (split on commas). Missing keys are
    absent from the result.
    """
    if not text or not text.strip():
        return {}

    label_to_key = {v: k for k, v in _LABELS.items()}
    result: dict[str, Any] = {}

    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("-"):
            continue
        line = line.lstrip("- ").strip()
        for label, key in label_to_key.items():
            prefix = f"{label}:"
            if line.upper().startswith(prefix):
                value = line[len(prefix):].strip()
                if key == "key_terms":
                    result[key] = [t.strip() for t in value.split(",") if t.strip()]
                else:
                    result[key] = value
                break

    return result


def attach_to_slide(slide: Any, notes: dict[str, Any] | None) -> None:
    """Attach formatted speaker notes to a python-pptx slide.

    Lifted from ``bobby_slides._speaker.attach_to_slide``. No-op if
    ``notes`` is ``None`` / empty.
    """
    formatted = format_speaker_notes(notes)
    if not formatted:
        return
    notes_slide = slide.notes_slide
    notes_slide.notes_text_frame.text = formatted


__all__ = [
    "DIVIDER",
    "attach_to_slide",
    "dual_format",
    "format_speaker_notes",
    "parse_dual_format",
    "parse_speaker_notes",
    "required_mental_map_keys",
]
