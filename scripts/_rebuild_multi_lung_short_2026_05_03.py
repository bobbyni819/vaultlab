"""Rebuild multi-lung short journal-club deck via Path A — Claude as the brain.

Per Bobby's 2026-05-03 ask: stop post-populating text-only decks. Generate
figure slides directly via build_from_plan with descriptive sentence titles,
THREE-tier speaker notes (mental_map + script + extended_walkthrough), and
figure annotations. CAR-T 30-min deck (advisor-package-2026-04-30) is the
gold standard reference.

Tier breakdown:
- mental_map     — keywords for fluent presenter
- script         — 200-400 word monologue (the "say-this" version)
- extended_walkthrough — 600-900 word concept walkthrough, background, jargon
                   definitions, why it matters; for presenters new to topic

This script writes the deck-plan dict authored by Claude in this session.
No separate LLM API call.

Output: G:/My Drive/Knowledge/vaultlab/Output/Decks/multiscale-tissue-simulation-lung-infection/short-2026-05-03-rebuilt.pptx
"""

from __future__ import annotations

import sys
from pathlib import Path

import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from vaultlab.slides.deck import build_from_plan
from vaultlab.slides.audit import audit_deck

KB = Path("G:/My Drive/Knowledge/vaultlab")
FIG_CACHE = Path("C:/Users/bobby/.cache/vaultlab/_deck_figures_2026_05_03")
OUT_DIR = KB / "Output" / "Decks" / "multiscale-tissue-simulation-lung-infection"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def _f(slug: str, fig: str = "fig1") -> str:
    return str(FIG_CACHE / f"{slug}_{fig}.png")


CITE = {
    "pollmacher_2014": "Pollmächer & Figge, PLoS One 2014;9(11):e111630",
    "vivarium_2022":   "Agmon et al., Bioinformatics 2022;38(6):1972",
    "hickey_2021":     "Hickey et al., Front Immunol 2021;12:727626",
    "sorin_2023":      "Sorin et al., Nature 2023;614:548",
    "pentimalli_2025": "Pentimalli & Rajewsky, Cell Systems 2025;16:101261",
}


REFS = [
    "Pollmächer J, Figge MT. PLoS One 2014;9:e111630.",
    "Agmon E et al. Bioinformatics 2022;38:1972.",
    "Hickey JW et al. Front Immunol 2021;12:727626.",
    "Hickey JW et al. Nature 2023;619:572.",
    "Sorin M et al. Nature 2023;614:548.",
    "Pentimalli TM et al. Cell Syst 2025;16:101261.",
    "Hickey JW, Agmon E et al. Cell Sys 2024;15:235.",
]


def plan() -> dict:
    return {
        "title": "Multiscale tissue simulation for lung infectious disease",
        "subtitle": "A 15-paper journal-club lineage (2004 → 2025)",
        "topic": "multi-lung-short-2026-05-03",
        "author": "Bobby Y.X. Ni",
        "kb": "vaultlab",
        "theme": "dark",
        "template": "plain",
        "slides": [
            # 1 — Title
            {
                "type": "title",
                "title": "Multiscale tissue simulation for lung infectious disease",
                "subtitle": "A 15-paper journal-club lineage (2004 → 2025)",
                "author": "Bobby Y.X. Ni",
                "speaker_notes": {
                    "hook": "Where does the field start, and where is it now?",
                    "key_claim": "Three threads — alveolus ABM, integration substrate, spatial-omics — converge in 2024 for cancer; lung infection is the missing translation.",
                    "transition": "Outline first.",
                },
            },

            # 2 — Outline
            {
                "type": "text",
                "title": "Three threads converge — and an empty cell remains",
                "bullets": [
                    "Thread 1: Alveolus ABM solved spatial first-passage (2004–2016)",
                    "Thread 2: Vivarium gives multi-engine composition (2022)",
                    "Thread 3: CODEX/IMC/CosMx deliver single-cell ground truth (2021–2025)",
                    "Cancer integration is proven (Hickey/Agmon Cell Systems 2024)",
                    "Lung infection is the empty cell of the matrix",
                ],
                "speaker_notes": {
                    "hook": "Quick map before we walk the lineage.",
                    "key_claim": "Each thread matured independently; cancer integration is done; lung-infection is missing.",
                    "transition": "Thread 1 — the alveolus ABM that started it all.",
                    "script": (
                        "Three independent maturations frame today's talk. The first is the agent-based "
                        "modelling tradition that begins with Segovia-Juarez 2004 in M. tuberculosis "
                        "granulomas and works its way down to single-alveolus resolution by Pollmächer "
                        "2014. The second is the integration-substrate problem: how do you compose a "
                        "metabolic engine, a spatial agent engine, an ODE signalling engine, and a PDE "
                        "diffusion field into one runnable model? Vivarium (Agmon 2022) is the answer. "
                        "The third is the experimental ground-truth problem: how do you measure cell "
                        "type AND spatial position at single-cell resolution across a whole tissue? "
                        "CODEX, IMC and CosMx now solve that — Hickey 2021/2023 for the methodology, "
                        "Sorin 2023 and Pentimalli 2025 for the first clinically-relevant applications. "
                        "The point of this deck: each thread has matured; their integration has been "
                        "demonstrated for cancer; the lung-infection translation is the empty cell "
                        "this thesis intends to fill."
                    ),
                    "extended_walkthrough": (
                        "BACKGROUND — what is multiscale tissue simulation, and why does it matter for "
                        "lung infection?\n\n"
                        "A 'multiscale model' in computational biology means a simulation that "
                        "represents biology at more than one spatial or temporal scale simultaneously. "
                        "In the lung, the relevant scales span 5+ orders of magnitude: an inhaled "
                        "Aspergillus conidium is ~3 µm in diameter; a single alveolar epithelial cell "
                        "is ~25 µm across; an alveolus is ~250 µm; a respiratory acinus is ~5 mm; the "
                        "whole lung is ~25 cm. A model that uses just one scale either misses the "
                        "molecular event that decided the outcome (intracellular signalling drives "
                        "cytokine secretion in seconds-to-minutes) or misses the organ-level pattern "
                        "(infection clears or progresses over hours-to-days).\n\n"
                        "The four pieces a complete multiscale lung-infection model needs:\n"
                        "(1) An AGENT-BASED MODEL of cells in 3D space — the spatial-cellular layer. "
                        "Each macrophage, T cell, and pathogen is its own object with position and "
                        "state. Cells move, contact each other, and trigger state transitions.\n"
                        "(2) A METABOLIC / SIGNALLING layer inside each cell — what genes are "
                        "expressed, what cytokines get secreted. Often modelled as flux-balance "
                        "analysis (FBA) for steady-state metabolism plus ODEs for transient signalling.\n"
                        "(3) A DIFFUSION FIELD for soluble factors (cytokines, antibiotics, oxygen). "
                        "Modelled as PDEs on a 3D lattice.\n"
                        "(4) An INTEGRATION SUBSTRATE that lets these three engines run together at "
                        "their declared time-scales without you writing the gluing code by hand.\n\n"
                        "All four pieces have been independently mature for ~5 years. What's been "
                        "missing — until 2024 — is the demonstration that you can wire them together "
                        "into one runnable, predictive model that AGREES with whole-tissue measurements. "
                        "Hickey & Agmon 2024 supplied that demonstration for the tumour microenvironment "
                        "(B16-F10 melanoma, CODEX × Vivarium, R²=0.97-0.99 simulation-vs-CODEX). The "
                        "thesis question this lineage answers is: can the same composition pattern "
                        "produce a working model of an infected alveolar duct?\n\n"
                        "WHY LUNG INFECTION SPECIFICALLY — three reasons. First, lung infection is the "
                        "first place an inhaled pathogen meets the host immune system; the spatial "
                        "geometry of that encounter dictates the outcome (Pollmächer's main result). "
                        "Second, the lung has been heavily measured: CODEX, IMC, and CosMx now produce "
                        "whole-tissue single-cell datasets that didn't exist in 2020. Third, the "
                        "clinical importance is acute: tuberculosis kills 1.3 million people/year, "
                        "Aspergillus invasive disease has 30-50% mortality even with treatment, and "
                        "post-COVID lung remodelling is a 5-million-patient problem. A predictive "
                        "model of infection control would change drug development."
                    ),
                },
            },

            # 3 — Pollmächer 2014 (figure_above_bullets — wide alveolus diagram)
            {
                "type": "figure",
                "layout": "figure_above_bullets",
                "title": "Random-walk macrophages can't find an inhaled conidium — chemotaxis is required",
                "image_path": _f("10.1371_journal.pone.0111630"),
                "caption": "3D respiring alveolus, ~120 µm radius; type-I/II AECs (cyan), pores of Kohn (black).",
                "citation_source": CITE["pollmacher_2014"],
                "bullets": [
                    "PRW macrophages: P(FPT > 6h) = 0.68",
                    "BPRW with chemotaxis: P(FPT > 6h) < 5%",
                    "AEC-emitted gradient is REQUIRED, not optional",
                ],
                "speaker_notes": {
                    "hook": "Where does the geometry start to matter?",
                    "key_claim": "Random-walk alveolar macrophages cannot find an inhaled Aspergillus conidium within the 6-hour germination window. AEC chemotaxis is required, not decorative.",
                    "evidence": "10⁵ Monte Carlo realizations of a 3D respiring alveolus, 4.4 ± 2.1 macrophages each, PRW vs. BPRW, FPT readout.",
                    "key_terms": ["FPT", "PRW", "BPRW", "chemotaxis", "AEC type I/II", "pore of Kohn"],
                    "transition": "One alveolus solved. To compose models across scales we need a substrate.",
                    "script": (
                        "Pollmächer and Figge 2014 is one of the cleanest existence proofs in "
                        "computational lung biology. They build a 3D agent-based alveolus — a 3/4 "
                        "sphere of radius about 120 micrometres, tiled with about 40 type-I and 80 "
                        "type-II alveolar epithelial cells via Voronoi tessellation, plus 24 pores of "
                        "Kohn at radius 3 micrometres. The alveolus respires: 116 to 125 micrometres "
                        "at 12 breaths per minute. A single conidium moves passively with the air; "
                        "alveolar macrophages enter at Poisson-distributed times calibrated to give "
                        "the observed mean of 4.4 macrophages per alveolus. They run 100,000 Monte "
                        "Carlo realizations and ask: what is the probability that at least one "
                        "macrophage contacts the conidium before the 6-hour germination window "
                        "closes? Under a persistent random walk — macrophages reorienting every 2 "
                        "minutes at 4 micrometres per minute — the probability of MISSING the conidium "
                        "for >6 hours is 68%. Even at 10 micrometres per minute, miss-probability "
                        "stays above 15%. When they switch to a BIASED random walk that weights toward "
                        "an epithelial-cell-emitted chemokine gradient, miss-probability collapses to "
                        "under 5%. Successful macrophages catch the gradient within 60-80 micrometres "
                        "of the conidium. Translational implication: any ABM that treats AECs as "
                        "passive substrate will mispredict early infection control. AECs are active."
                    ),
                    "extended_walkthrough": (
                        "BACKGROUND — what is Aspergillus and why a 6-hour window?\n\n"
                        "Aspergillus fumigatus is a saprophytic fungus that produces airborne spores "
                        "called conidia, ~3 µm in diameter. We inhale hundreds of conidia per day. "
                        "In a healthy person, alveolar macrophages clear them silently. In an "
                        "immunocompromised patient — neutropenic from chemotherapy, on steroids "
                        "post-transplant — clearance fails and conidia germinate into hyphae that "
                        "invade tissue. Mortality of invasive aspergillosis is 30-50% even with "
                        "antifungal therapy, so the early window matters disproportionately.\n\n"
                        "The 6-hour number comes from in vitro germination kinetics. At 37°C, a "
                        "deposited conidium begins to swell at 4 hours and forms a germ tube by 6-8 "
                        "hours. Once a germ tube extends, the fungus is committed to the invasive "
                        "phenotype and is much harder to phagocytose. So 'detect within 6 hours' is "
                        "the operational target for the early innate immune response.\n\n"
                        "WHAT IS A PERSISTENT RANDOM WALK? In 2D or 3D, a random walk where the "
                        "particle reorients to a new direction at Poisson-distributed times, then "
                        "moves persistently in that direction until the next reorientation. The two "
                        "free parameters are the persistence time t_p and the speed v. PRW is the "
                        "null model for macrophage motility — what you'd expect if macrophages had "
                        "no environmental cues. BPRW adds a bias term: at each step, the new "
                        "direction is a weighted combination of a random vector and a vector pointing "
                        "up the chemokine gradient.\n\n"
                        "WHY DO POLLMÄCHER'S NUMBERS MATTER FOR THE THESIS? Because they bracket "
                        "the parameter space where ABM-based infection models live. Any agent-based "
                        "lung-infection model needs to pick AM speed (v), persistence time (t_p), "
                        "and a chemotaxis weight, and this paper supplies the experimentally-anchored "
                        "ranges. It also tells you which parameter combinations are unphysical — "
                        "PRW alone at any speed is inconsistent with observed clearance rates. A "
                        "model that produces clearance under PRW is wrong.\n\n"
                        "WHAT THE FIGURE SHOWS — three nested views of the model geometry. Left: "
                        "the 3/4 sphere alveolus with cyan squares marking AECs and black circles "
                        "marking pores of Kohn. Middle (zoomed pink box): a region of the alveolar "
                        "surface showing tessellation into individual AECs. Right insets: type-II "
                        "AECs are smaller and surfactant-secreting; pores of Kohn connect adjacent "
                        "alveoli."
                    ),
                },
            },

            # 4 — Vivarium (figure_only — pure schematic, no bullets needed)
            {
                "type": "figure",
                "layout": "figure_only",
                "title": "Vivarium composes ABM + FBA + ODE + PDE engines via 5 primitives",
                "image_path": _f("10.1093_bioinformatics_btac049"),
                "caption": "Process / Store / Composite / Compartment / Hierarchy — the five primitives.",
                "citation_source": CITE["vivarium_2022"],
                "speaker_notes": {
                    "hook": "How do you actually compose engines that disagree on time, space, units?",
                    "key_claim": "Vivarium is a discrete-event composition engine. Processes declare timestep + ports; Topology routes ports through Stores; Engine schedules updates atomically.",
                    "evidence": "Five primitives: Process / Store / Composite / Compartment / Hierarchy. Used by Hickey/Agmon Cell Systems 2024 for tumour-immune ABM.",
                    "key_terms": ["Process", "Store", "Topology", "Composite", "Adaptor", "place-graph"],
                    "transition": "Composability matters because validation data is now whole-tissue. Hickey 2021 next.",
                    "script": (
                        "If Pollmächer's alveolus solves spatial dynamics within one engine, "
                        "Vivarium solves the harder problem: composing engines that disagree on "
                        "time-step, state, and units. Eran Agmon — the Vivarium architect, also "
                        "second author on Bobby's keystone paper — designed five primitives. A "
                        "Process is a typed callable that declares ports + timestep + a `next_update` "
                        "function returning a typed delta. A Store is a typed state container with "
                        "a schema. A Composite wires Processes to Stores via a Topology dict that "
                        "routes each port to a path in a place-graph. A Compartment is a Composite "
                        "with a boundary Store for cross-compartment interfaces. A Hierarchy is a "
                        "tree of Compartments. The Engine is a discrete-event loop that schedules "
                        "each Process at its declared timestep and applies updates atomically. "
                        "Adaptor processes translate units across engine boundaries — FBA flux "
                        "(mol/L/s) → Bioscrape concentration (mol/L); pymunk position → diffusion "
                        "voxel. The practical consequence: FBA + ABM + ODE + PDE wire into one "
                        "composite without manual gluing. Hickey/Agmon 2024 used this for tumour-"
                        "immune. The thesis question is whether it works for an infected alveolar duct."
                    ),
                    "extended_walkthrough": (
                        "BACKGROUND — what was the 'composition problem' before Vivarium?\n\n"
                        "Before Vivarium, every multi-engine biology model was a one-off glue script. "
                        "If you wanted FBA metabolism inside an agent-based spatial model, you wrote "
                        "Python that called COBRApy in a loop, fed its output into your ABM at the "
                        "right time-step, and prayed the units lined up. The standard outcome was a "
                        "pile of 'wrapper code' that was the largest part of the codebase, "
                        "untestable, and not re-usable across projects. Three earlier frameworks "
                        "tried to solve this — COPASI (focused on systems-biology ODEs/SBML), "
                        "Multiscale Modeling Library (CompuCell3D extension), Spatial Modeling "
                        "Framework (CHASTE) — but each was tied to a specific engine pair.\n\n"
                        "WHAT MAKES VIVARIUM DIFFERENT — three design choices.\n\n"
                        "(a) Engine-agnostic composition. A Process exposes a `ports_schema()` "
                        "method that declares its named state ports (e.g., `internal`, `external`, "
                        "`boundary`) and a `next_update(timestep, states)` method that returns a "
                        "typed delta. Any code can be a Process — an FBA solver, a pymunk physics "
                        "step, an ODE integrator, a PDE step, even a Python function. Vivarium "
                        "doesn't care, as long as you implement the API.\n\n"
                        "(b) Topology as data. The wiring between Processes and Stores is a dict "
                        "you can modify at runtime, not hard-coded function calls. This means you "
                        "can swap an FBA engine for a kinetic engine without changing the rest of "
                        "the model — just rewire the Topology.\n\n"
                        "(c) Discrete-event scheduling. Each Process declares its own timestep. "
                        "The Engine maintains a priority queue of (next_update_time, process_id) "
                        "and pops the earliest. So an ODE Process at 1ms timestep can run alongside "
                        "an ABM Process at 1min timestep without either forcing the other to its "
                        "rate. Updates are applied atomically — all deltas in a given simulation "
                        "step are computed against the same state, then committed together — which "
                        "matters for numerical stability.\n\n"
                        "READING THE FIGURE — five panels. Panel (a) Process: a box with parameters "
                        "and an update function, exposing two ports as black dots. Panel (b) Store: "
                        "a cylinder (database-style icon) holding state variables and a schema. "
                        "Panel (c) Composite: two Processes wired to two Stores via Topology arrows. "
                        "Panel (d) Compartment: a Composite enclosed by a boundary Store that lets "
                        "it talk to other Compartments. Panel (e) Hierarchy: a tree of Compartments "
                        "with the 'outer' compartment containing 'inner' ones.\n\n"
                        "WHY THIS MATTERS FOR THE THESIS — the lung-infection model needs ABM (cells "
                        "in 3D), PDE (chemokine field), ODE (intracellular signalling), and possibly "
                        "FBA (pathogen metabolism under iron starvation). Vivarium lets each run at "
                        "its native timestep without me writing 4-engine glue code. The same Process "
                        "I write for an alveolar duct can be re-used in a future granuloma model."
                    ),
                },
            },

            # 5 — Hickey 2021 (figure_above_bullets — wide multi-panel)
            {
                "type": "figure",
                "layout": "figure_above_bullets",
                "title": "CODEX 47-plex turns whole-tissue images into ABM-grade single-cell labels",
                "image_path": _f("10.3389_fimmu.2021.727626"),
                "caption": "DNA-barcoded antibody panel; 4-region tissue imaging; 4-step pipeline.",
                "citation_source": CITE["hickey_2021"],
                "bullets": [
                    "47 DNA-barcoded antibodies, 4 categories",
                    "CellSeg U-Net + hand-gating + clustering hybrid",
                    "Spatial verification ensures clusters land in the right tissue",
                ],
                "speaker_notes": {
                    "hook": "What does it actually take to turn a 47-plex image into ABM input?",
                    "key_claim": "Hickey 2021 is the methodological recipe for converting CODEX images into ABM-grade single-cell tables. Single-segmentation, multi-normalisation, hand-gate + cluster hybrid, spatial verification — now standard.",
                    "evidence": "4 healthy human colon FFPE sections, 47 DNA-barcoded antibodies, CellSeg, 5 normalisation methods compared, 4 clustering methods compared.",
                    "key_terms": ["CODEX", "DNA-barcoded antibody", "CellSeg", "PhenoGraph", "FlowSOM", "DRA"],
                    "transition": "Hickey's group then took this to whole-organ scale and to Vivarium tumour-immune ABM in 2024.",
                    "script": (
                        "Hickey 2021 in Frontiers Immunology is the methods paper that quietly "
                        "enables the rest of this lineage. The problem: a CODEX image is not a "
                        "single-cell table. Each pixel carries 47 antibody intensities, and you "
                        "need an opinion on what counts as a CD3+CD8+ cytotoxic T cell versus a "
                        "CD3+CD4+ helper. They work through this on four healthy human colon FFPE "
                        "sections. Step one: segmentation via CellSeg, a U-Net trained on DAPI + "
                        "membrane channels. Step two: normalisation, comparing per-cell z-score, "
                        "per-marker z-score, log, min-max, and double-log — none dominates "
                        "everywhere. Step three: cell-typing. Neither pure clustering nor pure "
                        "hand-gating wins. The right answer is hybrid — hand-gate canonical types, "
                        "cluster the rest with PhenoGraph or FlowSOM, merge clusters by centroid "
                        "distance to ~25 stable types. Step four — and this is the one most groups "
                        "skip — spatial verification: map clusters back onto the tissue and inspect "
                        "that an 'epithelial' cluster sits in epithelium. Two years later Hickey "
                        "applied this to the Nature 2023 intestine atlas; a year after that, to the "
                        "Vivarium tumour-immune ABM (Cell Systems 2024 — the keystone paper)."
                    ),
                    "extended_walkthrough": (
                        "BACKGROUND — what is CODEX and why 47 antibodies?\n\n"
                        "CODEX (CO-Detection by indEXing) is a multiplexed immunofluorescence "
                        "method developed in Garry Nolan's lab at Stanford in 2018. The trick: "
                        "instead of staining tissue with one antibody at a time, you stain with all "
                        "47 antibodies simultaneously, but each antibody is conjugated to a unique "
                        "DNA barcode. To image, you flow in a complementary fluorescent oligo that "
                        "lights up just one barcode (and therefore one antibody) at a time, image, "
                        "wash, repeat. You end up with a 47-channel image of the same tissue.\n\n"
                        "Why 47 specifically? It's roughly the practical ceiling for CODEX as of "
                        "2021 — beyond about 50 antibodies, signal-to-noise degrades and tissue "
                        "starts to fall apart from repeated washing. Newer methods (CODEX/Akoya "
                        "PhenoCycler-Fusion, MACSima) push this to 60-80; IBEX with iterative "
                        "antibody bleaching reaches 100+. But 47 is enough to define every major "
                        "cell type in most tissues.\n\n"
                        "THE 4-CATEGORY PANEL DESIGN. Hickey's panel splits 47 antibodies into "
                        "Epithelial (CK7, CDX2, MUC2, ITLN1, etc.), Stroma (αSMA, CD31, CD90, "
                        "vimentin, collagen IV), Adaptive Immune (CD3, CD4, CD8, CD20, CD138), "
                        "Innate Immune (CD45, CD11c, CD68, CD163, HLA-DR). The discipline matters: "
                        "if a cell is CD3+CD8+, you want to be sure it's not just bleed-through "
                        "from a neighbouring epithelial cell — so you confirm with negative "
                        "staining for CK7 and CDX2.\n\n"
                        "WHY HYBRID HAND-GATING + CLUSTERING — pure clustering misses canonical "
                        "cell types because they're rare (e.g., tuft cells are 1-2% of intestinal "
                        "epithelium, get absorbed into other clusters). Pure hand-gating misses "
                        "the long tail of less-canonical states. Hybrid: gate the rare types you "
                        "know about, cluster the residual to find what you don't.\n\n"
                        "WHY SPATIAL VERIFICATION IS THE KEY STEP — clustering on antibody "
                        "intensities alone can produce 'ghost' cell types that look distinct in "
                        "marker space but actually correspond to a tissue compartment with weird "
                        "background staining. Mapping clusters back to xy coordinates lets you see, "
                        "say, that 'cluster 17' is actually all the cells inside a single follicle "
                        "with autofluorescent debris. Without spatial verification you publish a "
                        "fake cell type. With it, you catch the artefact.\n\n"
                        "READING THE FIGURE — top-left: 4 healthy human colon FFPE sections + the "
                        "DNA-barcoded antibody panel + CODEX imaging schematic. Top-right: the "
                        "47-marker antibody table organised by category. Middle: 4 imaging regions "
                        "of the colon (Region 1-4 are different patients/sections) showing the "
                        "false-coloured CODEX image. Bottom: the 4-step computational pipeline — "
                        "image acquisition → cell segmentation/quantification → normalisation → "
                        "cell-type annotation."
                    ),
                },
            },

            # 6 — Sorin 2023 (figure_above_bullets — square heatmap fits well above bullets)
            {
                "type": "figure",
                "layout": "figure_above_bullets",
                "title": "Spatial neighbourhoods, not cell frequencies, predict LUAD survival",
                "image_path": _f("10.1038_s41586-022-05672-3", "fig_neighborhoods"),
                "caption": "Cell-cell co-occurrence matrix of 30 cellular neighbourhoods (CN), permutation-tested.",
                "citation_source": CITE["sorin_2023"],
                "bullets": [
                    "35-plex IMC, 416 LUAD patients, 1.64M cells",
                    "30 cellular neighbourhoods via 10-NN clustering",
                    "ResNet50 on raw IMC: 95.9% progression accuracy",
                ],
                "speaker_notes": {
                    "hook": "Does spatial actually beat cell-frequency on a clinical endpoint?",
                    "key_claim": "Cellular neighbourhoods — 10-nearest-neighbour windows — predict post-surgical LUAD progression at 95.9% accuracy. Cell-frequency-only models are dominated.",
                    "evidence": "35-plex IMC on 416 LUAD patients, 1.64M cells, 30 CNs from permutation-tested pairwise interactions, ResNet50 on raw IMC.",
                    "key_terms": ["IMC", "CN", "permutation test", "ResNet50", "TLS", "LUAD"],
                    "transition": "Sorin proves spatial wins in 2D. Pentimalli proves 2D itself leaves info on the table.",
                    "script": (
                        "Sorin 2023 in Nature is the most decisive existence proof to date that "
                        "spatial cell-cell interactions carry more clinical signal than cell "
                        "frequencies in a solid tumour. The cohort is large by spatial-imaging "
                        "standards: 416 LUAD patients across five histological patterns — lepidic, "
                        "papillary, acinar, micropapillary and solid — imaged with a 35-plex IMC "
                        "panel that captures 1.64 million single cells. They run a permutation-tested "
                        "pairwise spatial interaction analysis on cells within 6 pixels, then "
                        "cluster 10-nearest-neighbour windows into 30 cellular neighbourhoods. CN21 — "
                        "B-cell hot, Treg-low — is protective; CN25 with added CD4+ helper is "
                        "additionally protective. They take raw IMC images through ResNet50, "
                        "extract features, run sparse-PCA, train an SVM. Five-fold-CV accuracy is "
                        "95.9% from a single 1-mm² core. External validation on 60 patients: 93.3%. "
                        "Five-marker minimal panel: 90.8%. Takeaway: spatial cell-cell interactions "
                        "carry outcome signal that cell frequencies do not. ABMs that simulate "
                        "neighbourhoods are the natural computational complement."
                    ),
                    "extended_walkthrough": (
                        "BACKGROUND — what is IMC, and how is it different from CODEX?\n\n"
                        "Imaging Mass Cytometry (IMC) is a multiplexed-imaging method developed by "
                        "Bernd Bodenmiller's group, commercialised by Fluidigm/Standard BioTools as "
                        "the Hyperion platform. The key trick: instead of fluorescent antibodies, "
                        "use antibodies conjugated to RARE-EARTH METAL isotopes (lanthanides like "
                        "Yb-176, Eu-153, etc.). Stain the tissue, then ablate it pixel-by-pixel "
                        "with a UV laser; each ablated pixel goes into a mass spectrometer that "
                        "counts the metal ions. You get a multi-channel image where each channel = "
                        "one antibody, no fluorescence overlap, ~40 channels routine.\n\n"
                        "IMC vs CODEX: IMC is destructive (laser ablation), single-pass, and a bit "
                        "lower spatial resolution (~1 µm per pixel). CODEX is non-destructive, "
                        "multi-pass with washes, and slightly higher resolution. Different cohorts "
                        "tend to use one or the other — Hickey's group uses CODEX; Sorin's group "
                        "(Walsh-Quail labs at McGill/Université Laval) uses IMC.\n\n"
                        "WHAT IS A CELLULAR NEIGHBOURHOOD (CN)? A formal way to describe 'what is "
                        "this cell surrounded by'. The procedure: for each cell, find its 10 "
                        "nearest neighbours by Euclidean distance. Compute a 30-element vector "
                        "where each entry is the count of one cell type among those 10 neighbours. "
                        "Now cluster all cells in the cohort by their neighbourhood vectors using "
                        "MiniBatchKMeans — you get 30 distinct neighbourhood archetypes. CN21 = "
                        "'cell surrounded mostly by B cells with no Tregs'; CN25 = 'B + Th, no "
                        "Treg'; etc.\n\n"
                        "WHY THIS MATTERS — cell-FREQUENCY models say 'this tumour has 12% Tregs' "
                        "and predict outcome. CN models say 'this tumour has Tregs CO-LOCALIZED "
                        "with M2 macrophages in CN17, an immunosuppressive niche' and predict "
                        "outcome. The latter wins because the SPATIAL ARRANGEMENT of the same "
                        "cells matters: a tumour with infiltrating B cells in tertiary lymphoid "
                        "structures (CN21) does much better than the same tumour with the same "
                        "B cells scattered uniformly. Counting alone misses this entirely.\n\n"
                        "WHY ResNet50 ON RAW IMC WORKS BEST — the deep-learning model bypasses the "
                        "feature-engineering step. It finds spatial patterns the human-defined CN "
                        "approach might miss. The 95.9% accuracy is on a 5-fold cross-validation, "
                        "which is the right benchmark; external validation at 93.3% on 60 patients "
                        "from a different hospital confirms generalisation.\n\n"
                        "READING THE FIGURE — this is the cell-cell co-occurrence matrix. Rows and "
                        "columns are cell types (~16 types). Each cell of the matrix is the "
                        "permutation-tested log-odds-ratio of two cell types being within 6 pixels "
                        "of each other relative to chance. Red = enriched co-occurrence; blue = "
                        "depleted; white = chance. The diagonal red blocks are cells of the same "
                        "type clustering together (e.g., B cells in B-cell follicles). The off-"
                        "diagonal patterns are the 30 cellular neighbourhoods."
                    ),
                },
            },

            # 7 — Pentimalli 2025 (figure_above_bullets — multi-panel rich figure)
            {
                "type": "figure",
                "layout": "figure_above_bullets",
                "title": "3D recovers what 2D misses — 2.28× larger neighbourhoods reveal DC niches",
                "image_path": _f("10.1016_j.cels.2025.101261"),
                "caption": "34-section CosMx + SHG-ECM atlas; 114M transcripts, 340k cells, 17 cell types.",
                "citation_source": CITE["pentimalli_2025"],
                "bullets": [
                    "Z-stack: 34 sections × 16 mm² each",
                    "3D neighbourhoods 2.28× larger than 2D",
                    "DC niches + T-cell continuity invisible in single 2D section",
                ],
                "speaker_notes": {
                    "hook": "Does the third dimension actually buy you anything?",
                    "key_claim": "3D neighbourhoods are 2.28× larger than 2D — large enough to contain DC niches and T-cell continuity that single-section analyses miss.",
                    "evidence": "One early-stage NSCLC patient, 34 sections, CosMx (960-gene panel), SHG for ECM, 114M transcripts, 340k cells, 17 cell types.",
                    "key_terms": ["CosMx", "SHG", "z-stack", "label transfer", "DC niche"],
                    "transition": "We have alveolus ABMs, an integration substrate, and 3D × spatial × outcome — for cancer. Lung infection is empty.",
                    "script": (
                        "Pentimalli and Rajewsky 2025 answer a question the rest of the field has "
                        "been ducking: how much information is single-section 2D spatial "
                        "transcriptomics losing? They take ONE early-stage aggressive NSCLC patient, "
                        "section the tumour at varying z-spacing, and image 34 sections by CosMx — "
                        "Bruker's 960-gene panel — across a 16 mm² ROI per section. They co-image "
                        "second-harmonic generation of extracellular matrix in the same coordinate "
                        "frame, so collagen architecture and cell type live in one xyz space. Total: "
                        "114 million transcripts in 340 thousand segmented cells, 17 cell types via "
                        "label-transfer against the Human Lung Cell Atlas + an NSCLC reference. "
                        "Headline finding: when they construct cellular neighbourhoods on the 3D "
                        "point cloud, median neighbourhood volume is 2.28× larger than 2D. That "
                        "extra volume is not noise — it contains structures you simply could not "
                        "have detected in 2D: dendritic-cell niches that span multiple sections; "
                        "T-cell trajectories continuous in 3D but broken in 2D; immune aggregates "
                        "that look sparse in 2D and reveal as TLS precursors in 3D. Takeaway: 3D "
                        "neighbourhood analysis is now feasible at clinical scale; 2D analyses are "
                        "systematically losing the structures that matter most for response."
                    ),
                    "extended_walkthrough": (
                        "BACKGROUND — what is CosMx and how is it different from Visium?\n\n"
                        "CosMx Spatial Molecular Imager (NanoString, now Bruker after 2024 "
                        "acquisition) is a single-molecule imaging spatial-transcriptomics platform. "
                        "It uses cyclic in-situ hybridization to detect individual mRNA molecules "
                        "with subcellular resolution, currently up to a 6,000-gene panel. The output "
                        "is an xy-resolved point cloud of mRNA detections, plus segmented cell "
                        "boundaries from DAPI/membrane stains, plus per-cell expression vectors "
                        "you can analyse as if it were scRNA-seq.\n\n"
                        "CosMx vs Visium: Visium uses a barcoded array of 55 µm spots — each spot "
                        "captures all transcripts from ~1-10 cells, so it's NOT single-cell. "
                        "Visium-HD reduces spots to 2 µm (close to single-cell). CosMx is genuinely "
                        "single-cell from the start, at the cost of a target-panel constraint "
                        "(960-6000 genes vs Visium's whole transcriptome).\n\n"
                        "WHY 3D? The intuition: a 2D tissue section is a slice through a 3D tumour, "
                        "and the slice direction is arbitrary. A multicellular structure like a "
                        "tertiary lymphoid structure (TLS) — typical diameter ~150-300 µm — gets "
                        "cross-sectioned by a 5 µm slice, so you see a circular/ellipsoidal cluster "
                        "of B cells. But you DON'T see whether those B cells are connected to "
                        "another cluster 40 µm above or below. In 2D those clusters look like "
                        "independent foci; in 3D they're one TLS.\n\n"
                        "THE 2.28× NUMBER. They define a cellular neighbourhood as the set of "
                        "cells within radius r of a given cell. Computing the neighbourhood VOLUME "
                        "in 2D (πr²) vs 3D ((4/3)πr³) at matched cell density gives the 2.28× "
                        "ratio empirically — the 3D ball contains 2.28× more cells than the 2D "
                        "disc at the same r. The biological consequence: structures that need ≥10 "
                        "cells to be statistically significant get DETECTED in 3D and missed in 2D.\n\n"
                        "WHY SHG IMAGING ADDS A DIMENSION — second-harmonic generation is a "
                        "non-linear optical effect that lights up specifically when laser hits "
                        "ordered triple-helical collagen fibres. It requires no exogenous stain. "
                        "Co-acquired with CosMx, SHG gives you the ECM scaffold in the same "
                        "coordinate frame as the cells. So you can ask: are PD-1+ T cells preferentially "
                        "located in collagen-dense vs collagen-sparse regions? In NSCLC the answer "
                        "is yes — collagen-dense regions exclude T cells, with implications for "
                        "anti-PD-1 response.\n\n"
                        "READING THE FIGURE. Panel A: schematic showing the early-stage aggressive "
                        "NSCLC patient + 34-section z-axis stack. Panel B: H&E of the section + the "
                        "tumour/stroma/normal-lung mask. Panel C: UMAP of all 340k cells coloured "
                        "by 17 cell types (tumour cells, alveolar, fibroblasts, vascular, immune "
                        "subsets). 'Label transfer' in the legend means each cell's identity was "
                        "assigned by similarity to a reference atlas, not de novo clustered. Panel D: "
                        "high-resolution spatial map of selected ROIs at 2-cell-types and 17-cell-"
                        "types resolution. Panel E: similarity scores to the Human Lung Cell Atlas "
                        "(top row) and a separate NSCLC reference (bottom row), confirming the "
                        "label transfer."
                    ),
                },
            },

            # 8 — Take-aways
            {
                "type": "text",
                "title": "Lung infection sits at an empty cell of a now-mature 4-axis matrix",
                "bullets": [
                    "Alveolus ABM: solved (Pollmächer 2014, Oremland 2016)",
                    "Multi-engine substrate: solved (Vivarium, Agmon 2022)",
                    "CODEX/IMC/CosMx ground truth: solved (Hickey, Sorin, Pentimalli)",
                    "Cancer integration: PROVEN (Hickey/Agmon Cell Sys 2024)",
                    "Lung-infection translation: the obvious + unfilled next cell",
                ],
                "speaker_notes": {
                    "hook": "Where does this leave us?",
                    "key_claim": "Each thread is mature; cancer integration is demonstrated; lung-infection version is the empty cell of the 4-axis matrix this thesis programme intends to fill.",
                    "transition": "Open for questions.",
                },
            },

            # 9 — References
            {"type": "references", "title": "References", "references": REFS},
        ],
    }


def main() -> int:
    out_path = OUT_DIR / "short-2026-05-04-rebuilt-v6.pptx"
    print(f"Building {out_path.name} ...")
    plan_dict = plan()

    missing: list[str] = []
    for s in plan_dict["slides"]:
        ip = s.get("image_path")
        if ip and not Path(ip).exists():
            missing.append(ip)
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
