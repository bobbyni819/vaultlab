"""Live test of vaultlab.research on CRISPR + genetic editing.

Per Bobby 2026-04-29: 'go ahead and try the research pipeline; let's do
CRISPR genetic editing'. This script exercises the full lifted research
module + documents what each source contributes.

Output: a markdown report of the run for Bobby to review.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from vaultlab.research import ResearchClient

REPORT_PATH = Path(
    r"G:\My Drive\Knowledge\vaultlab\Sources\Notes\research-pipeline-crispr-test-2026-04-29.md"
)


def main() -> None:
    print("=" * 70)
    print("LIVE TEST: vaultlab.research on CRISPR genetic editing")
    print("=" * 70)

    client = ResearchClient(config_path="G:/My Drive/Knowledge/tools/.config/research_apis.json")

    queries = [
        "CRISPR-Cas9 base editing",
        "prime editing genome editing",
        "CRISPR therapeutics in vivo delivery",
    ]

    report_lines: list[str] = [
        "---",
        "title: vaultlab.research live test - CRISPR + genetic editing",
        "type: notes",
        "component: research-pipeline",
        "created: 2026-04-29",
        "status: live test results",
        "---",
        "",
        "# Live test: vaultlab.research on CRISPR + genetic editing",
        "",
        "> Bobby asked: 'try the research pipeline on CRISPR and document what",
        "> each API contributes'. This is the actual run.",
        "",
        "## Sources active",
        "",
        "5 sources auto-initialized from `~/research_apis.json`:",
        "- NCBI / PubMed",
        "- Springer (Open Access)",
        "- Semantic Scholar",
        "- CrossRef",
        "- bioRxiv",
        "",
        "Elsevier key set but not currently used in `unified_search`.",
        "Paperclip MCP: NOT integrated yet.",
        "",
    ]

    for query in queries:
        print(f"\n--- Query: {query} ---")
        report_lines.append(f"\n## Query: `{query}`\n")

        results = client.search(query, max_results=10)

        report_lines.append(f"\n**{len(results)} unique papers** after dedup.\n")
        report_lines.append("| # | Year | Title | Journal | DOI / source |")
        report_lines.append("|---|---|---|---|---|")

        for i, paper in enumerate(results[:8], start=1):
            year = paper.year or "?"
            title = paper.title[:80] if paper.title else "(no title)"
            journal = (paper.journal or "?")[:30]
            doi = paper.doi or paper.pmid or "(no id)"
            report_lines.append(f"| {i} | {year} | {title} | {journal} | `{doi}` |")
            print(f"  #{i} [{year}] {title[:60]}... ({journal})")

        # Source breakdown
        source_counts: dict[str, int] = {}
        for p in results:
            for src in (p.source_api or "unknown").split(","):
                src = src.strip()
                source_counts[src] = source_counts.get(src, 0) + 1
        report_lines.append("\n**Source contribution:**\n")
        for src, n in sorted(source_counts.items(), key=lambda x: -x[1]):
            report_lines.append(f"- {src}: {n} hits")

    # Per-source strategy guide
    report_lines.append("\n---\n")
    report_lines.append("## Per-source strategy reference\n")
    report_lines.append("""
What each source returns + when to prefer it:

### NCBI (PubMed via E-utilities)
- **Returns:** PubMed metadata (PMID, title, authors, journal, year, abstract,
  MeSH terms). PMC links when open access.
- **Strength:** Most comprehensive biomedical coverage. Best for clinical /
  preclinical biomedical research.
- **Weakness:** Slow without API key (3 req/sec); requires email in User-Agent.
- **When to prefer:** Always for biomedical queries. Default first source.

### Semantic Scholar
- **Returns:** Title, authors, year, abstract, citation graph (papers cited
  + papers citing), open-access PDF URLs when available, influence metrics.
- **Strength:** Citation graph is invaluable for backward / forward exploration.
  Open-access PDF URLs give free full text.
- **Weakness:** Coverage less consistent than PubMed for medical journals.
- **When to prefer:** Citation network exploration, finding seminal papers
  by influence rather than recency.

### Springer Nature (Open Access API)
- **Returns:** Springer-published papers' metadata + full text when OA.
- **Strength:** Direct full-text access for Springer journals (Nature family,
  Springer Nature open journals).
- **Weakness:** Limited to Springer's catalog.
- **When to prefer:** When you want full-text access to Nature / Sci Rep /
  Springer journal articles.

### CrossRef
- **Returns:** DOI metadata only (title, authors, year, journal). Sometimes
  abstracts. Always available for any DOI.
- **Strength:** Universal coverage - if a paper has a DOI, CrossRef has it.
- **Weakness:** No abstracts often; no full text.
- **When to prefer:** DOI resolution, citation cross-reference. Less useful
  as primary search.

### bioRxiv
- **Returns:** Preprints with full text URLs (PDFs are open).
- **Strength:** Latest preprints before peer review; full PDFs always free.
- **Weakness:** Preprints not peer-reviewed - quality varies.
- **When to prefer:** Recent / cutting-edge work; methods that haven't hit
  PubMed yet.

### Elsevier (ScienceDirect)
- **Status:** API key configured but `unified_search` doesn't call it yet.
- **Returns:** Elsevier journal metadata + full text via institution
  subscription.
- **When to prefer:** Cell Press journals (Cell, Cell Reports) when you have
  access.

### Paperclip MCP
- **Status:** NOT integrated. The lifted bobby_research module has no
  paperclip dependency.
- **Note:** Paperclip's value is its skill markdown that teaches an LLM
  how to combine literature tools. Pattern lesson: vaultlab can write
  similar skill markdown for slash commands.
""")

    # Strategy combining
    report_lines.append("""
## Strategy: combining sources

Current `unified_search()` behavior:
1. Hits NCBI, Springer, Semantic Scholar, CrossRef, bioRxiv in PARALLEL.
2. Deduplicates by DOI.
3. Merges metadata across sources (e.g., NCBI provides abstract; S2 adds
   citation count).
4. Sorts by citation count when available, falls back to year.

**Recommended strategy for different research goals:**

| Goal | Sources to prioritize | Rationale |
|---|---|---|
| Scoping a new field | NCBI + S2 | Comprehensive biomedical + citation graph for influential papers |
| Latest methods | bioRxiv + S2 | Preprints + recent citation activity |
| Specific paper lookup | CrossRef + NCBI by DOI | DOI resolution, then full metadata |
| Reading list for a topic | NCBI + Springer OA | Full text available + biomedical depth |
| Background for new lab | S2 by influence | Citation count surfaces classics |

## Honest gaps for Bobby's review

1. `ResearchClient.search()` returns Papers but doesn't auto-write to KB.
   Should auto-log query + results to `<kb>/Sources/Notes/lit-search-<query>-<date>.md`.
2. No LLM-driven query expansion yet (Q3 in research grill).
3. Paperclip not integrated - decided to defer per design grill.
4. Elsevier client exists but `unified_search` doesn't call it.
5. No re-ranking by relevance (currently citation-count + year).

End of live test report.
""")

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(report_lines), encoding="utf-8")
    print(f"\nReport written -> {REPORT_PATH}")


if __name__ == "__main__":
    main()
