"""Bundled CSS for vaultlab.report HTML output.

Single-file, no external assets, system-font stack, slate/indigo palette,
print + mobile responsive. Built from Thariq Shihipar's "Unreasonable
Effectiveness of HTML" gallery patterns (Anthropic, 2026).
"""

from __future__ import annotations

CSS = """
:root {
  --ink: #0f172a;
  --ink-soft: #334155;
  --muted: #64748b;
  --line: #e2e8f0;
  --line-soft: #f1f5f9;
  --bg: #ffffff;
  --bg-soft: #f8fafc;
  --accent: #4f46e5;
  --accent-soft: #eef2ff;
  --good: #15803d;
  --good-bg: #f0fdf4;
  --good-line: #bbf7d0;
  --warn: #b45309;
  --warn-bg: #fffbeb;
  --warn-line: #fde68a;
  --bad: #b91c1c;
  --bad-bg: #fef2f2;
  --bad-line: #fecaca;
  --code-bg: #0f172a;
  --code-ink: #e2e8f0;
  --shadow: 0 2px 8px rgba(15, 23, 42, 0.06);
}
[data-theme="dark"] {
  --ink: #f1f5f9;
  --ink-soft: #cbd5e1;
  --muted: #94a3b8;
  --line: #334155;
  --line-soft: #1e293b;
  --bg: #0f172a;
  --bg-soft: #1e293b;
}
* { box-sizing: border-box; }
html, body { background: var(--bg); color: var(--ink); margin: 0; padding: 0; }
body {
  font: 15px/1.55 -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui,
        "Helvetica Neue", Arial, sans-serif;
}
.vl-wrap { max-width: 1180px; margin: 0 auto; padding: 36px 24px 80px; }
.vl-head { border-bottom: 1px solid var(--line); padding-bottom: 18px; margin-bottom: 28px; }
.vl-head .eyebrow { color: var(--muted); font-size: 13px; letter-spacing: 0.04em; text-transform: uppercase; }
.vl-head h1 { font-size: 28px; line-height: 1.2; margin: 6px 0 8px; letter-spacing: -0.01em; }
.vl-head .meta { color: var(--muted); font-size: 13px; }
.vl-section { margin: 44px 0; }
.vl-section > h2 { font-size: 21px; margin: 0 0 12px; letter-spacing: -0.005em; }
.vl-section > h3 { font-size: 16px; margin: 18px 0 8px; }
.vl-section p { margin: 0 0 12px; }
a { color: var(--accent); }
code { font: 13px/1.4 ui-monospace, SFMono-Regular, "Cascadia Code", Menlo, monospace; background: var(--bg-soft); padding: 1px 5px; border-radius: 3px; }
pre { background: var(--code-bg); color: var(--code-ink); border-radius: 4px; padding: 12px 14px; font: 12px/1.5 ui-monospace, SFMono-Regular, Menlo, monospace; overflow-x: auto; margin: 8px 0; }

/* tldr_box */
.vl-tldr { background: var(--accent-soft); border: 1px solid #c7d2fe; border-left: 4px solid var(--accent); border-radius: 6px; padding: 16px 18px; }
.vl-tldr .label { margin: 0 0 8px; color: var(--accent); font-size: 13px; letter-spacing: 0.06em; text-transform: uppercase; font-weight: 600; }
.vl-tldr ul { margin: 0; padding-left: 20px; }
.vl-tldr p:last-child, .vl-tldr li:last-child { margin-bottom: 0; }

/* status_chip */
.vl-chip { display: inline-block; font-size: 11px; font-weight: 600; padding: 2px 8px; border-radius: 3px; letter-spacing: 0.02em; vertical-align: middle; }
.vl-chip.good { background: var(--good-bg); color: var(--good); border: 1px solid var(--good-line); }
.vl-chip.warn { background: var(--warn-bg); color: var(--warn); border: 1px solid var(--warn-line); }
.vl-chip.bad { background: var(--bad-bg); color: var(--bad); border: 1px solid var(--bad-line); }
.vl-chip.neutral { background: var(--line-soft); color: var(--ink-soft); border: 1px solid var(--line); }

/* card_grid + severity_card */
.vl-cards { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 14px; }
.vl-card { border: 1px solid var(--line); border-radius: 8px; padding: 14px 16px; background: var(--bg); display: flex; flex-direction: column; transition: border-color 0.15s, box-shadow 0.15s; }
.vl-card:hover { border-color: var(--accent); box-shadow: var(--shadow); }
.vl-card .title { font-weight: 600; font-size: 14px; margin-bottom: 6px; }
.vl-card .body { font-size: 13px; color: var(--ink-soft); line-height: 1.5; flex-grow: 1; }
.vl-card .footer { display: flex; gap: 6px; margin-top: 10px; flex-wrap: wrap; }
.vl-card .thumb { width: 100%; border-radius: 4px; margin-bottom: 8px; border: 1px solid var(--line-soft); }
.vl-card .actions { display: flex; gap: 6px; margin-top: 8px; }
.vl-card .actions button { font-size: 12px; padding: 4px 10px; border: 1px solid var(--line); background: var(--bg-soft); color: var(--ink-soft); border-radius: 4px; cursor: pointer; }
.vl-card .actions button:hover { border-color: var(--accent); color: var(--accent); }
.vl-card.severity-bad { border-left: 3px solid var(--bad); }
.vl-card.severity-warn { border-left: 3px solid var(--warn); }
.vl-card.severity-good { border-left: 3px solid var(--good); }

/* matrix_table */
.vl-table { width: 100%; border-collapse: collapse; font-size: 13px; margin: 8px 0; }
.vl-table th, .vl-table td { padding: 10px 12px; text-align: left; border-bottom: 1px solid var(--line-soft); vertical-align: top; }
.vl-table thead th { background: var(--bg-soft); border-bottom: 1px solid var(--line); font-weight: 600; font-size: 12px; text-transform: uppercase; letter-spacing: 0.04em; color: var(--muted); }
.vl-table tbody tr:hover td { background: var(--bg-soft); }
.vl-table td.path { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 12px; color: var(--ink-soft); }

/* compare_panel */
.vl-compare { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; margin: 14px 0; }
.vl-compare > div { border: 1px solid var(--line); border-radius: 6px; padding: 12px 14px; background: var(--bg-soft); }
.vl-compare .label { font-size: 11px; text-transform: uppercase; letter-spacing: 0.06em; color: var(--muted); margin-bottom: 6px; }

/* collapsible_step */
.vl-step { border: 1px solid var(--line); border-radius: 6px; margin: 8px 0; background: var(--bg); }
.vl-step > summary { padding: 12px 16px; cursor: pointer; font-weight: 600; font-size: 14px; list-style: none; display: flex; align-items: center; gap: 8px; }
.vl-step > summary::before { content: "▸"; color: var(--muted); transition: transform 0.15s; display: inline-block; }
.vl-step[open] > summary::before { transform: rotate(90deg); }
.vl-step > summary:hover { background: var(--bg-soft); }
.vl-step .body { padding: 0 16px 14px; font-size: 13px; color: var(--ink-soft); line-height: 1.5; }
.vl-step .ref { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 12px; color: var(--accent); }

/* tabbed_block */
.vl-tabs { border: 1px solid var(--line); border-radius: 6px; overflow: hidden; margin: 8px 0; }
.vl-tabs .vl-tab-bar { display: flex; background: var(--bg-soft); border-bottom: 1px solid var(--line); }
.vl-tabs .vl-tab-label { padding: 10px 16px; cursor: pointer; font-size: 13px; font-weight: 500; color: var(--ink-soft); border-right: 1px solid var(--line); user-select: none; }
.vl-tabs .vl-tab-label:hover { background: var(--bg); color: var(--ink); }
.vl-tabs .vl-tab-label.active { background: var(--bg); color: var(--accent); border-bottom: 2px solid var(--accent); }
.vl-tabs .vl-tab-pane { display: none; padding: 14px 16px; }
.vl-tabs .vl-tab-pane.active { display: block; }

/* timeline */
.vl-timeline { border-left: 2px solid var(--line); padding-left: 16px; margin: 12px 0; }
.vl-timeline .event { position: relative; padding: 6px 0 12px; }
.vl-timeline .event::before { content: ""; position: absolute; left: -22px; top: 12px; width: 10px; height: 10px; background: var(--bg); border: 2px solid var(--accent); border-radius: 50%; }
.vl-timeline .ts { font-size: 12px; color: var(--muted); font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }
.vl-timeline .label { font-weight: 600; font-size: 14px; margin: 2px 0; }
.vl-timeline .body { font-size: 13px; color: var(--ink-soft); }

/* svg_arg_graph */
.vl-graph { margin: 12px 0; }
.vl-graph svg { max-width: 100%; height: auto; }
.vl-graph .node { fill: var(--bg-soft); stroke: var(--line); stroke-width: 1.2; }
.vl-graph .node.hot { fill: var(--accent-soft); stroke: var(--accent); }
.vl-graph .node-label { font: 12px/1.2 system-ui, sans-serif; fill: var(--ink); text-anchor: middle; }
.vl-graph .edge { stroke: var(--line); stroke-width: 1.5; fill: none; }
.vl-graph .edge.hot { stroke: var(--accent); stroke-width: 2; }

/* kanban_board */
.vl-kanban { display: grid; grid-template-columns: repeat(var(--cols, 4), 1fr); gap: 12px; margin: 12px 0; }
.vl-col { border: 1px solid var(--line); border-radius: 6px; background: var(--bg-soft); padding: 10px; min-height: 200px; }
.vl-col h4 { margin: 0 0 8px; font-size: 13px; color: var(--ink-soft); text-transform: uppercase; letter-spacing: 0.04em; }
.vl-item { border: 1px solid var(--line); background: var(--bg); border-radius: 4px; padding: 8px 10px; margin-bottom: 6px; cursor: grab; font-size: 13px; transition: box-shadow 0.15s; }
.vl-item:hover { box-shadow: var(--shadow); }
.vl-item.dragging { opacity: 0.4; }
.vl-col.over { background: var(--accent-soft); }
.vl-export-bar { margin-top: 10px; display: flex; gap: 8px; }
.vl-export-bar button { font-size: 12px; padding: 6px 12px; border: 1px solid var(--line); background: var(--bg); color: var(--ink-soft); border-radius: 4px; cursor: pointer; }
.vl-export-bar button:hover { border-color: var(--accent); color: var(--accent); }

/* template_editor */
.vl-editor { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; margin: 12px 0; }
.vl-editor .pane { border: 1px solid var(--line); border-radius: 6px; padding: 12px; background: var(--bg); }
.vl-editor .pane h4 { margin: 0 0 8px; font-size: 12px; text-transform: uppercase; letter-spacing: 0.04em; color: var(--muted); }
.vl-editor textarea { width: 100%; min-height: 200px; font: 13px/1.5 ui-monospace, SFMono-Regular, Menlo, monospace; border: 1px solid var(--line); border-radius: 4px; padding: 10px; resize: vertical; background: var(--bg-soft); color: var(--ink); }
.vl-editor .samples { display: flex; flex-direction: column; gap: 8px; }
.vl-editor .sample { font-size: 12px; padding: 8px 10px; background: var(--bg-soft); border: 1px solid var(--line-soft); border-radius: 4px; white-space: pre-wrap; max-height: 120px; overflow-y: auto; }
.vl-editor .counter { font-size: 11px; color: var(--muted); margin-top: 6px; }
.vl-var { background: var(--accent-soft); color: var(--accent); padding: 1px 4px; border-radius: 2px; font-weight: 500; }

/* margin_glossary */
.vl-gloss { background: var(--bg-soft); border-left: 3px solid var(--muted); padding: 8px 12px; margin: 8px 0; font-size: 13px; }
.vl-gloss .term { font-weight: 600; color: var(--ink); }
.vl-gloss .def { color: var(--ink-soft); }

/* keynav_deck */
.vl-deck { border: 1px solid var(--line); border-radius: 6px; background: var(--bg); margin: 12px 0; }
.vl-deck .slide { display: none; padding: 24px; min-height: 400px; }
.vl-deck .slide.active { display: block; }
.vl-deck .slide h3 { font-size: 22px; margin: 0 0 14px; }
.vl-deck .nav { display: flex; align-items: center; justify-content: space-between; padding: 10px 14px; background: var(--bg-soft); border-top: 1px solid var(--line); border-radius: 0 0 6px 6px; }
.vl-deck .nav button { font-size: 13px; padding: 6px 14px; border: 1px solid var(--line); background: var(--bg); color: var(--ink); border-radius: 4px; cursor: pointer; }
.vl-deck .nav .pos { font-size: 12px; color: var(--muted); font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }

/* filter bar (shared) */
.vl-filter { display: flex; gap: 8px; flex-wrap: wrap; margin: 10px 0; }
.vl-filter button { font-size: 12px; padding: 4px 10px; border: 1px solid var(--line); background: var(--bg); color: var(--ink-soft); border-radius: 3px; cursor: pointer; }
.vl-filter button.active, .vl-filter button:hover { background: var(--accent-soft); color: var(--accent); border-color: var(--accent); }

/* footer */
.vl-foot { margin-top: 60px; padding-top: 18px; border-top: 1px solid var(--line); color: var(--muted); font-size: 12px; }

/* responsive */
@media (max-width: 768px) {
  .vl-wrap { padding: 24px 16px 60px; }
  .vl-head h1 { font-size: 22px; }
  .vl-compare, .vl-editor { grid-template-columns: 1fr; }
  .vl-kanban { grid-template-columns: 1fr; }
}
@media print {
  body { font-size: 12px; }
  .vl-card:hover { box-shadow: none; }
  .vl-section { page-break-inside: avoid; }
  .vl-export-bar, .vl-filter { display: none; }
}
"""
