---
name: scipy.stats
description: Probability distributions, statistical tests, and descriptive statistics. The default Python statistics library.
domains: [statistics, hypothesis-testing, distributions]
install: included with scipy (pip install scipy)
docs_url: https://docs.scipy.org/doc/scipy/reference/stats.html
---

# scipy.stats

The Python statistics workhorse. Hypothesis tests, distributions, descriptive statistics.

## When to use

- Compare two distributions / groups (t-test, Wilcoxon, KS)
- Compute correlations (Pearson, Spearman, Kendall)
- Fit / sample from probability distributions
- Compute p-values + 95% CIs

## Key functions

- `scipy.stats.ttest_ind(a, b, equal_var=False)` — Welch's t-test (default)
- `scipy.stats.mannwhitneyu(a, b, alternative='two-sided')` — non-parametric two-sample
- `scipy.stats.wilcoxon(a, b)` — paired non-parametric
- `scipy.stats.kstest(a, 'norm')` — Kolmogorov-Smirnov vs distribution
- `scipy.stats.pearsonr(x, y)` — correlation + p-value
- `scipy.stats.spearmanr(x, y)` — rank correlation
- `scipy.stats.fisher_exact(table)` — 2×2 contingency table
- `scipy.stats.bootstrap((data,), statistic=np.mean, n_resamples=10000, confidence_level=0.95)` — bootstrap CI

## Use-case examples

1. **Two-group differential expression (small n):** Mann-Whitney U via `mannwhitneyu`; report effect size separately (e.g., Cliff's delta).
2. **Marker correlation:** `spearmanr` for rank correlation between two genes across cells.
3. **Bootstrap CI for a custom statistic:** `bootstrap` with your own callable; returns BootstrapResult with `confidence_interval` attribute.

## Notes for the LLM

- For DE, prefer `pingouin` or `statsmodels` if you need effect sizes + CI in the same call. `scipy.stats` is bare-bones.
- `ttest_ind(equal_var=True)` is rarely correct — Welch's (False) is the better default unless equal-variance is verified.
- Multi-test correction: `statsmodels.stats.multitest.multipletests` (not in scipy).
