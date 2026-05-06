---
name: explore-data
description: Pure exploratory data analysis on a CSV / parquet / DataFrame — multi-agent EDA + auto-lit-pointer for top finding. No hypothesis required.
arguments: <file-or-dataframe-path>
---

# /explore-data <file>

> "I have a CSV with 200 columns. Tell me what's interesting."

Pure EDA on a tabular dataset. Multi-agent meeting examines the data from four perspectives (analyst / domain_expert / methods_critic / synthesizer), surfaces 3-5 ranked "interesting findings" with statistical evidence per finding, and attaches a 1-paper literature pointer to the top finding so the user has a hook to start reading.

## Lineage

Lifts:
- **virtual-lab 4-role meeting** with structured-JSON-only output + bounded loops (Swanson Nature 2025)
- **scanpy / squidpy EDA conventions** — descriptive stats first, distributions, missingness, outliers, cardinality
- **PaperQA2 grounded summaries** for the auto-lit-pointer (Tier-A summary cited with `[pN]`)

## Pre-flight checklist

1. Resolve KB root + project config
2. **Read the file's first 10 rows + dtype** to detect data shape (long-form / wide-form / matrix)
3. Read `decisions-log.md` for any prior EDA conventions in this project (e.g., "we always log-transform metabolite intensities")
4. State-aware preflight: search `Output/eda-*<filename>*` for prior EDA runs — if recent, default to `--extend` (build on prior insights)

## Execution

### Step 1 — Descriptive stats pass

Compute via `pandas` + `scipy.stats`:

```python
{
    "n_rows": <int>,
    "n_cols": <int>,
    "dtypes": <dict>,
    "missingness_per_col": <dict>,
    "cardinality_per_col": <dict>,  # for object/categorical
    "summary_stats": <df.describe()>,
    "outlier_count_per_col": <z-score > 3 count>,
    "skewness_per_col": <dict>,
    "low_variance_cols": <list>,  # candidates for dropping
}
```

### Step 2 — Multi-agent meeting

| Role | Task |
|---|---|
| **analyst** | Given the descriptive stats: surface the 5 most-interesting structural patterns. Bimodality? Long-tail? Strongly correlated columns? Heavy missingness in a subset? Outliers? |
| **domain_expert** | Map each pattern to project domain context. *"This column's distribution looks like a typical lipid-class abundance signature; cf. metabolism KB concept doc on phospholipid-sphingolipid axis."* Cross-reference KB concept docs. |
| **methods_critic** | For each finding: are confounds plausible? What sub-stratification would test it (per-donor, per-tissue, etc.)? Rate evidence strength ROBUST / NEEDS_VALIDATION / WEAK. |
| **synthesizer** | Rank the surviving findings 1..N. For #1: propose a 1-paper literature search to ground it (will hand off to a low-cost lit pass). |

### Step 3 — Auto-lit-pointer for top finding

For finding #1 (synthesizer's recommendation), invoke a low-cost lit pass:

```python
from vaultlab.research import unified_search
results = unified_search(query=<synthesizer's query>, depth="fast", limit=3)
top_paper = results[0]  # cite this in the EDA doc
```

The result is a 1-paper pointer (DOI + 1-line summary + relevance) attached to the top EDA finding.

### Step 4 — Render output

Write to `<kb_root>/<project>/Output/eda-<filename-slug>-<date>.md`:

```markdown
# EDA: <filename>

Generated <date> by /explore-data.

## Top finding

**<finding 1 — synthesizer's #1 rank>**

Evidence: <statistical evidence — distribution stats, p-value if applicable>

Statistical strength: <ROBUST / NEEDS_VALIDATION / WEAK>

Domain context: <from domain_expert>

**Literature pointer:** <DOI> — <1-line summary> ([read](<KB-summary-path>))

What to do next: <synthesizer's "follow-up analysis" suggestion>

---

## Findings 2-5

(brief; same structure)

---

## Data summary

- <n_rows> rows × <n_cols> columns
- Missingness: <% NaN by col>
- Skew alerts: <cols with |skew| > 2>
- Outlier alerts: <cols with z > 3 count>

## Open questions for Bobby

<from synthesizer>
```

### Step 5 — Reply

*"5 findings ranked. **Top: <name>**. Stat strength: <strength>. Lit pointer: <doi>. Want me to <synthesizer's follow-up>?"*

## When to invoke

- User says *"explore this data"*, *"what's interesting in this CSV"*, *"poke around X dataset"*
- After receiving a new dataset from a collaborator
- Mid-project, when stuck on what to analyze next (overlap with `/next-analysis` — `/explore-data` if data-first, `/next-analysis` if hypothesis-first)

## When NOT to invoke

- Pre-registered hypothesis test (use the test directly via `vaultlab.stats`)
- Quick column-name sanity check (just print `df.columns`)
- The user already has a finding and wants to deepen it (use `/next-analysis` instead)

## Follow-up

If the user says yes to the synthesizer's follow-up suggestion, scaffold + run the proposed analysis. Auto role-pass with `methods_critic` before any concept doc gets written.
