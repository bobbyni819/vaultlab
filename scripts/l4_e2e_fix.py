"""Re-render the arc with corrected wikilink slugs (use dots not hyphens)."""

from __future__ import annotations

import pickle
from pathlib import Path

from vaultlab.kb.paths import concept_path, summary_path
from vaultlab.research.lineage import (
    prepare_arc_task,
    render_arc_from_response,
)
from vaultlab.research.summarize import PaperSummary
import yaml
import re

# Reuse SUMMARIES + ARC_NARRATIVE from stage B (now with corrected slugs).
import sys
sys.path.insert(0, "C:/Users/bobby/Downloads/vaultlab/scripts")
from l4_e2e_stage_b import ARC_NARRATIVE, FORCE_TIER_A

TOPIC = "CODEX cellular neighborhoods"
KB_ROOT = Path(r"G:/My Drive/Knowledge/vaultlab")
DATE_STR = "2026-04-29"
STATE_DIR = Path(r"C:/Users/bobby/Downloads/vaultlab/scripts/_l4_state")


def load_summary_from_disk(doi: str) -> PaperSummary | None:
    path = summary_path(KB_ROOT, doi)
    if not path.exists():
        return None
    body = path.read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---\n", body, re.DOTALL)
    if not m:
        return None
    fm = yaml.safe_load(m.group(1))
    s = PaperSummary(
        doi=fm.get("doi", "").lower(),
        title=fm.get("title", ""),
        authors=list(fm.get("authors") or []),
        year=int(fm.get("year") or 0),
        journal=fm.get("journal", "") or "",
        og_score=float(fm.get("og_score") or 0.0),
        forward_influence=int(fm.get("forward_influence") or 0),
        year_bucket=fm.get("year_bucket", "unknown"),
        role_in_set=fm.get("role_in_set", ""),
        tier=fm.get("tier", "C"),
    )
    # Pull TL;DR
    tl_match = re.search(r"## TL;DR\s*\n(.*?)\n##", body, re.DOTALL)
    if tl_match:
        s.tldr = tl_match.group(1).strip()
    # Pull key findings
    kf_match = re.search(r"## Key findings[^\n]*\n(.*?)(?=\n## |\Z)", body, re.DOTALL)
    if kf_match:
        s.key_findings = [
            ln.strip().lstrip("- ").strip()
            for ln in kf_match.group(1).splitlines()
            if ln.strip().startswith("-") and "_(none)_" not in ln
        ]
    return s


def main():
    print("Loading corpus", flush=True)
    with open(STATE_DIR / "corpus.pkl", "rb") as f:
        corpus = pickle.load(f)

    # Build summaries dict from on-disk Wiki/Summaries files.
    summaries = {}
    for doi in corpus.papers:
        s = load_summary_from_disk(doi)
        if s is not None:
            summaries[doi] = s
    print(f"Loaded {len(summaries)} summaries from disk", flush=True)
    n_tier_a = sum(1 for s in summaries.values() if s.tier == "A" and s.tldr)
    print(f"  Of which {n_tier_a} have Tier-A real content", flush=True)

    # Prepare arc task
    task = prepare_arc_task(
        topic=TOPIC,
        corpus=corpus,
        summaries=summaries,
        kb_root=KB_ROOT,
        date_str=DATE_STR,
    )
    print(f"Arc output_path: {task.output_path}", flush=True)

    # Render with corrected narrative
    out = render_arc_from_response(task, ARC_NARRATIVE, corpus, write=True)
    print(f"Wrote: {out}", flush=True)
    print(f"Size: {out.stat().st_size} bytes", flush=True)


if __name__ == "__main__":
    main()
