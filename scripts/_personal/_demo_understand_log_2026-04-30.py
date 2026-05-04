"""Smoke-demo: run the figure-understanding pipeline on a real CODEX-corpus
figure and write a sample ``<fig-id>.understand.md`` log to the canonical KB
path.

Used once to produce a sample log for Bobby (Finding 9 verification). The
LLM steps are stubbed with deterministic Python — the *plumbing* is what
this demo proves end-to-end on real cached figures, not a real LLM trace.
"""

from __future__ import annotations

from pathlib import Path

from vaultlab.figures.understand import (
    ColorMotif,
    VerificationIteration,
    save_understand_log,
    understand_figure,
)


KB_ROOT = Path("G:/My Drive/Knowledge/vaultlab")
CORPUS_DIR = (
    KB_ROOT
    / "Output"
    / "codex-multiplexed-imaging-methods-and-applications-across-tissue-types-evening3-rerun"
    / "figures"
    / "10.1016_j.cell.2018.07.010"
)
DOI = "10.1016/j.cell.2018.07.010"
FIG_NAME = "gr1.jpg"


def describe(_path: Path) -> str:
    return (
        "Multiplexed CODEX immunofluorescence panel: large central tile is a colored "
        "tissue micrograph; smaller flanking sub-panels show single-channel insets "
        "with bright fluorescent foci on dark backgrounds. The dominant chromatic "
        "motifs are saturated greens (signal), magenta/red counterstains, and high-value "
        "white labels overlaid onto the imagery."
    )


def match(description: str, regions):
    """Stub matcher: pair each detected region with a plausible element name.

    This is illustrative — production wiring will route through an Anthropic
    multimodal call and do real semantic pairing.
    """
    out: list[dict] = []
    for i, r in enumerate(regions[:5]):  # cap at 5 so the log stays readable
        if "green" in r.motif_name.lower():
            elem = f"green-channel signal cluster #{i + 1}"
        elif "blue" in r.motif_name.lower() or "cyan" in r.motif_name.lower():
            elem = f"counterstain region #{i + 1}"
        elif "magenta" in r.motif_name.lower() or "red" in r.motif_name.lower():
            elem = f"red-channel marker #{i + 1}"
        else:
            elem = f"element #{i + 1}"
        out.append(
            {
                "element_name": elem,
                "matched_region_id": f"r{i}",
                "rationale": (
                    f"largest {r.motif_name} blob in the figure; bbox area "
                    f"{(r.bbox_px[2] - r.bbox_px[0]) * (r.bbox_px[3] - r.bbox_px[1])} px"
                ),
                "confidence": 0.65 + 0.05 * (5 - i),
            }
        )
    return out


def verify(_png: Path, anns, iteration: int) -> VerificationIteration:
    if iteration == 1:
        return VerificationIteration(
            iteration=1,
            annotated_image_read=(
                "Overlay boxes land on the brightest fluorescent foci, but the "
                "first marker overlaps a sub-panel label rather than the signal "
                "cluster underneath. The remaining markers look correctly placed."
            ),
            issues_found=[
                "marker #1 collides with sub-panel 'A' text label",
                "marker #2 sits slightly above its targeted region",
            ],
            decision="RETRY_MATCH",
        )
    return VerificationIteration(
        iteration=iteration,
        annotated_image_read=(
            f"Pass {iteration}: every annotation now sits on its named element with "
            "no text-label collisions. Bounding boxes hug the green and magenta "
            "fluorescent clusters cleanly."
        ),
        issues_found=[],
        decision="ACCEPT",
    )


def main() -> None:
    figure_path = CORPUS_DIR / FIG_NAME
    if not figure_path.exists():
        raise SystemExit(f"figure not found: {figure_path}")

    motifs = [
        ColorMotif("green", (90, 145), 0.30, 0.30, 0.0001),
        ColorMotif("magenta", (290, 340), 0.30, 0.30, 0.0001),
        ColorMotif("blue", (200, 250), 0.30, 0.30, 0.0001),
    ]

    annotations, log = understand_figure(
        figure_path,
        motifs,
        doi=DOI,
        figure_id=FIG_NAME,
        annotated_png_path=str(figure_path.with_suffix(".annotated.png")),
        describe_fn=describe,
        match_fn=match,
        verify_fn=verify,
    )

    out_path = save_understand_log(log, KB_ROOT)
    print(f"wrote: {out_path}")
    print(f"final_state: {log.final_state}")
    print(f"n_iterations: {log.n_iterations}")
    print(f"#regions: {len(log.step2_regions)}")
    print(f"#matches: {len(log.step3_matches)}")
    print(f"#annotations: {len(annotations)}")


if __name__ == "__main__":
    main()
