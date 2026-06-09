"""HTML audit report for deck plans.

Consumer #1 of ``vaultlab.report``. Renders a ``rigor_audit`` result + the
underlying deck plan as a single-file HTML report with per-slide cards,
severity filter, and copy-to-clipboard fix actions.

See ``vaultlab/Output/Plans/html-and-nature-skills-2026-05-12.html`` for the
pattern source (deck-audit before/after compare).

Background: ``rigor_audit`` (in ``vaultlab.workflows.crosstalk``) returns
``{"passed": bool, "issues": [{loc, severity, kind, fix}, ...]}``. This
module groups issues by slide, decorates with the slide title/type/bullets
from the plan dict, and emits an interactive HTML view.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Literal

from vaultlab.report import components as c
from vaultlab.report import render_report, write_report

Severity = Literal["blocker", "major", "minor"]

# Map rigor_audit severities → report severity badges.
_SEVERITY_LEVEL = {
    "blocker": "bad",
    "major": "bad",
    "warning": "warn",
    "warn": "warn",
    "minor": "warn",
    "info": "neutral",
    "note": "neutral",
}

_SLIDE_LOC_RE = re.compile(r"slide[\s_-]*(\d+)", re.IGNORECASE)


def _slide_index_from_loc(loc: str) -> int | None:
    """Extract a slide index from a location string like 'Slide 3' or 'slide_3'."""
    if not loc:
        return None
    m = _SLIDE_LOC_RE.search(loc)
    if not m:
        return None
    try:
        return int(m.group(1)) - 1  # convert 1-indexed → 0-indexed
    except (TypeError, ValueError):
        return None


def _level_for(severity: str | None) -> str:
    return _SEVERITY_LEVEL.get((severity or "").lower(), "neutral")


def _group_issues_by_slide(
    issues: list[dict[str, Any]],
    slide_count: int,
) -> tuple[dict[int, list[dict[str, Any]]], list[dict[str, Any]]]:
    """Bucket issues into (slide_index → issues) + a global-issues list."""
    by_slide: dict[int, list[dict[str, Any]]] = {}
    global_issues: list[dict[str, Any]] = []
    for issue in issues:
        loc = issue.get("loc", "") or ""
        idx = _slide_index_from_loc(loc)
        if idx is not None and 0 <= idx < slide_count:
            by_slide.setdefault(idx, []).append(issue)
        else:
            global_issues.append(issue)
    return by_slide, global_issues


def _summarize_severity(issues: list[dict[str, Any]]) -> tuple[int, int, int]:
    """Return (blockers, majors, minors)."""
    counts = {"blocker": 0, "major": 0, "minor": 0}
    for issue in issues:
        sev = (issue.get("severity") or "").lower()
        if sev in counts:
            counts[sev] += 1
    return counts["blocker"], counts["major"], counts["minor"]


def _slide_card_body(slide: dict[str, Any], issues: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    if slide.get("subtitle"):
        parts.append(
            f'<p style="margin:0 0 6px;color:var(--ink-soft);">{_safe(slide["subtitle"])}</p>'
        )
    bullets = slide.get("bullets") or []
    if bullets:
        bullet_html = "".join(f"<li>{_safe(b)}</li>" for b in bullets[:5])
        more = (
            ""
            if len(bullets) <= 5
            else f'<li style="color:var(--muted);">… +{len(bullets) - 5} more</li>'
        )
        parts.append(
            f'<ul style="margin:4px 0 8px;padding-left:18px;font-size:12px;color:var(--ink-soft);">{bullet_html}{more}</ul>'
        )
    if issues:
        issue_html = "".join(
            f'<div style="margin:6px 0;padding:6px 8px;background:var(--bg-soft);border-left:2px solid var(--bad);border-radius:3px;font-size:12px;">'
            f"<strong>{_safe((i.get('kind') or '').upper())}</strong> "
            f'<span style="color:var(--ink-soft);">{_safe(i.get("fix", "") or i.get("loc", ""))}</span>'
            f"</div>"
            for i in issues[:6]
        )
        parts.append(issue_html)
    return "".join(parts)


def _safe(text: Any) -> str:
    """Escape free-form text destined for HTML body."""
    import html as _html

    return _html.escape(str(text or ""))


def _filter_key_for(issues: list[dict[str, Any]]) -> str:
    """Determine the filter bucket for the slide (highest-severity wins)."""
    if not issues:
        return "ok"
    for issue in issues:
        if (issue.get("severity") or "").lower() == "blocker":
            return "blocker"
    for issue in issues:
        if (issue.get("severity") or "").lower() == "major":
            return "major"
    return "minor"


def _severity_for_card(issues: list[dict[str, Any]]) -> str | None:
    if not issues:
        return "good"
    bucket = _filter_key_for(issues)
    return {"blocker": "bad", "major": "bad", "minor": "warn", "ok": "good"}.get(bucket)


def build_audit_report_html(
    plan: dict[str, Any],
    audit: dict[str, Any],
    *,
    pptx_path: Path | str | None = None,
    title: str | None = None,
) -> str:
    """Render the deck audit as a self-contained HTML string.

    Parameters
    ----------
    plan:
        A deck plan dict with at least ``title`` and ``slides`` keys.
        Each slide should have ``type``, ``title``, optional ``subtitle``,
        ``bullets``.
    audit:
        A ``rigor_audit`` result: ``{"passed": bool, "issues": [...]}``.
    pptx_path:
        Optional path to the rendered .pptx (linked from the header).
    title:
        Override for the report title. Defaults to "Deck audit — <plan title>".
    """
    slides = plan.get("slides", []) or []
    issues = audit.get("issues", []) or []
    passed = bool(audit.get("passed", True))

    by_slide, global_issues = _group_issues_by_slide(issues, len(slides))
    b, mj, mn = _summarize_severity(issues)

    report_title = title or f"Deck audit — {plan.get('title') or '(untitled deck)'}"

    summary_chips = [
        c.status_chip(f"{len(slides)} slides", "neutral"),
        c.status_chip(
            "PASSED" if passed else "ISSUES FOUND",
            "good" if passed else "bad",
        ),
        c.status_chip(f"{b} blocker{'s' if b != 1 else ''}", "bad" if b else "neutral"),
        c.status_chip(f"{mj} major", "bad" if mj else "neutral"),
        c.status_chip(f"{mn} minor", "warn" if mn else "neutral"),
    ]

    tldr_items: list[str] = []
    if passed and not issues:
        tldr_items.append("✓ Deck passed rigor audit — no issues raised.")
    else:
        tldr_items.append(
            f"Audit raised {len(issues)} issue{'s' if len(issues) != 1 else ''} across "
            f"{len(by_slide)} slide{'s' if len(by_slide) != 1 else ''}."
        )
        if b or mj:
            tldr_items.append(f"{b + mj} require attention before ship (blocker/major).")
        if global_issues:
            tldr_items.append(
                f"{len(global_issues)} issue{'s' if len(global_issues) != 1 else ''} not tied to a specific slide."
            )

    slide_cards: list[str] = []
    for idx, slide in enumerate(slides):
        slide_issues = by_slide.get(idx, [])
        sev = _severity_for_card(slide_issues)
        slide_title = slide.get("title") or f"Slide {idx + 1}"
        slide_type = slide.get("type") or "?"
        badges: list[tuple[str, str]] = [(slide_type, "neutral")]
        bk, mjk, mnk = _summarize_severity(slide_issues)
        if bk:
            badges.append((f"{bk} blocker", "bad"))
        if mjk:
            badges.append((f"{mjk} major", "bad"))
        if mnk:
            badges.append((f"{mnk} minor", "warn"))
        if not slide_issues:
            badges.append(("clean", "good"))
        slide_cards.append(
            c.severity_card(
                f"Slide {idx + 1} — {slide_title}",
                body=_slide_card_body(slide, slide_issues),
                severity=sev,
                badges=badges,
                filter_key=_filter_key_for(slide_issues),
            )
        )

    sections = [
        c.section(
            None,
            c.tldr_box(tldr_items),
        ),
        c.section(
            "Per-slide verdicts",
            c.filter_bar(
                [
                    ("All", "all"),
                    ("Blocker", "blocker"),
                    ("Major", "major"),
                    ("Minor", "minor"),
                    ("Clean", "ok"),
                ],
                target_selector=".vl-cards .vl-card",
            ),
            c.card_grid(slide_cards) if slide_cards else "<p>No slides in plan.</p>",
            number=1,
        ),
    ]

    if global_issues:
        rows = [
            [
                _safe(issue.get("loc", "(unknown)")),
                c.status_chip(
                    (issue.get("severity") or "?").upper(),
                    _level_for(issue.get("severity")),
                ),
                _safe(issue.get("kind", "")),
                _safe(issue.get("fix", "")),
            ]
            for issue in global_issues
        ]
        sections.append(
            c.section(
                "Global / unattributed issues",
                c.matrix_table(["Location", "Severity", "Kind", "Fix"], rows),
                number=2,
            )
        )

    meta_html = (
        f"<code>{_safe(pptx_path)}</code>"
        if pptx_path
        else "rigor_audit result · no rendered .pptx linked"
    )

    return render_report(
        title=report_title,
        eyebrow="vaultlab · slide audit",
        meta=meta_html,
        chips=summary_chips,
        sections=sections,
    )


def write_audit_report(
    out_path: Path | str,
    plan: dict[str, Any],
    audit: dict[str, Any],
    **kwargs: Any,
) -> Path:
    """Render and write the HTML audit. Returns the resolved Path."""
    html_str = build_audit_report_html(plan, audit, **kwargs)
    p = Path(out_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(html_str, encoding="utf-8")
    return p


__all__ = ["build_audit_report_html", "write_audit_report"]
