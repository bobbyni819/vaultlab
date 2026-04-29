---
name: statsmodels
description: Statistical models, hypothesis tests, multiple-testing correction, GLMs, mixed-effects, time series.
domains: [statistics, regression, glm, multiple-testing, mixed-effects]
install: pip install statsmodels
docs_url: https://www.statsmodels.org
---

# statsmodels


## Summary

Where `scipy.stats` stops being enough: regression with R-style formulas (`'y ~ x + C(group)'`), GLMs (logistic / Poisson / negative binomial), mixed-effects models for nested designs, multiple-testing correction (Benjamini-Hochberg), time-series models. The right tool when batch effects or repeated-measures structure matters.

Where scipy.stats stops being enough. Regression formulas, GLMs, mixed-effects models, multiple-testing correction.

## When to use

- Linear regression with formula strings (`'y ~ x1 + x2 + C(group)'`)
- GLMs (logistic, Poisson, negative binomial) for count data
- Multiple-testing correction (Benjamini-Hochberg / Bonferroni)
- Mixed-effects models for nested / repeated-measures designs
- Time-series models (ARIMA, SARIMAX) when relevant

## Key functions

- `import statsmodels.formula.api as smf`
- `smf.ols('y ~ x', data=df).fit()` — OLS
- `smf.glm('outcome ~ x', data=df, family=sm.families.Binomial()).fit()` — logistic
- `smf.mixedlm('y ~ x', data=df, groups=df.subject).fit()` — random-intercept mixed-effects
- `from statsmodels.stats.multitest import multipletests`
- `multipletests(pvals, method='fdr_bh')` — Benjamini-Hochberg FDR
- `from statsmodels.stats.contingency_tables import Table2x2; Table2x2(table).oddsratio_confint(0.05)` — odds-ratio CI

## Use-case examples

1. **Differential expression with covariates:** `smf.ols('expression ~ condition + batch', data=df).fit()` — handles batch effects.
2. **Count-data DE:** `glm` with `NegativeBinomial()` family for RNA-seq counts.
3. **FDR correction:** after a per-gene p-value vector, apply `multipletests(pvals, method='fdr_bh')[1]` for q-values.

## Notes for the LLM

- Formula strings use R-style syntax — `*` for interaction, `:` for plain interaction term, `C(x)` for explicit categorical.
- `fit()` returns a results object — call `.summary()` for the printed report; `.params`, `.pvalues`, `.conf_int()` for individual quantities.
- For paired/within-subject designs, mixed-effects (`mixedlm`) is correct, not OLS.
