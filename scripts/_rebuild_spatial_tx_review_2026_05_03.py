"""Rebuild spatial-tx-tme review-paper-scope deck via Path A.

13 slides covering the 3-chapter arc (methodology → atlas-scale niches →
SOTA + integration). Uses notes_from_summary auto-extraction +
auto-layout dispatcher.

Output:
  G:/My Drive/Knowledge/vaultlab/Output/Decks/spatial-tx-tme/review-2026-05-03-rebuilt.pptx
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


def _fig_slide(*, slug, title, image_path, caption, bullets=None,
               hook="", key_claim="", transition="",
               audience_familiar=False, layout=None):
    record = load_summary(slug)
    if record is None:
        notes = {"hook": hook, "key_claim": key_claim, "evidence": caption,
                 "key_terms": [], "transition": transition,
                 "script": "", "extended_walkthrough": ""}
        citation = ""
    else:
        notes = speaker_notes_from_summary(
            record, hook=hook, key_claim=key_claim, transition=transition,
            audience_familiar=audience_familiar,
        )
        citation = record.citation_footer()
    spec = {
        "type": "figure",
        "title": title,
        "image_path": image_path,
        "caption": caption,
        "citation_source": citation,
        "bullets": bullets or [],
        "speaker_notes": notes,
    }
    if layout:
        spec["layout"] = layout
    return spec


REFS = [
    "Phillips D et al. medRxiv 2020.12.06.20244913.",
    "Hickey JW et al. Front Immunol 2021;12:727626.",
    "Qi J, Liu W et al. Nat Commun 2022;13:1742.",
    "Sorin M et al. Nature 2023;614:548.",
    "Pentimalli TM et al. Cell Syst 2025;16:101261.",
    "Hickey JW, Agmon E et al. Cell Sys 2024;15:235.",
    "Andersson A et al. Nat Biotechnol 2020;38:333.",
]


def plan() -> dict:
    return {
        "title": "Spatial transcriptomics of the tumor microenvironment",
        "subtitle": "A review-paper lineage (2020 → 2026)",
        "topic": "spatial-tx-tme-review-2026-05-03",
        "author": "Bobby Y.X. Ni",
        "kb": "vaultlab",
        "theme": "dark",
        "template": "plain",
        "slides": [
            # 1 — Title
            {
                "type": "title",
                "title": "Spatial transcriptomics of the tumor microenvironment",
                "subtitle": "A review-paper lineage (2020 → 2026)",
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
                "title": "From 'transcripts on tissue' to 'niches as biomarkers' to '3D × outcome'",
                "bullets": [
                    "Methodology: Visium + 47-plex CODEX/IMC tractable (2016–2021)",
                    "Atlases: recurring niches found — CAFs, edge states (2022–2023)",
                    "Scale + 3D + clinical translation (2024–2026)",
                    "Spatial cell-cell INTERACTIONS beat cell FREQUENCIES",
                    "3D recovers what 2D misses — 2.28× larger neighbourhoods",
                ],
                "speaker_notes": {
                    "hook": "Quick map before we walk the lineage.",
                    "key_claim": "The arc runs from anchored ST through atlas-scale niche discovery to outcome prediction at cohort scale.",
                    "transition": "Chapter 1 — methodology.",
                },
            },

            # 3 — CHAPTER 1
            {"type": "section_divider", "title": "1. Methodology (2016–2021)"},

            # 4 — Phillips 2020
            _fig_slide(
                slug="10.1101_2020.12.06.20244913",
                title="CODEX: immune-cell topography predicts PD-1 response in CTCL",
                image_path=_f("10.1101_2020.12.06.20244913"),
                caption="55-marker CODEX on pre/post-PD-1 CTCL biopsies; reactive vs malignant CD4+ T discrimination.",
                bullets=[
                    "55-marker CODEX, pre/post-PD-1, n=14",
                    "Topography (where) > abundance (how many)",
                    "Reactive vs malignant CD4+ separable",
                ],
                hook="Why do some CTCL patients respond to PD-1 blockade and others don't?",
                key_claim="CODEX shows immune-cell topography — where reactive CD4+ T cells sit relative to malignant cells — discriminates responders.",
                transition="Phillips proves CODEX can find the answer. Hickey 2021 supplies the methodological recipe.",
            ),

            # 5 — Hickey 2021
            _fig_slide(
                slug="10.3389_fimmu.2021.727626",
                title="The CODEX recipe: 47 antibodies → ABM-grade single-cell labels",
                image_path=_f("10.3389_fimmu.2021.727626"),
                caption="Antibody panel; 4-region tissue imaging; 4-step pipeline.",
                bullets=[
                    "47 DNA-barcoded antibodies, 4 categories",
                    "CellSeg + hand-gating + clustering hybrid",
                    "Spatial verification ensures correct tissue placement",
                ],
                hook="What does it take to turn a 47-plex image into a single-cell table?",
                key_claim="Hickey 2021 is the methodological recipe — single-segmentation, multi-normalisation, hand-gate + cluster hybrid, spatial verification — that's now standard for every CODEX-driven TME study.",
                transition="Methodology in place. Chapter 2 — what does the atlas find?",
            ),

            # 6 — CHAPTER 2
            {"type": "section_divider", "title": "2. Atlas-scale niches (2022–2023)"},

            # 7 — Qi/Liu 2022 CAF axis
            _fig_slide(
                slug="10.1038_s41467-022-29366-6",
                title="Spatial validates a paired FAP+ CAF–SPP1+ macrophage axis in CRC",
                image_path=_f("10.1038_s41467-022-29366-6"),
                caption="54k cells, scRNA + ST in paired CRC + adjacent normal; FAP+ CAFs co-localize with SPP1+ Mφ.",
                bullets=[
                    "scRNA: 54k cells, paired tumor + normal CRC",
                    "Spatial: FAP+ CAFs + SPP1+ Mφ form niche",
                    "Validated across 5 cohorts",
                    "Niche correlates with worse immunotherapy response",
                ],
                hook="What recurring spatial motifs predict immunotherapy resistance?",
                key_claim="Qi/Liu 2022 used scRNA + ST to validate that FAP+ CAFs and SPP1+ macrophages co-localize as a paired stromal-immune niche correlated with immunotherapy resistance.",
                transition="One specific niche found. Sorin 2023 then asks: do niches predict outcome at cohort scale?",
            ),

            # 8 — Sorin 2023
            _fig_slide(
                slug="10.1038_s41586-022-05672-3",
                title="Spatial neighbourhoods, not cell frequencies, predict LUAD survival",
                image_path=_f("10.1038_s41586-022-05672-3", "fig_neighborhoods"),
                caption="Cell-cell co-occurrence matrix of 30 cellular neighbourhoods (CN), permutation-tested.",
                bullets=[
                    "35-plex IMC, 416 LUAD patients, 1.64M cells",
                    "30 cellular neighbourhoods (10-NN clustering)",
                    "ResNet50 raw IMC: 95.9% progression accuracy",
                    "External validation: 93.3%",
                ],
                hook="Does spatial actually beat cell-frequency on a clinical endpoint?",
                key_claim="Cellular neighbourhoods predict post-surgical LUAD progression at 95.9% accuracy. Cell-frequency-only models are dominated.",
                transition="Spatial wins in 2D. Chapter 3 — does 3D extend the win?",
            ),

            # 9 — CHAPTER 3
            {"type": "section_divider", "title": "3. SOTA — 3D, integration, clinical translation"},

            # 10 — Pentimalli 2025 fig3 (2D vs 3D direct comparison)
            _fig_slide(
                slug="10.1016_j.cels.2025.101261",
                title="3D recovers what 2D misses — 2.28× larger neighbourhoods, DC niches in 3D",
                image_path=_f("10.1016_j.cels.2025.101261", "fig3"),
                caption="2D vs 3D cellular neighbourhoods: 3D has 2.28× more cells, 1.5× more cell types, higher α-diversity.",
                bullets=[
                    "2D vs 3D direct comparison (top row, p<0.0001)",
                    "T-cell niche continuity visible only in 3D (E)",
                    "Tumour core / surface / DC / Mφ niches in 3D (F)",
                    "ECM (SHG) co-imaged in same coords",
                ],
                hook="Does the third dimension actually buy you anything?",
                key_claim="3D neighbourhoods are 2.28× larger than 2D and recover DC niches + T-cell continuity that single-section 2D analyses systematically miss.",
                transition="Spatial-TME is now mature for cancer. The integration with multiscale modelling closes the loop.",
            ),

            # 11 — Hickey/Agmon 2024 Cell Systems keystone
            _fig_slide(
                slug="10.1016_j.cels.2024.03.004",
                title="Spatial-TME × multiscale ABM — proven for tumour-immune in 2024",
                image_path=_f("10.1016_j.cels.2024.03.004", "fig2"),
                caption="Deconstruct (CODEX) → reconstruct (Vivarium ABM); IFNγ-induced PD-L1+ phenotype switch.",
                bullets=[
                    "B16-F10 melanoma, 42-antibody CODEX",
                    "Vivarium ABM with PD-L1 + MHC-I + IFNγ",
                    "R²=0.97-0.99 simulation vs in vivo",
                    "Spatial position of T cells > T-cell phenotype",
                ],
                hook="Has anyone wired spatial-TME × multiscale modelling end-to-end?",
                key_claim="Hickey, Agmon et al. 2024 Cell Systems demonstrate the full deconstruct-reconstruct loop for tumour-immune interactions — the blueprint for any spatial × ABM project.",
                transition="The arc closes. Spatial-TME has graduated to a clinically predictive multiscale-modelling discipline.",
            ),

            # 12 — Take-aways
            {
                "type": "text",
                "title": "Spatial-TME has matured from descriptive to clinically predictive",
                "bullets": [
                    "Methodology: Visium + 47-plex CODEX/IMC are routine",
                    "Niches: FAP+ CAF / SPP1+ Mφ axis is recurring across cancers",
                    "Frequencies are dominated by neighbourhoods for outcome",
                    "3D is feasible at clinical scale; 2.28× more cells per CN",
                    "Multiscale integration is proven for cancer (Hickey/Agmon 2024)",
                ],
                "speaker_notes": {
                    "hook": "What does this leave us with?",
                    "key_claim": "Spatial-TME has matured from descriptive to clinically predictive in five years. The remaining frontier is temporal — how do these niches evolve under therapy?",
                    "transition": "Open for questions.",
                },
            },

            # 13 — References
            {"type": "references", "title": "References", "references": REFS},
        ],
    }


def main() -> int:
    out_path = OUT_DIR / "review-2026-05-04-rebuilt-v5.pptx"
    print(f"Building {out_path.name} ...")
    plan_dict = plan()

    missing = [s["image_path"] for s in plan_dict["slides"]
               if s.get("image_path") and not Path(s["image_path"]).exists()]
    if missing:
        print("MISSING figures:")
        for m in missing:
            print(f"  - {m}")
        return 1

    result = build_from_plan(plan_dict, out_path, write_marp=False, with_animations=True)
    print(f"  built: {result['pptx']}  ({result['pptx'].stat().st_size:,} bytes)")

    audit = audit_deck(out_path)
    print(f"  severity: {audit.severity}  overlap={audit.total_overlapping_pairs}  "
          f"overflow={audit.total_overflowing_shapes}  offslide={audit.total_offslide_shapes}  "
          f"thin={audit.thin_slides}  fig_gaps={audit.figure_gap_slides}  "
          f"imgs={audit.n_total_images}/{audit.n_slides}")
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
                print(f"    s{s.index}: {flags}")
        return 2
    print("AUDIT PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
