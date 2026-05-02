# Paperclip integration design

**Status**: design approved 2026-05-02 by Bobby; implementation in progress.

**Goal**: integrate the [Paperclip](https://paperclip.gxl.ai) 8M-paper biomedical corpus + MCP server as a first-class source in vaultlab's literature pipeline, while preserving vaultlab's reproducibility, customizable ranking, and paywall-aware fallbacks.

## Why both

**Paperclip strengths** — pre-indexed corpus of 8M+ papers from bioRxiv + medRxiv + PubMed Central with full text already extracted into sections + figures + supplements; CLI + MCP server; regex / SQL primitives; AI map / reduce; vision on figures. Updated server-side. **Single fast OA full-text source.**

**Vaultlab strengths** — federated live search across 6 APIs (PubMed, Semantic Scholar, CrossRef, bioRxiv, Springer, Elsevier); reproducible composite scoring `(is_seed, has_pdf, og_score + forward_influence)`; recency quotas (REVIEW=30+30, STANDARD=15+10, SHORT=4+2); paywall-aware fallbacks; multi-domain (not biomed-locked). **Customizable, reproducible ranking layer.**

The two **stack** rather than compete. Paperclip becomes one of N parallel search sources at layer 1, and the first preferred source for layer 3 (acquisition) and layer 4 (reading). Vaultlab keeps owning ranking, paywall transparency, summary format, and arc composition.

## Architecture

```
6. Compose arc (vaultlab — review/standard/short scope)
5. Tier-A/B/C summaries (vaultlab + LLM — frontmatter, TL;DR, provenance)
4. Read papers
   ◆ paperclip: pre-extracted sections/{abs,intro,methods,results,discussion}
   ◆ vaultlab fallback: pdftoppm pages 1-10 from cached PDF
3. Acquire (extended waterfall)
   paperclip → Unpaywall → PMC → biorxiv → Springer (gated_metadata_only)
     → Elsevier (gated_pdf with key) → failed_paywalled / failed_not_indexed
2. Pick + rank (vaultlab — composite_score + recency_quota + seed pinning)
1. Search (federated parallel fan-out, DOI dedupe)
   paperclip + PubMed + S2 + CrossRef + bioRxiv + Springer + Elsevier
```

## Decision record (2026-05-02 with Bobby)

**Q1 — Paperclip in parallel or as primary?** **A: parallel.** Paperclip is one of 7 sources in the search fan-out, all run concurrently, DOI-deduped on output. Reproducibility preserved because vaultlab still sees all sources. Multi-domain queries (CS / physics) still work because the other 6 APIs cover non-biomed.

**Q2 — Whose ranking?** **A: vaultlab's composite score always overrides.** Paperclip returns a relevance-ranked list, but we re-rank by `(is_seed, has_pdf, og_score + forward_influence)` + recency quotas. Reproducibility-first; recency quotas continue to work. Blending paperclip's relevance signal as a feature is deferred to v2 if needed.

**Q3 — Trust paperclip's section extraction?** **A: trust.** Read paperclip's pre-extracted `sections/methods.txt`, `sections/results.txt`, etc. directly when available. Faster, more accurate (semantic sections vs. page numbers). Fall back to `pdftoppm` pages 1-10 only when paperclip doesn't have the paper.

**Q4 — Out-of-corpus handling.** **B: explicit transparency.** Mark papers paperclip doesn't have as `not_in_paperclip_corpus` and surface in the user-facing acquisition log so the user knows why this paper went through a slower path.

**Q5 — Auth UX for new researchers.** **B: graceful degradation.** Paperclip skipped if unauthenticated; only public APIs (PubMed / S2 / CrossRef / biorxiv) run. Print a one-line `ℹ️ Paperclip skipped (run paperclip login to enable)` message. First-run UX matters.

**Q6 — Domain detection.** **A: no detection.** Always run all 7 sources in parallel; cheap to send a query to a non-matching API and get zero results. Add domain hints later only if performance becomes an issue.

**Q7 — Product shape.** **α: feature inside existing vaultlab package.** Smallest reversible change. Paperclip becomes one tier in the existing waterfall; existing primitives (composite_score, recency_quota, AcquisitionResult) extend; the CLI grows two new flags (`--paperclip-only`, `--no-paperclip`) and one new subcommand (`fetch-list`).

## Code changes

| Module | Change | Risk |
|---|---|---|
| `vaultlab.research.paperclip_client` (new) | Thin wrapper around paperclip CLI binary OR HTTP MCP endpoint. Methods: `search()`, `get_paper()`, `get_section()`, `is_authenticated()`. | Low — additive |
| `vaultlab.research.search` | Add paperclip as a parallel source in the `MultiSource` fan-out. Skip silently if `is_authenticated()` is False. | Low — additive |
| `vaultlab.research.acquisition.AcquisitionResult` | Extend with classified outcomes: `paperclip_full_text \| oa_pdf \| gated_pdf \| gated_metadata_only \| failed_paywalled \| failed_not_indexed \| not_in_paperclip_corpus` | Medium — touches every caller |
| `vaultlab.research.acquisition.acquire_pdf` | New top tier: paperclip first; on miss → existing waterfall. `not_in_paperclip_corpus` is a *miss-with-explanation*, not a failure. | Medium — touches the central waterfall function |
| `vaultlab.research.read_paper` (new) | Dispatcher: if `paperclip_full_text` source → read sections; else → `pdftoppm` pages 1-10. | Low — new function, callers opt in |
| `vaultlab.research.policy_skip` (new) | When LLM refuses a paper: write `tier: skipped_policy` stub, append to `<project>/policy_skipped.json`, continue. | Low — new pattern |
| CLI: `vaultlab fetch-list paywalled` (new) | Emit manual-fetch shopping list of `failed_paywalled` DOIs grouped by likely source (Nature / Cell / Springer / Elsevier) with proxy-URL hints. | Low — new subcommand |
| CLI: `vaultlab list-policy-skipped` (new) | Emit papers the LLM refused to read, for human review. | Low |
| CLI: `vaultlab paperclip-grep` / `paperclip-sql` | Power-user passthroughs to paperclip's regex + SQL primitives. | Low |
| `vaultlab search` CLI | New flags: `--paperclip-only`, `--no-paperclip` | Low |

## Implementation order

1. **`paperclip_client` module** — wraps paperclip CLI / MCP. Auth detection. (Foundational.)
2. **`AcquisitionResult` outcome taxonomy** — extend with the 7-state failure classifier. Update existing callers to populate the new field. (Touches everything; do early so subsequent layers can rely on it.)
3. **Paperclip as a search source** — parallel fan-out. Smallest user-visible win.
4. **Paperclip as acquisition tier** — top of waterfall. Gives full-text fast-path for biomed papers.
5. **Section-aware reading** — `read_paper` dispatcher. Tier-A summaries become higher-quality.
6. **`fetch-list paywalled` + `list-policy-skipped` CLI** — paywall transparency + skip-on-refusal report.
7. **Power-user passthroughs** — `paperclip-grep` / `paperclip-sql`.

Each step is a separate commit with tests; each is independently shippable.

## Tests required

- `paperclip_client`: mock the MCP HTTP responses; test auth-detection happy path + unauthenticated path.
- `AcquisitionResult`: extend test to cover all 7 outcome states.
- `acquire_pdf`: extend `test_acquisition.py` to cover paperclip-full-text + paperclip-miss + paperclip-skipped-due-to-no-auth paths.
- `read_paper`: test the dispatcher chooses the right source based on `AcquisitionResult.source`.
- `policy_skip`: test the skip-and-continue pattern; verify `<project>/policy_skipped.json` is written.
- CLI: snapshot tests of `fetch-list paywalled` and `list-policy-skipped` output.

## Compatibility / migration

- Existing arcs continue to work without paperclip (degraded, since paperclip is a new tier, not a replacement).
- Existing `AcquisitionResult` JSON is forward-compatible — the new `outcome` field is additive; old `source: "failed"` records are interpreted as `failed_unspecified` until migrated.
- No breaking changes to the CLI surface; new flags are opt-in.

## Known limitations discovered during demo (2026-05-02)

* **Two separate auth stores in paperclip 0.3.0.** The MCP server (`https://paperclip.gxl.ai/mcp`) uses Claude Code's OAuth flow and stores credentials in Claude Code's config. The CLI (`paperclip` binary) uses its own browser-based device flow and stores credentials in `~/.paperclip/`. **They do not share auth state.** A user who completes MCP auth via Claude Code still has to run `paperclip login` (or set `PAPERCLIP_API_KEY`) for vaultlab's Python-library subprocess calls to work. Documented in `paperclip_client` source. Worth filing an upstream issue to unify.
* **Windows console encoding bug in `paperclip config` 0.3.0.** Click traceback on stderr from a Unicode character (`✓`) in an output line. `paperclip config` exits non-zero on Windows even when authenticated; we work around this by checking `~/.paperclip/credentials.json` directly and falling back to optimistic-default for `is_authenticated()`.
* **Paperclip CLI device-code login on Windows is opaque.** `paperclip login` doesn't print a code to the terminal in a way that's reliably visible — likely a TTY/buffering issue. The MCP OAuth flow (browser-based) works correctly. For users who want both MCP and CLI auth, the Python `webbrowser` module + cached token write may be a future fix.

## Open questions for implementation

- Does paperclip's MCP HTTP endpoint expose `search` / `get_paper` / `get_section` as separate tools, or does the user invoke `paperclip search` via a generic `bash` tool? Answer affects whether `paperclip_client` calls MCP tools directly or shells out.
- Paperclip update cadence — file an issue on `GXL-ai/paperclip` to ask. Important for telling users "your paperclip results are at most 24h old" or whatever.
- Rate limits on paperclip MCP HTTP endpoint — TBD; need to test.
- Does paperclip return `og_score` and `forward_influence` analogues, or only relevance? If it only returns relevance, citation-graph metrics need to come from S2 / CrossRef separately for paperclip-sourced DOIs.

## Public-repo documentation tie-in

When this lands, the README needs:
- "Getting started" section with paperclip auth + 6-API-key walkthrough
- Tier-model explainer (A / B / C)
- Worked example end-to-end
- Paywall-transparency story (the `fetch-list paywalled` output) — no more silent failures
- Known limitations doc updated

## Empirical demo runs (2026-05-02)

After auth completed, two demo runs validated the parallel-source design:

### Demo 1 — search comparison

`paperclip search "spatial proteomics CODEX multiscale tissue computational" -n 15` returned **8 papers vaultlab's 5-sub-query × 50-result × 6-API run did NOT pick up**, including:

* **Hickey 2021 multiplex-imaging primer** (`arx_2107.07953`) — Bobby's own advisor's methods foundation paper, missed because arXiv isn't queried by our PubMed/S2/CrossRef stack
* **KRONOS foundation model 2025** (`arx_2506.03373`) — 2025 SOTA foundation model for spatial proteomics
* **VirTues 2025** (`arx_2501.06039`) — marker-aware foundation model with zero-shot panel transfer
* **Klingeberg 2025** (`bio_3ac44def6d63`) — 100+ spatial proteomes/day workflow
* **Horvath/Coscia 2025** (PMC12130312) — recent spatial proteomics translational review
* **DBiTplus 2024** (`bio_3b9c75ca6d7b`) — imaging+sequencing on same tissue section
* **SPOTS 2022** (`bio_6c7627536d44`) — integrated protein+transcriptome spatial
* **SM-Omics 2020** (`bio_ac9f36506ca1`) — high-throughput spatial multi-omics platform

**Coverage gap source**: vaultlab's existing federated search hits PubMed + S2 + CrossRef + bioRxiv + Springer + Elsevier. Paperclip additionally indexes **arXiv preprints** and offers a different relevance ranking on bioRxiv/medRxiv/PMC. arXiv coverage alone explains 3 of the missed papers (Hickey primer, KRONOS, VirTues).

### Demo 2 — `map` AI-reader primitive

`paperclip map --from <search_id> "Does this paper integrate spatial proteomics with multiscale modeling?"` ran across 10 papers in 11.4 seconds. Result: **0/10 of "multiscale lung infection" papers in paperclip's corpus integrate spatial proteomics with multiscale modeling**. Empirical confirmation of the thesis gap statement in the lineage arc.

### Implications for implementation

* **Paperclip absolutely is the 7th parallel source** — it surfaces both methods-foundation papers our advisor wrote AND 2025 SOTA we missed.
* **Map / reduce primitives are operationally faster than vaultlab's per-paper LLM loop** — 10 papers in 11s vs. our subagent-per-batch architecture taking ~20-40 min per batch. Worth integrating as an optional fast path for some Tier-A read use cases (probably not all — paperclip's lightweight model may produce shallower summaries than full-pages-1-10 reads with Claude).
* **arXiv coverage** is a meaningful non-overlap with our existing stack. Even after paperclip integration, adding arXiv directly to vaultlab (via the arXiv API) is worth doing for non-biomed work.

## Reference

- Paperclip upstream: <https://github.com/GXL-ai/paperclip>
- Paperclip docs: <https://paperclip.gxl.ai>
- Bobby's fork: <https://github.com/bobbyni819/paperclip>
- Policy-refusal incident from 2026-05-02 motivating the `policy_skip` pattern: `claude-config/Sources/Notes/policy-refusal-on-host-pathogen-batch-2026-05-02.md`
