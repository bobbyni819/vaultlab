# vaultlab tools index

Curated, source-cited markdown documentation of the Python packages vaultlab wraps. **Claude Code reads these files** when picking tools for a user request — no raw web searches at runtime.

> **Status:** v0.0.1 scaffold. The first 5 priority pages (scanpy, squidpy, scipy.stats, statsmodels, scikit-image) land in v0.1.0 via the `vaultlab tools-index build` CLI. See `G:/My Drive/Knowledge/vaultlab/Sources/Notes/vaultlab-ideation-2026-04-28/08-centralized-memory-and-tools-index.md` for the build methodology.

## Why this exists

When Claude Code (or vaultlab itself) needs to pick the right Python tool for a task, the default behavior is to **search the web** for `"how to do X in Python"` and pick something. That's wasteful (every session re-searches) and risky (Claude can hallucinate function names that don't exist).

vaultlab's tools index is the curated alternative:
- Each page condenses the official package docs into a single markdown file
- Frontmatter lists canonical-doc URL, version tested, modality, sources consulted
- A footer explicitly cites where the content came from
- Claude reads the page, picks the right function, calls it with confidence

**The rule:** if a function isn't in this index, Claude Code should treat it as suspect (might not exist; check the live docs).

## Curation rules

When adding a new tool page:

1. **Source must be the official package docs.** Not a Stack Overflow answer or an LLM-generated tutorial.
2. **Cite specific URL anchors.** *"`sc.pp.normalize_total` per https://scanpy.readthedocs.io/en/stable/api/scanpy.pp.normalize_total.html"* — not just *"scanpy normalizes counts."*
3. **Include version tested.** Frontmatter `version_tested: scanpy 1.10.2`. Future updates rerun the curation.
4. **Hedged voice.** *"Typical default is `method='wilcoxon'`"* not *"`method='wilcoxon'` is best."*
5. **Note alternatives explicitly.** *"For deep-learning normalization, scvi-tools provides..."* — helps Claude pick the right tool, not just the first one.
6. **Failure modes.** What goes wrong with this tool? *"Don't use raw counts after `log1p`; pull from `adata.raw` if needed."*

## Methodology (planned for v0.1.0)

The `vaultlab tools-index build <tool>` CLI command will:

1. Fetch official docs via the package's documented URL
2. Ask Claude to condense following the template (with anti-laziness rules: only include functions actually in the docs; cite specific URL anchors)
3. Write the markdown to `src/vaultlab/kb/tools_index/<tool>.md`
4. Open in an editor for Bobby (or a contributor) to review + approve
5. Commit

For v0.0.1, the index is **scaffolded** — the methodology is documented but the actual tool pages haven't landed yet.

## Priority order (v0.1.0)

1. **scanpy** — scRNA-seq + spatial preprocessing canonical
2. **squidpy** — spatial-specific extensions; cellular neighborhoods
3. **scipy.stats + statsmodels + pingouin** — general inference
4. **scikit-image** — image processing primitives
5. **Cellpose** — segmentation; modality-essential for CODEX

After these 5: scvi-tools, scanorama, pyimzML, FlowCytometryTools.

## Page template

See [`templates/tool_index_entry/README.md`](../../../../templates/tool_index_entry/README.md).

## How agents use this

The vaultlab roles that should consult this index:

- **`data_analyst`** (when picking analysis steps): `Read(vaultlab/kb/tools_index/<tool>.md)` BEFORE writing any analysis code
- **`methods_critic`** (when reviewing analysis): cross-check that every function called by `data_analyst` is in the index; flag if not
- **`recipe_picker`** (when generating figures): consult the index to know which plotting library to call

The agents NEVER call functions not in this index without first verifying via live docs (Read + WebFetch) and updating the index.

## Adding a new tool

1. Verify it's wrapped in some `vaultlab` subpackage already (otherwise it's not vaultlab's concern)
2. Run `vaultlab tools-index build <tool>` (when CLI lands)
3. Or manually: copy `templates/tool_index_entry/`, fill in following the rules above, commit
4. Add to `index.json` for queryable lookup

## Why this is a vaultlab differentiator

Most LLM research tools either:
- Use raw web search (wasteful + risky)
- Hardcode a few function calls (limited)
- Trust the LLM's training-data knowledge (hallucination-prone)

vaultlab's curated index + anti-laziness rules + source attribution = research tool that calls REAL functions from REAL packages, not invented ones.

This is part of vaultlab's research-robustness story (see [`docs/ORIGINAL-CONTRIBUTIONS.md`](../../../../docs/ORIGINAL-CONTRIBUTIONS.md)).

## See also

- [`docs/architecture.md`](../../../../docs/architecture.md) — where the tools index fits
- [`AGENTS.md`](../../../../AGENTS.md) — anti-laziness rules + curation discipline
- The piped-ideas file in the KB: 08-centralized-memory-and-tools-index.md
