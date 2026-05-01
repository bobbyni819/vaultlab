"""Re-run PDF acquisition on the existing CODEX corpus with VPN on.

No code changes to the pipeline. Pure diagnostic to measure acquire-rate
improvement now that Duke VPN auth is working through Elsevier.

Reads DOIs from `dois.json`, runs `acquire_pdf` on each (with all configured
API keys), writes per-DOI results to `acquisition-trace.json`, prints a
running progress + final summary.
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from vaultlab.research.acquisition import acquire_pdf


def main() -> int:
    output_dir = Path("G:/My Drive/Knowledge/vaultlab/Output/_pdf-reacquire-2026-05-01")
    cache_dir = output_dir / "pdfs"
    cache_dir.mkdir(parents=True, exist_ok=True)

    dois_path = output_dir / "dois.json"
    dois = json.loads(dois_path.read_text(encoding="utf-8"))

    api_config_path = Path(
        os.path.expanduser("~/AppData/Local")
    )  # placeholder
    real_path = Path("G:/My Drive/Knowledge/tools/.config/research_apis.json")
    cfg = json.loads(real_path.read_text(encoding="utf-8"))
    apis = {
        "elsevier_key": cfg.get("elsevier_key", ""),
        "springer_open_access_api_key": cfg.get("springer_open_access_api_key", ""),
    }

    print(f"PDF re-acquisition on {len(dois)} CODEX DOIs (VPN on)")
    print(f"Cache dir: {cache_dir}")
    print("=" * 90)

    results: list[dict] = []
    started = time.time()

    for i, doi in enumerate(dois, 1):
        t0 = time.time()
        try:
            r = acquire_pdf(doi, cache_dir=cache_dir, apis=apis)
            succeeded = r.source != "failed" and r.pdf_path is not None
            entry = {
                "doi": doi,
                "succeeded": succeeded,
                "source": r.source,
                "tried": list(r.tried),
                "tier_errors": dict(r.tier_errors),
                "license": r.license,
                "wall_time_ms": int((time.time() - t0) * 1000),
                "size_bytes": r.pdf_path.stat().st_size if (succeeded and r.pdf_path) else 0,
            }
        except Exception as e:  # noqa: BLE001
            entry = {
                "doi": doi,
                "succeeded": False,
                "source": "exception",
                "tried": [],
                "tier_errors": {"exception": str(e)[:200]},
                "license": None,
                "wall_time_ms": int((time.time() - t0) * 1000),
                "size_bytes": 0,
            }

        results.append(entry)

        # Live progress
        ok_so_far = sum(1 for r in results if r["succeeded"])
        if entry["succeeded"]:
            kb = entry["size_bytes"] / 1024
            print(
                f"[{i:>3}/{len(dois)}] OK   {entry['source']:>10} {kb:>7.0f} KB  "
                f"(running: {ok_so_far}/{i} = {100*ok_so_far/i:.0f}%)  {doi}"
            )
        else:
            tried = " -> ".join(entry["tried"]) if entry["tried"] else "—"
            print(
                f"[{i:>3}/{len(dois)}] FAIL [{tried}]  "
                f"(running: {ok_so_far}/{i} = {100*ok_so_far/i:.0f}%)  {doi}"
            )

        # Save trace incrementally so we can recover if interrupted
        if i % 10 == 0:
            (output_dir / "acquisition-trace.json").write_text(
                json.dumps(results, indent=2), encoding="utf-8"
            )

    # Final write
    (output_dir / "acquisition-trace.json").write_text(
        json.dumps(results, indent=2), encoding="utf-8"
    )

    elapsed = time.time() - started
    ok = [r for r in results if r["succeeded"]]
    by_source: dict[str, int] = {}
    for r in ok:
        by_source[r["source"]] = by_source.get(r["source"], 0) + 1

    print("=" * 90)
    print(
        f"FINAL: {len(ok)}/{len(results)} acquired "
        f"({100*len(ok)//len(results)}%)  in {elapsed/60:.1f} min"
    )
    print(f"Per-tier wins: {by_source}")
    print(f"Total bytes: {sum(r['size_bytes'] for r in ok) / 1024 / 1024:.1f} MB")
    print(f"Trace saved: {output_dir / 'acquisition-trace.json'}")

    # Summary file
    (output_dir / "summary.json").write_text(
        json.dumps(
            {
                "total_dois": len(results),
                "succeeded": len(ok),
                "succeeded_pct": round(100 * len(ok) / len(results), 1),
                "by_tier": by_source,
                "total_bytes": sum(r["size_bytes"] for r in ok),
                "wall_time_min": round(elapsed / 60, 2),
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())
