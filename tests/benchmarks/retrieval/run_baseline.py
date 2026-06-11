#!/usr/bin/env python
"""Retrieval benchmark v0 — score the current TF-IDF baseline at recall@1/5/20.

Measures (only) the existing `vaultlab.kb.semantic_search.search` TF-IDF backend
against a versioned corpus of (claim, source_doi, passage) tuples mined from the
user's manuscripts. This is the foundation artifact for the indexing direction:
every later index (embeddings, BM25 chunk store) gets scored against the same
`tuples.jsonl` with this same recall@k definition.

Recall@k definition
-------------------
For each tuple, query the baseline with the claim text and take the top-k returned
files. The tuple is a *hit@k* iff its `source_doi` (normalised: lowercased) appears
as a substring of the text of ANY of those top-k files — i.e. a returned result is
mapped back to a DOI by reading the file and looking for the DOI string.
``recall@k = (#tuples that hit@k) / (#tuples)``.

Important caveat (see corpus_meta.json `caveat`): in the current corpus the cited
DOI lives in the SAME file as the claim, so this is an inflated UPPER BOUND, not
true cross-doc citation retrieval. Reported honestly, not as a success metric.

Run:
    /opt/anaconda3/bin/python tests/benchmarks/retrieval/run_baseline.py
    /opt/anaconda3/bin/python tests/benchmarks/retrieval/run_baseline.py --kb-root /path/to/kb
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Make the package importable when run as a plain script.
_REPO_ROOT = Path(__file__).resolve().parents[3]
_SRC = _REPO_ROOT / "src"
if _SRC.is_dir() and str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from vaultlab.context import KbRootNotConfigured, resolve_kb_root  # noqa: E402
from vaultlab.kb.semantic_search import search  # noqa: E402

_HERE = Path(__file__).resolve().parent
_TUPLES_PATH = _HERE / "tuples.jsonl"
_META_PATH = _HERE / "corpus_meta.json"

_KS = (1, 5, 20)
_TOP_K = max(_KS)


def _report_path(backend: str) -> Path:
    name = "baseline_report.md" if backend == "tfidf" else f"baseline_report_{backend}.md"
    return _HERE / name


def _normalise_doi(doi: str) -> str:
    """Lowercase + strip so the substring match is case/whitespace insensitive."""
    return doi.strip().lower()


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


def _hit_at_k(source_doi: str, ranked_texts: list[str], k: int) -> bool:
    """True iff the DOI string appears in any of the top-k returned file texts."""
    needle = _normalise_doi(source_doi)
    return any(needle in text for text in ranked_texts[:k])


def main() -> int:
    parser = argparse.ArgumentParser(description="Retrieval baseline recall@k")
    parser.add_argument(
        "--kb-root",
        default=None,
        help="Override the KB root to search. Defaults to corpus_meta.json `kb_root`.",
    )
    parser.add_argument(
        "--backend",
        choices=("tfidf", "bm25", "embeddings"),
        default="tfidf",
        help="Retrieval backend to score. Default tfidf (the original baseline).",
    )
    args = parser.parse_args()

    # Refuse to score the embeddings path if its optional dep is missing — else
    # search() silently falls back to tfidf and the numbers would be mislabeled.
    if args.backend == "embeddings":
        import importlib.util

        if importlib.util.find_spec("sentence_transformers") is None:
            print(
                "[backend] ERROR: --backend embeddings requires sentence-transformers, "
                "which is not installed. Install it or run with the default tfidf backend.",
                file=sys.stderr,
            )
            return 1
    print(f"[backend] scoring backend: {args.backend}")

    # Honour the KB-resolution contract: resolve + print the configured root.
    try:
        configured_root = resolve_kb_root()
        print(f"[kb] configured root (resolve_kb_root): {configured_root}")
    except KbRootNotConfigured as exc:
        print(
            "[kb] KB not configured. Run `vaultlab init` "
            f"(default: {getattr(exc, 'suggested_default', '<unset>')}).",
            file=sys.stderr,
        )
        return 1

    meta = json.loads(_META_PATH.read_text(encoding="utf-8"))
    # The corpus records the KB its sources actually live in. Score against that,
    # not necessarily the configured root, or every tuple trivially misses.
    search_root = Path(args.kb_root) if args.kb_root else Path(meta["kb_root"])
    if str(search_root) != str(configured_root):
        print(
            "[kb] WARNING: scoring against the corpus KB root, which differs from the "
            "configured root.\n"
            f"        corpus kb_root : {search_root}\n"
            f"        configured     : {configured_root}\n"
            "        Reason: the cited sources for these tuples live in the corpus KB; "
            "searching the configured KB would make every tuple miss. "
            "Override with --kb-root.",
        )
    if not search_root.exists():
        print(f"[kb] ERROR: search root does not exist: {search_root}", file=sys.stderr)
        return 1

    tuples = _load_tuples(_TUPLES_PATH)
    total = len(tuples)
    if total == 0:
        print("[corpus] no tuples loaded — nothing to score.", file=sys.stderr)
        return 1
    declared = meta.get("tuple_count")
    if declared is not None and declared != total:
        print(
            f"[corpus] WARNING: loaded {total} tuples but corpus_meta.json declares "
            f"tuple_count={declared}. Lines may have been added/dropped.",
            file=sys.stderr,
        )

    skipped = meta.get("skipped", [])
    n_skipped = len(skipped)

    # Score each tuple. Track whether the baseline ever returned a result — if it
    # returns nothing for every query, the KB wasn't scanned (wrong root, empty KB)
    # and a 0.0 recall would be a collection artifact, not a retrieval signal.
    hits = {k: 0 for k in _KS}
    per_tuple: list[dict] = []
    n_nonempty_searches = 0
    for t in tuples:
        results = search(search_root, t["claim"], top_k=_TOP_K, backend=args.backend)
        if results:
            n_nonempty_searches += 1
        ranked_texts: list[str] = []
        for h in results:
            try:
                ranked_texts.append(h.path.read_text(encoding="utf-8", errors="ignore").lower())
            except OSError:
                ranked_texts.append("")
        row = {"source_doi": t["source_doi"], "claim": t["claim"]}
        for k in _KS:
            hit = _hit_at_k(t["source_doi"], ranked_texts, k)
            row[f"hit@{k}"] = hit
            if hit:
                hits[k] += 1
        # Rank at which the DOI first appears (for diagnostics).
        needle = _normalise_doi(t["source_doi"])
        row["first_rank"] = next(
            (i + 1 for i, txt in enumerate(ranked_texts) if needle in txt), None
        )
        per_tuple.append(row)

    recall = {k: hits[k] / total for k in _KS}

    if n_nonempty_searches == 0:
        print(
            f"\n[WARN] the baseline returned 0 files for ALL {total} queries — the KB at "
            f"`{search_root}` was not scanned (collection artifact, not a retrieval "
            f"signal). recall@k below is meaningless; check the search root.",
            file=sys.stderr,
        )

    # ---- console output ----
    print()
    print(f"[corpus] {total} tuples scored (all verified:false, pending user review)")
    print(f"recall@1  = {recall[1]:.3f}  ({hits[1]}/{total})")
    print(f"recall@5  = {recall[5]:.3f}  ({hits[5]}/{total})")
    print(f"recall@20 = {recall[20]:.3f}  ({hits[20]}/{total})")
    print()
    print("per-tuple hit/miss @k=5:")
    for row in per_tuple:
        mark = "HIT " if row["hit@5"] else "MISS"
        rank = row["first_rank"]
        rank_s = f"rank {rank}" if rank is not None else "not in top-20"
        print(f"  [{mark}] {row['source_doi']:<28} ({rank_s})  {row['claim'][:60]}...")
    print()
    print(f"{n_skipped} tuples skipped during mining because: "
          + "; ".join(s.get("reason", "?").split(":")[0] for s in skipped))

    report_path = _report_path(args.backend)
    _write_report(recall, hits, total, per_tuple, skipped, search_root, configured_root, meta,
                  args.backend, report_path)
    print(f"\n[report] written to {report_path}")
    return 0


def _write_report(recall, hits, total, per_tuple, skipped, search_root, configured_root, meta,
                  backend, report_path) -> None:
    lines: list[str] = []
    lines.append(f"# Retrieval Benchmark v0 — `{backend}` backend recall@k\n")
    lines.append(
        "> All corpus tuples are `verified: false` — these numbers are pending the "
        "user's review of `tuples.jsonl`.\n"
    )
    lines.append("## Headline\n")
    lines.append("| metric | value | hits/total |")
    lines.append("|---|---|---|")
    lines.append(f"| recall@1 | {recall[1]:.3f} | {hits[1]}/{total} |")
    lines.append(f"| recall@5 | {recall[5]:.3f} | {hits[5]}/{total} |")
    lines.append(f"| recall@20 | {recall[20]:.3f} | {hits[20]}/{total} |")
    lines.append("")
    lines.append("## How to read this number\n")
    lines.append(
        f"**Caveat — {meta.get('caveat', '').split(':', 1)[0]}.** "
        + meta.get("caveat", "").split(":", 1)[-1].strip()
        + "\n"
    )
    lines.append("## Configuration\n")
    lines.append(f"- Backend: `vaultlab.kb.semantic_search.search` (backend=`{backend}`, default subdirs)")
    lines.append(f"- Search KB root (corpus): `{search_root}`")
    lines.append(f"- Configured KB root (`resolve_kb_root`): `{configured_root}`")
    lines.append(
        f"- recall@k = (#tuples whose `source_doi` substring appears in the text of any "
        f"top-k returned file) / {total}\n"
    )
    lines.append("## Per-tuple result @k=5\n")
    lines.append("| hit | source_doi | first rank | claim |")
    lines.append("|---|---|---|---|")
    for row in per_tuple:
        mark = "✅" if row["hit@5"] else "❌"
        rank = row["first_rank"]
        rank_s = str(rank) if rank is not None else ">20"
        claim = row["claim"].replace("|", "\\|")[:80]
        lines.append(f"| {mark} | `{row['source_doi']}` | {rank_s} | {claim}… |")
    lines.append("")
    lines.append(f"## Mining audit — {len(skipped)} candidates skipped\n")
    lines.append(
        "Nothing was dropped silently. Each candidate below was considered during "
        "mining and excluded for the stated reason:\n"
    )
    for s in skipped:
        lines.append(f"- **{s.get('candidate', '?')}** — {s.get('reason', '?')}")
    lines.append("")
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
