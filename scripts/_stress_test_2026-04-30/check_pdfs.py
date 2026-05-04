"""Check which canonical PDFs are present for our candidate Tier-A picks."""
from __future__ import annotations
import pickle
from pathlib import Path
from vaultlab.research.acquisition import cache_path_for

SCRATCH = Path(__file__).parent
with (SCRATCH / "state.pkl").open("rb") as fh:
    state = pickle.load(fh)
kb = Path(state["kb_root"])
cache = kb / "Sources" / "Papers"

candidates = [
    "10.1002/eji.202048891",
    "10.1016/j.cell.2018.07.010",
    "10.1016/j.cell.2020.07.005",
    "10.3389/fimmu.2021.687673",
    "10.1038/s41596-021-00556-8",
    "10.1038/s41577-023-00936-z",
    "10.1038/s41592-022-01428-z",
    "10.7554/elife.31657",
    "10.1126/science.adq2084",
    "10.1080/29979676.2024.2437947",
    "10.1101/2025.06.23.661064",
    "10.17504/protocols.io.36wgqj3y3vk5/v1",
]

# Also reflect the actual acq_results
acq = state["acq_results"]

for doi in candidates:
    p = cache_path_for(doi, cache)
    exists = p.exists()
    acq_info = acq.get(doi.lower(), {})
    print(f"{doi}")
    print(f"   canonical -> {p.name}  exists={exists}")
    print(f"   acq pdf_path -> {acq_info.get('pdf_path')}")
    print(f"   source -> {acq_info.get('source')}")
