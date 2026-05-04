"""Backfill Wiki/Projects/<slug>/ for the existing CODEX + spatial-tx L4 runs.

Reads the existing lineage arcs at Wiki/Concepts/<topic>-lineage-<date>.md
(which embed the full corpus tables + tiers + cite stats), constructs
project-scoped manifests, and writes:

    Wiki/Projects/<project-slug>/
    ├── START_HERE.md
    ├── papers.md         (Tier A first, then Tier C; auto "Also in"
    │                       column derived by scanning sibling projects)
    ├── lineage.md        (entry-point pointer to Wiki/Concepts/...)
    └── decisions-log.md  (one entry seeded from the L4 run audit)

Per kb-project-organization-2026-04-30.md.
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

KB = Path(r"G:/My Drive/Knowledge/vaultlab")

# Two existing projects to backfill, with their canonical slugs + arc paths.
# Slug must match Output/<slug>/ which already exists.
PROJECTS = [
    {
        "slug": "codex-cn-test",
        "topic": "CODEX cellular neighborhoods",
        "arc_path": KB / "Wiki" / "Concepts" / "codex-cellular-neighborhoods-lineage-2026-04-29.md",
        "deck_path": KB / "Output" / "codex-cn-test" / "codex-cellular-neighborhoods-deck.pptx",
        "speaker": "Bobby Y.X. Ni",
        "affiliation": "Hickey Lab @ Duke BME",
    },
    {
        "slug": "spatial-tx-tme-test",
        "topic": "spatial transcriptomics tumor microenvironment",
        "arc_path": KB / "Wiki" / "Concepts" / "spatial-transcriptomics-tumor-microenvironment-lineage-2026-04-29.md",
        "deck_path": KB / "Output" / "spatial-tx-tme-test" / "spatial-transcriptomics-tumor-microenvironment-deck.pptx",
        "speaker": "Bobby Y.X. Ni",
        "affiliation": "Hickey Lab @ Duke BME",
    },
]

# Regex to parse arc-embedded paper-table rows like:
#   | 1955 | [[10.1214_aoms_1177728549|Anon 1955]] | C | 0.08 | 0 |
PAPER_ROW_RE = re.compile(
    r"^\|\s*(\d{4}|\?)\s*\|\s*\[\[([^|]+)\|([^\]]+)\]\]\s*\|\s*([AC])\s*\|\s*([\d.]+)\s*\|\s*(\d+)\s*\|\s*$"
)


def parse_arc_corpus(arc_md: str) -> list[dict]:
    """Pull every paper-table row out of the arc markdown."""
    papers = []
    for line in arc_md.splitlines():
        m = PAPER_ROW_RE.match(line.rstrip())
        if not m:
            continue
        year_raw, slug, label, tier, og, fwd = m.groups()
        try:
            year = int(year_raw)
        except ValueError:
            year = 0
        papers.append({
            "year": year,
            "slug": slug,
            "label": label,
            "tier": tier,  # "A" or "C"
            "og_score": float(og),
            "forward_influence": int(fwd),
        })
    return papers


def render_papers_md(project: dict, papers: list[dict], also_in: dict[str, list[str]]) -> str:
    """Render Wiki/Projects/<slug>/papers.md."""
    today = date.today().isoformat()
    tier_a = [p for p in papers if p["tier"] == "A"]
    tier_c = [p for p in papers if p["tier"] == "C"]
    # Sort Tier-A by og_score + forward_influence descending; Tier-C by year.
    tier_a.sort(key=lambda p: -(p["og_score"] + p["forward_influence"] / 10))
    tier_c.sort(key=lambda p: -p["year"])

    lines = [
        "---",
        f"project: {project['slug']}",
        f"topic: {project['topic']}",
        f"created: 2026-04-29",
        f"backfilled: {today}",
        f"total_corpus: {len(papers)}",
        f"tier_a_count: {len(tier_a)}",
        f"tier_c_count: {len(tier_c)}",
        "---",
        "",
        f"# Papers — {project['slug']}",
        "",
        f"This project read the following papers for the lineage arc *{project['topic']}*. ",
        "Each `[[wikilink]]` resolves to the **global** per-paper summary at "
        "`Wiki/Summaries/<doi-slug>.md`. Papers also surfaced by other projects ",
        "are noted in the *Also in* column.",
        "",
        f"**Lineage arc:** [[{project['arc_path'].stem}]]",
        f"**Slide deck:** `Output/{project['slug']}/{project['deck_path'].name}`",
        "",
        "## Tier A — full text read by Claude Code",
        "",
        f"Papers with cached PDFs read end-to-end and rendered as `Wiki/Summaries/<doi>.md` ",
        "with TL;DR, methods, key findings (with `[p<N>]` page markers), and connections.",
        "",
        "| Paper | Year | OG | Forward | Also in |",
        "|---|---|---|---|---|",
    ]
    for p in tier_a:
        also = ", ".join(f"`{x}`" for x in also_in.get(p["slug"], [])) or "—"
        lines.append(
            f"| [[{p['slug']}\\|{p['label']}]] "
            f"| {p['year'] or '?'} "
            f"| {p['og_score']:.2f} "
            f"| {p['forward_influence']} "
            f"| {also} |"
        )

    lines.extend([
        "",
        "## Tier C — citation-stat-only stubs",
        "",
        f"Papers cited via the corpus's citation graph but not read full-text. ",
        "Frontmatter has citation metrics; LLM-written content sections are empty. ",
        "Linked here so the citation network is navigable in Obsidian's graph view.",
        "",
    ])
    # Tier-C list as comma-separated wikilinks (would be a huge table otherwise)
    chunks = [
        f"[[{p['slug']}\\|{p['label']}]]"
        for p in tier_c
    ]
    # 5 per line for readability
    for i in range(0, len(chunks), 5):
        lines.append(" · ".join(chunks[i:i + 5]))

    return "\n".join(lines) + "\n"


def render_lineage_pointer(project: dict) -> str:
    """Wiki/Projects/<slug>/lineage.md — short pointer page."""
    return (
        "---\n"
        f"project: {project['slug']}\n"
        f"topic: {project['topic']}\n"
        "kind: lineage-pointer\n"
        "---\n\n"
        f"# Lineage — {project['slug']}\n\n"
        f"The full lineage arc for this project lives at: [[{project['arc_path'].stem}]]\n\n"
        f"Generated 2026-04-29 by `vaultlab.research.lineage.run_lit_arc`.\n"
    )


def render_decisions_log(project: dict, papers: list[dict]) -> str:
    """Wiki/Projects/<slug>/decisions-log.md — append-only record."""
    tier_a = [p for p in papers if p["tier"] == "A"]
    today = date.today().isoformat()
    return (
        "---\n"
        f"project: {project['slug']}\n"
        f"topic: {project['topic']}\n"
        "kind: decisions-log\n"
        "---\n\n"
        f"# Decisions log — {project['slug']}\n\n"
        f"## 2026-04-29 — initial L4 e2e run\n\n"
        f"- **Topic:** {project['topic']}\n"
        f"- **Speaker:** {project['speaker']} ({project['affiliation']})\n"
        f"- **Search:** 12 seeds, 6 sources (NCBI/S2/Springer/CrossRef/bioRxiv/Elsevier)\n"
        f"- **Corpus size:** {len(papers)} papers (1 layer of CrossRef references)\n"
        f"- **Tier A picks:** {len(tier_a)} (mechanical citation-graph picker; pre-content-aware-picker)\n"
        f"- **Multi-agent crosstalk:** none (`vaultlab.runner` not yet wired)\n"
        f"- **Decks:** [[{project['deck_path'].stem}|.pptx]] generated; 7 slides\n"
        f"- **Result verdict:** see [[L4-e2e-{project['slug'].split('-')[0]}-2026-04-29]]\n\n"
        f"## {today} — backfill\n\n"
        f"- Backfilled `Wiki/Projects/{project['slug']}/` from the existing L4 run data\n"
        f"- Slug locked as `{project['slug']}`\n"
        f"- Mirrors `Output/{project['slug']}/`\n"
    )


def render_start_here(project: dict, papers: list[dict]) -> str:
    """Wiki/Projects/<slug>/START_HERE.md — landing page."""
    tier_a = sum(1 for p in papers if p["tier"] == "A")
    tier_c = sum(1 for p in papers if p["tier"] == "C")
    today = date.today().isoformat()
    return (
        "---\n"
        f"project: {project['slug']}\n"
        f"topic: {project['topic']}\n"
        "kind: project-start-here\n"
        "---\n\n"
        f"# {project['topic']}\n\n"
        f"Project slug: `{project['slug']}` · Speaker: {project['speaker']}\n\n"
        f"## What this is\n\n"
        f"VaultLab project for a literature lineage arc on **{project['topic']}**. "
        f"Generated 2026-04-29 via `/lit-arc`.\n\n"
        f"## What's in the corpus\n\n"
        f"- **{len(papers)} papers** total across the citation-graph corpus\n"
        f"- **{tier_a} Tier-A** papers read full-text (TL;DRs in `Wiki/Summaries/`)\n"
        f"- **{tier_c} Tier-C** papers cited for citation-graph metrics only\n\n"
        f"## Where to look\n\n"
        f"- **The lineage narrative:** [[{project['arc_path'].stem}|→ open arc]]\n"
        f"- **Per-paper manifest:** [[papers|→ open papers list]]\n"
        f"- **Decisions log:** [[decisions-log|→ open log]]\n"
        f"- **Slide deck:** `Output/{project['slug']}/{project['deck_path'].name}`\n\n"
        f"## Last updated\n\n"
        f"{today} (backfill from L4 e2e run)\n"
    )


def main() -> None:
    # Pass 1: parse all projects' corpora.
    parsed = []
    for project in PROJECTS:
        if not project["arc_path"].exists():
            print(f"SKIP {project['slug']}: arc not found at {project['arc_path']}")
            continue
        arc_md = project["arc_path"].read_text(encoding="utf-8")
        papers = parse_arc_corpus(arc_md)
        parsed.append((project, papers))
        print(f"  {project['slug']}: {len(papers)} papers parsed from arc")

    # Pass 2: build the cross-project "Also in" map.
    # slug -> list of project slugs that include it.
    membership: dict[str, list[str]] = {}
    for project, papers in parsed:
        for p in papers:
            membership.setdefault(p["slug"], []).append(project["slug"])
    # For each paper, "also in" = membership minus the current project.
    for slug, projects in membership.items():
        if len(projects) > 1:
            print(f"  cross-project paper: {slug} in {projects}")

    # Pass 3: write the project-view files for each project.
    for project, papers in parsed:
        proj_dir = KB / "Wiki" / "Projects" / project["slug"]
        proj_dir.mkdir(parents=True, exist_ok=True)

        also_in_for_this_project = {
            slug: [p for p in projects if p != project["slug"]]
            for slug, projects in membership.items()
        }

        files = {
            "START_HERE.md": render_start_here(project, papers),
            "papers.md": render_papers_md(project, papers, also_in_for_this_project),
            "lineage.md": render_lineage_pointer(project),
            "decisions-log.md": render_decisions_log(project, papers),
        }
        for filename, content in files.items():
            (proj_dir / filename).write_text(content, encoding="utf-8")
            print(f"  wrote {proj_dir / filename}")

    # Summary
    print("\n=== Backfill complete ===")
    for project, papers in parsed:
        proj_dir = KB / "Wiki" / "Projects" / project["slug"]
        print(f"\n{project['slug']}:")
        for f in ["START_HERE.md", "papers.md", "lineage.md", "decisions-log.md"]:
            p = proj_dir / f
            print(f"  {p.relative_to(KB)}: {p.stat().st_size} bytes")


if __name__ == "__main__":
    main()
