<h1 align="center">VaultLab</h1>

<p align="center">
  <b>An AI research companion for biological scientists.</b><br>
  Literature, data, figures, manuscripts, slides — driven by you, on your terms.
</p>

<p align="center">
  <a href="https://pypi.org/project/vaultlab/"><img src="https://img.shields.io/pypi/v/vaultlab.svg" alt="PyPI"></a>
  <a href="https://pypi.org/project/vaultlab/"><img src="https://img.shields.io/pypi/pyversions/vaultlab.svg" alt="Python"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="License: MIT"></a>
  <a href="https://github.com/bobbyni819/vaultlab/actions"><img src="https://github.com/bobbyni819/vaultlab/actions/workflows/test.yml/badge.svg" alt="Tests"></a>
  <a href="docs/KNOWN_LIMITATIONS.md"><img src="https://img.shields.io/badge/status-alpha-orange.svg" alt="Status: Alpha"></a>
</p>

> 🚧 **Alpha.** v0.1.0 target: late May 2026. See [`docs/KNOWN_LIMITATIONS.md`](docs/KNOWN_LIMITATIONS.md).

---

## Quick start

```bash
git clone https://github.com/bobbyni819/vaultlab && cd vaultlab
pip install -e ".[all]"
```

Open [Claude Code](https://claude.com/claude-code) in the folder and paste:

```
I've just cloned VaultLab. Read README.md, CLAUDE.md, AGENTS.md, and
docs/getting-started.md, then walk me through what it does, set up my
first project, and run my first slash command. Hedged voice on placeholder capabilities.
```

Claude Code interviews you about your work, sets up your KB + first project, walks you through the first command. ~10–15 minutes. **No Anthropic API key needed** — Claude Code provides LLM access.

---

## What it is, in one paragraph

VaultLab pulls every source of context about your work — KB, meeting transcripts, inbox, calendar, lab log, project state — into one place the LLM reads, then orchestrates literature search, data analysis, figure generation, manuscript drafting, and slide assembly on top of that memory. Memory is plain markdown on Google Drive: share it with your lab, no infrastructure. The four flagship capabilities: **drafts figures from your data** (recipe library citing real published examples), **NotebookLM-style citation verification** (semantic match against the source paper), **paper → journal-club deck in 90 seconds**, and **wraps the analysis tools you trust** (scanpy / squidpy / Cellpose / scipy).

→ Full surface area: [`docs/what-vaultlab-does.md`](docs/what-vaultlab-does.md)
→ End-to-end workflows: [`docs/use-cases.md`](docs/use-cases.md)
→ How it compares to PaperQA2 / scanpy / FutureHouse / Aider: [`docs/comparison.md`](docs/comparison.md)

---

## Documentation

**Start here**

- ⭐ [`docs/getting-started.md`](docs/getting-started.md) — first 10 minutes + 10 best practices
- [`docs/what-vaultlab-does.md`](docs/what-vaultlab-does.md) — capabilities, modalities, architecture philosophy
- [`docs/use-cases.md`](docs/use-cases.md) — concrete workflows (CODEX, scRNA-seq, MALDI, etc.)
- [`docs/comparison.md`](docs/comparison.md) — vs PaperQA2 / scanpy / FutureHouse / scverse / Aider

**Setup**

- [`docs/setup-obsidian.md`](docs/setup-obsidian.md) — Obsidian + recommended plugins
- [`docs/setup-api-keys.md`](docs/setup-api-keys.md) — literature APIs (NCBI is free + 5 min)
- [`docs/setup-google.md`](docs/setup-google.md) — Google OAuth (~10 min)
- [`docs/setup-outlook-windows.md`](docs/setup-outlook-windows.md) — Outlook (Windows only)
- [`docs/setup-meeting-recorder.md`](docs/setup-meeting-recorder.md) — meeting transcripts

**Reference**

- [`docs/architecture.md`](docs/architecture.md) — full architecture spec
- [`.claude/commands/COMMANDS.md`](.claude/commands/COMMANDS.md) — slash command catalog
- [`AGENTS.md`](AGENTS.md) · [`CLAUDE.md`](CLAUDE.md) — invariants for contributors / Claude Code

**Privacy & compliance**

- [`docs/data-privacy.md`](docs/data-privacy.md) — what gets sent where (not HIPAA-compliant)
- [`docs/compliance.md`](docs/compliance.md) · [`docs/long-term-reproducibility.md`](docs/long-term-reproducibility.md)

**Lineage & contributing**

- [`INSPIRATIONS.md`](INSPIRATIONS.md) — what was lifted from where (virtual-lab, AI-Scientist, paperclip, scanpy, Cellpose, …)
- [`docs/design-rationale.md`](docs/design-rationale.md) — what's novel vs synthesized vs borrowed
- [`CONTRIBUTING.md`](CONTRIBUTING.md) · [`docs/graphics-guide.md`](docs/graphics-guide.md)

---

## Citation, privacy, license

```bibtex
@software{ni_vaultlab_2026,
  author = {Ni, Bobby Y.X.},
  title  = {VaultLab: A research companion for biological scientists},
  year   = 2026, url = {https://github.com/bobbyni819/vaultlab}
}
```

**Privacy:** prompts go to Anthropic via Claude Code. **Not HIPAA-compliant** — no PHI/PII/IRB-restricted data. See [`docs/data-privacy.md`](docs/data-privacy.md).

**License:** [MIT](LICENSE). Author: Bobby Y.X. Ni — Hickey Lab, Duke University Biomedical Engineering.
