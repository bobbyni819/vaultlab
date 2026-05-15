"""End-to-end journal-club deck workflow.

Pipeline
--------
1. Read a DOI from ``inputs/paper.json`` (Pentimalli & Rajewsky 2025,
   *Cell Systems* — a PMC-OA paper).
2. Try to fetch real metadata via :class:`vaultlab.research.ResearchClient`.
   Fall back to the bundled ``inputs/paper.json`` if no API config is
   available — examples must not block on missing keys.
3. Compose a journal-club slide plan (16 slides: title → why → who →
   field → divider → figures (placeholder) → strengths/limits →
   take-home → discussion → references).
4. Render to ``.pptx`` via :func:`vaultlab.slides.build_from_plan`.

Run
---

.. code-block:: bash

    python run.py                 # writes to ./out/
    python run.py --open          # open the deck after building (Windows)

Outputs
-------
- ``out/journal-club-<slug>.pptx`` — the deck
- ``out/paper.md``                 — Tier-A-style markdown summary

Adapt this
----------
Swap ``inputs/paper.json`` for any other open-access DOI/metadata.
The plan builder is intentionally a Python dict so external contributors
can read the structure end-to-end.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_REPO_ROOT = _HERE.parent.parent
if (_REPO_ROOT / "src" / "vaultlab" / "__init__.py").exists():
    sys.path.insert(0, str(_REPO_ROOT / "src"))

logger = logging.getLogger("journal-club-example")


def _load_bundled_paper() -> dict:
    """Read the bundled metadata fallback."""
    return json.loads((_HERE / "inputs" / "paper.json").read_text(encoding="utf-8"))


def _try_fetch_real_metadata(doi: str) -> dict | None:
    """Best-effort fetch of real metadata. Returns None on any failure.

    Examples must run offline; this is purely an enrichment hook.
    """
    try:
        from vaultlab.research import ResearchClient
    except Exception as exc:
        logger.info("vaultlab.research unavailable (%s); using bundled metadata", exc)
        return None

    try:
        client = ResearchClient()
        paper = client.get_paper(doi)
    except Exception as exc:  # noqa: BLE001 — any failure → fall back
        logger.info("Metadata fetch failed (%s); using bundled metadata", exc)
        return None

    if paper is None:
        return None
    return {
        "doi": paper.doi,
        "title": paper.title,
        "authors": [str(a) for a in (paper.authors or [])],
        "year": paper.year,
        "journal": paper.journal,
        "abstract": paper.abstract or "",
    }


def _build_plan(paper: dict) -> dict:
    """Compose the journal-club slide-plan dict.

    Returns a dict in the schema accepted by
    :func:`vaultlab.slides.build_from_plan`.
    """
    short_title = paper["title"][:60] + ("…" if len(paper["title"]) > 60 else "")
    first_author = (paper.get("authors") or ["Authors"])[0].split()[-1]
    year = paper.get("year") or "2025"
    venue = paper.get("journal") or "Cell Systems"

    return {
        "title": f"Journal club — {first_author} {year}",
        "author": "Hickey lab",
        "subtitle": short_title,
        "theme": "dark",
        "template": "lab",
        "slides": [
            {
                "type": "title",
                "title": short_title,
                "subtitle": f"{first_author} et al. — {venue} {year}",
                "author": "Hickey lab journal club",
            },
            {
                "type": "text",
                "title": "Why this paper",
                "bullets": [
                    "Test-bed for **end-to-end** vaultlab journal-club workflow",
                    "Demonstrates the dict-plan path: hand-authored plan → `.pptx`",
                    "Replace inputs/paper.json with your own DOI to retarget",
                ],
            },
            {
                "type": "text",
                "title": "Who built it",
                "bullets": paper.get("authors", ["Authors unknown"])[:6]
                + [f"Published in *{venue}* — {year}"],
            },
            {
                "type": "section_divider",
                "title": "The contribution",
            },
            {
                "type": "text",
                "title": "Take-home in one paragraph",
                "bullets": [
                    paper.get("abstract") or "Abstract unavailable in offline mode.",
                ],
            },
            {
                "type": "text",
                "title": "Strengths vs. limitations",
                "bullets": [
                    "STRENGTH — large, well-annotated dataset",
                    "STRENGTH — orthogonal validation across modalities",
                    "LIMIT — observational; mechanism not perturbed",
                    "LIMIT — generalization to other tissues untested",
                ],
            },
            {
                "type": "text",
                "title": "Discussion seeds",
                "bullets": [
                    "1. What replication experiment would falsify the central claim?",
                    "2. Which conclusions depend on the n=3 power assumption?",
                    "3. How does this connect to our own ongoing work?",
                    "4. What's the most-likely first contradicting paper to appear?",
                    "5. If you ran this study, what would you change?",
                ],
            },
            {
                "type": "references",
                "references": [
                    f"{', '.join((paper.get('authors') or [])[:3]) or 'Authors'} "
                    f"({year}). {paper['title']}. *{venue}*. "
                    f"doi:{paper.get('doi', 'n/a')}",
                ],
            },
        ],
    }


def _write_paper_md(paper: dict, out_dir: Path) -> Path:
    """Write a Tier-A-style markdown summary alongside the deck."""
    md = f"""---
doi: {paper.get("doi", "")}
title: {paper.get("title", "")}
year: {paper.get("year", "")}
journal: {paper.get("journal", "")}
tier: A
generated_by: examples/journal-club/run.py
---

# {paper.get("title", "Untitled")}

**Authors:** {", ".join(paper.get("authors") or [])}

**Venue:** {paper.get("journal", "")} ({paper.get("year", "")})

## Abstract

{paper.get("abstract") or "(abstract not available in offline mode)"}

## Why we read it

Bundled with the vaultlab `examples/journal-club/` workflow as a
runnable demo of the `ResearchClient → slide-plan → build_from_plan`
composition.
"""
    path = out_dir / "paper.md"
    path.write_text(md, encoding="utf-8")
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        type=Path,
        default=_HERE / "out",
        help="output directory (default: examples/journal-club/out)",
    )
    parser.add_argument(
        "--no-fetch",
        action="store_true",
        help="skip real-API metadata fetch and use bundled inputs/paper.json",
    )
    parser.add_argument(
        "--open",
        action="store_true",
        help="open the .pptx after building (best-effort)",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    out_dir: Path = args.out
    out_dir.mkdir(parents=True, exist_ok=True)

    paper = _load_bundled_paper()
    if not args.no_fetch:
        live = _try_fetch_real_metadata(paper["doi"])
        if live is not None:
            paper = {**paper, **{k: v for k, v in live.items() if v}}
            logger.info("Enriched metadata via ResearchClient")
        else:
            logger.info("Offline mode — using bundled metadata")

    plan = _build_plan(paper)
    paper_md = _write_paper_md(paper, out_dir)

    slug = (paper.get("title", "deck").split(":", 1)[0].lower().replace(" ", "-"))[:40]
    pptx_path = out_dir / f"journal-club-{slug or 'deck'}.pptx"

    from vaultlab.slides import build_from_plan

    results = build_from_plan(plan, pptx_path, write_marp=False)

    logger.info("")
    logger.info("Wrote:")
    logger.info("  - %s", results["pptx"])
    logger.info("  - %s", paper_md)
    logger.info("")
    logger.info("Open the deck:")
    logger.info("  start %s", results["pptx"])

    if args.open:
        try:
            import os

            os.startfile(results["pptx"])  # noqa: S606 — example helper
        except Exception:  # noqa: BLE001
            pass

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
