<h1 align="center">VaultLab</h1>

<p align="center">
  <b>An AI research companion for biological scientists.</b><br>
  Goes as deep as you want — literature, data, figures, manuscripts, slides. <i>Driven by you, on your terms.</i>
</p>

<p align="center">
  <a href="https://pypi.org/project/vaultlab/"><img src="https://img.shields.io/pypi/v/vaultlab.svg" alt="PyPI"></a>
  <a href="https://pypi.org/project/vaultlab/"><img src="https://img.shields.io/pypi/pyversions/vaultlab.svg" alt="Python"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="License: MIT"></a>
  <a href="https://github.com/bobbyni819/vaultlab/actions"><img src="https://github.com/bobbyni819/vaultlab/actions/workflows/test.yml/badge.svg" alt="Tests"></a>
  <a href="docs/KNOWN_LIMITATIONS.md"><img src="https://img.shields.io/badge/status-alpha-orange.svg" alt="Status: Alpha"></a>
</p>

> 🚧 **Alpha software** — see [`docs/KNOWN_LIMITATIONS.md`](docs/KNOWN_LIMITATIONS.md). v0.1.0 target: late May 2026.

---

## 🌟 The flagship — centralized memory for your whole research life

VaultLab pulls every source of context about your work into one place the LLM reads:

| | |
|---|---|
| 📓 **Knowledge base** | Plain-markdown KB (Obsidian-native). Papers, notes, findings, manuscripts, figures — all here. |
| 🎤 **Meeting transcripts** | Record + auto-transcribe (local Whisper or cloud). *"What did we decide about cluster 7 last Tuesday?"* — answered from the transcript. |
| 📥 **Inbox + calendar + work log** | Outlook (Windows) or Gmail + Google Docs lab log + Calendar. *"Brief me on this morning"* works without you setting context. |
| 🚀 **Auto-resumed projects** | Every project has a `START_HERE.md` VaultLab maintains. Read one file, you're caught up in 30 seconds. |

Onboard a lab member by sharing the Drive folder. Cross-project insights surface automatically: *"You saw a similar exhausted-T-cell phenotype in your 2026-03 tonsil run."*

---

## What VaultLab does on top of that memory

<table>
<tr>
<td width="50%">

### 📊 **Drafts entire figures from your data**

Not just "wraps matplotlib." VaultLab has a curated **recipe library** — every recipe cites ≥3 published examples. Tell it *"make a marker dot-plot for these clusters"* and you get a publication-tight figure with auto-generated caption, drawn from a pattern that's been used in real Cell / Nature papers. No invented visualizations.

</td>
<td width="50%">

### 📄 **Citations with traceable evidence**

Drafts methods sections with `[N]` markers, then verifies every one **semantically** against the actual source paper. Hover a citation in your draft to see the exact passage that supports it. Hallucinated citations get flagged automatically; VaultLab refuses to ship if any are unresolved.

</td>
</tr>
<tr>
<td width="50%">

### 🎤 **Slide decks from anything**

`/build-deck <source>` composes a deck — figures, captions, speaker notes, click-through animations — from whatever you point it at. A paper PDF, your own wet-lab data, a manuscript draft, or just a topic VaultLab pulls from your KB. Exports `.pptx`. Works for journal clubs, lab meetings, conference talks, dissertation defenses.

</td>
<td width="50%">

### 🧬 **Wraps the analysis tools you trust**

scanpy, squidpy, scikit-image, Cellpose, scipy.stats, statsmodels, pingouin — VaultLab has a curated index so the LLM picks **real functions from real packages**, not raw web searches that hallucinate function names.

</td>
</tr>
</table>

> [!IMPORTANT]
> **VaultLab is a companion you customize, build upon, and direct.** Take the agent as far as you want — quick assist or full lab-wide deep-dive. *Other tools force a single mode; VaultLab adapts to the depth your work needs.*

---

## Get started

```bash
git clone https://github.com/bobbyni819/vaultlab && cd vaultlab
pip install -e ".[all]"
```

Then open [Claude Code](https://claude.com/claude-code) in the folder. Pick the path that fits you:

| Path | When | First command |
|---|---|---|
| **A — Full project** | You have a folder with code, data, papers, notes | Copy `templates/project_intake.md` into your folder, fill it (5 min), then run `/onboard-project <path>` |
| **B — Quick scoping** | Just curious about a topic — no folder yet | `/start-project "<your topic>"` |
| **C — Non-research** | Any knowledge-management use case | Same as B — VaultLab works for any topic, not just biomedical |

The intake form has 9 sections (topic, goal, audience, what-you-have, exclusions, style, PI prefs, deadlines, free-form). Required: topic + goal + audience. Everything else is optional. After onboarding, `/lit-arc`, `/build-deck`, `/cite audit`, etc. all know your context.

Full walkthrough: [`docs/getting-started.md`](docs/getting-started.md). ~10–15 minutes total from clone to first useful KB entry.

> **No Anthropic API key needed.** VaultLab is Claude-Code-native — Claude Code provides LLM access. The optional API keys are for **literature search** (NCBI, Semantic Scholar, etc.) — see [`docs/setup-api-keys.md`](docs/setup-api-keys.md). NCBI is free + 5 min and is the only one most users need.

<details>
<summary><b>Prefer to read setup docs yourself first?</b></summary>

- ⭐ [`docs/getting-started.md`](docs/getting-started.md) — full first-10-minutes walkthrough + 10 best practices
- [`docs/setup-obsidian.md`](docs/setup-obsidian.md) — Obsidian + recommended plugins
- [`docs/setup-api-keys.md`](docs/setup-api-keys.md) — literature API keys (NCBI, S2, Springer, Elsevier)
- [`docs/setup-google.md`](docs/setup-google.md) — Google Cloud Console + OAuth (~10 min)
- [`docs/setup-outlook-windows.md`](docs/setup-outlook-windows.md) — Outlook (Windows only)

</details>

---

## How it works

```mermaid
flowchart TB
    subgraph Team["Your lab"]
        You[You]
        Mate[Lab member]
        Collab[Collaborator]
    end

    Team --> CC[Claude Code]
    CC --> VL[VaultLab capabilities]

    subgraph Memory["Centralized memory"]
        direction LR
        KB[(Obsidian KB)]
        GD[Google Workspace]
        OL[Outlook]
        MT[Meeting transcripts]
        FS[Local files]
        SH[START_HERE.md per project]
    end

    VL <--> Memory
    CC -.reads.-> Memory

    style Memory fill:#fef3c7,stroke:#854d0e,stroke-width:2px
    style Team fill:#e0f2fe,stroke:#0369a1
```

You (or anyone you've shared the KB with) talks to Claude Code. Claude Code reads VaultLab + memory. VaultLab orchestrates work, writes results back into the memory. Memory is **plain markdown** on Google Drive — share it like any folder, scale across your lab without infrastructure.

---

<details>
<summary><b>Specialized modules per modality</b> (CODEX, MALDI, spatial transcriptomics, scRNA-seq, imaging, flow)</summary>

VaultLab has modules tuned to specific modalities for spatial-omics-heavy research:

- **CODEX multiplex IF** — segmentation (Mesmer/Cellpose/StarDist), marker normalization, cellular neighborhood detection (Schürch 2020 + lab CN methodology)
- **MALDI imaging** — pyimzML + Cardinal-via-rpy2 wrappers, ion-image visualization, multi-modal coregistration with H&E
- **Spatial transcriptomics** — Visium / Xenium / SpatialData via squidpy
- **Single-cell RNA-seq** — scanpy + anndata canonical pipelines
- **Generic imaging / flow cytometry** — wrappers for standard tools

These are not required to use VaultLab; they're there if your work touches them. Generic AI tools wrap whatever's on PyPI — VaultLab's modality modules carry the methods working researchers actually use, not the generic defaults.

</details>

<details>
<summary><b>Architecture philosophy</b> (4 commitments)</summary>

1. **Markdown is the user-facing interface; Python is the engine.** Slash commands, role prompts, recipes are markdown — Claude Code reads them directly.
2. **Anti-laziness on semantic reading.** Every LLM call requires quoted evidence. No surface-skim.
3. **Result-oriented agentic loop.** You describe a goal; VaultLab plans + verifies + refines internally; you see the finished result.
4. **KB is the smartness.** No vector DBs, no hidden state. Markdown grows with your work; cross-project reasoning emerges via retrieval.

Full spec: [`docs/architecture.md`](docs/architecture.md). Invariants for contributors: [`AGENTS.md`](AGENTS.md).

</details>

<details>
<summary><b>What's unique vs PaperQA / scanpy / FutureHouse / scverse / Aider</b></summary>

| Capability | VaultLab | PaperQA2 | scanpy | FutureHouse | scverse | Aider |
|---|---|---|---|---|---|---|
| Wet-lab data analysis | ✓ | ✗ | ✓ | ✗ | ✓ | ✗ |
| Literature + citation verification | ✓ | ✓ | ✗ | ✓ | ✗ | ✗ |
| **Evidence-tied citation retrieval** | ✓ | partial | ✗ | ✗ | ✗ | ✗ |
| Manuscript drafting | ✓ | ✗ | ✗ | partial | ✗ | ✗ |
| **Slide deck output** | ✓ | ✗ | ✗ | ✗ | ✗ | ✗ |
| **Calendar / inbox / meeting context** | ✓ | ✗ | ✗ | ✗ | ✗ | ✗ |
| **Knowledge base (Obsidian-native, shareable)** | ✓ | ✗ | ✗ | ✗ | ✗ | ✗ |
| **Auto-resumed projects via START_HERE.md** | ✓ | ✗ | ✗ | ✗ | ✗ | ✗ |
| Local-first | ✓ | ✓ | ✓ | ✗ | ✓ | ✓ |
| **Companion mode (you control depth)** | ✓ | partial | n/a | ✗ | n/a | ✓ |
| Claude-Code-native skill bundle | ✓ | ✗ | ✗ | ✗ | ✗ | partial |

The combination is the value. Several rows nobody else even attempts. If you only need one piece, those tools are great. If you want a research companion that knows your whole lab, VaultLab is the only option.

</details>

<details>
<summary><b>Documentation index</b></summary>

**Reference:** [`docs/architecture.md`](docs/architecture.md) · [`.claude/commands/COMMANDS.md`](.claude/commands/COMMANDS.md) · [`AGENTS.md`](AGENTS.md) · [`CLAUDE.md`](CLAUDE.md)

**Use cases & workflows:** [`docs/use-cases.md`](docs/use-cases.md)

**Privacy:** [`docs/data-privacy.md`](docs/data-privacy.md) · [`docs/compliance.md`](docs/compliance.md) · [`docs/long-term-reproducibility.md`](docs/long-term-reproducibility.md)

**Lineage:** [`INSPIRATIONS.md`](INSPIRATIONS.md) · [`docs/design-rationale.md`](docs/design-rationale.md)

**Contributors:** [`CONTRIBUTING.md`](CONTRIBUTING.md) · [`docs/graphics-guide.md`](docs/graphics-guide.md)

</details>

---

## Methodological lineage

VaultLab is alpha software — no published paper has been written using it yet. **The credibility comes from what it draws on.** Patterns are deliberately lifted from established, peer-reviewed, or widely-used open-source projects, then adapted into a Claude-Code-native harness:

| What VaultLab does | Pattern source |
|---|---|
| Multi-agent meeting structure (adversarial vs round-table) | [virtual-lab](https://github.com/zou-group/virtual-lab) (Zou group, Stanford) |
| Bounded plan→execute→verify→refine loop | [AI-Scientist](https://github.com/SakanaAI/AI-Scientist) (Sakana AI) |
| Literature MCP + cross-source dedup | [paperclip](https://github.com/GXL-ai/paperclip) |
| Claude Code skill bundle organization + AGENTS.md framing | [gstack](https://github.com/garrytan/gstack) |
| Canonical scRNA-seq / spatial pipelines | [scanpy + squidpy](https://github.com/scverse) (scverse community, peer-reviewed in *Nat. Methods*) |
| Cell segmentation primitives | [Cellpose](https://github.com/MouseLand/cellpose) (Stringer & Pachitariu, *Nat. Methods* 2021) |
| Cellular neighborhood detection | [Schürch et al. 2020, *Cell*](https://doi.org/10.1016/j.cell.2020.07.005) |
| Fork-and-clone primary distribution | [nanoGPT](https://github.com/karpathy/nanoGPT) (Karpathy) |

Each row represents a method or interface design choice that I read, understood, and adapted — not invented from scratch. The implementations are mine, but the patterns have track records elsewhere.

Full per-component attribution: [`INSPIRATIONS.md`](INSPIRATIONS.md). For a project-level breakdown of design choices novel to VaultLab vs. synthesis vs. borrowed: [`docs/design-rationale.md`](docs/design-rationale.md).

VaultLab is developed by a member of the Hickey Lab at Duke University Biomedical Engineering.

---

## Citation, privacy, license

```bibtex
@software{ni_vaultlab_2026,
  author = {Ni, Bobby Y.X.},
  title = {VaultLab: A research companion for biological scientists},
  year = 2026, url = {https://github.com/bobbyni819/vaultlab}
}
```

**Privacy:** prompt content is sent to Anthropic's Claude API via Claude Code. **Not HIPAA-compliant.** Do not use with PHI/PII/IRB-restricted data. See [`docs/data-privacy.md`](docs/data-privacy.md) for the quick-compliance check.

**License:** [MIT](LICENSE). Author: Bobby Y.X. Ni — Hickey Lab, Duke University Biomedical Engineering.
