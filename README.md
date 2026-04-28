# vaultlab

> *"From microscope to manuscript, in one repo."*

**vaultlab** is the AI lab for biological researchers. Point [Claude Code](https://claude.com/claude-code) at your wet-lab data, your literature, and your unfinished manuscript — vaultlab orchestrates analysis, generates publication-quality figures, drafts manuscript sections with verified citations, and builds slide decks.

Open-source. Local-first. Claude-Code-native. **MIT licensed.**

> **🚧 Alpha software.** vaultlab is under active development toward v0.1.0 (target: late May 2026). Expect rough edges. See [`docs/KNOWN_LIMITATIONS.md`](docs/KNOWN_LIMITATIONS.md).

<!-- TODO: hero GIF showing /build-deck demo at the top of README -->
<!-- assets/hero.gif (~6 sec, ~2 MB) — auto-loops -->

## What it does

| | |
|---|---|
| 📄 | Literature search & citation verification (PubMed, Semantic Scholar, CrossRef, bioRxiv, Springer, Elsevier, paperclip MCP) |
| 🧬 | Wet-lab data analysis (CODEX, MALDI, Visium, scRNA-seq, H&E, flow) |
| 📊 | Publication-quality figures with corpus-backed recipes |
| ✍️ | Manuscript drafting with NotebookLM-style evidence retrieval |
| 🎤 | Slide decks built from research outputs |
| 🧠 | Knowledge base (Obsidian-native) that links it all |

## Install

```bash
git clone https://github.com/bobbyni819/vaultlab && cd vaultlab
pip install -e ".[all]"
vaultlab setup            # interactive: API keys, KB path, Obsidian
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
3. Auto-annotates clusters via LLM
4. Renders 3 publication-quality figures
5. Builds a 5-slide journal-club deck with speaker notes
6. Auto-writes a KB summary note linking everything

## Architecture philosophy

vaultlab is a **capability layer FOR Claude Code**, not a competing harness. Markdown is the user-facing interface; Python is the engine. Slash commands, role prompts, recipes, layouts, and skill definitions are all markdown files Claude Code can read at first repo open.

See [`docs/architecture.md`](docs/architecture.md) for the full spec.

### The four core commitments

1. **Markdown is the interface; Python is the engine.** Slash commands, role prompts, workflow descriptions are markdown.
2. **Anti-laziness on semantic reading.** Every LLM call requires quoted evidence. No surface-skim.
3. **Result-oriented agentic loop.** User says *"draft methods"* → vaultlab plans + verifies + refines internally → returns finished result.
4. **KB is the smartness.** Every analysis writes to KB; every analysis reads from it. The LLM gets smarter project-by-project.

## What's unique vs PaperQA / scanpy / FutureHouse / scverse

No competitor combines all of these:
- Wet-lab → manuscript end-to-end
- NotebookLM-style evidence retrieval per citation
- Publication-quality slide deck output (the flagship)
- Obsidian-native knowledge base
- Local-first
- Wraps existing OSS standards (doesn't fight them)
- Claude-Code-native skill bundle

See [`docs/comparison.md`](docs/comparison.md).

## Demos

| Demo | Dataset | Time |
|---|---|---|
| [`examples/pbmc3k`](examples/pbmc3k/) | 3k PBMCs (scRNA-seq) | 2 min — Hello World |
| [`examples/visium_brain`](examples/visium_brain/) | 10x mouse brain Visium | 30 min — spatial transcriptomics |
| [`examples/codex_hubmap_tonsil`](examples/codex_hubmap_tonsil/) | HuBMAP tonsil CODEX | 30 min — flagship spatial imaging |

## Documentation

- [`docs/architecture.md`](docs/architecture.md) — full architectural spec
- [`docs/setup-obsidian.md`](docs/setup-obsidian.md) — Obsidian setup walkthrough
- [`docs/setup-api-keys.md`](docs/setup-api-keys.md) — API key acquisition
- [`docs/data-privacy.md`](docs/data-privacy.md) — what data leaves your machine (and what doesn't)
- [`docs/compliance.md`](docs/compliance.md) — explicit non-HIPAA disclosure
- [`docs/long-term-reproducibility.md`](docs/long-term-reproducibility.md) — model-version philosophy
- [`docs/KNOWN_LIMITATIONS.md`](docs/KNOWN_LIMITATIONS.md) — honest failures
- [`docs/contributing.md`](docs/contributing.md) — how to contribute
- [`AGENTS.md`](AGENTS.md) — invariants and conventions for code contributors
- [`CLAUDE.md`](CLAUDE.md) — entrypoint for Claude Code sessions on this repo

## Citation

See [`CITATION.cff`](CITATION.cff). Once v0.1.0 ships, the preferred citation is:

```bibtex
@software{ni_vaultlab_2026,
  author = {Ni, Bobby Y.X.},
  title  = {vaultlab: An open-source AI laboratory for biological researchers},
  year   = 2026,
  url    = {https://github.com/bobbyni819/vaultlab},
  version= {0.1.0}
}
```

## Privacy & compliance

vaultlab uses Anthropic's Claude API. **Prompt content is sent to Anthropic.** vaultlab is **NOT HIPAA-compliant.** Do **NOT** use with PHI/PII/IRB-restricted data. See [`docs/data-privacy.md`](docs/data-privacy.md).

By using vaultlab, you take full responsibility for compliance with your institutional, IRB, IACUC, and regulatory obligations.

## Author

Bobby Y.X. Ni — Hickey Lab, Duke University Biomedical Engineering.

## License

[MIT](LICENSE) — anyone can use, modify, distribute, including commercial.
