# Retrieval Benchmark v0 — `bm25` backend recall@k

> All corpus tuples are `verified: false` — these numbers are pending the user's review of `tuples.jsonl`.

## Headline

| metric | value | hits/total |
|---|---|---|
| recall@1 | 1.000 | 12/12 |
| recall@5 | 1.000 | 12/12 |
| recall@20 | 1.000 | 12/12 |

## How to read this number

**Caveat — claim_source_colocation.** every cited DOI lives in the SAME .md file as the claim (no separate per-paper source docs exist). So search(kb, claim) retrieves that file, which contains the DOI -> near-guaranteed hit. Recall here is an inflated UPPER BOUND ('can TF-IDF re-find the document a claim was copied from'), NOT true cross-doc citation retrieval.

## Configuration

- Backend: `vaultlab.kb.semantic_search.search` (backend=`bm25`, default subdirs)
- Search KB root (corpus): `/Users/arnav/Library/CloudStorage/GoogleDrive-arnav.k.dhar@gmail.com/.shortcut-targets-by-id/1TOJkACpypCeQmNSe0-zftJqVjiP9zFJP/dataplus`
- Configured KB root (`resolve_kb_root`): `/Users/arnav/vaultlab-kb`
- recall@k = (#tuples whose `source_doi` substring appears in the text of any top-k returned file) / 12

## Per-tuple result @k=5

| hit | source_doi | first rank | claim |
|---|---|---|---|
| ✅ | `10.1172/JCI15950` | 1 | Detectable NK cytokine secretion could be achieved upon costimulation with only … |
| ✅ | `10.4049/jimmunol.1201528` | 1 | IL-12 alone induced a plateau of approximately 40% of NK cells expressing CD25 a… |
| ✅ | `10.1084/jem.20212434` | 1 | Low IL-12 concentrations are sufficient to induce expansion of human NK cells.… |
| ✅ | `10.3390/antib12030044` | 1 | At the lower limit of p > 0.005 for CD107a detection with antibody, 0.16 ng/mL, … |
| ✅ | `10.3390/antib12030044` | 1 | An EC50 of 0.22 ng/mL (1.5 × 10⁻¹² M) for the GA101-GE glycoengineered antibody.… |
| ✅ | `10.1007/s00262-024-03824-0` | 1 | IgA antibodies might require a higher level of antigen expression to efficiently… |
| ✅ | `10.4049/jimmunol.1701500` | 1 | An individual NK cell needed only 2 to 4 degranulation events, on average, to me… |
| ✅ | `10.4049/jimmunol.1701500` | 1 | Primary human NK cells contain 63±23 perforin-positive lytic granules per cell.… |
| ✅ | `10.1084/jem.20181454` | 1 | The serial killing activity differed between individual NK cells, with the major… |
| ✅ | `10.1084/jem.20181454` | 1 | NK cells release approximately 10% of their total granules in a single killing e… |
| ✅ | `10.3389/fimmu.2023.1133796` | 1 | Combination therapy with 5×10⁴ NK cells and avelumab or trastuzumab resulted in … |
| ✅ | `10.2147/ITT.S61292` | 1 | Glycoengineered antibodies can elicit up to a tenfold increase in ADCC against c… |

## Mining audit — 6 candidates skipped

Nothing was dropped silently. Each candidate below was considered during mining and excluded for the stated reason:

- **Hamada 2024 - 'CD89 protein expression on circulating NK cells is infrequent...' (and IgA1 inhibition quote)** — cited with PMC11323182 only; no 10.xxxx DOI string present in the file, so unscorable against a DOI-substring hit. 2 quote candidates dropped.
- **Trinchieri 2003 (10.1038/nri1001) for IL-12 1.55 ng/mL** — negative citation: the file explicitly states the value is NOT in the paper and 'Do not cite Trinchieri 2003 for this value.'
- **Busfield 2014 (10.1038/leu.2014.128) for ADCC threshold 16.6 ng/mL** — negative citation: the file flags the existing parameters.py citation as invalid for this value.
- **Chung 2014 JVI (10.1128/JVI.02506-14) for 2-5x ADCC enhancement** — paywalled / unverified: 'remains unverified; do not rely on it without access to the full text.'
- **Jegaskanda 2019 (10.1128/jvi.02090-18) influenza ADCC** — no claim extracted: 'Not yet fetched for exact values' - no direct quote or quantitative claim in the file.
- **week3-nk_parameter_inconsistencies.md paraphrase entries (Parihar/Lee summaries)** — author paraphrase, not a verbatim source quote; the underlying DOIs are already covered by direct-quote tuples. Dropped to keep precision over volume.

