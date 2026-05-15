"""Vaultlab feature-flag / config two-way HTML editor — Pattern #19.

Renders a grouped set of boolean toggles + descriptions as a single-file
HTML editor. The user flips checkboxes in the browser, clicks
"Copy as JSON" or "Copy as diff," and pastes the result back into a
prompt or directly into a config file.

Pattern source: Thariq's HTML-effectiveness gallery #19 ("Feature Flag
Editor"). Use cases inside vaultlab:

- ``~/.config/vaultlab/dispatch.json`` (task-weight overrides, SPEC-F).
- vaultlab pipeline phase toggles (verify / reason / write / review).
- figure-recipe parameter editor.

Composition follows the same shape as
:mod:`vaultlab.report.weekly_status_html` and
:mod:`vaultlab.report.editors`: ``build_<name>`` returns an HTML string;
``write_<name>`` writes to disk plus AGENTS.md Red Line #2 provenance
sidecars.

No new primitives are introduced — every visual element is composed
from :mod:`vaultlab.report._components`. The toggle UI is the standard
HTML ``<input type="checkbox">`` paired with two ``<button>`` actions
that the bundled JS already knows how to handle (``data-copy``).
"""

from __future__ import annotations

import html as _html
import json as _json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from vaultlab.report import _components as c
from vaultlab.report.html import render_report


# ---------------------------------------------------------------------------
# Public dataclasses


@dataclass
class FlagGroup:
    """One thematic group of feature flags.

    Attributes
    ----------
    title:
        Human-readable group label (e.g. ``"Pipeline phases"``).
    flags:
        Triples of ``(flag_name, default_value, description)``.
        ``flag_name`` becomes the JSON key; ``default_value`` is the
        initial checkbox state; ``description`` renders as muted helper
        text next to the toggle.
    """

    title: str
    flags: list[tuple[str, bool, str]] = field(default_factory=list)


@dataclass
class FeatureFlagConfig:
    """Top-level config for the feature-flag editor view.

    Attributes
    ----------
    groups:
        Ordered list of :class:`FlagGroup` panels.
    title:
        Report title. Defaults to ``"Vaultlab Configuration"``.
    intro:
        Optional one-paragraph intro rendered above the toggle grid.
    """

    groups: list[FlagGroup] = field(default_factory=list)
    title: str = "Vaultlab Configuration"
    intro: str = ""


# ---------------------------------------------------------------------------
# Internal helpers


def _safe(text: Any) -> str:
    return _html.escape(str(text or ""))


def _toggle_row(
    group_title: str,
    flag_name: str,
    default: bool,
    description: str,
) -> str:
    """Render one toggle row: checkbox + name + description.

    The checkbox gets ``data-group`` and ``data-flag`` attributes so the
    Copy-as-JSON button can collect the current state via vanilla DOM.
    """
    checked = " checked" if default else ""
    return (
        '<label class="vl-flag-row" '
        'style="display:flex;align-items:flex-start;gap:10px;padding:8px 10px;'
        "border:1px solid var(--line);border-radius:6px;margin:6px 0;"
        'background:var(--bg-soft);cursor:pointer;">'
        f'<input type="checkbox" class="vl-flag" '
        f'data-group="{_safe(group_title)}" data-flag="{_safe(flag_name)}"'
        f'{checked} style="margin-top:3px;">'
        '<div style="flex:1;">'
        f'<div style="font-weight:600;font-size:14px;color:var(--ink);">'
        f"{_safe(flag_name)}</div>"
        f'<div style="font-size:12px;color:var(--ink-soft);margin-top:2px;">'
        f"{_safe(description)}</div>"
        "</div>"
        "</label>"
    )


def _group_panel(group: FlagGroup) -> str:
    """Render one FlagGroup as a card containing the toggle rows."""
    rows = "".join(
        _toggle_row(group.title, name, default, desc)
        for name, default, desc in group.flags
    )
    body = rows or (
        '<p style="margin:0;color:var(--muted);font-size:13px;">'
        "(no flags in this group)</p>"
    )
    return c.severity_card(
        group.title,
        body=body,
        severity="neutral",
    )


def _defaults_payload(config: FeatureFlagConfig) -> dict[str, dict[str, bool]]:
    """Build the default JSON payload (group → flag → bool) for the
    Copy-defaults button and dependency-warning baseline.
    """
    payload: dict[str, dict[str, bool]] = {}
    for group in config.groups:
        payload[group.title] = {name: default for name, default, _ in group.flags}
    return payload


def _copy_buttons(config: FeatureFlagConfig) -> str:
    """Render the Copy-defaults / Copy-as-JSON / Copy-diff buttons.

    The buttons use the same ``data-copy`` attribute convention as
    :func:`vaultlab.report.components.severity_card` actions, so the
    bundled JS picks them up automatically. ``Copy current`` and
    ``Copy diff`` rely on a small inline script that walks the
    ``.vl-flag`` checkboxes — embedded below in build_*.
    """
    defaults_json = _json.dumps(_defaults_payload(config), indent=2)
    # data-copy must HTML-escape (quote=True) — the helper handles it.
    return (
        '<div class="vl-flag-actions" '
        'style="display:flex;gap:8px;flex-wrap:wrap;margin:14px 0;">'
        f'<button data-copy="{_html.escape(defaults_json, quote=True)}" '
        'style="padding:8px 14px;font-size:13px;border:1px solid var(--line);'
        'background:var(--bg-soft);border-radius:4px;cursor:pointer;">'
        "Copy defaults"
        "</button>"
        '<button class="vl-flag-copy-current" '
        'style="padding:8px 14px;font-size:13px;border:1px solid var(--line);'
        'background:var(--accent);color:white;border-radius:4px;cursor:pointer;">'
        "Copy current as JSON"
        "</button>"
        '<button class="vl-flag-copy-diff" '
        'style="padding:8px 14px;font-size:13px;border:1px solid var(--line);'
        'background:var(--bg-soft);border-radius:4px;cursor:pointer;">'
        "Copy diff from defaults"
        "</button>"
        "</div>"
    )


def _inline_script(config: FeatureFlagConfig) -> str:
    """Tiny script that wires Copy-current and Copy-diff to clipboard.

    Read-only on the page — only fires on button click. The defaults
    payload is embedded as JSON literal so the diff button can compute
    {group: {flag: value}} entries that differ from defaults.
    """
    defaults_json = _json.dumps(_defaults_payload(config))
    return (
        "<script>"
        "(function(){"
        f"const defaults = {defaults_json};"
        "function gather(){"
        "const out={};"
        "document.querySelectorAll('.vl-flag').forEach(function(el){"
        "const g=el.dataset.group,f=el.dataset.flag;"
        "if(!out[g])out[g]={};"
        "out[g][f]=el.checked;"
        "});"
        "return out;"
        "}"
        "function copy(text){"
        "navigator.clipboard&&navigator.clipboard.writeText(text);"
        "}"
        "const cur=document.querySelector('.vl-flag-copy-current');"
        "if(cur)cur.addEventListener('click',function(){"
        "copy(JSON.stringify(gather(),null,2));"
        "});"
        "const dif=document.querySelector('.vl-flag-copy-diff');"
        "if(dif)dif.addEventListener('click',function(){"
        "const cur=gather();const diff={};"
        "Object.keys(cur).forEach(function(g){"
        "Object.keys(cur[g]).forEach(function(f){"
        "if(!defaults[g]||defaults[g][f]!==cur[g][f]){"
        "if(!diff[g])diff[g]={};diff[g][f]=cur[g][f];"
        "}});});"
        "copy(JSON.stringify(diff,null,2));"
        "});"
        "})();"
        "</script>"
    )


# ---------------------------------------------------------------------------
# Public API


def build_feature_flag_editor(config: FeatureFlagConfig) -> str:
    """Compose the feature-flag editor HTML.

    Returns a self-contained HTML string. The editor renders each
    :class:`FlagGroup` as a neutral card with one toggle row per flag.
    Three copy buttons sit at the top:

    - ``Copy defaults`` — emits the original default payload
    - ``Copy current as JSON`` — walks the live checkbox state
    - ``Copy diff from defaults`` — only the flags the user changed

    The diff button is the most useful for pasting back into a prompt:
    it keeps the diff small and explicit.
    """
    flag_count = sum(len(g.flags) for g in config.groups)

    header_chips = [
        c.status_chip(f"{len(config.groups)} group{'s' if len(config.groups) != 1 else ''}", "neutral"),
        c.status_chip(f"{flag_count} flag{'s' if flag_count != 1 else ''}", "neutral"),
    ]

    sections: list[str] = []

    intro_items = [
        (
            "Flip toggles in any group, then click "
            "<strong>Copy diff from defaults</strong> to grab a minimal "
            "JSON payload of just your changes."
        ),
        "Paste the result into a prompt, slash command, or directly into "
        "the relevant config file (e.g. <code>~/.config/vaultlab/dispatch.json</code>).",
    ]
    if config.intro:
        intro_items.insert(0, config.intro)

    sections.append(
        c.section(
            None,
            c.tldr_box(intro_items),
            f'<div style="margin:10px 0 0;">{"".join(header_chips)}</div>',
            _copy_buttons(config),
        )
    )

    if config.groups:
        group_cards = [_group_panel(g) for g in config.groups]
        sections.append(
            c.section(
                "Flag groups",
                c.card_grid(group_cards, min_width=320),
            )
        )
    else:
        sections.append(
            c.section(
                "Flag groups",
                "<p>No flag groups configured.</p>",
            )
        )

    # Append the inline wiring script as a final "section" — it carries
    # no header and emits its work-side-effect on button click.
    sections.append(_inline_script(config))

    return render_report(
        title=config.title,
        eyebrow="vaultlab · feature-flag editor",
        subtitle=f"{flag_count} flag{'s' if flag_count != 1 else ''} across {len(config.groups)} group{'s' if len(config.groups) != 1 else ''}",
        meta="two-way HTML · copy diff or full payload",
        sections=sections,
    )


def write_feature_flag_editor(
    config: FeatureFlagConfig,
    output_path: Path | str,
) -> Path:
    """Render and write the feature-flag editor HTML to ``output_path``.

    Also emits provenance sidecars next to the output via
    :func:`vaultlab.provenance.write_receipts`. Best-effort — a
    failure to write receipts does not block the HTML.

    Returns the resolved output Path.
    """
    p = Path(output_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(build_feature_flag_editor(config), encoding="utf-8")

    try:
        from vaultlab.provenance import ProvenanceRecord, write_receipts

        record = ProvenanceRecord(
            generated_by="vaultlab.report.feature_flag_editor",
            kind="feature_flag_editor",
            inputs=[],
            params={
                "title": config.title,
                "group_count": len(config.groups),
                "flag_count": sum(len(g.flags) for g in config.groups),
            },
        )
        write_receipts(str(p), record)
    except Exception:  # pragma: no cover — defensive
        import logging

        logging.getLogger(__name__).exception(
            "write_receipts failed for feature-flag editor %s", p
        )

    return p


__all__ = [
    "FeatureFlagConfig",
    "FlagGroup",
    "build_feature_flag_editor",
    "write_feature_flag_editor",
]
