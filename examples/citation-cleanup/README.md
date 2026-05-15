# Citation Cleanup

**What this does:** Take a draft markdown manuscript with mixed-quality
citations and emit a remediation report classifying each citation by quality
signal — without making any API calls. This is the cheap, deterministic
pre-pass that runs before any LLM- or research-client-driven verification.

**Primitives composed:**

- `vaultlab.citations.extract_citations(path)` — pulls every `(Author, Year)`, `Author et al. (Year)`, `DOI:` and `PMID:` citation from a markdown file, with line numbers and claim context.
- Local `_classify(citation, current_year)` heuristic — bucket each into `ok` / `review` / `critical` based on DOI shape and year plausibility.

**Run:**

```bash
python run.py
```

Optional:

- `--draft PATH` — audit a different file (default `inputs/draft.md`)
- `--out PATH` — change output directory (default `./out/`)

**Outputs land in:** `./out/` (created on first run; not committed).

`./out/` contains:

- `audit_report.md` — human-readable remediation report with per-citation actions
- `audit_report.json` — same data, machine-readable

**Inputs:** synthetic. `inputs/draft.md` is a fabricated 10-citation draft
designed to exercise every classifier branch:

- 2 well-formed DOIs (one inline `DOI:`, one `doi:` lowercase)
- 1 PMID
- 5 author-year citations (no DOI)
- 1 implausible-year citation (`Doe et al., 2099`)
- 1 century-stamped citation (`Lee 1822`) for the historical-year edge case
- 1 truly-malformed `DOI: not-a-real-doi-string` — this is silently
  **dropped** by the extractor (it only matches `10.xxxx/...`-shaped DOIs).
  See "Known limits" below.

The draft is intentionally synthetic; real citations would carry
verifiable identifiers.

**Adapt this:**

- Swap `inputs/draft.md` for any markdown with citations.
- Extend `_classify` in `run.py` to add new rules — anything returning
  `(severity, action)` slots into the report.
- For a *verifying* audit (queries CrossRef / PubMed / Semantic Scholar),
  use `vaultlab.citations.audit_file(path, research_client=ResearchClient())`
  instead. See the "Next steps" block printed in `audit_report.md`.

**Known limits:**

- The extractor's DOI regex requires a `10.<digits>/<rest>` shape. Strings
  like `DOI: not-a-real-doi-string` are silently dropped. Improving
  malformed-DOI surfacing would be a good first contribution — file an
  issue with the malformed pattern you'd like caught.
- Multi-line citations (an author and year split across a line break) are
  also missed; the extractor is line-oriented.

**Reference output:** see `expected_outputs/` — fixed sample of what
`run.py` produces with the bundled inputs.
