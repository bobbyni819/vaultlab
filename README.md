# vaultlab

> *"From microscope to manuscript, in one repo."*

**vaultlab is a research companion for biological scientists.** Most AI lab tools take a research question and try to write the paper for you. vaultlab is different — it accompanies you through whatever you're actually doing today: searching literature, analyzing your CODEX run, drafting the methods section, building tomorrow's lab-meeting deck, triaging your inbox for the manuscript-deadline email you've been avoiding. With full context of your work — your knowledge base, your Google Docs, your Outlook calendar — Claude Code becomes a useful colleague instead of a generic chatbot.

Open-source. Local-first. Claude-Code-native. **MIT licensed.**

> **🚧 Alpha software.** vaultlab is under active development toward v0.1.0 (target: late May 2026). Expect rough edges. See [`docs/KNOWN_LIMITATIONS.md`](docs/KNOWN_LIMITATIONS.md).

<!-- TODO: hero GIF showing /build-deck demo at the top of README -->
<!-- assets/hero.gif (~6 sec, ~2 MB) — auto-loops -->

## What it does

| | |
|---|---|
| 📄 | **Literature search & citation verification** — PubMed, Semantic Scholar, CrossRef, bioRxiv, Springer, Elsevier, paperclip MCP |
| 🧬 | **Wet-lab data analysis** — CODEX, MALDI, Visium, scRNA-seq, H&E, flow cytometry |
| 📊 | **Publication-quality figures** with corpus-backed recipes (every recipe cites ≥3 published examples) |
| ✍️ | **Manuscript drafting** with NotebookLM-style evidence retrieval — every `[N]` shows the exact passage on hover |
| 🎤 | **Slide decks** built from research outputs — journal-club, thesis-committee, conference-talk modes |
| 🧠 | **Knowledge base** (Obsidian-native) that links it all, queryable via semantic search |
| 📥 | **Email + calendar context** — vaultlab reads your Outlook (Windows) or Gmail to know what's pressing |
| 📝 | **Google Docs integration** — your lab work log + Sheets data + Drive files become first-class context |

## Companion mode, not autonomous mode

vaultlab is **not** an autonomous AI scientist. It does not generate experiment ideas in a vacuum, run robots, or submit papers without you. It assumes:

- **You have ideas** — vaultlab amplifies them
- **You have context** — vaultlab indexes it
- **You make the calls** — vaultlab does the rote 60% so you can focus on the insightful 40%
- **You ship the paper** — vaultlab drafts, verifies, formats, but the byline is yours alone

The "research companion" framing is intentional. The published-paper-via-AI bans many journals impose? Not our use case. *"Here are 23 things vaultlab made my week easier"* is.

## Install

```bash
git clone https://github.com/bobbyni819/vaultlab && cd vaultlab
pip install -e ".[all]"
vaultlab setup            # interactive: API keys, KB path, Obsidian, Google, Outlook
```

Or, if you only want a piece (citations, lit search, figures):

```bash
pip install vaultlab            # core
pip install "vaultlab[research,citations]"   # specific subpackages
```

## 5-minute Hello World

```bash
vaultlab demo pbmc3k
```

In ~2 minutes on a laptop, this:
1. Downloads the 3k PBMC dataset (50 MB)
2. Runs QC + normalization + Leiden clustering
3. Auto-annotates clusters via LLM (with hedged voice and quoted evidence)
4. Renders 3 publication-quality figures
5. Builds a 5-slide journal-club deck with speaker notes
6. Auto-writes a KB summary note linking everything

## Use cases (real ones, not benchmarks)

These are the workflows vaultlab solves end-to-end:

- **"I have a CODEX run. Get me to a labeled figure."** Ingest TIFF → segment with Cellpose → cluster → LLM-annotate → publication-tight spatial overlay → caption draft → KB note.
- **"Draft me a Methods paragraph for the lung paper."** Reads project KB → drafts → verifies every citation semantically → flags any HALLUCINATED → produces a draft you edit, not write from scratch.
- **"Find papers using GPR55 in intestinal epithelium."** Multi-source lit search (PubMed + bioRxiv + paperclip MCP) → smart query expansion → dedupe → re-rank → KB ingest of top 10 → citation-graph view.
- **"Build me a journal-club deck on Smith et al. 2024."** `/paper-to-slides 10.1038/...` extracts figures from PDF → composes 12-slide deck → auto-drafts speaker notes → exports `.pptx`.
- **"What's on my calendar this week + which manuscripts are due?"** Outlook reads upcoming meetings, Gmail reads journal deadlines, KB cross-references active manuscripts → integrated daily brief.

See [`docs/use-cases.md`](docs/use-cases.md) for more (post-v0.1).

## Architecture philosophy

vaultlab is a **capability layer FOR Claude Code**, not a competing harness. Markdown is the user-facing interface; Python is the engine. Slash commands, role prompts, recipes, layouts, and skill definitions are all markdown files Claude Code can read at first repo open.

See [`docs/architecture.md`](docs/architecture.md) for the full spec.

### The four core commitments

1. **Markdown is the interface; Python is the engine.** Slash commands, role prompts, workflow descriptions are markdown.
2. **Anti-laziness on semantic reading.** Every LLM call requires quoted evidence. No surface-skim.
3. **Result-oriented agentic loop.** User says *"draft methods"* → vaultlab plans + verifies + refines internally → returns finished result.
4. **KB is the smartness.** Every analysis writes to KB; every analysis reads from it. The LLM gets smarter project-by-project.

## What's unique vs PaperQA / scanpy / FutureHouse / scverse / Aider

| | vaultlab | PaperQA2 | scanpy | FutureHouse | scverse | Aider |
|---|---|---|---|---|---|---|
| Wet-lab data analysis | ✓ | ✗ | ✓ | ✗ | ✓ | ✗ |
| Literature + citation verification | ✓ | ✓ | ✗ | ✓ | ✗ | ✗ |
| NotebookLM-style evidence retrieval | ✓ | partial | ✗ | ✗ | ✗ | ✗ |
| Manuscript drafting | ✓ | ✗ | ✗ | partial | ✗ | ✗ |
| **Slide deck output** | ✓ | ✗ | ✗ | ✗ | ✗ | ✗ |
| **Calendar / inbox context** | ✓ | ✗ | ✗ | ✗ | ✗ | ✗ |
| **Knowledge base (Obsidian)** | ✓ | ✗ | ✗ | ✗ | ✗ | ✗ |
| Local-first | ✓ | ✓ | ✓ | ✗ | ✓ | ✓ |
| Companion mode (not autonomous) | ✓ | partial | n/a | ✗ | n/a | ✓ |
| Claude-Code-native skill bundle | ✓ | ✗ | ✗ | ✗ | ✗ | partial |

No tool does all of these. **vaultlab's value is the combination** — wet-lab analysis (scverse-grade) + literature verification (PaperQA-grade) + manuscript + slides + life-context (calendar/inbox/docs) wired through Claude Code.

If you only need one piece, those tools are great. If you want a research companion, vaultlab is the only OSS option.

See [`docs/comparison.md`](docs/comparison.md) for the full positioning analysis.

## Demos

| Demo | Dataset | Time |
|---|---|---|
| [`examples/pbmc3k`](examples/pbmc3k/) | 3k PBMCs (scRNA-seq) | 2 min — Hello World |
| [`examples/visium_brain`](examples/visium_brain/) | 10x mouse brain Visium | 30 min — spatial transcriptomics |
| [`examples/codex_hubmap_tonsil`](examples/codex_hubmap_tonsil/) | HuBMAP tonsil CODEX | 30 min — flagship spatial imaging |

## Documentation

**Setup:**
- [`docs/setup-obsidian.md`](docs/setup-obsidian.md) — Obsidian + plugin walkthrough
- [`docs/setup-api-keys.md`](docs/setup-api-keys.md) — Anthropic + literature API keys
- [`docs/setup-google.md`](docs/setup-google.md) — Google ecosystem (Docs, Sheets, Drive, Gmail, Calendar)
- [`docs/setup-outlook-windows.md`](docs/setup-outlook-windows.md) — Outlook COM (Windows-only)

**Reference:**
- [`docs/architecture.md`](docs/architecture.md) — full architectural spec
- [`docs/use-cases.md`](docs/use-cases.md) — concrete examples of what vaultlab solves
- [`docs/comparison.md`](docs/comparison.md) — vs other tools

**Privacy & limits:**
- [`docs/data-privacy.md`](docs/data-privacy.md) — what data leaves your machine
- [`docs/compliance.md`](docs/compliance.md) — explicit non-HIPAA disclosure
- [`docs/long-term-reproducibility.md`](docs/long-term-reproducibility.md) — model-version philosophy
- [`docs/KNOWN_LIMITATIONS.md`](docs/KNOWN_LIMITATIONS.md) — honest failures

**For contributors:**
- [`CONTRIBUTING.md`](CONTRIBUTING.md) — how to contribute
- [`AGENTS.md`](AGENTS.md) — invariants and conventions
- [`CLAUDE.md`](CLAUDE.md) — entrypoint for Claude Code sessions
- [`INSPIRATIONS.md`](INSPIRATIONS.md) — what we drew from where (auditable lineage)

## Citation

See [`CITATION.cff`](CITATION.cff). Once v0.1.0 ships, the preferred citation is:

```bibtex
@software{ni_vaultlab_2026,
  author = {Ni, Bobby Y.X.},
  title  = {vaultlab: A research companion for biological scientists},
  year   = 2026,
  url    = {https://github.com/bobbyni819/vaultlab},
  version= {0.1.0}
}
```

## Privacy & compliance

vaultlab uses Anthropic's Claude API. **Prompt content is sent to Anthropic.** vaultlab is **NOT HIPAA-compliant.** Do **NOT** use with PHI/PII/IRB-restricted data. See [`docs/data-privacy.md`](docs/data-privacy.md).

When you opt into Google or Outlook integration, vaultlab also reads:
- Google Docs / Sheets / Drive content you authorize
- Gmail messages matching your search criteria
- Outlook calendar events + email subjects/bodies

This data may end up in prompts sent to Anthropic. **Do not enable Google/Outlook integration if your account contains PHI or institution-restricted data.** Each integration has its own scopes you can audit; see [`docs/data-privacy.md`](docs/data-privacy.md).

By using vaultlab, you take full responsibility for compliance with your institutional, IRB, IACUC, and regulatory obligations.

## Author

Bobby Y.X. Ni — Hickey Lab, Duke University Biomedical Engineering.

## License

[MIT](LICENSE) — anyone can use, modify, distribute, including commercial.
