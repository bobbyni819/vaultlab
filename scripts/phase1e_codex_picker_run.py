"""Phase 1E — pick top-30 Tier-A papers from the 200-candidate pool.

Composite ranking (Bobby's "leverage your strength" directive):
  1. ALL papers with cached PDFs + real abstracts → strong Tier-A candidates
  2. Seeds (high prior signal regardless of OG-score)
  3. High-OG papers we have a PDF for (even without abstract on file —
     we can read the PDF)
  4. Recent (2023+) papers with PDFs (SOTA)

Picks the top 30 by a composite score. This is the deterministic-pick
fallback path; the LLM-driven content-aware picker would refine but
shouldn't disagree drastically given how strong the explicit signals
are (PDF availability + abstract presence + OG-score).
"""

from __future__ import annotations

import json
from pathlib import Path


CANDIDATES_PATH = Path(
    "G:/My Drive/Knowledge/vaultlab/Output/_phase1d-codex-2026-05-01/candidates.json"
)
SEEDS_PATH = Path(
    "G:/My Drive/Knowledge/vaultlab/Output/_phase1b-codex-2026-05-01/seeds.json"
)
TARGET_N = 30


def main() -> None:
    candidates = json.loads(CANDIDATES_PATH.read_text(encoding="utf-8"))
    seeds = json.loads(SEEDS_PATH.read_text(encoding="utf-8"))
    seed_dois = {s["doi"].lower() for s in seeds if s.get("doi")}

    print(f"Picker pool size: {len(candidates)}")
    print(f"Seeds: {len(seed_dois)}")
    print()

    # Composite score: heavy emphasis on PDF availability + abstract presence
    def score(c: dict) -> float:
        s = 0.0
        if c["has_pdf"]:
            s += 5.0  # major boost; we can actually read this paper
        if c["has_real_abstract"]:
            s += 3.0
        if c["doi"].lower() in seed_dois:
            s += 4.0  # seeds carry prior relevance
        s += 5.0 * (c.get("og_score", 0) or 0)
        s += 0.3 * (c.get("forward_influence", 0) or 0)
        # Recency bonus
        year = c.get("year") or 0
        if year >= 2024:
            s += 1.5
        elif year >= 2022:
            s += 1.0
        elif year >= 2020:
            s += 0.5
        return s

    ranked = sorted(candidates, key=score, reverse=True)
    picks = ranked[:TARGET_N]

    print(f"Top {TARGET_N} Tier-A picks:")
    print(f"{'#':>3}  {'year':>4}  {'PDF':>3}  {'Abs':>3}  {'OG':>5}  {'Fwd':>3}  {'seed':>4}  title")
    print("-" * 120)
    for i, p in enumerate(picks, 1):
        is_seed = "S" if p["doi"].lower() in seed_dois else "."
        pdf_flag = "Y" if p["has_pdf"] else "."
        abs_flag = "Y" if p["has_real_abstract"] else "."
        title = (p.get("title") or "(untitled)")[:65]
        print(
            f"{i:>3}  {p['year']:>4}  {pdf_flag:>3}  {abs_flag:>3}  "
            f"{p['og_score']:>5.2f}  {p['forward_influence']:>3d}  "
            f"{is_seed:>4}  {title}"
        )

    n_with_pdf = sum(1 for p in picks if p["has_pdf"])
    n_with_abs = sum(1 for p in picks if p["has_real_abstract"])
    n_seeds_in_picks = sum(1 for p in picks if p["doi"].lower() in seed_dois)
    print()
    print(f"Picks with cached PDF:    {n_with_pdf}/{TARGET_N}")
    print(f"Picks with real abstract: {n_with_abs}/{TARGET_N}")
    print(f"Picks that are seeds:     {n_seeds_in_picks}/{TARGET_N}")
    print()

    # Save picks for downstream phases
    out_dir = Path("G:/My Drive/Knowledge/vaultlab/Output/_phase1e-codex-2026-05-01")
    out_dir.mkdir(exist_ok=True, parents=True)
    picks_doc = {
        "topic": "CODEX multiplexed imaging — methods and applications across tissue types",
        "n_picks": len(picks),
        "n_with_pdf": n_with_pdf,
        "n_with_abstract": n_with_abs,
        "n_seeds_in_picks": n_seeds_in_picks,
        "picks": [
            {
                "rank": i + 1,
                "doi": p["doi"],
                "title": p["title"],
                "year": p["year"],
                "og_score": p["og_score"],
                "forward_influence": p["forward_influence"],
                "has_pdf": p["has_pdf"],
                "has_real_abstract": p["has_real_abstract"],
                "is_seed": p["doi"].lower() in seed_dois,
                "composite_score": round(score(p), 2),
            }
            for i, p in enumerate(picks)
        ],
    }
    (out_dir / "tier-a-picks.json").write_text(
        json.dumps(picks_doc, indent=2), encoding="utf-8"
    )
    print(f"Saved: {out_dir / 'tier-a-picks.json'}")


if __name__ == "__main__":
    main()
