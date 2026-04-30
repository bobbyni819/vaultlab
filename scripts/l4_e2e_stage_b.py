"""L4 E2E Test - Stage B: render summaries + arc using my pre-composed JSON.

Reuses the corpus.pkl and acq_results.pkl from stage A. Has a curated
Tier-A pick set (8 papers I read in-session via the Read tool) plus
JSON dicts authored from the actual PDF content. Calls run_lit_arc with
reader=/narrator= callbacks that return those pre-composed dicts.

The picker logic in vaultlab.research.lineage._pick_top_n_for_summarization
ranks by og+forward, which only puts 2 of our 8 desired papers in
Tier-A. To force the 8 picks we want, we monkey-patch that function so
the orchestrator selects exactly our 8 DOIs.
"""

from __future__ import annotations

import json
import pickle
import sys
import time
from pathlib import Path

from vaultlab.kb.paths import summary_path
from vaultlab.research import (
    SummarizationTask,
    ArcTask,
    run_lit_arc,
)
from vaultlab.research import lineage as lineage_mod

TOPIC = "CODEX cellular neighborhoods"
KB_ROOT = Path(r"G:/My Drive/Knowledge/vaultlab")
DATE_STR = "2026-04-29"
MAX_SEEDS = 12
MAX_PAPERS_TO_SUMMARIZE = 8

STATE_DIR = Path(r"C:/Users/bobby/Downloads/vaultlab/scripts/_l4_state")

# Force these 8 DOIs as Tier-A picks (overrides _pick_top_n_for_summarization).
FORCE_TIER_A = {
    "10.1016/j.cell.2018.07.010",  # Goltsev 2018 - seminal CODEX
    "10.1126/sciadv.add1166",      # Mayer 2023 - UC tissue atlas
    "10.1371/journal.pcbi.1012344",  # Tao 2024 - CNTools
    "10.1016/j.cell.2024.04.013",  # Bandyopadhyay 2024 - bone marrow
    "10.1038/nmeth.4391",          # Schapiro 2017 - histoCAT/miCAT
    "10.1089/cmb.2019.0340",       # Chen 2020 - Spatial-LDA
    "10.1007/s00281-022-00974-0",  # Kuswanto 2023 - CODEX review
    "10.1038/s42003-022-04032-1",  # Lal 2022 - PDAC CN highlight
}

# ---------------------------------------------------------------------------
# Per-paper JSON responses (composed from real PDF reads)
# ---------------------------------------------------------------------------

SUMMARIES: dict[str, dict] = {
    "10.1016/j.cell.2018.07.010": {
        "tldr": (
            "Goltsev et al. introduce CODEX (CO-Detection by indEXing), a DNA-barcoded "
            "antibody imaging method that achieves single-cell quantification of dozens of "
            "antigens in tightly packed murine spleen tissue using iterative primer-extension "
            "cycles on a standard fluorescence microscope. Applied to normal BALB/c versus "
            "MRL/lpr autoimmune mouse spleens, the method recovers 27 cell-type clusters and "
            "100 indexed cellular neighborhoods (i-niches) from 734,101 segmented cells. They "
            "show that the cell's local i-niche significantly improves prediction of surface-"
            "marker expression, demonstrating that tissue locale shapes cell phenotype."
        ),
        "why_it_matters": [
            "First single-cell, in-situ multiplexed imaging method that scales to ~30+ markers on a standard 3-color fluorescence microscope",
            "Introduces the formal concept of 'cellular neighborhoods' (i-niches) as quantitative tissue subunits",
            "Demonstrates that local neighborhood significantly explains marker-expression variance beyond cell-type identity alone",
            "Provides an algorithmic compensation for lateral signal bleed between adjacent segmented cells in dense tissue",
            "Founds the CODEX/cellular-neighborhood lineage that downstream studies (Schurch 2020, Phillips 2021, Kennedy-Darling) build on",
        ],
        "methods_summary": (
            "Antibodies are conjugated to oligonucleotide duplexes whose 5' overhangs encode "
            "cycle-specific identity. At each rendering cycle Klenow polymerase extends the "
            "duplex with a mix of unlabeled dNTPs plus two fluorescent dye-labeled dNTPs (Cy3 "
            "and Cy5), unmasking exactly the antibodies for that cycle. After imaging the "
            "fluorophores are cleaved with TCEP and the next cycle is performed. CODEX was "
            "applied to fresh-frozen spleen cryosections (3 BALB/c, 6 MRL/lpr) using a 30-"
            "antibody panel; cells were segmented by combining nuclear and CD45 membrane "
            "channels, and clustered with X-shift to yield 27 cell-type groups. i-niches were "
            "defined as the ring of first-tier Delaunay neighbors around each index cell; 100 "
            "i-niches were identified by k-means clustering of cell-type frequencies in those "
            "rings."
        ),
        "key_findings": [
            "CODEX achieves ~98% efficient fluorophore release per cycle with signal-to-noise ~85:1, supporting up to 66 antigens via primer-dependent panel design [p2]",
            "Direct comparison to CyTOF on the same 24-antibody panel shows CODEX recovers cell-type frequencies similar to mass cytometry on dissociated splenocytes [p3]",
            "100 i-niches were identified by k-means clustering of first-tier neighbor cell-type frequencies across 734,101 segmented cells [p4]",
            "Adding i-niche identity to a linear regression model significantly improved prediction of surface-marker levels (CD90, B220, CD21/35, ERTR7), quantitatively demonstrating that local neighborhood shapes phenotype [p7]",
            "Disease progression in MRL/lpr produced a >100-fold increase in CD71+ erythroblasts and emergence of B220+ DN T cells, accompanied by reorganization of red-pulp i-niches [p8]",
            "A convolutional neural network trained on the multiparameter CODEX images automatically classified diseased vs. healthy regions and identified CD4+/CD8- cDCs distant from stromal regions as a key descriptor of disease [p10]",
            "For the majority of cell-type pairs, changes in interaction count between healthy and diseased spleen tracked with cell-frequency shifts (R^2 = 0.288) rather than with changes in interaction affinity (R^2 = 0.058) [p9]",
            "Cell-cell interaction networks reorganize in late MRL/lpr with appearance of novel B220+ DN T-dominated i-niches (e.g., #18, #29) absent from normal spleen [p10]",
        ],
        "extracted_references": [],
    },
    "10.1126/sciadv.add1166": {
        "tldr": (
            "Mayer, Holman, Sood et al. apply the 52-plex CODEX panel to 42 colon biopsies "
            "from 29 ulcerative colitis (UC) patients and 5 healthy controls, generating 1.71 "
            "million spatially-resolved single cells across 13 cell types. Unsupervised "
            "neighborhood analysis identifies 10 conserved cellular neighborhoods (CNs) "
            "including B-cell follicles, lymphoid aggregates, granulocyte-rich and inflamed-"
            "vasculature CNs whose frequencies and functional states track Mayo disease "
            "severity. The atlas reveals sex-dependent differences in disease-driving "
            "inflammatory cells and identifies CN signatures associated with TNF-inhibitor "
            "(TNFi) resistance, accessible via a public Explorer cloud platform."
        ),
        "why_it_matters": [
            "Largest CODEX-based UC tissue atlas to date (1.71M cells, 42 biopsies), enabling biomarker discovery for an indication where TNFi non-response affects 13-40% of patients",
            "Demonstrates that CNs (not just cell frequencies) carry therapy-response signal — innate-immune-cell-paired contacts persist in TNFi-treated UC even with mucosal healing",
            "Provides a public cloud Explorer (uc-study) so other groups can spatially query the atlas without reanalyzing raw imaging",
            "Couples spatial CN analysis to clinical Mayo score, showing CN-level functional state (e.g., TNFR2+ neutrophils in inflamed vasculature) shifts with disease severity",
            "Cautions about CNN-based clinical predictions and offers guidelines for reporting CNN models on spatial proteomic data",
        ],
        "methods_summary": (
            "Forty-two formalin-fixed colon biopsies from 29 UC patients (15 on TNFi at biopsy) "
            "and 5 healthy controls were imaged with a 52-plex CODEX antibody panel including "
            "lineage markers, immune-checkpoint markers (PD-1, PD-L1), 4-1BB/TNFRSF9, IL-6R, "
            "TNFR2, and Ki67. After CODEX, the same sections were H&E stained for morphologic "
            "validation. X-shift unsupervised clustering on 1,710,973 segmented cells yielded "
            "13 cell types (8 immune, 2 epithelial, plus stroma/vessels/smooth muscle). "
            "Cellular neighborhoods (CNs) were defined by the 10-nearest-neighbor cell-type "
            "frequency vector around each cell, k-means clustered into 10 CNs. CN functional "
            "state was assessed by enrichment of activation markers per CN. A CNN was also "
            "trained to predict patient clinical variables and the authors discuss limitations."
        ),
        "key_findings": [
            "CODEX imaging of 42 UC/HC colon biopsies generated 1,710,973 spatially-resolved single cells annotated to 13 conserved cell types via X-shift clustering [p2]",
            "Ten conserved cellular neighborhoods were identified including B-cell follicle (CN-9), lymphoid aggregate (CN-2), granulocyte-rich (CN-3), inflamed vasculature (CN-7), inflamed stroma (CN-0), basal/luminal/proliferative epithelium and lamina propria CNs [p4]",
            "CN-7 (inflamed vasculature) had significantly higher TNFR2+ neutrophil frequency than CN-0 or CN-4 (the other neutrophil-enriched CNs) [p4]",
            "PD-1+ T-cell frequency varied by neighborhood: T cells in B-cell follicles (CN-9) vs lymphoid aggregates (CN-2) vs mixed-immune (CN-4) showed distinct PD-1 expression [p4]",
            "Mayo severity score 1->3 was associated with significant increases in granulocyte (CN-3), mixed immune (CN-4), and lamina propria (CN-5) neighborhoods and decreases in luminal (CN-1) and basal (CN-8) epithelial CNs [p4]",
            "TNFi treatment shifted T-cell, B-cell, and epithelial-T-cell contacts toward healthy-control patterns in Mayo-2 patients (volcano plot of cell-cell contacts) [p6]",
            "A subset of inflammatory cell types and CNs persisted in TNFi-resistant patients, suggesting spatial niches as candidate resistance markers [p6]",
            "Sex-dependent differences in CN abundance were observed in the cohort, though their predictive value for individual TNFi-response was minimal [p2]",
        ],
        "extracted_references": [],
    },
    "10.1371/journal.pcbi.1012344": {
        "tldr": (
            "Tao et al. release CNTools, a Python toolbox unifying state-of-the-art cellular-"
            "neighborhood (CN) identification methods (CC, CF-IDF, Spatial-LDA, ClusterNet, "
            "GAP) with post-identification smoothing techniques and downstream CT-CN/CN-CN "
            "analysis pipelines. They introduce a new method, Cellular Neighbor Embedding "
            "(CNE), and a Naive Smoothing post-processing step. Benchmarks on three real CODEX "
            "datasets (CRC, T2D pancreatic islets, lymphoid HLT) show CNE+Naive Smoothing "
            "outperforms prior methods and produces more biologically meaningful CN instances."
        ),
        "why_it_matters": [
            "First open-source toolbox to unify the major CN-identification algorithms behind a single API, enabling apples-to-apples benchmarking",
            "Introduces CNE, which addresses the cell-type-frequency imbalance limitation of Schurch's k-means / CF-IDF approaches",
            "Provides downstream analyses (tensor decomposition, inter-CN communication network, CN combination map, assembly rule identification) so users can move past identification into hypothesis generation",
            "Establishes Naive Smoothing as a fast alternative to HMRF for cleaning up small spurious CN instances",
            "Offers practical guidance on choosing CN identification methods given input characteristics (data size, CT distribution)",
        ],
        "methods_summary": (
            "CNTools is a Python package (pip-installable as 'cntools', source on GitHub) that "
            "takes a cell table with xy coordinates and pre-assigned cell-type labels as input. "
            "It implements four CN identification methods: CC (Schurch's k-means on k-NN cell-"
            "type frequencies), CF-IDF (Bhate's inverse-distance TF-IDF community detection), "
            "Spatial-LDA (Chen 2020), and the authors' new CNE (cell-neighbor embedding via a "
            "neural encoder), plus optional ClusterNet and GAP graph-NN approaches. After "
            "identification, post-processing options include the new Naive Smoothing (replace "
            "small-size CN instances with majority neighbor) and HMRF. Downstream tools include "
            "CT enrichment, differential CT enrichment, tensor decomposition, inter-CN "
            "communication networks, CN combination maps, and assembly rule identification. "
            "Benchmarks were run on three published CODEX datasets: CRC (Schurch 2020), T2D "
            "pancreatic islets, and Human Lymphoid Tissue."
        ),
        "key_findings": [
            "CNTools unifies five+ cellular-neighborhood identification methods (CC, CF-IDF, Spatial-LDA, ClusterNet, GAP, plus the new CNE) behind a single Python API [p1]",
            "CNE with Naive Smoothing 'overall outperforms state-of-the-art methods' on three real CODEX datasets (CRC, T2D, Lymphoid) per quantitative and qualitative evaluation [p1]",
            "Identifies a key limitation of Schurch's CC method: k-means on local cell-type frequencies ignores that neighboring cells may have different importance based on distance and CT frequency imbalance [p2]",
            "Naive Smoothing replaces small CN instances with their majority neighbor, addressing the spurious-small-CN problem common to graph-based methods like ClusterNet [p2]",
            "Downstream analysis modules include CT enrichment, differential CT enrichment, tensor decomposition, inter-CN communication network, CN combination map, and assembly-rule identification [p3]",
            "CNTools is publicly available as a Python package on PyPI ('cntools') and source code at github.com/liu-bioinfo-lab/CNTools, with ClusterNet/GAP at github.com/yctao7/CNTools_ClusterNet-GAP [p2]",
        ],
        "extracted_references": [],
    },
    "10.1016/j.cell.2024.04.013": {
        "tldr": (
            "Bandyopadhyay et al. profile 29,325 non-hematopoietic and 53,417 hematopoietic "
            "cells of human bone marrow with single-cell RNA-seq plus CODEX imaging of >1.2 "
            "million cells, then integrate the two to map cellular signaling onto spatial "
            "proximity. They identify nine transcriptionally-distinct non-hematopoietic "
            "subtypes and reveal a hyperoxygenated arterio-endosteal cellular neighborhood for "
            "early myelopoiesis and an adipocytic neighborhood for early hematopoietic stem-"
            "and-progenitor cells. The CODEX atlas is then used to annotate AML patient "
            "samples, where mesenchymal stromal cells (MSCs) expand and co-enrich with leukemic "
            "blasts in disease-specific neighborhoods."
        ),
        "why_it_matters": [
            "Largest paired scRNA-seq + CODEX human bone-marrow atlas, addressing a long-standing gap in non-hematopoietic profiling (MSCs are <0.5% of BM)",
            "Establishes spatial-niche-level differences (arterio-endosteal vs. adipocytic vs. sinusoidal) for early myelopoiesis vs. HSPC localization in human marrow",
            "Provides a Fibro-MSC ISCT-defined reference set against which AML, fetal, and aging marrow can be compared",
            "Shows AML reorganizes the MSC compartment, with MSC expansion and leukemic-blast co-enrichment as a candidate biomarker for niche dysfunction",
            "Couples scRNA-seq predicted ligand-receptor interactions to spatial CODEX neighborhoods, validating the predictions in tissue context",
        ],
        "methods_summary": (
            "Twelve adult human bone marrow donors contributed paired material for scRNA-seq "
            "(profiling 29,325 non-hematopoietic and 53,417 hematopoietic cells) and CODEX "
            "spatial imaging of >1.2 million cells. The scRNA-seq workflow used flow-sorted "
            "non-hematopoietic enrichment to overcome the <0.5% representation of these cells "
            "in standard marrow aspirates. CODEX was performed on fresh-frozen marrow sections "
            "with a custom panel for hematopoietic, mesenchymal, endothelial, vascular smooth-"
            "muscle, and neural lineage markers. The two modalities were integrated by matching "
            "cell-type signatures so that scRNA-seq-predicted cytokine ligand-receptor pairs "
            "could be queried against the spatial CODEX neighborhood. The CODEX atlas was then "
            "applied to AML and fetal-MSC samples for niche-level comparison."
        ),
        "key_findings": [
            "scRNA-seq identified nine transcriptionally distinct non-hematopoietic subtypes in human bone marrow [p2]",
            "CODEX profiled >1.2 million cells and integrated with scRNA-seq to link predicted ligand-receptor signaling to spatial proximity [p2]",
            "An arterio-endosteal hyperoxygenated cellular neighborhood was identified for early myelopoiesis [p2]",
            "Early hematopoietic stem and progenitor cells localized to an adipocytic spatial neighborhood, distinct from the myelopoiesis niche [p2]",
            "Adipo-MSCs and THY1+ MSCs co-localize with hematopoietic cells and express most of the supportive cytokines (CXCL12, KITLG, IL7) per the experimental-design schematic [p3]",
            "In AML patient samples the CODEX atlas detected MSC compartment expansion and co-enrichment of leukemic blasts with MSCs in disease-specific neighborhoods [p2]",
            "A novel Fibro-MSC subset matching ISCT-defined mesenchymal stem cell criteria (NT5E+/THY1+/ENG+, tripotent) was identified and shown to be the most proliferative subset, localized to trabecular bone [p3]",
        ],
        "extracted_references": [],
    },
    "10.1038/nmeth.4391": {
        "tldr": (
            "Schapiro et al. release histoCAT (miCAT in the manuscript), an open-source "
            "computational toolbox for interactive analysis of multiplex image cytometry data "
            "(MIBI, IMC, FISSEQ, MERFISH, CODEX-class measurements). histoCAT links every "
            "single-cell row of high-dimensional cytometry to its corresponding pixel mask in "
            "the multiplex image, enabling round-trip exploration from a tSNE plot back to a "
            "specific cell in tissue. A novel permutation-based algorithm identifies "
            "statistically over- and under-represented cell-cell pairwise interactions, "
            "surfacing tissue 'social networks' that the authors validate on 49 human breast "
            "cancer samples profiled by imaging mass cytometry."
        ),
        "why_it_matters": [
            "First broadly-adopted, open-source multiplex-image-cytometry analysis platform that handles segmentation-linked spatial features (cell neighbors, crowding, shape) alongside standard cytometry",
            "Introduces the permutation-test interaction algorithm now used by Schurch 2020 and successors to define statistically-significant tissue interactions",
            "Demonstrates 'round-trip' analysis: tSNE-defined phenotype clusters can be projected back to specific cells in the original tissue image",
            "Establishes the breast-cancer IMC dataset (49 samples) as a community benchmark for multiplexed tissue analysis",
            "Pre-dates and is complementary to the cellular-neighborhood literature — its interaction-network algorithm is a key methodological building block",
        ],
        "methods_summary": (
            "histoCAT is implemented as MATLAB-based software (Mac, Windows 7, Windows 10 "
            "supplementary builds; data and sessions at bodenmillerlab.org/research-2/micat). "
            "It ingests segmentation masks plus per-channel multiplex images, extracts per-cell "
            "marker abundances, spatial features (size, shape, neighbors, crowding), and "
            "exports flow-standard FCS files. The interaction algorithm permutes cell labels "
            "while keeping spatial positions fixed and computes the empirical p-value of "
            "observed pairwise contact counts versus the null. tSNE and PhenoGraph clustering "
            "produce phenotypic groupings that are linked back to the source images. Validation "
            "used imaging mass cytometry on 49 human breast cancer samples plus 6 matched "
            "normal tissues stained with a panel covering cell lineages, signaling, "
            "proliferation, apoptosis, and clinical markers."
        ),
        "key_findings": [
            "histoCAT provides round-trip analysis linking single-cell tSNE clusters back to their source pixels in the multiplex image, enabling visual context for every analytical step [p2]",
            "A novel permutation-based algorithm identifies cell-cell pairwise interactions that occur more or less frequently than expected by chance [p2]",
            "PhenoGraph clustering on 49 breast cancer IMC samples plus 6 matched normal tissues identified 29 phenotype clusters shared across images and clinical subgroups [p3]",
            "The toolbox is built for FISSEQ, MERFISH, cycling immunofluorescence, MIBI, and IMC data — an explicit platform-agnostic design that anticipates CODEX-class data [p2]",
            "histoCAT was made available as MATLAB Supplementary Software (versions for OS12, Win7, Win10) plus public data and sessions at bodenmillerlab.org/research-2/micat [p1]",
            "Tumor-associated macrophage (TAM) phenotype #7 with high CD68 was investigated via gating on the tSNE plot and re-projected to source images for spatial analysis [p3]",
        ],
        "extracted_references": [],
    },
    "10.1089/cmb.2019.0340": {
        "tldr": (
            "Chen, Soifer, Hilton, Keren and Jojic introduce Spatial-LDA, a topic-model "
            "extension of Latent Dirichlet Allocation that recovers microenvironment "
            "signatures from multiplexed tissue images by treating each cell's local "
            "neighborhood as a 'document' and cell-types as 'words.' The model assumes spatial "
            "coherence among neighboring microenvironment loadings, which both regularizes "
            "the inference and lets the data dictate the size of the cellular neighborhood. "
            "Applied to mouse spleen and a 41-patient triple-negative breast cancer (TNBC) "
            "MIBI cohort, Spatial-LDA recovers known anatomical compartments and discovers a "
            "novel CD45+/FoxP3+-enriched immunosuppressed microenvironment near the tumor-"
            "immune boundary."
        ),
        "why_it_matters": [
            "First topic-model formulation of cellular neighborhoods, providing soft-mixture loadings rather than hard CN labels — a natural fit for tissue regions with mixed character",
            "Introduces spatial coherence as a regularizer, allowing data-driven selection of neighborhood size",
            "Demonstrates utility on both a normal-tissue benchmark (mouse spleen B-cell zones) and a clinical TNBC cohort (Keren 2018), bridging mechanism and translation",
            "Discovers a novel immunosuppressed CD45+/FoxP3+ microenvironment near the TNBC tumor-immune boundary that is invisible to hard-clustering CN methods",
            "Becomes one of the canonical CN-identification baselines that subsequent toolboxes (e.g., CNTools) integrate",
        ],
        "methods_summary": (
            "Spatial-LDA reformulates the 'bag-of-cells' representation of a local neighborhood "
            "as the bag-of-words analog from natural language processing. For each cell i and "
            "its neighbors, a count vector w_i over cell-type identities is constructed. A "
            "Dirichlet prior generates per-document topic distributions theta_i, and each "
            "neighbor's cell-type identity is drawn from the topic-conditional distribution "
            "beta. The novel addition is a spatial coherence prior that links nearby theta_i "
            "loadings, regularizing inference. Posterior is approximated by mean-field "
            "variational inference with an Evidence Lower BOund (ELBO) optimization, "
            "iteratively updating phi (per-word topic), gamma (per-document topic Dirichlet), "
            "and lambda (topic-word Dirichlet). The method was validated on Goltsev 2018 mouse "
            "spleen CODEX data and applied to Keren et al. 2018 TNBC MIBI-TOF data (41 "
            "patients, ~30-40 markers per cell)."
        ),
        "key_findings": [
            "Spatial-LDA recovers 'distinct populations of spleen B cells defined by their characteristic neighborhoods' on the Goltsev 2018 CODEX dataset [p1]",
            "Applied to a 41-patient TNBC MIBI cohort, the model recovers the previously-reported tumor-immune boundary microenvironment enriched for IDO-high and PD-L1-high cells [p1]",
            "A novel immunosuppressed microenvironment enriched for CD45+/FoxP3+ cells was discovered near the tumor-immune boundary in TNBC [p1]",
            "The bag-of-cells assumption (cell ordering within a neighborhood is irrelevant) is justified by combinatorial explosion of equivalent layouts and by the fact that nearby cells signal via diffusible/contact mechanisms regardless of local order [p3]",
            "Mean-field variational inference with ELBO maximization is used to approximate the posterior over theta, beta, and z [p3]",
            "The spatial-coherence prior limits the number of free parameters and lets the data choose the effective neighborhood size, removing a tunable hyperparameter required by k-NN-based methods [abstract, p1]",
        ],
        "extracted_references": [],
    },
    "10.1007/s00281-022-00974-0": {
        "tldr": (
            "Kuswanto, Nolan and Lu review the CODEX (Co-Detection by indEXing) platform for "
            "highly multiplexed spatial profiling, covering the wet-lab workflow (DNA-barcoded "
            "antibody conjugation, iterative fluorophore reveal/strip, FFPE compatibility) and "
            "the bioinformatic pipeline from cell segmentation through cellular-neighborhood "
            "analysis. They survey published CODEX studies in cancer (CRC, bladder), "
            "autoimmunity (UC, kidney injury), and infection (Ebola in rhesus macaques), "
            "summarizing methods (k-NN gating, SpatialScore, X-shift, U-Net, Phenograph, "
            "CODEX-MAV) and key findings per study, and conclude with practical guidance on "
            "panel design, batch effects, and emerging analytical challenges."
        ),
        "why_it_matters": [
            "Single-source review surveying CODEX applications in cancer, autoimmunity, and infection — useful onboarding reference for new groups entering the field",
            "Enumerates the bioinformatic toolchain (CODEX-MAV, U-Net segmentation, X-shift, Phenograph, SpatialScore, CN k-means) used across CODEX studies",
            "Maps each published study to disease state, tissue, and analytical tool — providing a structured comparative view of the lineage",
            "Discusses challenges (panel design, FFPE compatibility, batch effect mitigation) and future directions (cross-modality integration with genomics)",
            "Authored by the Nolan group (originators of CODEX) plus Stanford collaborators, providing authoritative methodological commentary",
        ],
        "methods_summary": (
            "This is a narrative review with no new experimental data. Section 1 (Introduction) "
            "outlines the CODEX wet-lab workflow: DNA-barcoded antibodies hybridize to "
            "fluorescently-labeled complementary oligos, three of which are imaged per cycle "
            "before being stripped; the cycle is repeated until all antibodies in the 50+ panel "
            "have been imaged. Section 2 (Applications) tabulates published CODEX studies by "
            "tissue / disease state / key findings / analytic tools. Section 3 (Bioinformatics) "
            "covers preprocessing (CODEX-MAV), cell segmentation (U-Net), cell-type "
            "identification (Phenograph, X-shift, manual gating), and spatial analysis "
            "(SpatialScore, k-NN cellular neighborhoods)."
        ),
        "key_findings": [
            "CODEX uses DNA-barcoded antibodies plus iterative fluorophore reveal/strip cycles to image 50+ markers on FFPE or fresh-frozen tissue [p1]",
            "Published CODEX studies span tissue injury/kidney, cutaneous T-cell lymphoma, bladder cancer, colorectal cancer (Schurch 2020), follicular lymphoma, Ebola in rhesus macaques, and ulcerative colitis [p3]",
            "The Schurch 2020 CRC study identified two CD4+/CD8+ T-cell subsets at the tumor boundary whose ratio is prognostic; CN composition and organization is described as 'cellular composition and organization' of CN [p3]",
            "Mayer 2021 (the prior version of the UC paper) developed a CN-based model of TNFi resistance using unsupervised X-shift clustering with manual gating [p3]",
            "Bioinformatic tools surveyed include CODEX-MAV (preprocessing), U-Net (segmentation), Phenograph and X-shift (cell-type calling), and SpatialScore + k-NN gating (spatial analysis) [p3]",
            "Phillips 2021 in cutaneous T-cell lymphoma quantified distance between CD4+/PD-1+ T cells, Tregs, and tumor cells via SpatialScore and correlated with checkpoint inhibitor response [p3]",
            "The review is published as part of a Seminars in Immunopathology special issue on Single-cell and spatial multi-omics in clinical outcomes studies [p1]",
        ],
        "extracted_references": [],
    },
    "10.1038/s42003-022-04032-1": {
        "tldr": (
            "Lal's Communications Biology Research Highlight summarizes Hwang et al.'s "
            "spatial-transcriptomic and single-nucleus RNA-seq study of pancreatic ductal "
            "adenocarcinoma (PDAC), in which recurrent gene-expression patterns define "
            "cellular neighborhoods of malignant and fibroblast cells that correlate with "
            "chemoradiation outcome. The highlight emphasizes four cancer-associated "
            "fibroblast (CAF) subsets — myofibroblastic, neurotropic, immunomodulatory, and "
            "adhesive — and notes that adhesive-CAF signatures correlate with poor survival "
            "in treatment, while myofibroblast signatures decreased in the treatment group. "
            "It calls for better single-cell pipelines to fully exploit spatially-resolved "
            "transcriptomics in PDAC."
        ),
        "why_it_matters": [
            "Brings the cellular-neighborhood concept from CODEX-style imaging into the spatially-resolved transcriptomics modality (Visium / digital spatial profiling)",
            "Identifies CXCL12-CXCR4 as a candidate druggable interaction in chemoradiation-treated PDAC, suggesting a mechanism for treatment-induced immune-stromal remodeling",
            "Defines four cancer-associated fibroblast (CAF) subsets with distinct treatment-response signatures",
            "Establishes neural-progenitor-like malignant cell signatures as enriched in chemoradiation-treated tumors — a candidate marker of treatment-induced phenotype switching",
            "Argues for development of standard pipelines for cell-type segmentation/annotation on transcriptomic spatial data, mirroring the CODEX bioinformatic stack",
        ],
        "methods_summary": (
            "This is a 2-page Research Highlight commenting on Hwang et al. (Nat Genet 2022, "
            "54:1178-1191), not an original research article. It summarizes Hwang's experimental "
            "design: single-nucleus RNA sequencing plus digital spatial profiling on "
            "chemoradiation-treated and untreated PDAC tumors and organoids. Hwang's pipeline "
            "identified recurrent expression patterns that define cellular neighborhoods of "
            "malignant and fibroblast cells; CAF cell states were defined into four "
            "subpopulations (myofibroblastic, neurotropic, immunomodulatory, adhesive) and "
            "three major cellular clusters were spatially mapped to illustrate PDAC complexity."
        ),
        "key_findings": [
            "Hwang et al. defined four cancer-associated fibroblast (CAF) cell states: myofibroblastic, neurotropic, immunomodulatory, and adhesive [p1]",
            "Adhesive-CAF gene signature increase associated with poor survival in chemoradiation-treated PDAC patients [p1]",
            "Myofibroblast-CAF signature decreased in the chemoradiation treatment group versus controls [p1]",
            "Three-dimensional spatial mapping identified three major cellular clusters illustrating PDAC tumor complexity [p1]",
            "Increased CXCL12-CXCR4 receptor-ligand expression was identified in cancer-immune-cell interactions in the chemoradiation group, suggesting blocking this interaction could benefit chemoradiation-treated PDAC patients [p1]",
            "Malignant neural-like progenitor cellular signatures were enriched in chemoradiation-treated tumors, a candidate signal of treatment-induced phenotype switching [p1]",
            "The author calls for better cell segmentation and annotation pipelines for transcriptomic spatial data to advance precision-medicine drug discovery in PDAC [p1]",
        ],
        "extracted_references": [],
    },
}


# ---------------------------------------------------------------------------
# Lineage-arc narrator output (composed from the per-paper summaries above)
# ---------------------------------------------------------------------------

ARC_NARRATIVE = {
    "history": (
        "The cellular-neighborhood concept emerged from a confluence of multiplexed-imaging "
        "innovations between 2017 and 2018. [[10.1038_nmeth.4391|Schapiro 2017]] introduced "
        "histoCAT/miCAT and a permutation-test algorithm for statistically-significant "
        "cell-cell interactions in imaging mass cytometry, establishing the analytical "
        "vocabulary for tissue 'social networks.' "
        "[[10.1016_j.cell.2018.07.010|Goltsev 2018]] then operationalized the term *indexed "
        "niche* (i-niche) in the seminal CODEX paper on mouse spleen, showing that the ring "
        "of first-tier Delaunay neighbors around an index cell explains a significant fraction "
        "of marker-expression variance beyond cell-type identity. Together, these works "
        "established two foundations of the field — a scalable wet-lab modality (CODEX) and "
        "a quantitative framework for treating local neighborhoods as the unit of analysis."
    ),
    "development": (
        "The 2020-2022 development phase translated the CODEX/CN framework from "
        "method-establishment into a methodological ecosystem. "
        "[[10.1089_cmb.2019.0340|Chen 2020]] introduced Spatial-LDA, recasting cellular "
        "neighborhoods as soft topic-model mixtures with a spatial-coherence prior, and "
        "applied it both to Goltsev's mouse spleen CODEX and to a triple-negative breast "
        "cancer MIBI cohort, discovering a novel immunosuppressed CD45+/FoxP3+ tumor-boundary "
        "microenvironment. [[10.1038_s42003-022-04032-1|Lal 2022]] extended the cellular-"
        "neighborhood lens beyond imaging into spatially-resolved transcriptomics in PDAC, "
        "linking adhesive- and myofibroblast-CAF neighborhood states to chemoradiation "
        "outcome. By the close of this period, neighborhood-aware analyses were converging "
        "across CODEX, MIBI, IMC, and Visium-class data."
    ),
    "sota": (
        "The current state of the art (2023-2024) is defined by clinical-scale atlases and "
        "consolidated tooling. [[10.1126_sciadv.add1166|Mayer 2023]] published the largest "
        "CODEX atlas of ulcerative colitis (1.71M cells across 42 biopsies), identifying ten "
        "conserved CNs whose composition tracks Mayo severity and pinpointing TNFi-resistance-"
        "associated niches via a public cloud Explorer. [[10.1007_s00281-022-00974-0|"
        "Kuswanto 2023]] reviewed and structured the CODEX bioinformatic stack across "
        "cancer, autoimmunity and infection. [[10.1016_j.cell.2024.04.013|Bandyopadhyay "
        "2024]] extended the paradigm to human bone marrow with paired scRNA-seq + CODEX of "
        ">1.2M cells, mapping arterio-endosteal vs. adipocytic niches for myelopoiesis vs. "
        "HSPCs and revealing AML-specific MSC-blast neighborhoods. Finally, "
        "[[10.1371_journal.pcbi.1012344|Tao 2024]] released CNTools, unifying CC, CF-IDF, "
        "Spatial-LDA, ClusterNet and a new CNE method in a single benchmarked Python toolbox — "
        "marking the field's transition from method invention to method consolidation."
    ),
}


# ---------------------------------------------------------------------------
# Reader and narrator callbacks
# ---------------------------------------------------------------------------


def reader(task: SummarizationTask) -> dict:
    """Return the pre-composed summary JSON for this DOI."""
    doi = task.doi.lower()
    if doi in SUMMARIES:
        print(f"  [reader] returning summary for {doi}", flush=True)
        return SUMMARIES[doi]
    print(f"  [reader] WARN: no pre-composed summary for {doi} - returning empty (Tier-C-like)", flush=True)
    return {}


def narrator(task: ArcTask) -> dict:
    """Return the pre-composed arc paragraphs."""
    print(f"  [narrator] returning arc for topic={task.topic!r}", flush=True)
    return ARC_NARRATIVE


# ---------------------------------------------------------------------------
# Monkey-patch the Tier-A picker so our 8 papers get full-text reads
# ---------------------------------------------------------------------------


def _force_tier_a_picker(corpus, *, n):
    # Return our 8 forced DOIs, ignoring n.
    return [doi for doi in FORCE_TIER_A if doi in corpus.papers]


lineage_mod._pick_top_n_for_summarization = _force_tier_a_picker


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    started = time.time()

    # Re-run the full pipeline with our reader + narrator. The corpus
    # rebuild will hit the cache (PDFs and CrossRef refs from stage A
    # remain on disk), so this is faster than the cold start.
    print(f"Running run_lit_arc with reader+narrator callbacks", flush=True)
    print(f"  TOPIC = {TOPIC!r}", flush=True)
    print(f"  KB_ROOT = {KB_ROOT}", flush=True)
    print(f"  Forced Tier-A picks: {len(FORCE_TIER_A)}", flush=True)
    print(flush=True)

    result = run_lit_arc(
        TOPIC,
        kb_root=KB_ROOT,
        max_seeds=MAX_SEEDS,
        max_papers_to_summarize=MAX_PAPERS_TO_SUMMARIZE,
        reader=reader,
        narrator=narrator,
        _today=DATE_STR,
    )

    elapsed = time.time() - started
    print(flush=True)
    print(f"[DONE] run_lit_arc complete in {elapsed:.1f}s", flush=True)
    print(f"  topic = {result.topic}", flush=True)
    print(f"  arc_path = {result.arc_path}", flush=True)
    print(f"  search_log_path = {result.search_log_path}", flush=True)
    print(f"  corpus_size = {result.corpus_size}", flush=True)
    print(f"  pdfs_acquired = {result.pdfs_acquired}", flush=True)
    print(f"  summaries_written = {result.summaries_written}", flush=True)
    print(f"  duration_seconds = {result.duration_seconds:.1f}", flush=True)
    print(flush=True)

    # Verify: each forced Tier-A summary should exist on disk.
    print("Tier-A summary file existence check:", flush=True)
    for doi in FORCE_TIER_A:
        sp = summary_path(KB_ROOT, doi)
        marker = "OK" if sp.exists() else "MISSING"
        size = sp.stat().st_size if sp.exists() else 0
        print(f"  [{marker}] {doi}  ({size} bytes)  {sp}", flush=True)


if __name__ == "__main__":
    main()
