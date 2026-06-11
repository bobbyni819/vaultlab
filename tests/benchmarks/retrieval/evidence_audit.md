# Evidence-index audit — `citations/evidence.py` vs the retrieval benchmark

Each of the **12** benchmark tuples (`tuples.jsonl`, all `verified:false`) was looked up through `EvidenceIndex.lookup(source_doi, claim)` — the exact-match (normalize-then-equal) path, unchanged. No fuzzy/semantic matching was added.

## Headline

| KB root | hits / total | dominant failure mode |
|---|---|---|
| configured (`resolve_kb_root`) | **0 / 12** | index file absent (no .evidence_index.json exists in this KB) |
| corpus (`corpus_meta.kb_root`) | **0 / 12** | index file absent (no .evidence_index.json exists in this KB) |

**Plainly: evidence.py found the correct source for 0 of 12 benchmark claims in the configured KB** (and 0 of 12 in the corpus KB where the claims were mined).

## Configured KB — `/Users/arnav/vaultlab-kb`

- `.evidence_index.json` present: **False** (`/Users/arnav/vaultlab-kb/Sources/.evidence_index.json`)
- Index contents: 0 papers / 0 claims; 0 distinct DOIs indexed
- Outcome counts (nothing dropped silently):
  - hits: **0**
  - miss — index-lacks-entry (DOI absent): **12**
  - miss — normalization/exact-match failed (DOI indexed, claim unmatched): **0**
  - tuples silently skipped: **0** (all 12 scored)

## Corpus KB — `/Users/arnav/Library/CloudStorage/GoogleDrive-arnav.k.dhar@gmail.com/.shortcut-targets-by-id/1TOJkACpypCeQmNSe0-zftJqVjiP9zFJP/dataplus`

- `.evidence_index.json` present: **False** (`/Users/arnav/Library/CloudStorage/GoogleDrive-arnav.k.dhar@gmail.com/.shortcut-targets-by-id/1TOJkACpypCeQmNSe0-zftJqVjiP9zFJP/dataplus/Sources/.evidence_index.json`)
- Dot-path/Drive-shortcut KB: `evidence.py` reads it via `os.path`, so it is **not skipped** (unlike the TF-IDF collector). Presence reported above.
- Index contents: 0 papers / 0 claims; 0 distinct DOIs indexed
- Outcome counts (nothing dropped silently):
  - hits: **0**
  - miss — index-lacks-entry (DOI absent): **12**
  - miss — normalization/exact-match failed (DOI indexed, claim unmatched): **0**
  - tuples silently skipped: **0** (all 12 scored)

## Per-tuple result (configured KB)

| DOI | mode | claim |
|---|---|---|
| `10.1172/JCI15950` | miss:index-lacks-entry | Detectable NK cytokine secretion could be achieved upon costimulation … |
| `10.4049/jimmunol.1201528` | miss:index-lacks-entry | IL-12 alone induced a plateau of approximately 40% of NK cells express… |
| `10.1084/jem.20212434` | miss:index-lacks-entry | Low IL-12 concentrations are sufficient to induce expansion of human N… |
| `10.3390/antib12030044` | miss:index-lacks-entry | At the lower limit of p > 0.005 for CD107a detection with antibody, 0.… |
| `10.3390/antib12030044` | miss:index-lacks-entry | An EC50 of 0.22 ng/mL (1.5 × 10⁻¹² M) for the GA101-GE glycoengineered… |
| `10.1007/s00262-024-03824-0` | miss:index-lacks-entry | IgA antibodies might require a higher level of antigen expression to e… |
| `10.4049/jimmunol.1701500` | miss:index-lacks-entry | An individual NK cell needed only 2 to 4 degranulation events, on aver… |
| `10.4049/jimmunol.1701500` | miss:index-lacks-entry | Primary human NK cells contain 63±23 perforin-positive lytic granules … |
| `10.1084/jem.20181454` | miss:index-lacks-entry | The serial killing activity differed between individual NK cells, with… |
| `10.1084/jem.20181454` | miss:index-lacks-entry | NK cells release approximately 10% of their total granules in a single… |
| `10.3389/fimmu.2023.1133796` | miss:index-lacks-entry | Combination therapy with 5×10⁴ NK cells and avelumab or trastuzumab re… |
| `10.2147/ITT.S61292` | miss:index-lacks-entry | Glycoengineered antibodies can elicit up to a tenfold increase in ADCC… |

## Interpretation

The exact-match approach is only as good as what `/cite-watch` has previously stored: a claim hits only if that exact paper+claim was verified before and the claim string matches after `.strip().lower()`. With no `.evidence_index.json` present, the index is structurally empty and every lookup misses as *index-lacks-entry* — this is a coverage finding, not a normalization failure. Improving recall (populating the index, or fuzzy/semantic matching) is a separate decision the user owns.

