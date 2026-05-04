"""Rebuild spatial-tx-tme short journal-club deck via Path A.

Uses vaultlab.research.notes_from_summary to auto-derive 3-tier speaker
notes from Tier-A summaries (with overrides where useful) and the auto-
layout dispatcher in build_from_plan.

Output:
  G:/My Drive/Knowledge/vaultlab/Output/Decks/spatial-tx-tme/short-2026-05-03-rebuilt.pptx
"""

from __future__ import annotations

import io
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from vaultlab.research.notes_from_summary import (
    load_summary,
    speaker_notes_from_summary,
)
from vaultlab.slides.audit import audit_deck
from vaultlab.slides.deck import build_from_plan

KB = Path("G:/My Drive/Knowledge/vaultlab")
FIG_CACHE = Path("C:/Users/bobby/.cache/vaultlab/_deck_figures_2026_05_03")
OUT_DIR = KB / "Output" / "Decks" / "spatial-tx-tme"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def _f(slug: str, fig: str = "fig1") -> str:
    return str(FIG_CACHE / f"{slug}_{fig}.png")


def _fig_slide(
    *,
    slug: str,
    title: str,
    image_path: str,
    caption: str,
    bullets: list[str] | None = None,
    hook: str = "",
    key_claim: str = "",
    transition: str = "",
    audience_familiar: bool = False,
) -> dict:
    """Build a figure slide with auto-extracted 3-tier speaker notes."""
    record = load_summary(slug)
    if record is None:
        # Fallback if summary missing
        notes = {
            "hook": hook, "key_claim": key_claim,
            "evidence": caption, "key_terms": [],
            "transition": transition, "script": "", "extended_walkthrough": "",
        }
        citation = ""
    else:
        notes = speaker_notes_from_summary(
            record,
            hook=hook,
            key_claim=key_claim,
            transition=transition,
            audience_familiar=audience_familiar,
        )
        citation = record.citation_footer()
    return {
        "type": "figure",
        "title": title,
        "image_path": image_path,
        "caption": caption,
        "citation_source": citation,
        "bullets": bullets or [],
        "speaker_notes": notes,
    }


def plan() -> dict:
    return {
        "title": "Spatial transcriptomics of the tumor microenvironment",
        "subtitle": "A short lineage (2020 → 2025)",
        "topic": "spatial-tx-tme-short-2026-05-03",
        "author": "Bobby Y.X. Ni",
        "kb": "vaultlab",
        "theme": "dark",
        "template": "plain",
        "slides": [
            # 1 — Title
            {
                "type": "title",
                "title": "Spatial transcriptomics of the tumor microenvironment",
                "subtitle": "A short lineage (2020 → 2025)",
                "author": "Bobby Y.X. Ni",
                "speaker_notes": {
                    "hook": "How did spatial methods become the dominant TME phenotyping primitive?",
                    "key_claim": "Three threads — anchored ST, multiplexed protein imaging, and 3D × outcome — converge into clinical-scale TME atlases.",
                    "transition": "Outline first.",
                },
            },

            # 2 — Outline
            {
                "type": "text",
                "title": "From 'put transcripts on tissue' to 'use the niches as biomarkers'",
                "bullets": [
                    "2016–2021: Visium + CODEX/IMC make spatial-TME tractable",
                    "2022–2023: atlases find recurring niches — CAFs, edge states",
                    "2024–2026: scale, 3D, and clinical translation",
                    "Spatial cell-cell interactions beat cell frequencies for outcome",
                    "3D recovers what 2D misses",
                ],
                "speaker_notes": {
                    "hook": "Quick map before we walk the 5 papers.",
                    "key_claim": "The arc runs from anchored ST through atlas-scale niche discovery to outcome prediction at cohort scale.",
                    "transition": "Paper 1 — Phillips 2020 CTCL CODEX.",
                    "script": (
                        "The story has three phases. The first is methodology: between 2016 and "
                        "2021, the Ståhl-Lundeberg array-capture method and its commercialisation "
                        "as 10x Visium gave the field a barcoded grid that anchored transcripts "
                        "back to histology. In parallel, multiplexed protein imaging — CODEX, IMC, "
                        "MIBI — let ~40-plex panels in situ define cellular neighbourhoods. The "
                        "second phase, 2022-2023, was atlas-scale work that found the recurring "
                        "biological motifs: tumour-edge states, CAF subtypes, immune-exclusion "
                        "barriers. The third phase, 2024-2026, is what we're living through: scale "
                        "(thousand-patient cohorts), 3D (CosMx z-stacks), and clinical translation "
                        "(spatial biomarkers driving therapy choice). The two key lessons are: "
                        "first, spatial cell-cell INTERACTIONS predict survival better than cell "
                        "FREQUENCIES; second, 3D neighbourhoods are 2.28× larger than 2D and "
                        "contain structures that 2D loses entirely. Today's deck walks five papers "
                        "that establish each step of the arc."
                    ),
                },
            },

            # 3 — Phillips 2020 CTCL CODEX
            _fig_slide(
                slug="10.1101_2020.12.06.20244913",
                title="CODEX: immune-cell topography predicts PD-1 response in CTCL",
                image_path=_f("10.1101_2020.12.06.20244913"),
                caption="55-marker CODEX on pre/post-PD-1 CTCL biopsies; reactive vs malignant CD4+ T discrimination.",
                bullets=[
                    "55-marker CODEX, pre/post-PD-1, n=14",
                    "Topography (where) > abundance (how many)",
                    "Reactive vs malignant CD4+ separable",
                    "Cohort precursor for Phillips 2024 Nat Commun",
                ],
                hook="Why do some CTCL patients respond to PD-1 blockade and others don't?",
                key_claim="CODEX shows that immune-cell topography — where reactive CD4+ T cells sit relative to malignant cells — discriminates responders from non-responders.",
                transition="Phillips proves CODEX can find the answer. Hickey 2021 supplies the recipe.",
            ),

            # 4 — Hickey 2021 CODEX strategies (cross-deck reuse)
            _fig_slide(
                slug="10.3389_fimmu.2021.727626",
                title="The CODEX recipe: 47 antibodies → ABM-grade single-cell labels",
                image_path=_f("10.3389_fimmu.2021.727626"),
                caption="DNA-barcoded antibody panel (top); 4-region tissue imaging; 4-step pipeline.",
                bullets=[
                    "4 healthy colon FFPE × 47 antibodies",
                    "CellSeg U-Net + hand-gating + clustering hybrid",
                    "Spatial verification: clusters land in right tissue",
                ],
                hook="What does it actually take to turn a 47-plex image into a single-cell table?",
                key_claim="Hickey 2021 is the methodological recipe — single-segmentation, multi-normalisation, hand-gate + cluster hybrid, spatial verification — that's now standard for every CODEX-driven TME study.",
                transition="Methodology in place; the field then went atlas-scale on tumours. Qi/Liu 2022 shows what the atlas finds.",
            ),

            # 5 — Qi/Liu 2022 CRC CAF FAP+/SPP1+ axis
            _fig_slide(
                slug="10.1038_s41467-022-29366-6",
                title="Spatial validates a paired FAP+ CAF–SPP1+ macrophage axis in CRC",
                image_path=_f("10.1038_s41467-022-29366-6"),
                caption="54k cells, scRNA + ST in paired CRC + adjacent normal; FAP+ CAFs + SPP1+ macrophages co-localize.",
                bullets=[
                    "scRNA: 54k cells, paired tumor + normal CRC",
                    "Spatial: FAP+ CAFs + SPP1+ Mφ form niche",
                    "Multi-cohort validation across 5 datasets",
                    "Niche correlates with worse immunotherapy response",
                ],
                hook="What recurring spatial motifs predict immunotherapy resistance?",
                key_claim="Qi/Liu 2022 used scRNA + ST in colorectal cancer to validate that FAP+ CAFs and SPP1+ macrophages co-localize as a paired stromal-immune niche, and that this niche correlates with immunotherapy resistance across multiple cohorts.",
                transition="The CAF-macrophage niche is the recurring motif. Sorin 2023 then asks: do these niches predict outcome at cohort scale?",
            ),

            # 6 — Sorin 2023 LUAD IMC (cross-deck reuse with multi-lung short)
            _fig_slide(
                slug="10.1038_s41586-022-05672-3",
                title="Spatial neighbourhoods, not cell frequencies, predict LUAD survival",
                image_path=_f("10.1038_s41586-022-05672-3", "fig_neighborhoods"),
                caption="Cell-cell co-occurrence matrix of 30 cellular neighbourhoods (CN), permutation-tested.",
                bullets=[
                    "35-plex IMC, 416 LUAD patients, 1.64M cells",
                    "30 cellular neighbourhoods (10-NN clustering)",
                    "ResNet50 raw IMC: 95.9% progression accuracy",
                    "External validation: 93.3% on 60 patients",
                ],
                hook="Does spatial actually beat cell-frequency on a clinical endpoint?",
                key_claim="Cellular neighbourhoods — 10-nearest-neighbour windows — predict post-surgical LUAD progression at 95.9% accuracy. Cell-frequency-only models are dominated.",
                transition="Sorin proves spatial wins in 2D. Pentimalli 2025 then proves 2D itself leaves information on the table.",
            ),

            # 7 — Pentimalli 2025 3D NSCLC
            _fig_slide(
                slug="10.1016_j.cels.2025.101261",
                title="3D recovers what 2D misses — 2.28× larger neighbourhoods, DC niches revealed",
                image_path=_f("10.1016_j.cels.2025.101261"),
                caption="34-section CosMx + SHG-ECM atlas; 114M transcripts, 340k cells, 17 cell types.",
                bullets=[
                    "Z-stack: 34 sections × 16 mm² each",
                    "3D neighbourhoods 2.28× larger than 2D",
                    "DC niches + T-cell continuity 2D-invisible",
                    "ECM (SHG) co-imaged in same coords",
                ],
                hook="Does the third dimension actually buy you anything?",
                key_claim="3D neighbourhoods are 2.28× larger than 2D — large enough to contain DC niches and T-cell continuity that single-section analyses miss entirely.",
                transition="We have anchored ST, atlas-scale niches, and 3D × outcome. The arc closes.",
            ),

            # 8 — Take-aways
            {
                "type": "text",
                "title": "Spatial-TME has matured from descriptive to clinically predictive",
                "bullets": [
                    "Method: anchored ST + 47-plex CODEX/IMC are routine",
                    "Niches: FAP+ CAF / SPP1+ Mφ axis is recurring",
                    "Frequencies are dominated by neighbourhoods for outcome",
                    "3D is now feasible; 2.28× more cells per CN",
                    "Next gap: spatial-time-perturbation (response trajectories)",
                ],
                "speaker_notes": {
                    "hook": "What does this leave us with?",
                    "key_claim": "Spatial-TME has matured from descriptive to clinically predictive in five years. The remaining gap is temporal — how do these niches respond under therapy over time?",
                    "transition": "Open for questions.",
                },
            },

            # 9 — References
            {
                "type": "references",
                "title": "References",
                "references": [
                    "Phillips D et al. medRxiv 2020.12.06.20244913.",
                    "Hickey JW et al. Front Immunol 2021;12:727626.",
                    "Qi J, Liu W et al. Nat Commun 2022;13:1742.",
                    "Sorin M et al. Nature 2023;614:548.",
                    "Pentimalli TM et al. Cell Syst 2025;16:101261.",
                    "Andersson A et al. Nat Biotechnol 2020;38:333.",
                    "Hickey JW et al. Nature 2023;619:572.",
                ],
            },
        ],
    }


def main() -> int:
    out_path = OUT_DIR / "short-2026-05-04-rebuilt-v6.pptx"
    print(f"Building {out_path.name} ...")
    plan_dict = plan()

    # Verify all figures exist
    missing = [s["image_path"] for s in plan_dict["slides"]
               if s.get("image_path") and not Path(s["image_path"]).exists()]
    if missing:
        print("MISSING figures:")
        for m in missing:
            print(f"  - {m}")
        return 1

    result = build_from_plan(
        plan_dict, out_path, write_marp=False, with_animations=True,
    )
    print(f"  built: {result['pptx']}  ({result['pptx'].stat().st_size:,} bytes)")

    audit = audit_deck(out_path)
    print(f"  severity:               {audit.severity}")
    print(f"  overlap_pairs:          {audit.total_overlapping_pairs}")
    print(f"  overflow_shapes:        {audit.total_overflowing_shapes}")
    print(f"  offslide_shapes:        {audit.total_offslide_shapes}")
    print(f"  over_bulleted_slides:   {audit.n_over_bulleted_slides}")
    print(f"  long_titles:            {audit.n_long_titles}")
    print(f"  figure_gap_slides:      {audit.figure_gap_slides}")
    print(f"  thin_slides:            {audit.thin_slides}")
    print(f"  n_total_images:         {audit.n_total_images} / {audit.n_slides} slides")
    if audit.severity == "fail":
        print("AUDIT FAILED")
        for s in audit.per_slide:
            flags = []
            if s.text_overflow_shapes: flags.append(f"overflow={s.text_overflow_shapes}")
            if s.offslide_shapes: flags.append(f"offslide={s.offslide_shapes}")
            if s.overlapping_shapes: flags.append(f"overlap={s.overlapping_shapes}")
            if s.title_too_long: flags.append("long_title")
            if s.over_bulleted: flags.append("over_bulleted")
            if flags:
                print(f"    slide {s.index} [{s.title[:55]!r}]: {flags}")
        return 2
    print("AUDIT PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
