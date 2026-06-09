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

Severity = Literal["pass", "warn", "fail", "info", "flag", "neutral", "good", "bad"]

# Canonical status levels carry a colorblind-safe glyph. Legacy ``good`` /
# ``bad`` are accepted from un-migrated callers and normalised to pass / fail.
_LEVEL_ALIASES = {"good": "pass", "bad": "fail"}
_LEVEL_GLYPHS = {
    "pass": "✓",
    "warn": "⚠",
    "fail": "✕",
    "info": "?",
    "flag": "⚑",
    "neutral": "●",
}


def _norm_level(level: str) -> str:
    """Map a (possibly legacy) severity name to a canonical status level."""
    lvl = _LEVEL_ALIASES.get(level, level)
    return lvl if lvl in _LEVEL_GLYPHS else "neutral"


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


def _maybe_section(title: str | None, body: str, number: int | None = None) -> str:
    if title:
        if number is not None:
            sec_no = f'<span class="sec-no">§ {number:02d}</span>'
            head = f"<h2>{sec_no}{_esc(title)}</h2>\n<div class=\"sec-rule\"></div>\n"
        else:
            head = f"<h2>{_esc(title)}</h2>\n"
    else:
        head = ""
    return f'<section class="vl-section">\n{head}{body}\n</section>'


# ---------------------------------------------------------------------------
# 1. status_chip


def status_chip(label: str, level: Severity = "neutral") -> str:
    """Render an inline status badge with a colorblind-safe glyph.

    level: pass, warn, fail, info, flag, neutral. Legacy ``good`` / ``bad``
    are accepted and normalised to pass / fail.
    """
    lvl = _norm_level(level)
    glyph = _LEVEL_GLYPHS[lvl]
    return (
        f'<span class="vl-chip {lvl}">'
        f'<span class="vl-chip__g" aria-hidden="true">{glyph}</span>'
        f"{_esc(label)}</span>"
    )


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
    kind: str | None = None,
    href: str | None = None,
    filename: tuple[str, str] | str | None = None,
    badges: list[tuple[str, Severity]] | None = None,
    thumbnail: str | Path | None = None,
    actions: list[tuple[str, str]] | None = None,
    filter_key: str | None = None,
) -> str:
    """One card.

    severity controls the left tick of color; kind is the uppercase eyebrow
    above the title; href turns the card into a navigable ``<a>``; filename is
    a (name, size) pair (or bare name) for the dotted footer slot; badges
    render via status_chip; thumbnail is an inline src; actions are
    (label, copy-string) pairs that render as copy-to-clipboard buttons.
    """
    sev_cls = f" severity-{_norm_level(severity)}" if severity else ""
    fk = _attr("data-filter-key", filter_key)
    thumb = f'<img class="thumb" src="{_esc(thumbnail)}" alt="">' if thumbnail else ""
    kind_html = f'<div class="kind">{_esc(kind)}</div>' if kind else ""
    filename_html = ""
    if filename:
        if isinstance(filename, tuple):
            name, size = filename
            filename_html = (
                f'<div class="filename"><span>{_esc(name)}</span>'
                f'<span class="size">{_esc(size)}</span></div>'
            )
        else:
            filename_html = f'<div class="filename"><span>{_esc(filename)}</span></div>'
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
                f'<button class="vl-btn vl-btn--sm" type="button" '
                f'data-copy="{_esc(copy)}">{_esc(lbl)}</button>'
                for lbl, copy in actions
            )
            + "</div>"
        )
    tag = "a" if href else "div"
    href_attr = _attr("href", href)
    return (
        f'<{tag} class="vl-card{sev_cls}"{href_attr}{fk}>'
        f"{thumb}{kind_html}"
        f'<div class="title">{_esc(title)}</div>'
        f'<div class="body">{body}</div>'
        f"{filename_html}{badges_html}{actions_html}"
        f"</{tag}>"
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


def _infer_verdict(label: str) -> str:
    """Guess a colorblind-safe verdict from a kanban column label."""
    t = label.lower()
    if any(k in t for k in ("plagiar", "fabric", "flag")):
        return "flag"
    if any(k in t for k in ("accept", "approve", "keep", "pass", "robust", "fresh")):
        return "pass"
    if any(k in t for k in ("reject", "fail", "cut", "drop", "blocker")):
        return "fail"
    if any(k in t for k in ("review", "needs", "question", "open", "unsure")):
        return "info"
    if any(k in t for k in ("warn", "validat", "revis")):
        return "warn"
    return "neutral"


def kanban_board(
    columns: list[str],
    items: dict[str, list[str]],
    *,
    drag: bool = True,
    export: tuple[bool, bool] = (True, True),
    verdicts: dict[str, str] | None = None,
    hint: str | None = None,
) -> str:
    """Drag-and-drop board. columns is the ordered column labels; items maps
    column-label → list of item strings. export = (markdown, json) buttons.

    ``verdicts`` optionally maps a column label to a colorblind-safe verdict
    (pass / fail / warn / info / flag / neutral); unmapped columns are inferred
    from the label. Each column header emits the
    ``.glyph`` / ``.name`` / ``.count`` contract the shared JS depends on.
    """
    _ = drag
    verdicts = verdicts or {}
    col_html = []
    for c in columns:
        verdict = _norm_level(verdicts.get(c) or _infer_verdict(c))
        glyph = _LEVEL_GLYPHS[verdict]
        body = "".join(f'<div class="vl-item">{_esc(t)}</div>' for t in items.get(c, []))
        col_html.append(
            f'<div class="vl-col" data-verdict="{verdict}">'
            f"<h4>"
            f'<span class="glyph" aria-hidden="true">{glyph}</span>'
            f'<span class="name">{_esc(c)}</span>'
            f'<span class="count">{len(items.get(c, []))}</span>'
            f"</h4>"
            f'<div class="vl-col-body">{body}</div></div>'
        )
    btns = []
    if export[1]:
        btns.append(
            '<button class="vl-btn vl-btn--primary vl-export-json" type="button">'
            "Copy as JSON</button>"
        )
    if export[0]:
        btns.append(
            '<button class="vl-btn vl-export-md" type="button">'
            "Copy as markdown</button>"
        )
    bar = ""
    if btns:
        hint_html = (
            f'<span class="vl-export-hint">{_esc(hint)}</span>'
            if hint
            else '<span class="vl-export-hint">Drag items between piles, '
            "then copy the result back into your next prompt.</span>"
        )
        bar = f'<div class="vl-export-bar">{hint_html}{"".join(btns)}</div>'
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
        sample_html.append(f"<h4>{_esc(title)}</h4>")
        sample_html.append(f"<div class=\"sample\" data-context='{ctx_json}'></div>")
    samples_block = "".join(sample_html) or "<em>No samples</em>"
    return (
        '<div class="vl-editor">'
        f'<div class="pane"><h4>{_esc(label)}</h4>'
        f"<textarea>{_esc(template)}</textarea>"
        '<div class="counter">0 chars · ~0 tokens</div>'
        '<button class="vl-btn vl-btn--sm copy-prompt" type="button" '
        'style="margin-top:8px;">Copy prompt</button>'
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


def section(title: str | None, *body_parts: str, number: int | None = None) -> str:
    """Wrap content in a <section> with an optional H2.

    Pass ``number`` to render the letterpress ``§ NN`` eyebrow and the accented
    section divider rule.
    """
    return _maybe_section(title, "\n".join(body_parts), number)


# ---------------------------------------------------------------------------
# 16. stats_row


def stats_row(stats: list[tuple[str, str]] | dict[str, str]) -> str:
    """Letterpress key/value strip. Each entry is (label, value).

    A value may carry a trailing unit wrapped for de-emphasis by appending it
    after a ``|`` — e.g. ``("Total size", "412|kb")`` renders ``412`` large
    with a small ``kb``.
    """
    pairs = list(stats.items()) if isinstance(stats, dict) else list(stats)
    cells = []
    for k, v in pairs:
        v = str(v)
        if "|" in v:
            num, unit = v.split("|", 1)
            val = f"{_esc(num)}<small>{_esc(unit)}</small>"
        else:
            val = _esc(v)
        cells.append(
            f'<div class="vl-stat"><div class="k">{_esc(k)}</div>'
            f'<div class="v">{val}</div></div>'
        )
    return (
        '<div class="vl-stats" role="group" aria-label="Summary statistics">'
        f'{"".join(cells)}</div>'
    )


__all__ = [
    "Severity",
    "TimelineEvent",
    "status_chip",
    "stats_row",
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
