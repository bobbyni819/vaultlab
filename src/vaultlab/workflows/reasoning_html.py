"""HTML reasoning-chain report.

Consumer #3 of ``vaultlab.report``. Renders a :class:`CrosstalkResult` as a
single-file HTML report — color-coded per-role rounds, collapsible
prompt+output for each turn, the final synthesized output rendered as a
clean block, and runtime + status chips in the header.

Background: Bobby's research-reason / crosstalk runs produce per-round
markdown branch docs (one per role per round). Hard to scan; hard to see
when an argument shifts hands. The HTML view consolidates the whole run
into one navigable file with role-attribution colors and an expandable
prompt history.
"""

from __future__ import annotations

import html as _html
import json as _json
from pathlib import Path
from typing import Any

from vaultlab.report import components as c
from vaultlab.report import render_report

# Color tag per role family (matches what readers expect from the role library).
_ROLE_COLOR = {
    "data_analyst": ("#0369a1", "#e0f2fe"),
    "literature_surveyor": ("#0369a1", "#e0f2fe"),
    "domain_expert": ("#7c2d12", "#fef3e7"),
    "methods_critic": ("#9f1239", "#ffe4e6"),
    "literature_critic": ("#9f1239", "#ffe4e6"),
    "rigor_auditor": ("#9f1239", "#ffe4e6"),
    "synthesizer": ("#5b21b6", "#ede9fe"),
    "narrator": ("#5b21b6", "#ede9fe"),
    "figure_lead": ("#166534", "#dcfce7"),
}
_DEFAULT_COLOR = ("#334155", "#f1f5f9")


def _safe(text: Any) -> str:
    return _html.escape(str(text or ""))


def _role_chip(role_id: str) -> str:
    fg, bg = _ROLE_COLOR.get(role_id, _DEFAULT_COLOR)
    return (
        f'<span style="display:inline-block;font-size:11px;font-weight:600;'
        f"padding:2px 8px;border-radius:3px;letter-spacing:0.02em;"
        f'background:{bg};color:{fg};border:1px solid {fg}33;">'
        f"{_safe(role_id)}</span>"
    )


def _round_card(
    round_index: int,
    turn: dict[str, Any] | Any,
    *,
    is_last: bool = False,
) -> str:
    """One turn in the conversation. Accepts dict or MeetingTurn-like object."""
    if isinstance(turn, dict):
        role_id = turn.get("role_id", "?")
        prompt = turn.get("prompt", "")
        output = turn.get("output", "")
    else:
        role_id = getattr(turn, "role_id", "?")
        prompt = getattr(turn, "prompt", "")
        output = getattr(turn, "output", "")

    fg, bg = _ROLE_COLOR.get(role_id, _DEFAULT_COLOR)
    open_by_default = is_last  # last turn auto-expands; rest are collapsed

    return (
        f'<details class="vl-step" style="border-left:3px solid {fg};"'
        f"{' open' if open_by_default else ''}>"
        f"<summary>"
        f'<span style="margin-right:8px;color:var(--muted);font-weight:500;">'
        f"Round {round_index + 1}</span>"
        f"{_role_chip(role_id)}"
        f"</summary>"
        '<div class="body">'
        f"{_prompt_block(prompt)}"
        f"{_output_block(output, fg, bg)}"
        f"</div></details>"
    )


def _prompt_block(prompt: str) -> str:
    if not prompt:
        return ""
    return (
        '<details style="margin:4px 0 10px;">'
        '<summary style="cursor:pointer;font-size:12px;color:var(--muted);">'
        "Prompt (click to expand)</summary>"
        f'<pre style="margin-top:6px;background:var(--bg-soft);color:var(--ink-soft);'
        f'border:1px solid var(--line);font-size:11px;">{_safe(prompt)}</pre>'
        "</details>"
    )


def _output_block(output: str, fg: str, bg: str) -> str:
    if not output:
        return '<p style="color:var(--muted);font-style:italic;">(no output)</p>'
    # Pretty-print JSON if the output is JSON
    pretty = output
    try:
        parsed = _json.loads(output)
        pretty = _json.dumps(parsed, indent=2, ensure_ascii=False)
        return (
            f'<pre style="background:{bg};color:{fg};border:1px solid {fg}55;">'
            f"{_safe(pretty)}</pre>"
        )
    except (ValueError, TypeError):
        pass
    return (
        f'<div style="background:{bg};color:var(--ink);'
        f"border-left:2px solid {fg}55;padding:10px 14px;border-radius:4px;"
        f'white-space:pre-wrap;font-size:13px;line-height:1.55;">'
        f"{_safe(output)}</div>"
    )


def _final_output_block(final: dict[str, Any]) -> str:
    if not final:
        return '<p style="color:var(--muted);">(no final synthesizer output)</p>'
    try:
        pretty = _json.dumps(final, indent=2, ensure_ascii=False)
        return (
            f'<pre style="background:var(--code-bg);color:var(--code-ink);">{_safe(pretty)}</pre>'
        )
    except (TypeError, ValueError):
        return f"<pre>{_safe(str(final))}</pre>"


def build_reasoning_report_html(
    result: dict[str, Any] | Any,
    *,
    topic: str | None = None,
    title: str | None = None,
) -> str:
    """Render a CrosstalkResult-shaped dict (or dataclass) as HTML.

    Accepts either:
      * a dict shaped like ``{"final_output": ..., "rounds": [...], "purpose":
        ..., "crosstalk_status": ..., "runtime_seconds": ...}``, or
      * the :class:`vaultlab.workflows.crosstalk.CrosstalkResult` dataclass.
    """
    if hasattr(result, "rounds"):
        rounds = list(result.rounds)
        final = getattr(result, "final_output", {}) or {}
        status = getattr(result, "crosstalk_status", "complete")
        purpose = getattr(result, "purpose", "")
        runtime = getattr(result, "runtime_seconds", 0.0)
    else:
        rounds = result.get("rounds", [])
        final = result.get("final_output", {}) or {}
        status = result.get("crosstalk_status", "complete")
        purpose = result.get("purpose", "")
        runtime = result.get("runtime_seconds", 0.0)

    report_title = title or f"Reasoning chain — {topic or purpose or '(investigation)'}"

    # Build role-attribution stats
    role_count: dict[str, int] = {}
    for turn in rounds:
        rid = turn.get("role_id", "?") if isinstance(turn, dict) else getattr(turn, "role_id", "?")
        role_count[rid] = role_count.get(rid, 0) + 1

    summary_chips = [
        c.status_chip(f"{len(rounds)} turns", "neutral"),
        c.status_chip(
            status,
            "good" if status == "complete" else "warn",
        ),
    ]
    if runtime:
        summary_chips.append(c.status_chip(f"{runtime:.1f}s", "neutral"))

    role_chips_block = " ".join(
        f"{_role_chip(rid)} <span style='font-size:11px;color:var(--muted);'>× {n}</span>"
        for rid, n in role_count.items()
    )

    tldr_items = [
        f"Investigation completed with status: {status}.",
        f"{len(rounds)} agent turn{'s' if len(rounds) != 1 else ''} across "
        f"{len(role_count)} distinct role{'s' if len(role_count) != 1 else ''}.",
    ]
    if final:
        tldr_items.append(
            "Final synthesizer output below; expand the last round to see derivation."
        )

    sections = [
        c.section(
            None,
            c.tldr_box(tldr_items),
            f'<div style="margin:14px 0;">{"".join(summary_chips)}</div>',
            f'<div style="margin:14px 0;font-size:13px;">{role_chips_block}</div>',
        ),
        c.section(
            "Final synthesized output",
            _final_output_block(final),
        ),
        c.section(
            "Agent rounds (chronological)",
            "<p style='color:var(--muted);font-size:13px;'>"
            "Each round is one role's turn. Output is auto-expanded for the last turn; "
            "expand earlier ones to see the derivation. Prompt history is nested inside.</p>",
            "".join(
                _round_card(i, turn, is_last=(i == len(rounds) - 1))
                for i, turn in enumerate(rounds)
            )
            if rounds
            else "<p>No rounds recorded.</p>",
        ),
    ]

    return render_report(
        title=report_title,
        eyebrow=f"vaultlab · reasoning chain · {purpose or 'investigation'}",
        subtitle=topic,
        meta=f"status: {status} · {len(rounds)} turns · {runtime:.1f}s runtime",
        sections=sections,
    )


def write_reasoning_report(
    out_path: Path | str,
    result: dict[str, Any] | Any,
    **kwargs: Any,
) -> Path:
    """Render and write the reasoning HTML report."""
    html_str = build_reasoning_report_html(result, **kwargs)
    p = Path(out_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(html_str, encoding="utf-8")
    return p


__all__ = ["build_reasoning_report_html", "write_reasoning_report"]
