# Figure-text consistency checker

`vaultlab.manuscript.figure_text_consistency` runs deterministic checks that
compare manuscript prose with the claim ledger and publication-figure coverage
manifests. It does not call an LLM or the network.

## API

```python
from vaultlab.manuscript import check_figure_text_consistency

report = check_figure_text_consistency(
    manuscript_md,
    ledger=ledger,
    figures_dir="figures",
    coverage_dir="figures",
)
```

The report is a `ConsistencyReport(ok, problems)` and serializes with
`to_dict()`. Each `ConsistencyProblem` has one of four kinds:

- `missing_figure`: a referenced figure has no `<id>.png`, `<id>.svg`,
  `<id>.pdf`, or `<id>.coverage.json` in the supplied directories.
- `cut_figure`: a ledger-linked figure is not mentioned in prose, or a figure
  file/coverage sidecar exists but is not referenced in prose.
- `number_mismatch`: prose states a numeric value for the same quantity name as
  a `NumericLink`, or a linked coverage manifest does, but the values differ.
- `identity_contradiction`: the same identity entity, such as an m/z value, is
  associated with different labels in prose and coverage metadata.

Absence is not treated as contradiction. If the prose omits a number or label,
or the coverage manifest has no comparable statement, the checker skips that
comparison.

## Figure callout grammar

`find_figure_callouts(text)` returns `FigureCallout` entries with
`figure_id`, optional `panel`, source line, and source type.

It detects:

- claim-ledger figure tags parsed with `claim_ledger._TAG_RE`, such as
  `[FIG:5]` and `[FIG:5 panel=C]`
- natural prose references such as `Figure 5`, `Figure 5C`, `Fig. 6`,
  `Fig 5c`, `(Fig. 5C)`, and `Figures 5 and 6`

Natural prose references split a trailing panel letter from the figure token:
`Figure 5C` becomes `figure_id="5", panel="C"`.

## Composition with existing vaultlab data

The checker reuses:

- `ClaimLedger` for manuscript claim, figure, and numeric links
- `NumericLink` and `FigureLink` for claim-level evidence comparisons
- `CoverageManifest.read_json()` for `<id>.coverage.json` sidecars
- `CoverageManifest.footer`, `footer_text()`, `params`, and `analysis_params`
  as figure-side text for identity and numeric comparisons

When no ledger is supplied, the checker builds one with
`ClaimLedger.from_markdown(manuscript_md)`.

## Identity heuristic and limits

The default identity pattern extracts m/z entities:

```text
m/z\s*(?P<entity>[0-9]+\.[0-9]+)
```

For each entity, the checker looks for a nearby explicit label cue
(`as`, `labelled`, `labeled`, `annotated as`, `identified as`) or an immediate
class-like token. The built-in label filter is deliberately conservative: it
accepts common lipid-style labels such as `PI`, `PC`, `PE`, `PS`, `LPI`,
`sulfatide`, and uppercase class tokens, while ignoring generic prose words.

This is a heuristic screen, not ontology reasoning. It is designed to catch
real contradictions such as a figure footer saying `m/z 553.28 sulfatide` while
the manuscript calls the same entity `PI`. It should not be interpreted as
evidence that an omitted label is wrong, and it does not resolve synonyms unless
their normalized text matches.
