#!/usr/bin/env python
"""Audit `citations/evidence.py` exact-match hit-rate against the retrieval benchmark.

Feeds each benchmark tuple's (source_doi, claim) through `EvidenceIndex.lookup` and
records hit/miss. A miss is classified into two distinct failure modes the user needs
separately:

- **index-lacks-entry**  — the DOI is not present in the index at all.
- **normalization/exact-match-failed** — the DOI *is* indexed, but exact-string
  normalize-then-equal did not match the claim.

Nothing is dropped silently: a missing index file, a dot-path/Drive-shortcut KB, and
DOI-not-indexed each get a counted, named line.

Two KB roots are audited:
- **configured** — `resolve_kb_root()` (the contract; never hardcoded).
- **corpus**     — `corpus_meta.json["kb_root"]` (where the benchmark claims were
  mined). `evidence.py` uses `os.path`, so it can read a dot-path index if one exists
  (unlike the TF-IDF collector) — this root is therefore audited, not skipped.

Run:
    /opt/anaconda3/bin/python tests/benchmarks/retrieval/evidence_audit.py
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# Make the package importable when run as a plain script.
_REPO_ROOT = Path(__file__).resolve().parents[3]
_SRC = _REPO_ROOT / "src"
if _SRC.is_dir() and str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from vaultlab.citations.evidence import EvidenceIndex  # noqa: E402
from vaultlab.context import KbRootNotConfigured, resolve_kb_root  # noqa: E402

_HERE = Path(__file__).resolve().parent
_TUPLES_PATH = _HERE / "tuples.jsonl"
_META_PATH = _HERE / "corpus_meta.json"
_REPORT_PATH = _HERE / "evidence_audit.md"


def _load_tuples(path: Path) -> list[dict]:
    tuples: list[dict] = []
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = line.strip()
        if not line:
            continue
        try:
            tuples.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise SystemExit(f"Malformed JSON in {path.name} line {i}: {exc}") from exc
    return tuples


def _has_dot_component(root: Path) -> bool:
    return any(part.startswith(".") for part in root.parts)


def _audit_root(root: Path, tuples: list[dict]) -> dict:
    """Score every tuple against the evidence index at `root`. Returns counts +
    per-tuple rows + structural findings. Never drops a tuple silently."""
    index_path = Path(root) / "Sources" / ".evidence_index.json"
    index_file_present = index_path.exists()

    idx = EvidenceIndex(str(root))  # graceful on a missing/corrupt file
    stats = idx.stats()
    # DOIs that actually carry ≥1 claim. A degenerate key with zero claims can never
    # match a lookup, so it counts as index-lacks-entry — not normalization-failed.
    indexed_dois = {e["doi"] for e in idx.list_all() if e["claim_count"] > 0}

    hits = 0
    miss_doi_absent = 0
    miss_claim_unmatched = 0
    rows: list[dict] = []
    for t in tuples:
        doi = t.get("source_doi", "") or ""
        claim = t.get("claim", "") or ""
        result = idx.lookup(doi, claim)
        if result is not None:
            hits += 1
            mode = "hit"
        elif doi.lower().strip() not in indexed_dois:
            miss_doi_absent += 1
            mode = "miss:index-lacks-entry"
        else:
            miss_claim_unmatched += 1
            mode = "miss:normalization-failed"
        rows.append({"doi": doi, "claim": claim, "mode": mode})

    return {
        "root": str(root),
        "index_path": str(index_path),
        "index_file_present": index_file_present,
        "is_dot_path": _has_dot_component(Path(root)),
        "stats": stats,
        "indexed_doi_count": len(indexed_dois),
        "total": len(tuples),
        "hits": hits,
        "miss_doi_absent": miss_doi_absent,
        "miss_claim_unmatched": miss_claim_unmatched,
        "rows": rows,
    }


def _print_root(label: str, a: dict) -> None:
    print(f"\n=== {label} KB: {a['root']} ===")
    print(f"  .evidence_index.json present: {a['index_file_present']}  ({a['index_path']})")
    if a["is_dot_path"]:
        print("  NOTE: dot-path/Drive-shortcut KB — evidence.py reads it via os.path "
              "(not skipped); the index file's presence is reported above.")
    print(f"  index stats: {a['stats']['total_papers']} papers / "
          f"{a['stats']['total_claims']} claims; {a['indexed_doi_count']} distinct DOIs indexed")
    print(f"  HEADLINE: evidence.py found the correct source for {a['hits']} of {a['total']} benchmark claims")
    print(f"    miss — index-lacks-entry (DOI absent):        {a['miss_doi_absent']}")
    print(f"    miss — normalization/exact-match failed:      {a['miss_claim_unmatched']}")
    print(f"    tuples silently skipped:                      0 (all {a['total']} scored)")


def _dominant_mode(a: dict) -> str:
    if a["hits"] == a["total"]:
        return "none — all hits"
    if not a["index_file_present"]:
        return "index file absent (no .evidence_index.json exists in this KB)"
    if a["miss_doi_absent"] >= a["miss_claim_unmatched"]:
        return "index-lacks-entry (DOI not in index)"
    return "normalization/exact-match failed (DOI indexed, claim not matched)"


def _write_report(configured: dict, corpus: dict, total: int) -> None:
    lines: list[str] = []
    lines.append("# Evidence-index audit — `citations/evidence.py` vs the retrieval benchmark\n")
    lines.append(
        f"Each of the **{total}** benchmark tuples (`tuples.jsonl`, all `verified:false`) was looked up "
        "through `EvidenceIndex.lookup(source_doi, claim)` — the exact-match (normalize-then-equal) path, "
        "unchanged. No fuzzy/semantic matching was added.\n"
    )
    lines.append("## Headline\n")
    lines.append("| KB root | hits / total | dominant failure mode |")
    lines.append("|---|---|---|")
    lines.append(f"| configured (`resolve_kb_root`) | **{configured['hits']} / {configured['total']}** | "
                 f"{_dominant_mode(configured)} |")
    lines.append(f"| corpus (`corpus_meta.kb_root`) | **{corpus['hits']} / {corpus['total']}** | "
                 f"{_dominant_mode(corpus)} |")
    lines.append("")
    lines.append(
        f"**Plainly: evidence.py found the correct source for {configured['hits']} of {configured['total']} "
        f"benchmark claims in the configured KB** "
        f"(and {corpus['hits']} of {corpus['total']} in the corpus KB where the claims were mined).\n"
    )

    for label, a in (("Configured", configured), ("Corpus", corpus)):
        lines.append(f"## {label} KB — `{a['root']}`\n")
        lines.append(f"- `.evidence_index.json` present: **{a['index_file_present']}** (`{a['index_path']}`)")
        if a["is_dot_path"]:
            lines.append("- Dot-path/Drive-shortcut KB: `evidence.py` reads it via `os.path`, so it is "
                         "**not skipped** (unlike the TF-IDF collector). Presence reported above.")
        lines.append(f"- Index contents: {a['stats']['total_papers']} papers / {a['stats']['total_claims']} "
                     f"claims; {a['indexed_doi_count']} distinct DOIs indexed")
        lines.append("- Outcome counts (nothing dropped silently):")
        lines.append(f"  - hits: **{a['hits']}**")
        lines.append(f"  - miss — index-lacks-entry (DOI absent): **{a['miss_doi_absent']}**")
        lines.append(f"  - miss — normalization/exact-match failed (DOI indexed, claim unmatched): "
                     f"**{a['miss_claim_unmatched']}**")
        lines.append(f"  - tuples silently skipped: **0** (all {a['total']} scored)")
        lines.append("")

    lines.append("## Per-tuple result (configured KB)\n")
    lines.append("| DOI | mode | claim |")
    lines.append("|---|---|---|")
    for r in configured["rows"]:
        claim = r["claim"].replace("|", "\\|")[:70]
        lines.append(f"| `{r['doi']}` | {r['mode']} | {claim}… |")
    lines.append("")

    lines.append("## Interpretation\n")
    lines.append(
        "The exact-match approach is only as good as what `/cite-watch` has previously stored: a claim hits "
        "only if that exact paper+claim was verified before and the claim string matches after `.strip().lower()`. "
        "With no `.evidence_index.json` present, the index is structurally empty and every lookup misses as "
        "*index-lacks-entry* — this is a coverage finding, not a normalization failure. Improving recall "
        "(populating the index, or fuzzy/semantic matching) is a separate decision the user owns.\n"
    )
    _REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    if not _TUPLES_PATH.exists():
        print(f"[STOP] benchmark tuples not found at {_TUPLES_PATH}. Not rebuilding the benchmark.",
              file=sys.stderr)
        return 1

    try:
        configured_root = resolve_kb_root()
        print(f"[kb] configured root (resolve_kb_root): {configured_root}")
    except KbRootNotConfigured as exc:
        print("[kb] KB not configured. Run `vaultlab init` "
              f"(default: {getattr(exc, 'suggested_default', '<unset>')}).", file=sys.stderr)
        return 1

    tuples = _load_tuples(_TUPLES_PATH)
    meta = json.loads(_META_PATH.read_text(encoding="utf-8"))
    corpus_root = Path(meta["kb_root"])  # from data, not hardcoded

    configured = _audit_root(Path(configured_root), tuples)
    corpus = _audit_root(corpus_root, tuples)

    _print_root("CONFIGURED", configured)
    _print_root("CORPUS", corpus)

    _write_report(configured, corpus, len(tuples))
    print(f"\n[report] written to {_REPORT_PATH}")

    # Loud root-cause line so a null result is not dressed up.
    if configured["hits"] == 0 and not configured["index_file_present"]:
        print("\n[finding] 0 hits in the configured KB because no .evidence_index.json exists there "
              "(index-lacks-entry for all tuples) — a coverage gap, not a normalization failure.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
