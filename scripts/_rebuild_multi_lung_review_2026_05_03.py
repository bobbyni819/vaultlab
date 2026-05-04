"""Rebuild multi-lung review-paper-scope deck via Path A.

Review-paper scope = ~14-16 slides covering the 10-section arc structure
condensed into 3 chapter-divider transitions. Each section's keystone
paper gets a figure slide with descriptive title + 3-tier speaker notes
auto-derived from its Tier-A summary.

Output:
  G:/My Drive/Knowledge/vaultlab/Output/Decks/multiscale-tissue-simulation-lung-infection/review-2026-05-03-rebuilt.pptx
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
OUT_DIR = KB / "Output" / "Decks" / "multiscale-tissue-simulation-lung-infection"
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
    layout: str | None = None,
) -> dict:
    record = load_summary(slug)
    if record is None:
        notes = {
            "hook": hook, "key_claim": key_claim,
            "evidence": caption, "key_terms": [],
            "transition": transition, "script": "", "extended_walkthrough": "",
        }
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
    "Pollmächer J, Figge MT. PLoS One 2014;9:e111630.",
    "Agmon E et al. Bioinformatics 2022;38:1972.",
    "Hickey JW et al. Front Immunol 2021;12:727626.",
    "Hickey JW et al. Nature 2023;619:572.",
    "Hickey JW, Agmon E et al. Cell Sys 2024;15:235.",
    "Sorin M et al. Nature 2023;614:548.",
    "Pentimalli TM et al. Cell Syst 2025;16:101261.",
    "Börner K, Hickey JW et al. Nat Methods 2025.",
    "Wong Fok Lung T, Prince A. Cell Metab 2022;34:761.",
    "Blickensdorf M et al. Front Microbiol 2020;11:1951.",
]


def plan() -> dict:
    return {
        "title": "Multiscale tissue simulation for lung infectious disease",
        "subtitle": "A review-paper lineage (2004 → 2026)",
        "topic": "multi-lung-review-2026-05-03",
        "author": "Bobby Y.X. Ni",
        "kb": "vaultlab",
        "theme": "dark",
        "template": "plain",
        "slides": [
            # 1 — Title
            {
                "type": "title",
                "title": "Multiscale tissue simulation for lung infectious disease",
                "subtitle": "A review-paper lineage (2004 → 2026)",
                "author": "Bobby Y.X. Ni",
                "speaker_notes": {
                    "hook": "Where does the field start, and where is it now?",
                    "key_claim": "Three threads — alveolus ABM, multi-engine substrate, and spatial-omics ground truth — converge in 2024 for cancer; the lung-infection translation is the missing piece.",
                    "transition": "Outline first.",
                },
            },

            # 2 — TL;DR / outline
            {
                "type": "text",
                "title": "Three independent maturations bridge to one frontier",
                "bullets": [
                    "Multi-engine integration substrates are mature (Vivarium 2022)",
                    "Alveolus ABMs solved spatial first-passage (2004–2016)",
                    "CODEX/IMC/CosMx deliver single-cell ground truth (2021–2025)",
                    "Cancer integration PROVEN (Hickey/Agmon Cell Sys 2024)",
                    "Lung-infection translation is the obvious + unfilled next cell",
                ],
                "speaker_notes": {
                    "hook": "Quick map before we walk the lineage.",
                    "key_claim": "Each thread matured independently; cancer integration is done; lung-infection is missing.",
                    "transition": "Chapter 1 — theoretical foundations.",
                },
            },

            # 3 — CHAPTER 1 divider
            {"type": "section_divider", "title": "1. Theoretical foundations"},

            # 4 — Vivarium primitives (architectural anchor)
            _fig_slide(
                slug="10.1093_bioinformatics_btac049",
                title="Vivarium composes ABM + FBA + ODE + PDE engines via 5 primitives",
                image_path=_f("10.1093_bioinformatics_btac049"),
                caption="Process / Store / Composite / Compartment / Hierarchy.",
                hook="How do you actually compose engines that disagree on time, space, units?",
                key_claim="Vivarium is a discrete-event composition engine. Processes declare timestep + ports; Topology routes them through Stores; Engine schedules updates atomically.",
                transition="Composition substrate in place. The next problem is spatial dynamics within one engine.",
                layout="figure_only",
            ),

            # 5 — Pollmächer 2014 alveolus ABM
            _fig_slide(
                slug="10.1371_journal.pone.0111630",
                title="Random-walk macrophages can't find an inhaled conidium — chemotaxis is required",
                image_path=_f("10.1371_journal.pone.0111630"),
                caption="3D respiring alveolus, ~120 µm radius; type-I/II AECs (cyan), pores of Kohn (black).",
                bullets=[
                    "PRW: P(FPT > 6h) = 0.68 — too slow",
                    "BPRW with chemotaxis: P(FPT > 6h) < 5%",
                    "AEC-emitted gradient is required",
                ],
                hook="Where does the geometry start to matter?",
                key_claim="Random-walk alveolar macrophages cannot find an inhaled Aspergillus conidium within the 6-hour germination window. AEC chemotaxis is required, not decorative.",
                transition="Geometry within one engine matters; multi-engine composition matters more. Chapter 2 is about validation data.",
            ),

            # 6 — Blickensdorf 2020 (compensation by alveolar architecture)
            _fig_slide(
                slug="10.3389_fmicb.2020.01951",
                title="Pores of Kohn are not required — alveolar architecture compensates",
                image_path=_f("10.3389_fmicb.2020.01951"),
                caption="Hybrid agent-based model of inter-alveolar trafficking with/without pores of Kohn.",
                bullets=[
                    "Inter-alveolar conduits (Pores of Kohn) eliminated in silico",
                    "Macrophage clearance preserved by alveolar geometry",
                    "Robust-by-design — not redundant infrastructure",
                ],
                hook="Do pores of Kohn actually matter for clearance?",
                key_claim="Knocking out pores of Kohn in silico reveals that alveolar architecture compensates — AM cross-alveolar trafficking is robust by design.",
                transition="Theoretical foundations done. Chapter 2 — measurement: how do we get ABM-grade ground truth?",
            ),

            # 7 — CHAPTER 2 divider
            {"type": "section_divider", "title": "2. Measurement → validation substrate"},

            # 8 — Hickey 2021 CODEX recipe
            _fig_slide(
                slug="10.3389_fimmu.2021.727626",
                title="The CODEX recipe: 47 antibodies → ABM-grade single-cell labels",
                image_path=_f("10.3389_fimmu.2021.727626"),
                caption="Antibody panel (top); 4-region tissue imaging; 4-step pipeline.",
                bullets=[
                    "47 DNA-barcoded antibodies, 4 categories",
                    "CellSeg + hand-gating + clustering hybrid",
                    "Spatial verification ensures correct tissue placement",
                ],
                hook="What does it take to turn a 47-plex image into a single-cell table?",
                key_claim="Hickey 2021 is the methodological recipe — single-segmentation, multi-normalisation, hand-gate + cluster hybrid, spatial verification — that's now standard for every CODEX-driven study.",
                transition="With both engines and CODEX in place, the integration becomes possible. The keystone paper proves it.",
            ),

            # 9 — KEYSTONE: Hickey/Agmon 2024 Cell Systems
            # Crop to panel A (the system-of-multiscale-interactions schematic)
            # so just the conceptual diagram dominates the slide; the CODEX
            # and reconstruction panels (B, C) get separate slides.
            {
                **_fig_slide(
                    slug="10.1016_j.cels.2024.03.004",
                    title="CODEX × Vivarium × multiscale ABM — proven for tumour-immune in 2024",
                    image_path=_f("10.1016_j.cels.2024.03.004", "fig2"),
                    caption="System of multiscale interactions: cancer ↔ tissue ↔ intercellular ↔ molecular.",
                    bullets=[
                        "B16-F10 melanoma, 42-antibody CODEX",
                        "Vivarium ABM with PD-L1 + MHC-I + IFNγ",
                        "R²=0.97-0.99 simulation vs in vivo",
                        "T-cell SPATIAL POSITION beats T-cell phenotype",
                    ],
                    hook="Has anyone wired CODEX × Vivarium × ABM end-to-end?",
                    key_claim="Hickey, Agmon et al. 2024 in Cell Systems demonstrate the full deconstruct-reconstruct loop for tumour-immune interactions — the precedent Bobby's lung-infection thesis extends.",
                    transition="Cancer is solved. Chapter 3 — what's the lung-side of the matrix?",
                ),
                "panel": "A",  # crop to top schematic only
                # No caption_position override — let the dispatcher detect
                # the cropped panel's wide-flat aspect (~2.3) and route to
                # figure_top_caption_br automatically (figure on top full
                # width, caption + citation in bottom-right corner).
            },

            # 10 — CHAPTER 3 divider
            {"type": "section_divider", "title": "3. State of the art (2023–2025)"},

            # 11 — Sorin 2023 LUAD spatial neighborhoods
            _fig_slide(
                slug="10.1038_s41586-022-05672-3",
                title="Spatial neighbourhoods, not cell frequencies, predict LUAD survival",
                image_path=_f("10.1038_s41586-022-05672-3", "fig_neighborhoods"),
                caption="Cell-cell co-occurrence matrix of 30 cellular neighbourhoods (CN), permutation-tested.",
                bullets=[
                    "35-plex IMC, 416 LUAD patients, 1.64M cells",
                    "30 cellular neighbourhoods, 10-NN clustering",
                    "ResNet50: 95.9% post-surgical progression accuracy",
                ],
                hook="Does spatial actually beat cell-frequency on a clinical endpoint?",
                key_claim="Cellular neighbourhoods predict post-surgical LUAD progression at 95.9% accuracy. Cell-frequency-only models are dominated.",
                transition="Sorin proves spatial wins in 2D. Pentimalli 2025 then proves 2D itself leaves info on the table.",
            ),

            # 12 — Pentimalli 2025 3D
            _fig_slide(
                slug="10.1016_j.cels.2025.101261",
                title="3D recovers what 2D misses — 2.28× larger neighbourhoods reveal DC niches",
                image_path=_f("10.1016_j.cels.2025.101261"),
                caption="34-section CosMx + SHG-ECM atlas; 114M transcripts, 340k cells, 17 cell types.",
                bullets=[
                    "Z-stack: 34 sections × 16 mm² each",
                    "3D neighbourhoods 2.28× larger than 2D",
                    "DC niches + T-cell continuity 2D-invisible",
                ],
                hook="Does the third dimension actually buy you anything?",
                key_claim="3D neighbourhoods are 2.28× larger than 2D — large enough to contain DC niches and T-cell continuity that single-section analyses miss.",
                transition="3D × spatial × outcome — solved for cancer. The reference geometry came in 2025.",
            ),

            # 13 — HuBMAP Börner 2025 reference geometry
            _fig_slide(
                slug="10.1038_s41592-024-02563-5",
                title="HuBMAP HRA v2.0 supplies the reference geometry for spatial models",
                image_path=_f("10.1038_s41592-024-02563-5"),
                caption="3D Human Reference Atlas: 4,499 anatomical structures, 1,195 cell types, 65 organs.",
                bullets=[
                    "Common Coordinate Framework (CCF) across organs",
                    "Bronchopulmonary-dysplasia VCCF demonstration",
                    "Quantifies perivascular immune-cell aggregation",
                ],
                hook="What's the canonical 3D coordinate frame for tissue models?",
                key_claim="HuBMAP's 3D Human Reference Atlas v2.0 unifies anatomical structures + cell types + biomarkers into a Common Coordinate Framework, with a working bronchopulmonary-dysplasia lung VCCF demonstration.",
                transition="Reference geometry in place. Last piece — host metabolism shapes the immune environment.",
            ),

            # 14 — Wong Fok Lung 2022 Klebsiella metabolism
            _fig_slide(
                slug="10.1016_j.cmet.2022.03.009",
                title="Klebsiella induces host glutaminolysis — metabolism shapes immune tolerance",
                image_path=_f("10.1016_j.cmet.2022.03.009"),
                caption="K. pneumoniae infection drives host glutaminolysis + fatty-acid oxidation in the airway.",
                bullets=[
                    "Host metabolism remodels under bacterial infection",
                    "Glutaminolysis + FAO drive immune tolerance",
                    "Cross-scale (metabolism → immune state → spatial niche)",
                    "Encodable in Vivarium-style multiscale composition",
                ],
                hook="Where does host metabolism fit in the multiscale picture?",
                key_claim="Wong Fok Lung & Prince 2022 add a metabolism dimension — Klebsiella induces host glutaminolysis and fatty-acid oxidation that shape an immune-tolerant microenvironment.",
                transition="The 4-axis matrix is now mature for cancer. The thesis-relevant gap is sharply defined.",
            ),

            # 15 — Take-aways
            {
                "type": "text",
                "title": "Lung infection sits at an empty cell of a now-mature 4-axis matrix",
                "bullets": [
                    "ABM substrate: solved (Vivarium 2022, Pollmächer 2014, Blickensdorf 2020)",
                    "Validation data: solved (CODEX 2021, IMC LUAD 2023, CosMx 3D 2025)",
                    "Reference geometry: solved (HuBMAP HRA 2.0, 2025)",
                    "Cancer integration: PROVEN (Hickey/Agmon Cell Sys 2024)",
                    "Lung-infection translation: the obvious + unfilled next step",
                ],
                "speaker_notes": {
                    "hook": "Where does this leave us?",
                    "key_claim": "The integration is proven for cancer; the lung-infection version is the empty cell of the [organ × disease type × measurement modality × multiscale modelling] matrix.",
                    "transition": "Open for questions.",
                },
            },

            # 16 — References
            {"type": "references", "title": "References", "references": REFS},
        ],
    }


def main() -> int:
    out_path = OUT_DIR / "review-2026-05-04-rebuilt-v6.pptx"
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
    print(f"  severity:  {audit.severity}")
    print(f"  overlap:   {audit.total_overlapping_pairs}")
    print(f"  overflow:  {audit.total_overflowing_shapes}")
    print(f"  offslide:  {audit.total_offslide_shapes}")
    print(f"  bullet>:   {audit.n_over_bulleted_slides}")
    print(f"  long_titles: {audit.n_long_titles}")
    print(f"  fig_gaps:  {audit.figure_gap_slides}")
    print(f"  thin:      {audit.thin_slides}")
    print(f"  imgs:      {audit.n_total_images} / {audit.n_slides} slides")
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
                print(f"    s{s.index} [{s.title[:55]!r}]: {flags}")
        return 2
    print("AUDIT PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
