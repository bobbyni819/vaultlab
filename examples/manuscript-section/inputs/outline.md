# Results — Spatial-niche signatures predict immune infiltration

We analyzed spatial transcriptomics data from 12 NSCLC donors to test
whether reproducible niche-level signatures track with intra-tumoral
immune composition. Three observations follow.

## Niche identity is reproducible across donors

We identified 8 transcriptomic niches by clustering 55-µm spatial spots
on shared marker programs [FIG:1]. Niche identity was reproducible
across donors (Spearman ρ = 0.81, n = 12 donors), with the three
tumour-associated niches showing the lowest within-donor variance
(Smith et al., 2024).

It is important to note that two niches — the tumour-stromal interface
(N4) and the tertiary-lymphoid-structure niche (N7) — were detected in
every donor analyzed, while the rare hypoxic-core niche (N8) appeared
in only 4 of 12 donors. We characterized the cellular composition of
each niche using deconvolution against a published reference (Park et al., 2023).

## Immune infiltration tracks niche composition

To quantify the relationship between niche composition and immune
infiltration, we computed per-donor CD8 T-cell density in matched
sections [FIG:2]. Donors with elevated N7 prevalence showed 2.4-fold
higher CD8 density compared to N7-low donors (P = 0.003, Wilcoxon rank
sum). The effect was robust to bootstrap resampling over both spots
and donors (95 % CI: 1.6–3.1).

In contrast, N4 prevalence showed no association with CD8 density
(P = 0.41), suggesting that the tumour-stromal interface alone is
insufficient to drive infiltration. This is consistent with prior
single-cell observations (Jones and Patel, 2022).

## Synthesis

Together these data support a model in which a small number of
reproducible spatial niches — rather than overall tumour heterogeneity —
account for between-donor variability in immune infiltration. We
discuss the mechanistic implications in the next section.
