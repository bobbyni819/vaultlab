---
name: pingouin
description: Statistical tests with effect sizes, 95% CIs, and Bayes factors as default outputs. Friendlier than scipy.stats for reporting.
domains: [statistics, effect-sizes, hypothesis-testing]
install: pip install pingouin
docs_url: https://pingouin-stats.org
---

# pingouin


## Summary

Statistical tests that return p-values, effect sizes, and 95% CIs in one call — paper-ready output without manual bootstrap. T-tests, Mann-Whitney, correlations, ANOVA + repeated-measures ANOVA, linear regression. Returns one-row DataFrames easy to concatenate. Use when you need Cohen's d / eta-squared alongside the p-value.

Returns p-values, effect sizes, AND confidence intervals from one call — rather than scipy's bare-bones p-value-only output. Good for paper-ready statistical tables.

## When to use

- Group comparisons where you need effect sizes alongside the p-value
- Reporting confidence intervals for correlations / regression slopes
- ANOVA / repeated-measures ANOVA with effect-size eta-squared
- Bayes factors (helpful for "is the difference negligible?" framing)

## Key functions

- `pg.ttest(a, b)` — t-test → DataFrame with t, dof, p, CI95%, Cohen's d, BF10, power
- `pg.mwu(a, b)` — Mann-Whitney → effect-size r-rank-biserial
- `pg.corr(x, y, method='pearson')` — correlation → r, CI, p, power, BF10
- `pg.anova(data=df, dv='y', between='group')` — one-way ANOVA + eta-squared
- `pg.rm_anova(data=df, dv='y', within='condition', subject='id')` — repeated-measures ANOVA
- `pg.linear_regression(X, y)` — regression with CI on coefficients
- `pg.compute_effsize(a, b, eftype='cohen')` — standalone effect-size compute

## Use-case examples

1. **Two-group DE with effect size:** `pg.ttest(group_a, group_b)` returns Cohen's d alongside the p-value — both go into the figure caption.
2. **Repeated-measures across timepoints:** `pg.rm_anova` with subject-id column; one call produces the full ANOVA table.
3. **Correlation reporting:** `pg.corr(x, y)` returns 95% CI on r — paper-ready without manual bootstrap.

## Notes for the LLM

- pingouin output is always a one-row DataFrame — easy to concatenate into summary tables.
- Effect-size types: `'cohen'` (Cohen's d), `'hedges'` (Hedges' g, small-sample-corrected).
- Bayes factor `BF10`: > 3 typically interpreted as "moderate" evidence FOR the alternative; < 1/3 against.
