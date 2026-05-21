"""Bundled CSS for vaultlab.report HTML output.

Single-file, no external assets, system-font stack. Aesthetic: "printed lab
notebook on warm paper" — system serif display, warm off-white paper, a single
fountain-pen ink-blue accent, a colorblind-safe status palette, hairline rules.
Print + mobile responsive, with a dark theme on ``[data-theme="dark"]``.

This is the canonical visual system shared by every consumer page. Ported from
the Claude Design handoff (``design_handoff_vaultlab_visual_system/``).
"""

from __future__ import annotations

CSS = """\
/* ============================================================
   vaultlab.report — shared visual system
   ============================================================
   This is the SINGLE source of truth for the visual system.
   Every consumer page inlines this into an inline style block;
   no external stylesheet is loaded at runtime.

   Aesthetic: printed lab notebook on warm paper.
   - System serif (Iowan / Charter / Sitka / Cambria / Georgia)
     for display, system sans for body, ui-monospace for codes
     and metadata.
   - Single fountain-pen ink accent. No multi-hue gradients.
   - Status palette is colorblind-safe (deuteranopia /
     protanopia): lightness AND hue separation, plus a textual
     label and a glyph on every chip.
   - 1px warm hairline rules, 2–4px radii, no drop shadows.
   ============================================================ */

:root {
  /* Paper & ink */
  --paper:      #faf8f3;
  --paper-soft: #f3eee4;
  --paper-sunk: #ebe6d8;
  --ink:        #1a1a1f;
  --ink-1:      #3a3a45;
  --ink-2:      #6b6660;
  --ink-3:      #948f86;
  --rule:       #d8d1c2;
  --rule-soft:  #e8e2d4;

  /* Accent — fountain-pen ink */
  --accent:        #2f4a6b;
  --accent-strong: #1c3148;
  --accent-soft:   #dde4ed;

  /* Status — colorblind-safe: lightness AND hue separated, always paired with text. */
  --pass:      #115e4a;  --pass-soft:  #d8e8d6;
  --warn:      #8a5400;  --warn-soft:  #f1e2bc;
  --fail:      #8a2820;  --fail-soft:  #ecd5cf;
  --info:      #234a6f;  --info-soft:  #d8e0ec;
  --flag:      #7a3200;  --flag-soft:  #ecd6bd;

  /* Code */
  --code-bg:   #1d1c19;
  --code-ink:  #ebe5d6;
  --code-mute: #8e887a;

  /* Type */
  --font-serif: "Iowan Old Style", "Charter", "Sitka Text", Cambria, "Times New Roman", Georgia, serif;
  --font-sans:  -apple-system, BlinkMacSystemFont, "Segoe UI", "Helvetica Neue", Arial, system-ui, sans-serif;
  --font-mono:  ui-monospace, "SF Mono", "Cascadia Mono", Menlo, Consolas, "Liberation Mono", monospace;

  /* Spacing scale — small integers, predictable */
  --s1: 4px;  --s2: 8px;  --s3: 12px; --s4: 16px;
  --s5: 24px; --s6: 32px; --s7: 48px; --s8: 64px;

  /* Radii — restrained */
  --r1: 2px;  --r2: 4px;
  --press: 0 1px 0 rgba(26,26,31,0.04);
}

[data-theme="dark"] {
  --paper:      #1a1916;
  --paper-soft: #232017;
  --paper-sunk: #2b271d;
  --ink:        #ece6d8;
  --ink-1:      #c8c2b3;
  --ink-2:      #8e8a82;
  --ink-3:      #6b6660;
  --rule:       #3a342a;
  --rule-soft:  #2b271d;
  --accent:        #8db0d4;
  --accent-strong: #b5cae0;
  --accent-soft:   #2a3548;
  --pass: #6dba90;  --pass-soft: #1a3328;
  --warn: #d9a04a;  --warn-soft: #3d2e14;
  --fail: #d27a6e;  --fail-soft: #3a201c;
  --info: #88a8cc;  --info-soft: #1f2c3d;
  --flag: #d99c4a;  --flag-soft: #3d2810;
  --code-bg:  #0f0e0b;
  --code-ink: #d8d2c2;
}

/* ─── Base ─────────────────────────────────────────────── */
*, *::before, *::after { box-sizing: border-box; }
html { -webkit-text-size-adjust: 100%; }
body {
  margin: 0;
  background: var(--paper);
  color: var(--ink);
  font: 16px/1.6 var(--font-sans);
  font-feature-settings: "kern", "ss01";
  -webkit-font-smoothing: antialiased;
  text-rendering: optimizeLegibility;
}
a { color: var(--accent); text-decoration: underline; text-decoration-thickness: 1px; text-underline-offset: 2px; }
a:hover { color: var(--accent-strong); text-decoration-thickness: 2px; }
a:focus-visible, button:focus-visible, [tabindex]:focus-visible, summary:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 2px;
  border-radius: 2px;
}
::selection { background: var(--accent-soft); color: var(--accent-strong); }

code, kbd, samp {
  font: 13px/1.4 var(--font-mono);
  background: var(--paper-soft);
  padding: 1px 5px;
  border-radius: 2px;
  color: var(--ink-1);
  border: 1px solid var(--rule-soft);
}
pre {
  font: 12.5px/1.55 var(--font-mono);
  background: var(--code-bg);
  color: var(--code-ink);
  padding: 14px 16px;
  border-radius: var(--r1);
  overflow-x: auto;
  margin: 12px 0;
}

/* ─── Layout ───────────────────────────────────────────── */
.vl-wrap { max-width: 1080px; margin: 0 auto; padding: 0 24px; }

/* Masthead: thin top strip with brand + meta */
.vl-masthead {
  background: var(--paper-soft);
  border-bottom: 1px solid var(--rule);
}
.vl-masthead .vl-wrap {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 16px;
  padding-top: 10px;
  padding-bottom: 10px;
  flex-wrap: wrap;
}
.vl-mark {
  font: italic 500 17px/1 var(--font-serif);
  letter-spacing: -0.005em;
  color: var(--ink);
  text-decoration: none;
}
.vl-mark::before {
  content: "§";
  font-style: normal;
  font-weight: 400;
  margin-right: 4px;
  color: var(--accent);
}
.vl-mast-meta {
  font: 11px/1.4 var(--font-mono);
  color: var(--ink-2);
  letter-spacing: 0.06em;
  text-transform: uppercase;
  display: flex;
  align-items: baseline;
  gap: 12px;
  flex-wrap: wrap;
}
.vl-theme-toggle {
  appearance: none;
  background: transparent;
  border: 1px solid var(--rule);
  color: var(--ink-2);
  font: 11px/1 var(--font-mono);
  letter-spacing: 0.08em;
  text-transform: uppercase;
  padding: 4px 8px;
  border-radius: var(--r1);
  cursor: pointer;
}
.vl-theme-toggle:hover { color: var(--ink); border-color: var(--ink-2); }

/* Page header */
.vl-head {
  padding: 56px 0 28px;
  border-bottom: 1px solid var(--rule);
  margin-bottom: 40px;
  position: relative;
}
.vl-head .breadcrumb {
  font: 11px/1 var(--font-mono);
  color: var(--ink-3);
  text-transform: uppercase;
  letter-spacing: 0.1em;
  margin-bottom: 22px;
}
.vl-head .breadcrumb a { color: var(--ink-2); text-decoration: none; }
.vl-head .breadcrumb a:hover { color: var(--ink); text-decoration: underline; }
.vl-head .breadcrumb .sep { color: var(--ink-3); margin: 0 6px; }
.vl-head h1 {
  font: 400 40px/1.12 var(--font-serif);
  letter-spacing: -0.015em;
  margin: 0 0 12px;
  color: var(--ink);
  text-wrap: balance;
}
.vl-head .lede {
  font: italic 400 19px/1.5 var(--font-serif);
  color: var(--ink-1);
  margin: 0 0 18px;
  max-width: 62ch;
  text-wrap: pretty;
}
.vl-head .meta {
  font: 12px/1.5 var(--font-mono);
  color: var(--ink-2);
  letter-spacing: 0.02em;
}
.vl-head .meta code { background: transparent; border: 0; padding: 0; color: var(--ink-1); }
.vl-head .chip-row { display: flex; gap: 6px; flex-wrap: wrap; margin-top: 14px; }

/* Sections */
.vl-section { margin: 48px 0; position: relative; }
.vl-section > h2 {
  font: 400 26px/1.2 var(--font-serif);
  letter-spacing: -0.005em;
  margin: 0 0 6px;
  color: var(--ink);
  display: flex;
  align-items: baseline;
  gap: 14px;
}
.vl-section > h2 .sec-no {
  font: 600 11px/1 var(--font-mono);
  color: var(--ink-3);
  letter-spacing: 0.16em;
  text-transform: uppercase;
  flex-shrink: 0;
  padding-top: 6px;
}
.vl-section > h2 + .sec-rule {
  height: 1px;
  background: var(--rule);
  margin: 0 0 18px;
  position: relative;
}
.vl-section > h2 + .sec-rule::before {
  content: "";
  position: absolute;
  left: 0; top: 0;
  width: 60px; height: 1px;
  background: var(--accent);
}
.vl-section > h3 { font: 600 15px/1.3 var(--font-sans); margin: 24px 0 10px; color: var(--ink); }
.vl-section p { margin: 0 0 12px; color: var(--ink-1); max-width: 70ch; }
.vl-section p code { color: var(--ink-1); }

/* ─── TL;DR annotation ─────────────────────────────────── */
.vl-tldr {
  background: var(--paper-soft);
  border-left: 3px solid var(--accent);
  padding: 18px 22px;
  margin: 14px 0 24px;
  border-radius: 0 var(--r1) var(--r1) 0;
}
.vl-tldr .label {
  font: 600 11px/1 var(--font-mono);
  color: var(--accent);
  letter-spacing: 0.14em;
  text-transform: uppercase;
  margin: 0 0 12px;
}
.vl-tldr ul { margin: 0; padding-left: 18px; color: var(--ink-1); }
.vl-tldr li { margin-bottom: 6px; line-height: 1.5; }
.vl-tldr li:last-child { margin-bottom: 0; }
.vl-tldr p { margin: 0 0 6px; color: var(--ink-1); line-height: 1.55; }
.vl-tldr p:last-child { margin-bottom: 0; }

/* ─── Status chips ─────────────────────────────────────── */
/* Always carries a text label. Optional glyph via .vl-chip__g. */
.vl-chip {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font: 600 11px/1 var(--font-mono);
  letter-spacing: 0.08em;
  text-transform: uppercase;
  padding: 4px 8px 4px 7px;
  border-radius: var(--r1);
  vertical-align: middle;
  background: var(--paper-sunk);
  color: var(--ink-1);
  border: 1px solid var(--rule);
  white-space: nowrap;
}
.vl-chip__g {
  font: 600 11px/1 var(--font-sans);
  letter-spacing: 0;
  display: inline-block;
  width: 11px;
  text-align: center;
}
.vl-chip.pass { color: var(--pass);   background: var(--pass-soft);   border-color: var(--pass); }
.vl-chip.warn { color: var(--warn);   background: var(--warn-soft);   border-color: var(--warn); }
.vl-chip.fail { color: var(--fail);   background: var(--fail-soft);   border-color: var(--fail); }
.vl-chip.info { color: var(--info);   background: var(--info-soft);   border-color: var(--info); }
.vl-chip.flag { color: var(--flag);   background: var(--flag-soft);   border-color: var(--flag); }
.vl-chip.neutral { color: var(--ink-2); background: var(--paper-sunk); border-color: var(--rule); }
.vl-chip.solid.pass { background: var(--pass); color: var(--paper); border-color: var(--pass); }
.vl-chip.solid.warn { background: var(--warn); color: var(--paper); border-color: var(--warn); }
.vl-chip.solid.fail { background: var(--fail); color: var(--paper); border-color: var(--fail); }
.vl-chip.solid.info { background: var(--info); color: var(--paper); border-color: var(--info); }
.vl-chip.solid.flag { background: var(--flag); color: var(--paper); border-color: var(--flag); }

/* ─── Cards (gallery / severity) ───────────────────────── */
.vl-cards {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 14px;
}
.vl-card {
  display: flex;
  flex-direction: column;
  background: var(--paper);
  border: 1px solid var(--rule);
  border-radius: var(--r1);
  padding: 18px 18px 16px;
  position: relative;
  text-decoration: none;
  color: inherit;
  transition: border-color 150ms, transform 150ms, background 150ms;
  overflow: hidden;
}
a.vl-card { cursor: pointer; }
.vl-card:hover { border-color: var(--accent); }
a.vl-card:hover { transform: translateY(-1px); background: #fffdf8; }
[data-theme="dark"] a.vl-card:hover { background: #1e1c18; }
.vl-card .kind {
  font: 600 10px/1 var(--font-mono);
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: var(--ink-3);
  margin-bottom: 14px;
  display: flex;
  align-items: center;
  gap: 6px;
}
.vl-card .kind::after {
  content: "";
  flex: 1;
  border-top: 1px dotted var(--rule);
}
.vl-card .title {
  font: 500 19px/1.25 var(--font-serif);
  letter-spacing: -0.005em;
  color: var(--ink);
  margin: 0 0 8px;
  text-wrap: balance;
}
.vl-card .body {
  font-size: 14px;
  color: var(--ink-1);
  line-height: 1.5;
  flex-grow: 1;
  margin: 0;
}
.vl-card .filename {
  font: 11.5px/1 var(--font-mono);
  color: var(--ink-2);
  margin-top: 14px;
  padding-top: 12px;
  border-top: 1px dotted var(--rule);
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
}
.vl-card .filename .size { color: var(--ink-3); }
.vl-card .actions { display: flex; gap: 6px; margin-top: 12px; flex-wrap: wrap; }
.vl-card .footer { display: flex; gap: 6px; margin-top: 12px; flex-wrap: wrap; }

/* Severity variant — left tick of color */
.vl-card.severity-pass::before,
.vl-card.severity-warn::before,
.vl-card.severity-fail::before,
.vl-card.severity-info::before {
  content: "";
  position: absolute;
  left: 0; top: 0; bottom: 0;
  width: 3px;
}
.vl-card.severity-pass::before { background: var(--pass); }
.vl-card.severity-warn::before { background: var(--warn); }
.vl-card.severity-fail::before { background: var(--fail); }
.vl-card.severity-info::before { background: var(--info); }

/* ─── Buttons ──────────────────────────────────────────── */
.vl-btn {
  appearance: none;
  font: 500 13px/1 var(--font-sans);
  padding: 8px 14px;
  border: 1px solid var(--rule);
  background: var(--paper);
  color: var(--ink-1);
  border-radius: var(--r1);
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  transition: border-color 120ms, color 120ms, background 120ms;
  letter-spacing: 0.01em;
  text-decoration: none;
}
.vl-btn:hover { border-color: var(--accent); color: var(--accent); }
.vl-btn[disabled] { opacity: 0.5; cursor: not-allowed; }
.vl-btn--primary {
  background: var(--accent);
  color: var(--paper);
  border-color: var(--accent);
}
.vl-btn--primary:hover { background: var(--accent-strong); color: var(--paper); border-color: var(--accent-strong); }
.vl-btn--ghost { background: transparent; border-color: transparent; color: var(--ink-2); }
.vl-btn--ghost:hover { color: var(--accent); border-color: var(--rule); }
.vl-btn--lg { padding: 11px 18px; font-size: 14px; }
.vl-btn--sm { padding: 5px 10px; font-size: 12px; }
.vl-btn .glyph { font-family: var(--font-sans); font-weight: 500; }

/* ─── Table ────────────────────────────────────────────── */
.vl-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 14px;
  margin: 8px 0;
  background: var(--paper);
}
.vl-table th, .vl-table td {
  padding: 11px 14px;
  text-align: left;
  vertical-align: top;
  border-bottom: 1px solid var(--rule-soft);
}
.vl-table thead th {
  background: transparent;
  border-bottom: 2px solid var(--ink);
  font: 600 11px/1 var(--font-mono);
  text-transform: uppercase;
  letter-spacing: 0.1em;
  color: var(--ink-2);
  padding-top: 8px;
  padding-bottom: 10px;
}
.vl-table tbody tr:last-child td { border-bottom: 1px solid var(--rule); }
.vl-table tbody tr:hover td { background: var(--paper-soft); }
.vl-table td.path, .vl-table td code { font-family: var(--font-mono); font-size: 12.5px; color: var(--ink-1); }
.vl-table td.num { font-variant-numeric: tabular-nums; text-align: right; font-family: var(--font-mono); font-size: 13px; color: var(--ink-1); }

/* ─── Compare panel ────────────────────────────────────── */
.vl-compare { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; margin: 14px 0; }
.vl-compare > div { border: 1px solid var(--rule); border-radius: var(--r1); padding: 14px 16px; background: var(--paper); }
.vl-compare .label { font: 600 10px/1 var(--font-mono); text-transform: uppercase; letter-spacing: 0.14em; color: var(--ink-3); margin-bottom: 8px; }

/* ─── Collapsible step ─────────────────────────────────── */
.vl-step {
  border: 1px solid var(--rule);
  border-radius: var(--r1);
  margin: 8px 0;
  background: var(--paper);
}
.vl-step > summary {
  padding: 12px 16px;
  cursor: pointer;
  font: 500 14px/1.4 var(--font-sans);
  list-style: none;
  display: flex;
  align-items: center;
  gap: 10px;
}
.vl-step > summary::-webkit-details-marker { display: none; }
.vl-step > summary::before {
  content: "+";
  display: inline-block;
  width: 12px;
  text-align: center;
  color: var(--accent);
  font: 600 14px/1 var(--font-mono);
  transition: transform 150ms;
}
.vl-step[open] > summary::before { content: "−"; }
.vl-step > summary:hover { background: var(--paper-soft); }
.vl-step .body { padding: 4px 16px 16px 38px; font-size: 14px; color: var(--ink-1); line-height: 1.55; }
.vl-step .ref { font: 12px/1 var(--font-mono); color: var(--accent); }

/* ─── Tabs (binder dividers) ───────────────────────────── */
.vl-tabs { margin: 8px 0; }
.vl-tabs .vl-tab-bar {
  display: flex;
  gap: 0;
  border-bottom: 1px solid var(--rule);
  margin-bottom: 0;
  flex-wrap: wrap;
}
.vl-tabs .vl-tab-label {
  padding: 10px 16px 12px;
  cursor: pointer;
  font: 500 13px/1.35 var(--font-sans);
  color: var(--ink-2);
  background: transparent;
  border: 0;
  border-bottom: 2px solid transparent;
  margin-bottom: -1px;
  user-select: none;
  position: relative;
}
.vl-tabs .vl-tab-label:hover { color: var(--ink); }
.vl-tabs .vl-tab-label.active { color: var(--ink); border-bottom-color: var(--accent); font-weight: 600; }
.vl-tabs .vl-tab-pane { display: none; padding: 22px 4px 8px; }
.vl-tabs .vl-tab-pane.active { display: block; }
.vl-tabs .vl-tab-pane ul { padding-left: 18px; color: var(--ink-1); }
.vl-tabs .vl-tab-pane > details { margin-top: 18px; border-top: 1px dotted var(--rule); padding-top: 10px; }
.vl-tabs .vl-tab-pane > details summary { cursor: pointer; font: 11px/1 var(--font-mono); color: var(--ink-3); text-transform: uppercase; letter-spacing: 0.12em; }
.vl-tabs .vl-tab-pane > details ul { font: 12px/1.5 var(--font-mono); color: var(--ink-2); padding-left: 20px; margin: 8px 0; }

/* ─── Timeline ─────────────────────────────────────────── */
.vl-timeline { border-left: 2px solid var(--rule); padding-left: 18px; margin: 12px 0; }
.vl-timeline .event { position: relative; padding: 6px 0 14px; }
.vl-timeline .event::before {
  content: "";
  position: absolute;
  left: -25px; top: 12px;
  width: 10px; height: 10px;
  background: var(--paper);
  border: 2px solid var(--accent);
  border-radius: 50%;
}
.vl-timeline .ts { font: 11px/1 var(--font-mono); color: var(--ink-3); letter-spacing: 0.04em; }
.vl-timeline .label { font: 600 14px/1.3 var(--font-sans); margin: 4px 0; color: var(--ink); }
.vl-timeline .body { font-size: 13.5px; color: var(--ink-1); line-height: 1.5; }

/* ─── Argument graph ───────────────────────────────────── */
.vl-graph { margin: 12px 0; }
.vl-graph svg { max-width: 100%; height: auto; }
.vl-graph .node { fill: var(--paper-soft); stroke: var(--rule); stroke-width: 1.2; }
.vl-graph .node.hot { fill: var(--accent-soft); stroke: var(--accent); }
.vl-graph .node-label { font: 12px/1.2 var(--font-sans); fill: var(--ink); text-anchor: middle; }
.vl-graph .edge { stroke: var(--rule); stroke-width: 1.5; fill: none; }
.vl-graph .edge.hot { stroke: var(--accent); stroke-width: 2; }

/* ─── Kanban (drag-drop) ───────────────────────────────── */
.vl-kanban { display: grid; grid-template-columns: repeat(var(--cols, 4), minmax(0, 1fr)); gap: 12px; margin: 12px 0; }
.vl-col {
  display: flex;
  flex-direction: column;
  background: var(--paper-soft);
  border: 1px solid var(--rule);
  border-radius: var(--r1);
  min-height: 200px;
  overflow: hidden;
  position: relative;
}
.vl-col::before {
  content: "";
  position: absolute;
  inset: 0 0 auto 0;
  height: 3px;
  background: var(--ink-3);
}
.vl-col[data-verdict="pass"]::before { background: var(--pass); }
.vl-col[data-verdict="fail"]::before { background: var(--fail); }
.vl-col[data-verdict="warn"]::before { background: var(--warn); }
.vl-col[data-verdict="info"]::before { background: var(--info); }
.vl-col[data-verdict="flag"]::before { background: var(--flag); }
.vl-col[data-verdict="neutral"]::before { background: var(--ink-3); }
.vl-col h4 {
  margin: 0;
  padding: 12px 12px 8px;
  font: 600 11.5px/1.2 var(--font-mono);
  color: var(--ink-1);
  text-transform: uppercase;
  letter-spacing: 0.1em;
  display: flex;
  align-items: center;
  gap: 6px;
}
.vl-col h4 .glyph {
  font: 600 12px/1 var(--font-sans);
  letter-spacing: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 18px; height: 18px;
  border-radius: 50%;
  background: var(--paper);
  border: 1px solid currentColor;
  color: var(--ink-2);
  flex-shrink: 0;
}
.vl-col[data-verdict="pass"] h4 .glyph { color: var(--pass); }
.vl-col[data-verdict="fail"] h4 .glyph { color: var(--fail); }
.vl-col[data-verdict="warn"] h4 .glyph { color: var(--warn); }
.vl-col[data-verdict="info"] h4 .glyph { color: var(--info); }
.vl-col[data-verdict="flag"] h4 .glyph { color: var(--flag); }
.vl-col h4 .count {
  margin-left: auto;
  font: 600 11px/1 var(--font-mono);
  color: var(--ink-3);
  background: var(--paper);
  border: 1px solid var(--rule);
  padding: 2px 6px;
  border-radius: 8px;
  letter-spacing: 0.04em;
}
.vl-col-body {
  padding: 4px 10px 10px;
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-height: 80px;
}
.vl-col-body:empty::after {
  content: "Drop here";
  font: italic 12px/1.4 var(--font-serif);
  color: var(--ink-3);
  border: 1px dashed var(--rule);
  border-radius: var(--r1);
  padding: 18px 12px;
  text-align: center;
  margin-top: 4px;
}
.vl-item {
  background: var(--paper);
  border: 1px solid var(--rule);
  border-radius: var(--r1);
  padding: 10px 12px 10px 26px;
  font-size: 13px;
  line-height: 1.45;
  color: var(--ink-1);
  cursor: grab;
  position: relative;
  transition: border-color 120ms, transform 120ms, box-shadow 120ms;
}
.vl-item::before {
  content: "⠿";
  position: absolute;
  left: 8px; top: 9px;
  color: var(--ink-3);
  font: 14px/1 var(--font-mono);
}
.vl-item:hover { border-color: var(--accent); }
.vl-item:active { cursor: grabbing; }
.vl-item.dragging { opacity: 0.4; transform: rotate(-1deg); }
.vl-item .ref { font: 600 11px/1 var(--font-mono); color: var(--accent); letter-spacing: 0.04em; margin-right: 4px; }
.vl-item .author { font-weight: 600; color: var(--ink); }
.vl-col.over { background: var(--accent-soft); }
.vl-col.over .vl-col-body { outline: 1px dashed var(--accent); outline-offset: -8px; border-radius: var(--r1); }

/* Export bar (drag-drop confirm) */
.vl-export-bar {
  margin-top: 18px;
  display: flex;
  gap: 10px;
  align-items: center;
  padding: 14px 16px;
  background: var(--paper-soft);
  border: 1px solid var(--rule);
  border-radius: var(--r1);
  flex-wrap: wrap;
}
.vl-export-bar .vl-export-hint {
  font: 12.5px/1.5 var(--font-sans);
  color: var(--ink-2);
  flex: 1;
  min-width: 200px;
}
.vl-export-bar .vl-export-hint code {
  background: var(--paper);
  border: 1px solid var(--rule);
}

/* ─── Template editor ──────────────────────────────────── */
.vl-editor { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; margin: 12px 0; }
.vl-editor .pane { border: 1px solid var(--rule); border-radius: var(--r1); padding: 14px; background: var(--paper); }
.vl-editor .pane h4 { margin: 0 0 10px; font: 600 11px/1 var(--font-mono); text-transform: uppercase; letter-spacing: 0.12em; color: var(--ink-3); }
.vl-editor textarea {
  width: 100%;
  min-height: 220px;
  font: 13px/1.55 var(--font-mono);
  border: 1px solid var(--rule);
  border-radius: var(--r1);
  padding: 12px;
  resize: vertical;
  background: var(--paper-soft);
  color: var(--ink);
}
.vl-editor textarea:focus { outline: 2px solid var(--accent); outline-offset: 0; }
.vl-editor .samples { display: flex; flex-direction: column; gap: 8px; }
.vl-editor .sample {
  font: 12px/1.5 var(--font-mono);
  padding: 10px 12px;
  background: var(--paper-soft);
  border: 1px solid var(--rule-soft);
  border-left: 3px solid var(--rule);
  border-radius: var(--r1);
  white-space: pre-wrap;
  max-height: 140px;
  overflow-y: auto;
  color: var(--ink-1);
}
.vl-editor .counter { font: 11px/1 var(--font-mono); color: var(--ink-3); margin-top: 8px; letter-spacing: 0.04em; }
.vl-var { background: var(--accent-soft); color: var(--accent); padding: 1px 4px; border-radius: 2px; font-weight: 500; font-family: var(--font-mono); }

/* ─── Margin glossary ──────────────────────────────────── */
.vl-gloss {
  background: var(--paper-soft);
  border-left: 3px solid var(--ink-2);
  padding: 10px 14px;
  margin: 8px 0;
  font-size: 13.5px;
  border-radius: 0 var(--r1) var(--r1) 0;
}
.vl-gloss .term { font-weight: 600; color: var(--ink); }
.vl-gloss .def { color: var(--ink-1); }

/* ─── Keynav deck ──────────────────────────────────────── */
.vl-deck { border: 1px solid var(--rule); border-radius: var(--r1); background: var(--paper); margin: 12px 0; }
.vl-deck .slide { display: none; padding: 32px; min-height: 380px; }
.vl-deck .slide.active { display: block; }
.vl-deck .slide h3 { font: 400 26px/1.2 var(--font-serif); margin: 0 0 18px; color: var(--ink); }
.vl-deck .nav {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  background: var(--paper-soft);
  border-top: 1px solid var(--rule);
}
.vl-deck .nav .pos { font: 11px/1 var(--font-mono); color: var(--ink-3); letter-spacing: 0.06em; }

/* ─── Filter bar ───────────────────────────────────────── */
.vl-filter { display: flex; gap: 6px; flex-wrap: wrap; margin: 12px 0; }
.vl-filter button {
  appearance: none;
  font: 500 12px/1 var(--font-sans);
  padding: 6px 12px;
  border: 1px solid var(--rule);
  background: var(--paper);
  color: var(--ink-2);
  border-radius: var(--r1);
  cursor: pointer;
  letter-spacing: 0.01em;
}
.vl-filter button:hover { border-color: var(--accent); color: var(--accent); }
.vl-filter button.active { background: var(--accent); color: var(--paper); border-color: var(--accent); }

/* ─── Footer ───────────────────────────────────────────── */
.vl-foot {
  margin-top: 72px;
  padding: 22px 0 32px;
  border-top: 1px solid var(--rule);
  color: var(--ink-3);
  font: 11px/1.4 var(--font-mono);
  letter-spacing: 0.04em;
  text-transform: uppercase;
  display: flex;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
}
.vl-foot a { color: var(--ink-2); text-decoration: none; }
.vl-foot a:hover { color: var(--accent); text-decoration: underline; }

/* ─── Stat row ─────────────────────────────────────────── */
.vl-stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 0; margin: 18px 0 24px; border-top: 1px solid var(--rule); border-bottom: 1px solid var(--rule); }
.vl-stat { padding: 14px 16px; border-right: 1px solid var(--rule-soft); }
.vl-stat:last-child { border-right: 0; }
.vl-stat .k { font: 600 10px/1 var(--font-mono); text-transform: uppercase; letter-spacing: 0.14em; color: var(--ink-3); margin-bottom: 6px; }
.vl-stat .v { font: 400 22px/1.1 var(--font-serif); color: var(--ink); font-variant-numeric: tabular-nums; }
.vl-stat .v small { font: 12px/1 var(--font-mono); color: var(--ink-2); margin-left: 4px; letter-spacing: 0.04em; text-transform: uppercase; }

/* ─── Toast (copy confirmation) ────────────────────────── */
.vl-toast {
  position: fixed;
  left: 50%;
  bottom: 24px;
  transform: translateX(-50%) translateY(12px);
  background: var(--ink);
  color: var(--paper);
  font: 500 13px/1 var(--font-sans);
  padding: 10px 16px;
  border-radius: var(--r1);
  pointer-events: none;
  opacity: 0;
  transition: opacity 180ms, transform 180ms;
  z-index: 100;
  display: inline-flex;
  align-items: center;
  gap: 8px;
}
.vl-toast.show { opacity: 1; transform: translateX(-50%) translateY(0); }
.vl-toast .check { color: var(--pass); font-weight: 700; }
[data-theme="dark"] .vl-toast .check { color: #6dba90; }

/* ─── Responsive ───────────────────────────────────────── */
@media (max-width: 900px) {
  .vl-head h1 { font-size: 32px; }
  .vl-head .lede { font-size: 17px; }
  .vl-section > h2 { font-size: 22px; }
  .vl-compare, .vl-editor { grid-template-columns: 1fr; }
}
@media (max-width: 720px) {
  .vl-wrap { padding: 0 16px; }
  .vl-head { padding-top: 32px; }
  .vl-head h1 { font-size: 28px; }
  .vl-section { margin: 36px 0; }
  .vl-section > h2 { font-size: 20px; flex-wrap: wrap; gap: 8px; }
  .vl-cards { grid-template-columns: 1fr; }
  .vl-kanban { grid-template-columns: 1fr; }
  .vl-col { min-height: 0; }
  .vl-export-bar { position: sticky; bottom: 8px; box-shadow: 0 -4px 12px rgba(26,26,31,0.06); }
}

/* ─── Print ────────────────────────────────────────────── */
@media print {
  :root { --paper: #ffffff; --paper-soft: #f7f5f0; }
  body { font-size: 11pt; }
  .vl-masthead, .vl-theme-toggle, .vl-export-bar, .vl-filter { display: none !important; }
  .vl-section { page-break-inside: avoid; }
  .vl-card, .vl-col { break-inside: avoid; }
  a { color: inherit; text-decoration: none; }
}

/* ============================================================
   Legacy variable aliases — back-compat for un-migrated
   consumers that still reference the pre-refresh token names
   in inline styles. Migration seam: remove once every consumer
   uses the canonical tokens above.
   ============================================================ */
:root {
  --bg:        var(--paper);
  --bg-soft:   var(--paper-soft);
  --ink-soft:  var(--ink-1);
  --muted:     var(--ink-2);
  --line:      var(--rule);
  --line-soft: var(--rule-soft);
  --good:      var(--pass);
  --good-bg:   var(--pass-soft);
  --good-line: var(--pass);
  --bad:       var(--fail);
  --bad-bg:    var(--fail-soft);
  --bad-line:  var(--fail);
  --warn-bg:   var(--warn-soft);
  --warn-line: var(--warn);
  --shadow:    none;
}
"""
