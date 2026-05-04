"""Phase 4 — acquire PDFs for the 15 curated picks via the waterfall.

Tier-0: paperclip pre-extracted full text
Tier-1: Unpaywall / PMC OA
Tier-2: bioRxiv / medRxiv
Tier-3: Springer OA
Tier-4: Elsevier (gated, requires institutional key)
"""
from __future__ import annotations
import json
from pathlib import Path
from vaultlab.research.acquisition import acquire_pdf
from vaultlab.research.sources.paperclip import PaperclipClient
from vaultlab.research.config import get_config

WORKSPACE = Path("G:/My Drive/Knowledge/vaultlab/Wiki/Projects/multiscale-tissue-simulation-lung-infection/_short_2026_05_02_workspace")
CACHE = Path("G:/My Drive/Knowledge/vaultlab/Sources/Papers")
CACHE.mkdir(parents=True, exist_ok=True)

picks = json.loads((WORKSPACE / "curated_picks.json").read_text(encoding="utf-8"))["picks"]
apis = get_config()
pc = PaperclipClient()

print(f"Acquiring {len(picks)} PDFs into {CACHE}")
acq_results = []
for i, p in enumerate(picks, 1):
    doi = p["doi"]
    print(f"  [{i:2d}/{len(picks)}] {doi}")
    try:
        result = acquire_pdf(
            doi,
            cache_dir=CACHE,
            apis=apis,
            paperclip_client=pc,
            timeout=60,
        )
        outcome = result.source
        path = str(result.pdf_path) if result.pdf_path else None
        license_ = result.license
        tried = result.tried
        err = result.error
    except Exception as e:
        outcome = "exception"
        path = None
        license_ = None
        tried = []
        err = str(e)
    print(f"      => {outcome} ({license_ or '-'}) tried={tried} {('path=' + str(path)) if path else ('err=' + (err or 'none'))}")
    acq_results.append({
        "doi": doi,
        "rank": p["rank"],
        "bucket": p["bucket"],
        "outcome": outcome,
        "pdf_path": path,
        "license": license_,
        "tried": tried,
        "error": err,
    })

(WORKSPACE / "acquisition_results.json").write_text(
    json.dumps(acq_results, indent=2, default=str), encoding="utf-8"
)

print()
print("Summary:")
counts = {}
for r in acq_results:
    counts[r["outcome"]] = counts.get(r["outcome"], 0) + 1
for k, v in sorted(counts.items(), key=lambda x: -x[1]):
    print(f"  {k}: {v}")
print(f"  total acquired: {sum(1 for r in acq_results if r['pdf_path'])}/{len(acq_results)}")
