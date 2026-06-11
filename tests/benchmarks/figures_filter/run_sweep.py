#!/usr/bin/env python
"""Sweep `research/figures.py`'s quality filter over a PMC/JATS corpus.

Characterizes the existing `(min_dimension, min_bytes)` keep/drop predicate — it does
NOT change `figures.py`. For every image file in each PMC OA package the JATS XML
gives a ground-truth label (positive = a `<fig>` graphic, negative = any other image),
then the filter predicate is swept over a 2-D grid and precision/recall/F1 are pooled
across the corpus.

Filter predicate (faithful to figures.py lines 106 & 116):
    keep ⟺ min_dim_px >= min_dimension AND size_bytes >= min_bytes
The current defaults are IMPORTED from figures.py (not hardcoded) to mark that cell.

Precision/recall vs the keep/drop decision:
    kept positive = TP, kept negative = FP, dropped positive = FN
    precision = TP/(TP+FP), recall = TP/(TP+FN), F1 = 2PR/(P+R)

Run:
    /opt/anaconda3/bin/python tests/benchmarks/figures_filter/run_sweep.py --corpus-dir <dir>
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))  # import sibling `labeling`
_REPO_ROOT = _HERE.parents[2]
_SRC = _REPO_ROOT / "src"
if _SRC.is_dir() and str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

import labeling  # noqa: E402
from vaultlab.research.figures import _DEFAULT_MIN_BYTES, _DEFAULT_MIN_DIM  # noqa: E402

_REPORT_PATH = _HERE / "filter_sweep_report.md"
_DEFAULT_CORPUS = _HERE / "corpus"

# Explicit sweep grid (brackets the figures.py defaults 200 px / 5000 B).
GRID_MIN_DIM = [0, 100, 150, 200, 250, 300, 400]
GRID_MIN_BYTES = [0, 1000, 2500, 5000, 10000, 25000, 50000]


def _keep(min_dim_px: int, size_bytes: int, min_dim: int, min_bytes: int) -> bool:
    """figures.py keep decision: drop if min(w,h) < min_dim OR size < min_bytes.

    Mirrors figures.py lines 106 & 116 exactly (strict `<` drop ⟺ `>=` keep, both
    conditions). `size_bytes` is the PNG-encoded size (see labeling.read_image_features),
    matching how figures.py measures it. If figures.py ever adds a third filter
    condition, update this predicate to match.
    """
    return min_dim_px >= min_dim and size_bytes >= min_bytes


def _prf(tp: int, fp: int, fn: int) -> tuple[float, float, float]:
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return precision, recall, f1


def _aggregate_findings(results: list) -> dict:
    return {
        "articles_total": len(results),
        "articles_no_nxml": sum(1 for r in results if not r.has_xml),
        "articles_xml_unparseable": sum(1 for r in results if r.has_xml and not r.parseable_xml),
        "articles_zero_images": sum(1 for r in results if r.n_candidate_images == 0),
        "articles_zero_positives_mapped": sum(
            1 for r in results if r.parseable_xml and r.n_fig_hrefs > 0 and r.n_positive == 0
        ),
        "fig_hrefs_total": sum(r.n_fig_hrefs for r in results),
        "unmatched_hrefs": sum(len(r.unmatched_hrefs) for r in results),
        "ambiguous_hrefs": sum(len(r.ambiguous_hrefs) for r in results),
        "candidate_images_total": sum(r.n_candidate_images for r in results),
        "unreadable_images": sum(len(r.unreadable_files) for r in results),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="figures.py filter precision/recall sweep")
    parser.add_argument("--corpus-dir", default=str(_DEFAULT_CORPUS),
                        help="Dir of PMC OA packages (one folder per article).")
    parser.add_argument("--note", default="",
                        help="Free-text note recorded in the report header (e.g. corpus provenance).")
    args = parser.parse_args()

    corpus_dir = Path(args.corpus_dir)
    articles = labeling.discover_articles(corpus_dir)
    if not articles:
        print(
            f"[corpus] No PMC OA packages found under {corpus_dir}.\n"
            "         Point me at the PMC corpus dir: "
            "--corpus-dir <path-to-folder-of-OA-packages>\n"
            "         (each article = a folder containing a .nxml + its bundled image files).",
            file=sys.stderr,
        )
        return 1

    results = [labeling.label_article(a) for a in articles]
    findings = _aggregate_findings(results)

    images = [img for r in results for img in r.images]
    positives = [i for i in images if i.label == "positive"]
    negatives = [i for i in images if i.label == "negative"]
    n_pos, n_neg = len(positives), len(negatives)

    # Sweep the grid; pool TP/FP/FN across the whole corpus.
    grid: dict[tuple[int, int], tuple[float, float, float, int, int, int]] = {}
    for md in GRID_MIN_DIM:
        for mb in GRID_MIN_BYTES:
            tp = sum(1 for i in positives if _keep(i.min_dim_px, i.size_bytes, md, mb))
            fp = sum(1 for i in negatives if _keep(i.min_dim_px, i.size_bytes, md, mb))
            fn = n_pos - tp  # dropped positives
            p, r, f1 = _prf(tp, fp, fn)
            grid[(md, mb)] = (p, r, f1, tp, fp, fn)

    default_cell = (_DEFAULT_MIN_DIM, _DEFAULT_MIN_BYTES)
    # Best by F1, tie-broken by recall then fewer false positives.
    best_cell = max(grid, key=lambda k: (grid[k][2], grid[k][1], -grid[k][4]))
    n_best_ties = sum(1 for v in grid.values() if abs(v[2] - grid[best_cell][2]) < 1e-9)

    _print_summary(args, corpus_dir, findings, n_pos, n_neg, grid, default_cell, best_cell)
    _write_report(args, corpus_dir, findings, n_pos, n_neg, grid, default_cell, best_cell, n_best_ties)
    print(f"\n[report] written to {_REPORT_PATH}")
    return 0


def _print_summary(args, corpus_dir, findings, n_pos, n_neg, grid, default_cell, best_cell) -> None:
    dp, dr, df1, *_ = grid[default_cell]
    bp, br, bf1, *_ = grid[best_cell]
    print(f"[corpus] {corpus_dir}  ({findings['articles_total']} articles)")
    if args.note:
        print(f"[note] {args.note}")
    print(f"[labels] positives={n_pos}  negatives={n_neg}  "
          f"(unmatched hrefs={findings['unmatched_hrefs']}, unreadable images={findings['unreadable_images']})")
    print(f"[default {default_cell}]  P={dp:.3f} R={dr:.3f} F1={df1:.3f}")
    print(f"[best    {best_cell}]  P={bp:.3f} R={br:.3f} F1={bf1:.3f}")
    if n_pos == 0:
        print("[WARN] 0 positives mapped — the grid is uninformative (check the corpus/JATS).",
              file=sys.stderr)


def _grid_table(grid, value_idx, default_cell, best_cell) -> list[str]:
    """Markdown table of one metric (value_idx into the cell tuple) across the grid."""
    header = "| min_dim \\ min_bytes | " + " | ".join(str(mb) for mb in GRID_MIN_BYTES) + " |"
    sep = "|" + "---|" * (len(GRID_MIN_BYTES) + 1)
    rows = [header, sep]
    for md in GRID_MIN_DIM:
        cells = []
        for mb in GRID_MIN_BYTES:
            val = grid[(md, mb)][value_idx]
            tag = ""
            if (md, mb) == default_cell:
                tag = " (def)"
            if (md, mb) == best_cell:
                tag += "*"
            cells.append(f"{val:.3f}{tag}")
        rows.append(f"| **{md}** | " + " | ".join(cells) + " |")
    return rows


def _write_report(args, corpus_dir, findings, n_pos, n_neg, grid, default_cell, best_cell, n_ties) -> None:
    dp, dr, df1, dtp, dfp, dfn = grid[default_cell]
    bp, br, bf1, btp, bfp, bfn = grid[best_cell]
    L: list[str] = []
    L.append("# figures.py quality-filter sweep — precision/recall vs PMC/JATS ground truth\n")
    L.append(f"- **Corpus:** `{corpus_dir}` — {findings['articles_total']} articles")
    if args.note:
        L.append(f"- **Note:** {args.note}")
    L.append("- **Filter characterized:** `research/figures.py` `extract_figures` inline predicate "
             "(lines 106 & 116), unchanged. `keep ⟺ min(w,h) ≥ min_dimension AND size_bytes ≥ min_bytes`.")
    L.append(f"- **Current default (imported from figures.py):** min_dimension={_DEFAULT_MIN_DIM}, "
             f"min_bytes={_DEFAULT_MIN_BYTES}")
    L.append("- **Ground truth:** positive = image file matching a `<fig>//<graphic>` xlink:href; "
             "negative = any other package image. **P/R:** kept positive=TP, kept negative=FP, "
             "dropped positive=FN.\n")

    L.append("## Headline\n")
    L.append(f"- **Current default ({default_cell[0]}, {default_cell[1]}):** "
             f"precision **{dp:.3f}**, recall **{dr:.3f}**, F1 **{df1:.3f}** "
             f"(TP={dtp}, FP={dfp}, FN={dfn})")
    L.append(f"- **Best F1 ({best_cell[0]}, {best_cell[1]}):** "
             f"precision **{bp:.3f}**, recall **{br:.3f}**, F1 **{bf1:.3f}** "
             f"(TP={btp}, FP={bfp}, FN={bfn})")
    if best_cell == default_cell:
        L.append("- The current default **is** the best-F1 cell on this corpus.")
    else:
        L.append(f"- ΔF1 vs default: **{bf1 - df1:+.3f}** "
                 f"(ΔP {bp - dp:+.3f}, ΔR {br - dr:+.3f}). "
                 f"{n_ties} cell(s) share the best F1.")
    L.append(f"- Label population: **{n_pos}** positives, **{n_neg}** negatives.\n")

    L.append("## F1 grid (rows = min_dim px, cols = min_bytes; `(def)` = default, `*` = best F1)\n")
    L.extend(_grid_table(grid, 2, default_cell, best_cell))
    L.append("")
    L.append("## Precision grid\n")
    L.extend(_grid_table(grid, 0, default_cell, best_cell))
    L.append("")
    L.append("## Recall grid\n")
    L.extend(_grid_table(grid, 1, default_cell, best_cell))
    L.append("")

    L.append("## Corpus accounting (nothing dropped silently)\n")
    L.append(f"- articles total: **{findings['articles_total']}**")
    L.append(f"- articles with no `.nxml`: **{findings['articles_no_nxml']}**")
    L.append(f"- articles with unparseable `.nxml`: **{findings['articles_xml_unparseable']}**")
    L.append(f"- articles with zero candidate images: **{findings['articles_zero_images']}**")
    L.append(f"- articles with fig hrefs but zero mapped to files: "
             f"**{findings['articles_zero_positives_mapped']}**")
    L.append(f"- `<fig>` graphic hrefs total: **{findings['fig_hrefs_total']}**")
    L.append(f"- unmatched hrefs (declared figure, no on-disk file — excluded from P/R): "
             f"**{findings['unmatched_hrefs']}**")
    L.append(f"- ambiguous hrefs (matched >1 file — excluded from P/R): "
             f"**{findings['ambiguous_hrefs']}**")
    L.append(f"- candidate image files total: **{findings['candidate_images_total']}**")
    L.append(f"- images unreadable by Pillow (excluded from P/R): **{findings['unreadable_images']}**")
    L.append("")
    _REPORT_PATH.write_text("\n".join(L) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
