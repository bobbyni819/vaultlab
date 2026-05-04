"""Trust-but-verify: do CrossRef / S2 / OpenAlex actually return citation graphs
for paywalled papers? Run real API calls, report what we get.

Test paper: Jinek 2012 (Science, paywalled) — DOI 10.1126/science.1225829.
Known to be the foundational CRISPR-Cas9 paper; should have ~70 references and
~22,000 citations.
"""

from __future__ import annotations

import json
import urllib.request
import urllib.error
from pathlib import Path

CONFIG = Path(r"G:/My Drive/Knowledge/tools/.config/research_apis.json")
DOI = "10.1126/science.1225829"  # Jinek 2012, paywalled in Science

apis = json.loads(CONFIG.read_text(encoding="utf-8"))
S2_KEY = apis.get("semantic_scholar_api_key", "")


def fetch(url: str, headers: dict | None = None) -> dict | None:
    headers = headers or {}
    headers.setdefault("User-Agent", "vaultlab-test (bobby.ni@duke.edu)")
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        print(f"  HTTP {e.code}: {e.reason}")
        return None
    except Exception as e:
        print(f"  ERROR: {type(e).__name__}: {e}")
        return None


print("=" * 70)
print(f"TEST PAPER: Jinek et al. 2012 — DOI {DOI}")
print("Paywalled in Science. Known seminal CRISPR-Cas9 paper.")
print("=" * 70)

# 1. CrossRef — free, no key
print("\n[1] CrossRef /works/{doi} — free, no key")
cr = fetch(f"https://api.crossref.org/works/{DOI}")
if cr:
    msg = cr.get("message", {})
    refs = msg.get("reference", [])
    print(f"  Title: {msg.get('title', ['?'])[0][:60]}...")
    print(f"  References returned: {len(refs)}")
    if refs:
        sample = refs[0]
        print(f"  Sample ref keys: {list(sample.keys())[:8]}")
        has_doi = sum(1 for r in refs if r.get("DOI"))
        print(f"  Refs with DOI resolved: {has_doi}/{len(refs)}")
    cited_by_count = msg.get("is-referenced-by-count", "?")
    print(f"  is-referenced-by-count (forward citations, total): {cited_by_count}")
else:
    print("  CrossRef call FAILED")

# 2. Semantic Scholar — needs key
print("\n[2] Semantic Scholar /paper/DOI:{doi} — using existing key")
s2_url = (
    f"https://api.semanticscholar.org/graph/v1/paper/DOI:{DOI}"
    f"?fields=title,year,citationCount,influentialCitationCount,references.title,references.year,references.citationCount,citations.title,citations.year"
)
s2 = fetch(s2_url, headers={"x-api-key": S2_KEY})
if s2:
    print(f"  Title: {s2.get('title', '?')[:60]}...")
    print(f"  Citation count: {s2.get('citationCount', '?')}")
    print(f"  Influential citation count: {s2.get('influentialCitationCount', '?')}")
    refs = s2.get("references", []) or []
    cites = s2.get("citations", []) or []
    print(f"  References returned: {len(refs)} (S2 caps at 100 per endpoint)")
    print(f"  Citations returned: {len(cites)} (S2 caps at 100 per endpoint)")
else:
    print("  S2 call FAILED")

# 3. OpenAlex — free, no key (just polite-pool email recommended)
print("\n[3] OpenAlex /works/doi:{doi} — free, no key required")
oa = fetch(f"https://api.openalex.org/works/doi:{DOI}?mailto=bobby.ni@duke.edu")
if oa:
    print(f"  Title: {oa.get('title', '?')[:60]}...")
    refs = oa.get("referenced_works", []) or []
    print(f"  Referenced works (backward citations): {len(refs)}")
    print(f"  Cited by count: {oa.get('cited_by_count', '?')}")
    print(f"  Open access status: {oa.get('open_access', {}).get('oa_status', '?')}")
else:
    print("  OpenAlex call FAILED")

# 4. Direct comparison: which has the most complete reference list?
print("\n" + "=" * 70)
print("VERDICT")
print("=" * 70)
print("Coverage of references for this PAYWALLED paper:")
if cr:
    print(f"  CrossRef:        {len(cr.get('message', {}).get('reference', []))} refs")
if s2:
    print(f"  Semantic Scholar: {len(s2.get('references', []) or [])} refs")
if oa:
    print(f"  OpenAlex:        {len(oa.get('referenced_works', []) or [])} refs")
print("\nIf all three return refs for a paywalled paper, the citation-graph claim")
print("holds — we don't need full text to know what a paper cites.")
