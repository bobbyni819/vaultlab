"""HTML view for a :class:`vaultlab.manuscript.respond.ResponseLetter`.

Consumer of ``vaultlab.report``. Renders a reviewer-response letter as a
single-file HTML report with color-coded action badges, per-comment
severity cards (red for ``AUTHOR_INPUT_NEEDED`` / ``DISAGREE_*``, green
for accepted, amber for soften/defer), a filter bar by action type, and
copy-comment / copy-fix buttons.

The /respond slash command emits both the markdown letter and this HTML
view alongside each other.
"""

from __future__ import annotations

import html as _html
from pathlib import Path
from typing import Any, cast

from vaultlab.manuscript.respond import (
    ActionType,
    CommentKind,
    ResponseLetter,
    ReviewerComment,
)
from vaultlab.report import _components as c
from vaultlab.report.html import render_report

# Action → severity colour
_ACTION_LEVEL: dict[str, c.Severity] = {
    "ACCEPT_TEXT": "good",
    "ACCEPT_ANALYSIS": "good",
    "ACCEPT_EXPERIMENT": "good",
    "ACCEPT_FIGURE": "good",
    "ACCEPT_CITATION": "good",
    "SOFTEN_CLAIM": "warn",
    "DISAGREE_WITH_RATIONALE": "bad",
    "AUTHOR_INPUT_NEEDED": "bad",
    "DEFER_TO_FUTURE_WORK": "warn",
}


def _safe(text: Any) -> str:
    return _html.escape(str(text or ""))


def _comment_card(cm: ReviewerComment | dict[str, Any]) -> str:
    if isinstance(cm, ReviewerComment):
        d = {
            "stable_id": cm.stable_id,
            "quote": cm.quote,
            "kind": cm.kind.value if isinstance(cm.kind, CommentKind) else cm.kind,
            "action": cm.action.value if isinstance(cm.action, ActionType) else cm.action,
            "evidence_ref": cm.evidence_ref,
            "response_text": cm.response_text,
            "open_question": cm.open_question,
        }
    else:
        d = dict(cm)

    action = str(d.get("action", ""))
    severity = _ACTION_LEVEL.get(action, "neutral")
    kind = str(d.get("kind", ""))
    filter_keys = ",".join(filter(None, [action, kind]))

    body_parts: list[str] = []
    if d.get("quote"):
        body_parts.append(
            f'<blockquote style="margin:0 0 10px;padding:8px 12px;border-left:3px solid var(--line);background:var(--bg-soft);color:var(--ink-soft);font-size:13px;font-style:italic;">{_safe(d["quote"])}</blockquote>'
        )
    if d.get("evidence_ref"):
        body_parts.append(
            f'<p style="margin:4px 0;font-size:12px;color:var(--muted);"><strong>Where in revision:</strong> <code>{_safe(d["evidence_ref"])}</code></p>'
        )
    if d.get("response_text"):
        body_parts.append(
            f'<p style="margin:6px 0;line-height:1.55;">{_safe(d["response_text"])}</p>'
        )
    if action == "AUTHOR_INPUT_NEEDED" and d.get("open_question"):
        body_parts.append(
            f'<div style="margin-top:10px;padding:8px 12px;background:var(--bad-bg);border-left:3px solid var(--bad);border-radius:3px;color:var(--bad);font-size:13px;">'
            f"⚠️ <strong>AUTHOR INPUT NEEDED:</strong> {_safe(d['open_question'])}"
            f"</div>"
        )

    badges: list[tuple[str, c.Severity]] = [
        (action, severity),
        (kind, "neutral"),
    ]

    actions: list[tuple[str, str]] = []
    if d.get("quote"):
        actions.append(("Copy quote", d["quote"]))
    if d.get("response_text"):
        actions.append(("Copy response", d["response_text"]))

    return c.severity_card(
        d.get("stable_id", "?"),
        body="".join(body_parts),
        severity=severity,
        badges=badges,
        actions=actions,
        filter_key=filter_keys,
    )


def build_response_letter_html(
    letter: ResponseLetter | dict[str, Any],
    *,
    title: str | None = None,
) -> str:
    """Render a response letter as a single-file HTML.

    Accepts a :class:`ResponseLetter` dataclass or a dict shaped like
    ``{"reviewer": int, "opening": str, "closing": str, "comments": list[ReviewerComment-or-dict]}``.
    """
    comments: list[ReviewerComment | dict[str, Any]]
    if isinstance(letter, ResponseLetter):
        reviewer = letter.reviewer
        opening = letter.opening
        closing = letter.closing
        comments = list(letter.comments)
    else:
        reviewer = letter.get("reviewer", 1)
        opening = letter.get("opening", "")
        closing = letter.get("closing", "")
        comments = [
            cast("ReviewerComment | dict[str, Any]", item)
            for item in list(letter.get("comments", []))
        ]

    report_title = title or f"Response to Reviewer {reviewer}"

    # Build action counts for chips
    action_counts: dict[str, int] = {}
    open_questions = 0
    for cm in comments:
        if isinstance(cm, ReviewerComment):
            act = cm.action.value if isinstance(cm.action, ActionType) else cm.action
            if cm.action == ActionType.AUTHOR_INPUT_NEEDED:
                open_questions += 1
        else:
            act = str(cm.get("action", "?"))
            if act == "AUTHOR_INPUT_NEEDED":
                open_questions += 1
        action_counts[act] = action_counts.get(act, 0) + 1

    summary_chips = [c.status_chip(f"{len(comments)} comments", "neutral")]
    for action, count in action_counts.items():
        level = _ACTION_LEVEL.get(action, "neutral")
        summary_chips.append(c.status_chip(f"{action.lower().replace('_', ' ')}: {count}", level))
    if open_questions:
        summary_chips.append(c.status_chip(f"⚠ {open_questions} need author input", "bad"))

    tldr_items = [
        f"Response letter to Reviewer {reviewer} — {len(comments)} comment{'s' if len(comments) != 1 else ''}.",
    ]
    if open_questions:
        tldr_items.append(
            f"{open_questions} comment{'s' if open_questions != 1 else ''} flagged as "
            "AUTHOR INPUT NEEDED — review the bad-bordered cards before finalizing."
        )

    # Filter buckets
    filter_buckets: list[tuple[str, str]] = [("All", "all")]
    for act in action_counts:
        if action_counts[act]:
            filter_buckets.append((act.replace("_", " "), act))

    comment_cards = [_comment_card(cm) for cm in comments]

    sections = [
        c.section(
            None,
            c.tldr_box(tldr_items),
        ),
    ]
    _n = 0  # running section number

    if opening:
        _n += 1
        sections.append(
            c.section(
                "Opening",
                f'<p style="line-height:1.55;">{_safe(opening)}</p>',
                number=_n,
            )
        )

    _n += 1
    sections.append(
        c.section(
            "Comments + responses",
            c.filter_bar(
                filter_buckets,
                target_selector=".vl-cards .vl-card",
            ),
            c.card_grid(comment_cards) if comment_cards else "<p>No comments.</p>",
            number=_n,
        ),
    )

    if closing:
        _n += 1
        sections.append(
            c.section(
                "Closing",
                f'<p style="line-height:1.55;">{_safe(closing)}</p>',
                number=_n,
            )
        )

    return render_report(
        title=report_title,
        eyebrow=f"vaultlab · reviewer response · R{reviewer}",
        subtitle=f"{len(comments)} comments · {open_questions} need author input",
        chips=summary_chips,
        sections=sections,
    )


def write_response_letter_html(
    out_path: Path | str,
    letter: ResponseLetter | dict[str, Any],
    **kwargs: Any,
) -> Path:
    """Render and write the response-letter HTML view."""
    html_str = build_response_letter_html(letter, **kwargs)
    p = Path(out_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(html_str, encoding="utf-8")
    return p


__all__ = ["build_response_letter_html", "write_response_letter_html"]
