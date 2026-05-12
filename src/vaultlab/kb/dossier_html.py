"""HTML project-dossier report.

Consumer #5 of ``vaultlab.report``. Renders a :class:`Dossier`
(:mod:`vaultlab.kb.dossier`) as a single-file HTML — header with project
slug + freshness badge, tabbed 9-section navigation, source files
inventory, and a "what changed since last compile" hint.

Background: dossiers are the standing project mental model (SPEC-N). The
markdown form is loaded as Layer-0 context for every primitive, but as a
human-readable artifact the 9 sections benefit from tabbed nav. Same
source data, different surface.
"""

from __future__ import annotations

import html as _html
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from vaultlab.report import components as c
from vaultlab.report import render_report


def _safe(text: Any) -> str:
    return _html.escape(str(text or ""))


def _md_to_html(text: str) -> str:
    """Minimal markdown → HTML for dossier section bodies."""
    if not text:
        return ""
    out: list[str] = []
    buf: list[str] = []
    in_list = False

    def flush_paragraph() -> None:
        nonlocal buf
        if buf:
            joined = " ".join(buf).strip()
            if joined:
                out.append(f"<p>{_inline(joined)}</p>")
            buf = []

    def flush_list() -> None:
        nonlocal in_list
        if in_list:
            out.append("</ul>")
            in_list = False

    for raw in text.splitlines():
        line = raw.rstrip()
        if not line:
            flush_paragraph()
            flush_list()
            continue
        m = re.match(r"^(#{1,4})\s+(.+)$", line)
        if m:
            flush_paragraph()
            flush_list()
            level = min(len(m.group(1)) + 2, 6)
            out.append(f"<h{level}>{_inline(m.group(2))}</h{level}>")
            continue
        m = re.match(r"^[-*]\s+(.+)$", line)
        if m:
            flush_paragraph()
            if not in_list:
                out.append("<ul>")
                in_list = True
            out.append(f"<li>{_inline(m.group(1))}</li>")
            continue
        buf.append(line)
    flush_paragraph()
    flush_list()
    return "\n".join(out)


def _inline(text: str) -> str:
    text = _safe(text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"\*([^*]+)\*", r"<em>\1</em>", text)
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    text = re.sub(
        r"\[\[([^\]]+)\]\]",
        r'<span style="color:var(--accent);font-weight:500;">[[ \1 ]]</span>',
        text,
    )
    return text


def _freshness_badge(compiled_at: datetime) -> tuple[str, str]:
    """Compute freshness label + severity."""
    now = datetime.now(timezone.utc)
    if compiled_at.tzinfo is None:
        compiled_at = compiled_at.replace(tzinfo=timezone.utc)
    age_hours = (now - compiled_at).total_seconds() / 3600
    if age_hours < 24:
        return (f"fresh ({age_hours:.0f}h ago)", "good")
    if age_hours < 72:
        return (f"{age_hours / 24:.1f} days old", "warn")
    return (f"stale ({age_hours / 24:.0f} days old)", "bad")


def _section_payload(sec: Any) -> tuple[str, str, str, list[Path]]:
    """Extract (slug, title, body, sources) from a DossierSection or dict."""
    if hasattr(sec, "slug"):
        return sec.slug, sec.title, sec.body, list(getattr(sec, "sources", []) or [])
    return (
        sec.get("slug", ""),
        sec.get("title", ""),
        sec.get("body", ""),
        list(sec.get("sources", []) or []),
    )


def build_dossier_report_html(
    dossier: Any,
    *,
    title: str | None = None,
) -> str:
    """Render a :class:`Dossier` (or equivalent dict) as HTML.

    Accepts:
      * :class:`vaultlab.kb.dossier.Dossier` (uses .project_slug, .sections,
        .compiled_at attributes), or
      * a dict shaped like ``{"project_slug": ..., "sections": [...],
        "compiled_at": ...}`` where each section has slug/title/body/sources.
    """
    if hasattr(dossier, "project_slug"):
        project_slug = dossier.project_slug
        sections_raw = list(dossier.sections)
        compiled_at = dossier.compiled_at
        kb_root = getattr(dossier, "kb_root", None)
    else:
        project_slug = dossier.get("project_slug", "(unknown)")
        sections_raw = dossier.get("sections", []) or []
        compiled_at_raw = dossier.get("compiled_at")
        compiled_at = (
            compiled_at_raw if isinstance(compiled_at_raw, datetime) else datetime.now(timezone.utc)
        )
        kb_root = dossier.get("kb_root")

    report_title = title or f"Project dossier — {project_slug}"

    freshness_label, freshness_level = _freshness_badge(compiled_at)

    # Header chips
    summary_chips = [
        c.status_chip(project_slug, "neutral"),
        c.status_chip(freshness_label, freshness_level),
        c.status_chip(f"{len(sections_raw)} sections", "neutral"),
    ]

    tldr_items = [
        f"Standing mental model of the {project_slug} project, "
        f"compiled {compiled_at:%Y-%m-%d %H:%M UTC}.",
        "Loaded as Layer-0 context before non-trivial primitives. "
        "Refresh policy: daily, or on big events.",
    ]
    if freshness_level == "bad":
        tldr_items.append(
            "⚠ This dossier is stale — refresh via /refresh-dossier "
            f"{project_slug} before relying on it."
        )

    # Build tabbed sections
    tabs: dict[str, str] = {}
    all_sources: list[Path] = []
    for sec_raw in sections_raw:
        slug, sec_title, body, sources = _section_payload(sec_raw)
        all_sources.extend(sources)
        body_html = (
            _md_to_html(body) if body else '<p style="color:var(--muted);"><em>(empty)</em></p>'
        )
        source_block = ""
        if sources:
            source_list = "".join(f"<li><code>{_safe(str(s))}</code></li>" for s in sources[:6])
            source_block = (
                '<details style="margin-top:14px;border-top:1px solid var(--line-soft);padding-top:10px;">'
                '<summary style="cursor:pointer;font-size:12px;color:var(--muted);">'
                f"Sources ({len(sources)})</summary>"
                f'<ul style="font-size:12px;color:var(--ink-soft);margin:6px 0;padding-left:20px;">{source_list}</ul>'
                "</details>"
            )
        tabs[sec_title] = body_html + source_block

    sections_out = [
        c.section(
            None,
            c.tldr_box(tldr_items),
            f'<div style="margin:14px 0;">{"".join(summary_chips)}</div>',
        ),
        c.section(
            "Dossier sections",
            c.tabbed_block(tabs) if tabs else "<p>No sections compiled.</p>",
        ),
    ]

    if all_sources:
        # Dedupe by string repr for the appendix
        unique_sources = sorted({str(s) for s in all_sources})
        source_rows = [[f"<code>{_safe(s)}</code>"] for s in unique_sources[:80]]
        sections_out.append(
            c.section(
                "All source files referenced",
                c.matrix_table(["Path"], source_rows),
            )
        )

    meta_html = f"compiled {compiled_at:%Y-%m-%d %H:%M UTC}" + (
        f" · KB root <code>{_safe(kb_root)}</code>" if kb_root else ""
    )

    return render_report(
        title=report_title,
        eyebrow=f"vaultlab · dossier · {project_slug}",
        meta=meta_html,
        sections=sections_out,
    )


def write_dossier_report(
    out_path: Path | str,
    dossier: Any,
    **kwargs: Any,
) -> Path:
    """Render and write the dossier HTML."""
    html_str = build_dossier_report_html(dossier, **kwargs)
    p = Path(out_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(html_str, encoding="utf-8")
    return p


__all__ = ["build_dossier_report_html", "write_dossier_report"]
