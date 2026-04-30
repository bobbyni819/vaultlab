"""One-off: print Phase 2 table of source-by-source author recovery.

Hits CrossRef, S2, OpenAlex, bioRxiv for each DOI and prints a markdown
table showing the recovery status. Used in the report only — not part
of the production pipeline.
"""

from __future__ import annotations

import io
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(
        sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True
    )

keys = json.load(
    open(
        os.path.expanduser("G:/My Drive/Knowledge/tools/.config/research_apis.json"),
        encoding="utf-8",
    )
)
S2_KEY = keys["semantic_scholar_api_key"]

DOIS = [
    "10.1039/c6sc05420j",
    "10.1038/nm.3488",
    "10.1371/journal.pone.0188799",
    "10.1038/s41591-018-0014-x",
    "10.1101/574160",
    "10.1038/nature21349",
    "10.1073/pnas.0408197102",
    "10.1167/iovs.11-7909",
    "10.1038/nrc.2016.52",
    "10.1126/science.aaa6204",
]


def fetch(url: str, headers=None, timeout: int = 15):
    req = urllib.request.Request(url, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return e.code, None
    except Exception as e:
        return None, str(e)


def cr(doi: str):
    code, d = fetch(
        f"https://api.crossref.org/works/{urllib.parse.quote(doi, safe=':/.-')}",
        headers={"User-Agent": "vaultlab/0.1 (mailto:test@test)"},
    )
    if code == 200 and d:
        return ("OK", len(d.get("message", {}).get("author", [])))
    return (str(code), 0)


def s2(doi: str):
    code, d = fetch(
        f"https://api.semanticscholar.org/graph/v1/paper/DOI:"
        f"{urllib.parse.quote(doi, safe=':/.-')}?fields=authors",
        headers={"x-api-key": S2_KEY},
    )
    if code == 200 and d:
        return ("OK", len(d.get("authors") or []))
    return (str(code), 0)


def oa(doi: str):
    code, d = fetch(
        f"https://api.openalex.org/works/doi:"
        f"{urllib.parse.quote(doi, safe=':/.-')}?mailto=test@test"
    )
    if code == 200 and d:
        return ("OK", len(d.get("authorships") or []))
    return (str(code), 0)


def br(doi: str):
    if not doi.startswith("10.1101/"):
        return ("skip", 0)
    code, d = fetch(f"https://api.biorxiv.org/details/biorxiv/{doi}/na/na")
    if code == 200 and d:
        coll = d.get("collection") or []
        if coll and coll[0].get("authors"):
            return ("OK", len(coll[0]["authors"].split(";")))
        return ("empty", 0)
    return (str(code), 0)


print(
    "| DOI | CrossRef | S2 | OpenAlex | bioRxiv | First successful (chain order) |"
)
print("|---|---|---|---|---|---|")
for doi in DOIS:
    c1 = cr(doi)
    time.sleep(0.3)
    c2 = s2(doi)
    time.sleep(0.3)
    c3 = oa(doi)
    time.sleep(0.3)
    c4 = br(doi)
    # Chain order: openalex, crossref-by-doi, s2, biorxiv
    first = "-"
    for name, status in [
        ("OpenAlex", c3),
        ("CrossRef", c1),
        ("S2", c2),
        ("bioRxiv", c4),
    ]:
        if status[0] == "OK" and status[1] > 0:
            first = name
            break
    print(
        f"| `{doi}` | {c1[0]}/{c1[1]} | {c2[0]}/{c2[1]} | "
        f"{c3[0]}/{c3[1]} | {c4[0]}/{c4[1]} | **{first}** |"
    )
