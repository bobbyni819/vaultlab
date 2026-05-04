"""Extract structured text from the 6 Tier-A PDFs so Claude can summarize."""
from __future__ import annotations
import json
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore
except Exception:
    pass

from vaultlab.research.pdf import extract_text

CACHE = Path("G:/My Drive/Knowledge/vaultlab/Sources/Papers")
OUT = Path(__file__).parent / "tier_a_text"
OUT.mkdir(exist_ok=True)

PAPERS = [
    ("10.1002/eji.202048891", "10.1002_eji.202048891.pdf"),
    ("10.1016/j.cell.2018.07.010", "10-1016_j-cell-2018-07-010.pdf"),
    ("10.3389/fimmu.2021.687673", "10.3389_fimmu.2021.687673.pdf"),
    ("10.1038/s41592-022-01428-z", "10.1038_s41592-022-01428-z.pdf"),
    ("10.7554/elife.31657", "10-7554_elife-31657.pdf"),
    ("10.1126/science.adq2084", "10.1126_science.adq2084.pdf"),
]


def main() -> int:
    for doi, fname in PAPERS:
        pdf = CACHE / fname
        if not pdf.exists():
            print(f"[skip] {doi}: {pdf} not found")
            continue
        print(f"[extract] {doi} ({pdf.stat().st_size // 1024} KB) ...")
        try:
            text = extract_text(str(pdf))
        except Exception as exc:
            print(f"  failed: {exc}")
            continue
        # Truncate to first ~25k chars (~6-8 pages dense)
        head = text[:30000]
        out = OUT / (doi.replace("/", "_") + ".txt")
        out.write_text(head, encoding="utf-8")
        print(f"  wrote {out.name}: {len(text)} chars total, kept {len(head)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
