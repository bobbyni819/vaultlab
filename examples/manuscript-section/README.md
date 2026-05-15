# Manuscript Section

**What this does:** Take a bullet outline plus a few figure images and produce a
draft Results section (markdown) with an automatic polish pass and a citation
audit. Demonstrates `vaultlab.manuscript` + `vaultlab.citations` composed
end-to-end without an LLM.

**Primitives composed:**

- `vaultlab.manuscript.polish.check_sentence_length(text, max_words=30)` — flags long sentences for review.
- `vaultlab.manuscript.polish.check_us_spelling(text)` — surfaces US → UK spelling pairs.
- `vaultlab.citations.audit_file(path)` — extracts every (Author, Year) / DOI / PMID citation, returns an `AuditReport`.

A short deterministic regex-based "mock polish" (`_mock_polish` in `run.py`)
stands in for an LLM call. Real workflows would route through the
`vaultlab.manuscript.polish.POLISH_RULES` × `WORKFLOW_STEPS` flow guided by
Claude.

**Run:**

```bash
python run.py
```

**Outputs land in:** `./out/` (created on first run; not committed).

`./out/` contains:

- `section.md` — assembled + lightly-polished Results section
- `polish_findings.md` — long sentences + residual US spellings flagged by `vaultlab.manuscript.polish`
- `section.audit.json` — citation-audit JSON dump (extraction only, no API verification)

**Inputs:** synthetic — see "Inputs format" below.

- `inputs/outline.md` — markdown outline with `[FIG:1]` / `[FIG:2]` callouts and 3 author-year citations.
- `inputs/figures/fig1_niche_heatmap.png` — synthetic 8-niche × 12-marker heatmap (matplotlib, ~20 KB).
- `inputs/figures/fig2_cd8_vs_n7.png` — synthetic scatter + regression (~26 KB).

The scientific content is fabricated for demo purposes; the citations
("Smith et al., 2024", "Park et al., 2023", "Jones and Patel, 2022") are
intentionally generic so the audit's "unverified" status is the *expected*
output.

**Adapt this:**

- Swap `inputs/outline.md` and `inputs/figures/` for your own.
- Outline format: any markdown. `[FIG:<n>]` tokens map to figure files
  positionally (`[FIG:1]` → first file in alphabetic order).
- For a real audit, pass `research_client=ResearchClient()` into
  `audit_file()` and supply a `kb_dir` — citations gain
  `verified_fulltext` / `verified_abstract` / `api_confirmed` statuses.
- Replace `_mock_polish` with an LLM-driven polish step keyed on
  `vaultlab.manuscript.polish.POLISH_RULES`.

**Reference output:** see `expected_outputs/` — fixed sample of what
`run.py` produces with the bundled inputs.
