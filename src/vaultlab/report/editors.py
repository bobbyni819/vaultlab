"""Two-way HTML editors — kanban + template tuners.

Track D of the v0.0.4 plan. Consumers turn vaultlab artifacts into tiny
purpose-built HTML editors: the user drags / reorders / edits, then
clicks "Copy as JSON" or "Copy as markdown" to paste the result back
into the next prompt.

Pattern source: Thariq Shihipar's gallery (Anthropic) — #18 triage
board, #19 feature-flag editor, #20 prompt tuner. Built on top of the
:func:`vaultlab.report.components.kanban_board` and
:func:`vaultlab.report.components.template_editor` primitives.

Three editors here:

- :func:`build_slide_reorder_editor` — drag slides between buckets,
  export new plan-dict JSON.
- :func:`build_citation_triage_editor` — drag citations between
  accept/reject/flag piles, export verdict map.
- :func:`build_deckplan_tuner` — edit a slide-plan template with
  ``{{var}}`` placeholders, live-preview against 2-3 sample papers,
  copy the tuned template.

All three emit single-file HTML, vanilla JS, no external deps.
"""

from __future__ import annotations

import html as _html
from pathlib import Path
from typing import Any

from vaultlab.report import _components as c
from vaultlab.report.html import render_report


def _safe(text: Any) -> str:
    return _html.escape(str(text or ""))


# ---------------------------------------------------------------------------
# Slide reorder kanban editor


def build_slide_reorder_editor(
    plan: dict[str, Any],
    *,
    sections: list[str] | None = None,
    title: str | None = None,
) -> str:
    """Render a deck-plan as a kanban board grouped by section.

    Each card is one slide (showing its title + type). Bobby drags
    slides between sections and the export buttons emit the new ordering
    as markdown or JSON for pasting back into a prompt.

    Parameters
    ----------
    plan:
        Deck plan dict with ``title`` and ``slides``. Each slide may have
        a ``section`` field; otherwise all slides go in "Unsectioned".
    sections:
        Explicit column order. Defaults to discovered sections + "Cut" at
        the end as a holding bin.
    title:
        Override report title.
    """
    slides = plan.get("slides", []) or []
    deck_title = plan.get("title", "(untitled deck)")
    report_title = title or f"Reorder — {deck_title}"

    # Discover sections from the plan
    discovered: dict[str, list[str]] = {}
    for i, slide in enumerate(slides):
        section = slide.get("section") or "Unsectioned"
        slide_label = f"{i + 1}. [{slide.get('type', '?')}] {slide.get('title', 'untitled')}"
        discovered.setdefault(section, []).append(slide_label)

    columns = sections or list(discovered) + ["Cut"]
    if "Cut" not in columns:
        columns.append("Cut")
    # Ensure all discovered sections appear (don't silently drop user data)
    for sec in discovered:
        if sec not in columns:
            columns.insert(-1, sec)

    items: dict[str, list[str]] = {col: discovered.get(col, []) for col in columns}

    sections_out = [
        c.section(
            None,
            c.tldr_box(
                [
                    f"{len(slides)} slide{'s' if len(slides) != 1 else ''} across "
                    f"{len(discovered)} section{'s' if len(discovered) != 1 else ''}.",
                    "Drag slides between sections to reorder. Use the 'Cut' column "
                    "to mark slides for removal. Click 'Copy as JSON' (or markdown) "
                    "to export the new plan back into your prompt.",
                ]
            ),
        ),
        c.section(
            None,
            c.kanban_board(columns, items),
        ),
    ]

    return render_report(
        title=report_title,
        eyebrow="vaultlab · slide reorder editor",
        subtitle=deck_title,
        meta=f"{len(slides)} slides · drag-drop · two-way HTML",
        sections=sections_out,
    )


def write_slide_reorder_editor(
    out_path: Path | str,
    plan: dict[str, Any],
    **kwargs: Any,
) -> Path:
    html_str = build_slide_reorder_editor(plan, **kwargs)
    p = Path(out_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(html_str, encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# Citation triage kanban editor


def build_citation_triage_editor(
    citations: list[dict[str, Any]],
    *,
    title: str = "Citation triage",
) -> str:
    """Render citations as a drag-drop triage board with accept/reject/flag
    piles. The user drags citations into piles and exports the verdict
    map as JSON.
    """
    columns = ["Pending", "Accept", "Reject", "Needs review", "Flag for plagiarism"]
    items: dict[str, list[str]] = {col: [] for col in columns}
    # All citations start in "Pending"; status field can override.
    for i, cit in enumerate(citations):
        author = cit.get("authors", "?")
        year = cit.get("year", "?")
        claim = cit.get("claim") or cit.get("title") or "(no text)"
        label = f"[{i + 1}] {author} ({year}) — {claim[:80]}{'…' if len(claim) > 80 else ''}"
        status_to_bucket = {
            "verified_fulltext": "Accept",
            "verified_abstract": "Accept",
            "api_confirmed": "Needs review",
            "unverified": "Pending",
            "suspect": "Flag for plagiarism",
            "contradicted": "Reject",
        }
        bucket = status_to_bucket.get(cit.get("status", ""), "Pending")
        items[bucket].append(label)

    pile_legend = [
        ("Pending", "neutral", "Not yet triaged — the default landing pile."),
        ("Accept", "pass", "Verified — safe to cite as written."),
        ("Reject", "fail", "Contradicted or wrong — drop the claim."),
        ("Needs review", "info", "Plausible but unconfirmed — a human should look."),
        ("Flag for plagiarism", "flag", "Suspected fabrication or text overlap."),
    ]
    legend_rows = [
        [c.status_chip(name, lvl), meaning] for name, lvl, meaning in pile_legend
    ]

    counts = {col: len(items[col]) for col in columns}
    sections_out = [
        c.section(
            None,
            c.tldr_box(
                [
                    f"{len(citations)} citation{'s' if len(citations) != 1 else ''} to triage.",
                    "Drag each citation into a pile. Click 'Copy as JSON' to export "
                    "the verdict map back to your prompt.",
                    "Tip: drag suspicious citations to 'Flag for plagiarism' for "
                    "manual review before final export.",
                ]
            ),
            c.stats_row(
                [
                    ("Candidates", str(len(citations))),
                    ("Pending", str(counts["Pending"])),
                    ("Accepted", str(counts["Accept"])),
                    ("Flagged", str(counts["Flag for plagiarism"])),
                ]
            ),
        ),
        c.section(
            "Triage board",
            c.kanban_board(
                columns,
                items,
                hint="Drag each citation into its verdict pile, then "
                "Copy as JSON to paste the verdict map into your next prompt.",
            ),
            number=1,
        ),
        c.section(
            "Pile reference",
            c.matrix_table(["Pile", "Meaning"], legend_rows),
            number=2,
        ),
    ]

    return render_report(
        title=title,
        breadcrumb=["vaultlab", "editors", "citation triage"],
        screen_label="Citation triage",
        subtitle=f"{len(citations)} candidate citations awaiting a verdict.",
        meta="drag-drop · two-way HTML",
        chips=[
            c.status_chip(f"{len(citations)} candidates", "info"),
            c.status_chip(f"{counts['Pending']} pending", "neutral"),
            c.status_chip(f"{counts['Flag for plagiarism']} flagged", "flag"),
        ],
        sections=sections_out,
    )


def write_citation_triage_editor(
    out_path: Path | str,
    citations: list[dict[str, Any]],
    **kwargs: Any,
) -> Path:
    html_str = build_citation_triage_editor(citations, **kwargs)
    p = Path(out_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(html_str, encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# Deck-plan template tuner


def build_deckplan_tuner(
    template: str,
    samples: list[dict[str, str]],
    *,
    sample_titles: list[str] | None = None,
    title: str = "Deck-plan template tuner",
    sample_descriptions: list[str] | None = None,
) -> str:
    """Render an editable deck-plan template with live preview on 2-3
    sample papers. The template uses ``{{var}}`` placeholders; as the
    user edits, the preview re-renders.

    Use case: tune the slide-title generation template, watch how it
    re-renders across 3 different paper frontmatters, copy the final
    template back into the prompt.
    """
    descriptions = sample_descriptions or [f"Paper {i + 1}" for i in range(len(samples))]
    titles_resolved = sample_titles or descriptions
    intro_items = []
    for i, desc in enumerate(descriptions):
        intro_items.append(f"<li><strong>{_safe(titles_resolved[i])}</strong> — {_safe(desc)}</li>")

    sections_out = [
        c.section(
            None,
            c.tldr_box(
                [
                    f"Edit the template on the left; preview {len(samples)} sample paper{'s' if len(samples) != 1 else ''} on the right.",
                    "Placeholders use the format <code>{{variable_name}}</code>. "
                    "Unknown variables stay literal in the preview, marking work to be done.",
                    "When the previews all look right, click 'Copy prompt' and paste back into your next vaultlab prompt.",
                ]
            ),
            f'<ul style="font-size:13px;color:var(--ink-soft);margin-top:10px;">{"".join(intro_items)}</ul>',
        ),
        c.section(
            None,
            c.template_editor(
                template=template,
                samples=samples,
                sample_titles=titles_resolved,
                label="Slide-plan template",
            ),
        ),
    ]

    return render_report(
        title=title,
        eyebrow="vaultlab · deck-plan tuner",
        subtitle=f"{len(samples)} sample paper{'s' if len(samples) != 1 else ''}",
        meta="live preview · two-way HTML",
        sections=sections_out,
    )


def write_deckplan_tuner(
    out_path: Path | str,
    template: str,
    samples: list[dict[str, str]],
    **kwargs: Any,
) -> Path:
    html_str = build_deckplan_tuner(template, samples, **kwargs)
    p = Path(out_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(html_str, encoding="utf-8")
    return p


__all__ = [
    "build_citation_triage_editor",
    "build_deckplan_tuner",
    "build_slide_reorder_editor",
    "write_citation_triage_editor",
    "write_deckplan_tuner",
    "write_slide_reorder_editor",
]
