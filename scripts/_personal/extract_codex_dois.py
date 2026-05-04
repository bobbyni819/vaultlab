"""Extract DOIs from CODEX papers.md for PDF re-acquisition test."""
import re
import json
from pathlib import Path

papers_md = Path(
    "G:/My Drive/Knowledge/vaultlab/Wiki/Projects/"
    "codex-multiplexed-imaging-methods-and-applications-across-tissue-types-evening3-rerun/"
    "papers.md"
)
text = papers_md.read_text(encoding="utf-8")

# Wikilinks like [[10.1016_j.cell.2018.07.010|Goltsev 2018]]
# Slug shape: <reg>_<rest>
pattern = re.compile(r"\[\[(\d{2}\.\d{4,}[^|\]\\]+)")
slugs = pattern.findall(text)

dois: list[str] = []
seen: set[str] = set()
for s in slugs:
    s_clean = s.replace(".pdf", "").strip()
    parts = s_clean.split("_", 1)
    if len(parts) == 2:
        doi = parts[0] + "/" + parts[1]
        if doi not in seen:
            seen.add(doi)
            dois.append(doi)

print(f"Extracted {len(dois)} unique DOIs from papers.md")
out = Path("G:/My Drive/Knowledge/vaultlab/Output/_pdf-reacquire-2026-05-01/dois.json")
out.parent.mkdir(exist_ok=True, parents=True)
out.write_text(json.dumps(dois, indent=2), encoding="utf-8")
print(f"First 10: {dois[:10]}")
print(f"Saved to {out}")
