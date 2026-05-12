"""HTML component primitives for vaultlab.report.

15 deep components composed into reports. Pure string functions — deterministic,
testable, framework-free. Interactive variants (tabs, kanban, editor, deck,
filter) depend on the inline JS bundled by html.py.

Modeled on Thariq Shihipar's "Unreasonable Effectiveness of HTML" gallery
(thariqs.github.io/html-effectiveness).
"""

from __future__ import annotations

import html as _html
import json as _json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

Severity = Literal["good", "warn", "bad", "neutral"]


# ---------------------------------------------------------------------------
# Internal helpers


def _esc(s: Any) -> str:
    return _html.escape(str(s), quote=True)


def _attr(name: str, value: Any) -> str:
    if value is None or value is False:
        return ""
    if value is True:
        return f" {name}"
    return f' {name}="{_esc(value)}"'


def _maybe_section(title: str | None, body: str) -> str:
    head = f"<h2>{_esc(title)}</h2>\n" if title else ""
    return f'<section class="vl-section">\n{head}{body}\n</section>'


# ---------------------------------------------------------------------------
# 1. status_chip


def status_chip(label: str, level: Severity = "neutral") -> str:
    """Render an inline status badge.

    level: good, warn, bad, neutral.
    """
    return f'<span class="vl-chip {level}">{_esc(label)}</span>'


# ---------------------------------------------------------------------------
# 2. tldr_box


def tldr_box(
    items: list[str] | str,
    *,
    label: str = "TL;DR",
) -> str:
    """Accent box for headline summary. Items can be a list (rendered as bullets)
    or a single string (rendered as paragraphs).
    """
    if isinstance(items, str):
        body = "".join(f"<p>{p}</p>" for p in items.split("\n\n") if p.strip())
    else:
        body = "<ul>" + "".join(f"<li>{_esc(i)}</li>" for i in items) + "</ul>"
    return f'<div class="vl-tldr"><p class="label">{_esc(label)}</p>{body}</div>'


# ---------------------------------------------------------------------------
# 3. card_grid + severity_card


def severity_card(
    title: str,
    *,
    body: str = "",
    severity: Severity | None = None,
    badges: list[tuple[str, Severity]] | None = None,
    thumbnail: str | Path | None = None,
    actions: list[tuple[str, str]] | None = None,
    filter_key: str | None = None,
) -> str:
    """One card. severity controls the left border; badges render via status_chip;
    thumbnail is an inline src (data URL or relative path); actions are
    (label, copy-string) pairs that render as copy-to-clipboard buttons.
    """
    sev_cls = f" severity-{severity}" if severity else ""
    fk = _attr("data-filter-key", filter_key)
    thumb = f'<img class="thumb" src="{_esc(thumbnail)}" alt="">' if thumbnail else ""
    badges_html = ""
    if badges:
        badges_html = (
            '<div class="footer">'
            + "".join(status_chip(lbl, lvl) for lbl, lvl in badges)
            + "</div>"
        )
    actions_html = ""
    if actions:
        actions_html = (
            '<div class="actions">'
            + "".join(
                f'<button data-copy="{_esc(copy)}">{_esc(lbl)}</button>' for lbl, copy in actions
            )
            + "</div>"
        )
    return (
        f'<div class="vl-card{sev_cls}"{fk}>'
        f"{thumb}"
        f'<div class="title">{_esc(title)}</div>'
        f'<div class="body">{body}</div>'
        f"{badges_html}{actions_html}"
        f"</div>"
    )


def card_grid(cards: list[str], *, min_width: int = 280) -> str:
    """Auto-fill responsive grid of pre-rendered cards."""
    style = f'style="--min-card: {min_width}px;"'
    return f'<div class="vl-cards" {style}>{"".join(cards)}</div>'


# ---------------------------------------------------------------------------
# 4. matrix_table


def matrix_table(
    columns: list[str],
    rows: list[list[str]],
    *,
    sortable: bool = False,
) -> str:
    """Standard table. Rows are pre-rendered HTML cell contents (escape your own
    text); columns are header labels (auto-escaped). sortable not yet wired.
    """
    _ = sortable  # reserved for v0.0.5
    head = "<thead><tr>" + "".join(f"<th>{_esc(c)}</th>" for c in columns) + "</tr></thead>"
    body_rows = []
    for row in rows:
        body_rows.append("<tr>" + "".join(f"<td>{cell}</td>" for cell in row) + "</tr>")
    body = "<tbody>" + "".join(body_rows) + "</tbody>"
    return f'<table class="vl-table">{head}{body}</table>'


# ---------------------------------------------------------------------------
# 5. compare_panel


def compare_panel(
    left_label: str,
    left_content: str,
    right_label: str,
    right_content: str,
) -> str:
    """Two-pane side-by-side compare. Contents are HTML; pre-escape your strings."""
    return (
        '<div class="vl-compare">'
        f'<div><div class="label">{_esc(left_label)}</div>{left_content}</div>'
        f'<div><div class="label">{_esc(right_label)}</div>{right_content}</div>'
        "</div>"
    )


# ---------------------------------------------------------------------------
# 6. collapsible_step


def collapsible_step(
    title: str,
    body: str,
    *,
    file_path: str | None = None,
    line: int | None = None,
    open_by_default: bool = False,
) -> str:
    """Expandable <details> step. body is HTML. Optional file:line reference."""
    ref = ""
    if file_path:
        loc = f"{file_path}:{line}" if line is not None else file_path
        ref = f' <span class="ref">{_esc(loc)}</span>'
    return (
        f'<details class="vl-step"{_attr("open", open_by_default)}>'
        f"<summary>{_esc(title)}{ref}</summary>"
        f'<div class="body">{body}</div>'
        f"</details>"
    )


# ---------------------------------------------------------------------------
# 7. tabbed_block


def tabbed_block(tabs: dict[str, str], *, default: int = 0) -> str:
    """Tabbed content. Keys are tab labels, values are HTML pane content."""
    items = list(tabs.items())
    label_html = "".join(
        f'<div class="vl-tab-label{" active" if i == default else ""}">{_esc(lbl)}</div>'
        for i, (lbl, _) in enumerate(items)
    )
    pane_html = "".join(
        f'<div class="vl-tab-pane{" active" if i == default else ""}">{content}</div>'
        for i, (_, content) in enumerate(items)
    )
    return f'<div class="vl-tabs"><div class="vl-tab-bar">{label_html}</div>{pane_html}</div>'


# ---------------------------------------------------------------------------
# 8. timeline


@dataclass
class TimelineEvent:
    timestamp: str
    label: str
    body: str = ""


def timeline(events: list[TimelineEvent | tuple[str, str, str]]) -> str:
    """Vertical timeline. Events as TimelineEvent or (ts, label, body) tuples."""
    parts = []
    for ev in events:
        if isinstance(ev, tuple):
            ts, label, body = ev
        else:
            ts, label, body = ev.timestamp, ev.label, ev.body
        parts.append(
            f'<div class="event">'
            f'<div class="ts">{_esc(ts)}</div>'
            f'<div class="label">{_esc(label)}</div>'
            f'<div class="body">{body}</div>'
            f"</div>"
        )
    return f'<div class="vl-timeline">{"".join(parts)}</div>'


# ---------------------------------------------------------------------------
# 9. svg_arg_graph


def svg_arg_graph(
    nodes: list[dict[str, Any]],
    edges: list[tuple[str, str]],
    *,
    hot_path: list[str] | None = None,
    width: int = 600,
    height: int = 320,
) -> str:
    """Inline SVG graph. Nodes need at least {id, x, y, label}; edges are
    (from_id, to_id). hot_path lists node IDs to highlight (and edges between
    them get the .hot class).
    """
    hot = set(hot_path or [])
    node_by_id = {n["id"]: n for n in nodes}
    parts = [f'<svg viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg">']
    # edges first so nodes sit on top
    for a, b in edges:
        na, nb = node_by_id.get(a), node_by_id.get(b)
        if not na or not nb:
            continue
        cls = "edge hot" if a in hot and b in hot else "edge"
        parts.append(
            f'<line class="{cls}" x1="{na["x"]}" y1="{na["y"]}" x2="{nb["x"]}" y2="{nb["y"]}"/>'
        )
    for n in nodes:
        cls = "node hot" if n["id"] in hot else "node"
        r = n.get("r", 28)
        parts.append(
            f'<g><circle class="{cls}" cx="{n["x"]}" cy="{n["y"]}" r="{r}"/>'
            f'<text class="node-label" x="{n["x"]}" y="{n["y"] + 4}">{_esc(n["label"])}</text></g>'
        )
    parts.append("</svg>")
    return f'<div class="vl-graph">{"".join(parts)}</div>'


# ---------------------------------------------------------------------------
# 10. kanban_board


def kanban_board(
    columns: list[str],
    items: dict[str, list[str]],
    *,
    drag: bool = True,
    export: tuple[bool, bool] = (True, True),
) -> str:
    """Drag-and-drop board. columns is the ordered column labels; items maps
    column-label → list of item strings. export = (markdown, json) buttons.
    """
    _ = drag
    col_html = []
    for c in columns:
        body = "".join(f'<div class="vl-item">{_esc(t)}</div>' for t in items.get(c, []))
        col_html.append(
            f'<div class="vl-col"><h4>{_esc(c)}</h4><div class="vl-col-body">{body}</div></div>'
        )
    md_btn = '<button class="vl-export-md">Copy as markdown</button>' if export[0] else ""
    json_btn = '<button class="vl-export-json">Copy as JSON</button>' if export[1] else ""
    bar = f'<div class="vl-export-bar">{md_btn}{json_btn}</div>' if (md_btn or json_btn) else ""
    return (
        f'<div><div class="vl-kanban" style="--cols: {len(columns)};">'
        f"{''.join(col_html)}</div>{bar}</div>"
    )


# ---------------------------------------------------------------------------
# 11. template_editor


def template_editor(
    template: str,
    samples: list[dict[str, str]],
    *,
    sample_titles: list[str] | None = None,
    label: str = "Template",
) -> str:
    """Live-preview template editor.

    template — text with {{var}} placeholders.
    samples — list of dicts mapping var → sample value. Each dict re-renders
              the template live as the user types.
    """
    titles = sample_titles or [f"Sample {i + 1}" for i in range(len(samples))]
    sample_html = []
    for title, ctx in zip(titles, samples, strict=False):
        ctx_json = _json.dumps(ctx)
        sample_html.append(f"<div class=\"sample\" data-context='{ctx_json}'></div>")
        sample_html.insert(
            -1, f'<div style="font-size:11px;color:var(--muted);">{_esc(title)}</div>'
        )
    samples_block = "".join(sample_html) or "<em>No samples</em>"
    return (
        '<div class="vl-editor">'
        f'<div class="pane"><h4>{_esc(label)}</h4>'
        f"<textarea>{_esc(template)}</textarea>"
        '<div class="counter">0 chars · ~0 tokens</div>'
        '<button class="copy-prompt" style="margin-top:8px;font-size:12px;padding:6px 12px;border:1px solid var(--line);background:var(--bg-soft);border-radius:4px;cursor:pointer;">Copy prompt</button>'
        "</div>"
        '<div class="pane"><h4>Live preview</h4>'
        f'<div class="samples">{samples_block}</div>'
        "</div></div>"
    )


# ---------------------------------------------------------------------------
# 12. margin_glossary


def margin_glossary(term: str, definition: str) -> str:
    """Inline glossary callout."""
    return (
        f'<div class="vl-gloss"><span class="term">{_esc(term)}</span> — '
        f'<span class="def">{_esc(definition)}</span></div>'
    )


# ---------------------------------------------------------------------------
# 13. keynav_deck


def keynav_deck(slides: list[tuple[str, str]]) -> str:
    """Arrow-key navigable slide deck. slides is list of (title, html_content)."""
    slide_html = "".join(
        f'<div class="slide{" active" if i == 0 else ""}"><h3>{_esc(title)}</h3>{content}</div>'
        for i, (title, content) in enumerate(slides)
    )
    return (
        '<div class="vl-deck" tabindex="0">'
        f"{slide_html}"
        '<div class="nav">'
        '<button class="prev">← Prev</button>'
        f'<span class="pos">1 / {len(slides)}</span>'
        '<button class="next">Next →</button>'
        "</div></div>"
    )


# ---------------------------------------------------------------------------
# 14. filter_bar (shared utility — wires .vl-filter UI to vl-card / row filtering)


def filter_bar(
    buckets: list[tuple[str, str]],
    *,
    target_selector: str,
    default_key: str = "all",
) -> str:
    """Filter bar that toggles visibility of elements matching data-filter-key.

    buckets — list of (label, key) tuples. Key "all" shows everything.
    target_selector — CSS selector for elements with data-filter-key attrs.
    """
    btns = "".join(
        f'<button class="{"active" if k == default_key else ""}" '
        f'data-filter="{_esc(k)}">{_esc(lbl)}</button>'
        for lbl, k in buckets
    )
    return f'<div class="vl-filter" data-target="{_esc(target_selector)}">{btns}</div>'


# ---------------------------------------------------------------------------
# 15. section (wrapper)


def section(title: str | None, *body_parts: str) -> str:
    """Wrap content in a <section> with optional H2."""
    return _maybe_section(title, "\n".join(body_parts))


__all__ = [
    "Severity",
    "TimelineEvent",
    "status_chip",
    "tldr_box",
    "severity_card",
    "card_grid",
    "matrix_table",
    "compare_panel",
    "collapsible_step",
    "tabbed_block",
    "timeline",
    "svg_arg_graph",
    "kanban_board",
    "template_editor",
    "margin_glossary",
    "keynav_deck",
    "filter_bar",
    "section",
]
