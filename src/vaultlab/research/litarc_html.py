"""HTML lit-arc narrative report.

Consumer #2 of ``vaultlab.report``. Renders a literature arc — narrative text
plus the cumulative paper corpus — as a single self-contained HTML file with
collapsible paper cards, frontmatter chips, and (optionally) an inline SVG
citation graph.

Background: Bobby's lit-arc outputs are typically long markdown narratives
with a cumulative paper corpus appended. He's noted that he doesn't read MD
past ~100 lines; this consumer renders the same content as a scan-friendly
HTML report with filter bars by tier, year-bucket, and role-in-set.
"""

from __future__ import annotations

import html as _html
import re
from pathlib import Path
from typing import Any

from vaultlab.report import components as c
from vaultlab.report import render_report

# Tier → severity colour
_TIER_LEVEL = {"A": "good", "B": "warn", "C": "neutral", "D": "neutral"}


def _safe(text: Any) -> str:
    return _html.escape(str(text or ""))


def _md_paragraphs(text: str) -> str:
    """Convert simple markdown paragraphs and headings to HTML.

    Not a full markdown renderer — only handles paragraphs, ATX headings
    (#-##-###), bullet lists, and bold/italic emphasis. Anything more
    structured should be pre-rendered.
    """
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
        # heading
        m = re.match(r"^(#{1,4})\s+(.+)$", line)
        if m:
            flush_paragraph()
            flush_list()
            level = len(m.group(1)) + 2  # H3 minimum to play nice with <section><h2>
            level = min(level, 6)
            out.append(f"<h{level}>{_inline(m.group(2))}</h{level}>")
            continue
        # bullet
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
    """Inline emphasis: **bold**, *italic*, `code`, [[wikilink]]."""
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


def _paper_card(paper: dict[str, Any]) -> str:
    """Render one paper as a card with frontmatter chips."""
    title = paper.get("title") or paper.get("doi") or "(untitled)"
    doi = paper.get("doi") or ""
    year = paper.get("year")
    journal = paper.get("journal") or ""
    authors = paper.get("authors") or []
    tier = (paper.get("tier") or "").upper()
    year_bucket = paper.get("year_bucket") or ""
    role = paper.get("role_in_set") or ""
    tldr = paper.get("tldr") or ""

    chips: list[tuple[str, str]] = []
    if tier:
        chips.append((f"Tier {tier}", _TIER_LEVEL.get(tier, "neutral")))
    if year:
        chips.append((str(year), "neutral"))
    if year_bucket:
        chips.append((year_bucket, "neutral"))
    if role:
        chips.append((role, "neutral"))
    if paper.get("citation_count") is not None:
        chips.append((f"cites: {paper.get('citation_count')}", "neutral"))

    # filter key combines tier + role + year_bucket for the filter bar
    filter_keys = ",".join(
        x for x in [f"tier-{tier.lower()}", role.replace(" ", "-"), year_bucket] if x
    )

    author_label = ""
    if authors:
        author_label = ", ".join(authors[:3])
        if len(authors) > 3:
            author_label += f" + {len(authors) - 3}"

    body_parts: list[str] = []
    if author_label:
        body_parts.append(
            f'<div style="font-size:12px;color:var(--muted);margin-bottom:6px;">'
            f"{_safe(author_label)}{f' · {_safe(journal)}' if journal else ''}</div>"
        )
    if tldr:
        body_parts.append(f"<p>{_inline(tldr)}</p>")

    findings = paper.get("key_findings") or []
    if findings:
        fh = "".join(f"<li>{_inline(f)}</li>" for f in findings[:3])
        body_parts.append(
            f'<ul style="margin:6px 0 0;padding-left:18px;font-size:12px;color:var(--ink-soft);">{fh}</ul>'
        )

    actions: list[tuple[str, str]] = []
    if doi:
        actions.append(("Copy DOI", doi))

    return c.severity_card(
        title,
        body="".join(body_parts),
        badges=chips,
        actions=actions,
        filter_key=filter_keys,
    )


def _citation_svg(
    papers: list[dict[str, Any]],
    citations: list[tuple[str, str]],
) -> str | None:
    """Lay out papers in a circle and draw citation edges. Returns None if
    fewer than 3 papers/edges.
    """
    if len(papers) < 3 or not citations:
        return None
    import math

    # Use only papers that appear in citations
    ids = {doi for edge in citations for doi in edge}
    nodes_in: list[dict[str, Any]] = [p for p in papers if p.get("doi") in ids]
    if len(nodes_in) < 3:
        return None
    cx, cy, r = 300, 200, 160
    n = len(nodes_in)
    nodes_payload = []
    for i, p in enumerate(nodes_in):
        angle = (2 * math.pi * i) / n - math.pi / 2
        nodes_payload.append(
            {
                "id": p["doi"],
                "x": int(cx + r * math.cos(angle)),
                "y": int(cy + r * math.sin(angle)),
                "label": str(p.get("year") or "?"),
                "r": 18,
            }
        )
    return c.svg_arg_graph(nodes_payload, citations, width=600, height=400)


def build_litarc_report_html(
    *,
    topic: str,
    narrative: str,
    papers: list[dict[str, Any]],
    scope: str = "standard",
    citations: list[tuple[str, str]] | None = None,
    title: str | None = None,
    figures_dir: Path | str | None = None,
) -> str:
    """Render a lit-arc narrative + paper corpus as a single-file HTML report.

    Parameters
    ----------
    topic:
        Topic the arc covers (becomes part of the title).
    narrative:
        The arc narrative text (markdown-ish; basic paragraphs/headings/lists
        are converted).
    papers:
        List of paper frontmatter dicts (doi, title, authors, year, journal,
        tier, year_bucket, role_in_set, tldr, key_findings, ...).
    scope:
        "review_paper_strict", "standard", "short", etc. — used in subtitle.
    citations:
        Optional list of (citing_doi, cited_doi) tuples for the citation graph.
    title:
        Override report title. Defaults to "Lit-arc — <topic>".
    figures_dir:
        Reserved; not yet rendered. Will display thumbnails in a future commit.
    """
    _ = figures_dir
    report_title = title or f"Lit-arc — {topic}"

    # Tier counts
    tier_counts = {"A": 0, "B": 0, "C": 0, "D": 0, "?": 0}
    bucket_counts: dict[str, int] = {}
    for p in papers:
        t = (p.get("tier") or "?").upper()
        tier_counts[t] = tier_counts.get(t, 0) + 1
        b = p.get("year_bucket") or "?"
        bucket_counts[b] = bucket_counts.get(b, 0) + 1

    summary_chips: list[str] = [
        c.status_chip(f"{len(papers)} papers", "neutral"),
        c.status_chip(f"scope: {scope}", "neutral"),
    ]
    for tier_id, count in tier_counts.items():
        if count and tier_id != "?":
            summary_chips.append(
                c.status_chip(f"Tier {tier_id}: {count}", _TIER_LEVEL.get(tier_id, "neutral"))
            )

    tldr_items = [
        f"Arc covers {len(papers)} paper{'s' if len(papers) != 1 else ''} "
        f"across {len([b for b in bucket_counts if b != '?'])} year-buckets.",
        f"Top tiers: A={tier_counts.get('A', 0)}, B={tier_counts.get('B', 0)}, "
        f"C={tier_counts.get('C', 0)}.",
    ]

    # Filter bar buckets — tier filters
    tier_buckets: list[tuple[str, str]] = [("All", "all")]
    for tier_id in ("A", "B", "C", "D"):
        if tier_counts.get(tier_id):
            tier_buckets.append((f"Tier {tier_id}", f"tier-{tier_id.lower()}"))

    paper_cards = [_paper_card(p) for p in papers]

    sections = [
        c.section(
            None,
            c.tldr_box(tldr_items),
        ),
        c.section(
            "Arc narrative",
            f'<div class="vl-narrative">{_md_paragraphs(narrative)}</div>',
            number=1,
        ),
        c.section(
            "Cumulative paper corpus",
            c.filter_bar(
                tier_buckets,
                target_selector=".vl-cards .vl-card",
            ),
            c.card_grid(paper_cards) if paper_cards else "<p>No papers in corpus.</p>",
            number=2,
        ),
    ]

    # Optional citation graph
    if citations:
        graph = _citation_svg(papers, citations)
        if graph:
            sections.append(
                c.section(
                    "Citation graph",
                    '<p style="color:var(--muted);font-size:13px;">'
                    "Nodes are papers (labelled by year); edges are citations from corpus. "
                    "Layout is circular — not chronological.</p>",
                    graph,
                    number=3,
                )
            )

    return render_report(
        title=report_title,
        eyebrow=f"vaultlab · lit-arc · {scope}",
        subtitle=topic,
        meta=f"{len(papers)} papers · {len(citations or [])} citation edges",
        chips=summary_chips,
        sections=sections,
    )


def write_litarc_report(
    out_path: Path | str,
    *,
    topic: str,
    narrative: str,
    papers: list[dict[str, Any]],
    **kwargs: Any,
) -> Path:
    """Render and write the lit-arc HTML report."""
    html_str = build_litarc_report_html(topic=topic, narrative=narrative, papers=papers, **kwargs)
    p = Path(out_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(html_str, encoding="utf-8")
    return p


__all__ = ["build_litarc_report_html", "write_litarc_report"]
