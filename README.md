<h1 align="center">VaultLab</h1>

<p align="center">
  <b>The Claude Code setup for biological research.</b><br>
  Centralized lab memory + literature + data analysis + figures + manuscripts + slides — directed by you, run by Claude Code.
</p>

<p align="center">
  <a href="https://pypi.org/project/vaultlab/"><img src="https://img.shields.io/pypi/v/vaultlab.svg" alt="PyPI"></a>
  <a href="https://pypi.org/project/vaultlab/"><img src="https://img.shields.io/pypi/pyversions/vaultlab.svg" alt="Python"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="License: MIT"></a>
  <a href="https://github.com/bobbyni819/vaultlab/actions"><img src="https://github.com/bobbyni819/vaultlab/actions/workflows/test.yml/badge.svg" alt="Tests"></a>
  <a href="docs/KNOWN_LIMITATIONS.md"><img src="https://img.shields.io/badge/status-alpha-orange.svg" alt="Status: Alpha"></a>
</p>

> *"Most lit-search tools answer one question. VaultLab is what happens when your literature, your wet-lab data, your meeting transcripts, your inbox, and your manuscript live in one place that an LLM can read."*

## About

I'm Bobby Ni, a PhD student in Biomedical Engineering at Duke. I do wet-lab spatial omics and a lot of computational work.

Research at scale is fragmented: a lot of meetings, most of which don't get recorded; papers piling up in Drive; notes on a lab NAS; archives on University OneDrive; updates from collaborators in whichever app they happened to ping you on. The university hands you several storage locations; the lab adds its own. Context lives everywhere except where the LLM is looking.

VaultLab puts all of it into an Obsidian knowledge base that Claude Code reads. The KB is plain markdown — runs on whatever storage you already have.

I've used OpenClaw to automate workflows. Token cost doesn't justify the lift. I've found more value operating inside Claude Code. Watching others ship — [gstack](https://github.com/garrytan/gstack), [nanoGPT](https://github.com/karpathy/nanoGPT), [virtual-lab](https://github.com/zou-group/virtual-lab), [AI-Scientist](https://github.com/SakanaAI/AI-Scientist), other research-specific agent systems — was the push to ship mine and join the open-source wave. Most of what's here adapts beyond research; the KB, citation auditing, and slide composition work on any topic.

---

**VaultLab lives inside [Claude Code](https://claude.com/claude-code).** Open Claude Code in a folder. VaultLab adds ~30 slash commands (`/lit-arc`, `/build-deck`, `/cite audit`, `/onboard-project`, `/lit-report`) that Claude Code reads as plain markdown. No Anthropic API key needed — Claude Code provides the LLM. KB is plain markdown on Google Drive, OneDrive, a lab NAS, or any folder that syncs. **If you've used Claude Code, you already know how to use VaultLab.**

> **Alpha software.** v0.1.0 target: late May 2026. Honest gap inventory: [`docs/KNOWN_LIMITATIONS.md`](docs/KNOWN_LIMITATIONS.md).

---

## Centralized memory

Inside Claude Code, VaultLab reads your whole research ecosystem and writes back into it. Five context sources, one place the LLM looks:

| Source | What VaultLab does with it |
|---|---|
| **Knowledge base** (Obsidian-native markdown) | Per-paper summaries with citation graph, lineage arcs, project pages, manuscript drafts — all linked by `[[wikilinks]]`. Grows with your work. |
| **Literature** (NCBI, Semantic Scholar, Springer, Elsevier, bioRxiv, CrossRef) | Multi-source search → citation-graph metrics (OG-score, forward-influence, year-buckets) → LLM-driven lineage binning → grounded summaries with `[pN]` page markers. |
| **Meeting transcripts** | Record any meeting on your machine — Zoom, Teams, or any Windows audio source — and auto-transcribe (local Whisper or cloud). Ask *"what did we decide about cluster 7 last Tuesday?"* and the answer comes from the transcript. |
| **Inbox + calendar + work log** | Outlook (Windows) or Gmail + Google Docs lab log + Calendar. *"Brief me on this morning"* works without you setting context. |
| **Project state** | Every project has a `START_HERE.md` VaultLab maintains. Read one file, you're caught up in 30 seconds. Cross-project insights surface automatically: *"You saw a similar exhausted-T-cell phenotype in your 2026-03 tonsil run."* |

Onboard a lab member by sharing the Drive folder. That's the whole onboarding.

---

## Features

<table>
<tr>
<td width="50%">

### Drafts entire figures from your data

Not just "wraps matplotlib." VaultLab has a curated **recipe library** — every recipe cites ≥3 published examples. Tell it *"make a marker dot-plot for these clusters"* and you get a publication-tight figure with auto-generated caption, drawn from a pattern that's been used in real Cell / Nature papers. No invented visualizations.

</td>
<td width="50%">

### Citations with traceable evidence

Drafts methods sections with `[N]` markers, then verifies every one **semantically** against the actual source paper. Hover a citation in your draft to see the exact passage that supports it. Hallucinated citations get flagged automatically; VaultLab refuses to ship if any are unresolved.

</td>
</tr>
<tr>
<td width="50%">

### Slide decks from anything

`/build-deck <source>` composes a deck — figures, captions, speaker notes, click-through animations — from whatever you point it at. A paper PDF, your own wet-lab data, a manuscript draft, or just a topic VaultLab pulls from your KB. Exports `.pptx`. Works for journal clubs, lab meetings, conference talks, dissertation defenses.

</td>
<td width="50%">

### Wraps the analysis tools you trust

scanpy, squidpy, scikit-image, Cellpose, scipy.stats, statsmodels, pingouin — VaultLab has a curated index so the LLM picks **real functions from real packages**, not raw web searches that hallucinate function names.

</td>
</tr>
<tr>
<td width="50%">

### Multi-agent crosstalk for hard questions

`/lit-report` runs analyst → critic → synthesizer over a corpus to produce a 3000–5000 word grounded review. Adversarial picker meeting catches off-topic seminal papers; rigor auditor blocks decks that ship with unverified claims. The bigger the question, the more agents weigh in.

</td>
<td width="50%">

### LLM-driven lineage binning

Reads abstracts of every paper in a corpus and decides *history / development / state-of-the-art* by conceptual lineage, not just publication year. A 2018 method paper goes in *history* if it's foundational; a 2024 incremental application goes in *development*, not *sota*. Solves the empty-history-bin failure pure-quartile binning produces.

</td>
</tr>
</table>

> [!IMPORTANT]
> **A companion you customize and direct.** Quick assist or full lab-wide deep-dive — pick the depth. Other tools force a single mode; VaultLab adapts.

---

## Get started — inside Claude Code

If you don't have Claude Code yet, install it from [claude.com/claude-code](https://claude.com/claude-code). VaultLab is the bundle of slash commands + role prompts + Python machinery you point Claude Code at.

```bash
git clone https://github.com/bobbyni819/vaultlab && cd vaultlab
pip install -e ".[all]"
claude   # opens Claude Code in this folder; VaultLab's slash commands are now available
```

From inside Claude Code, pick the path that fits you:

| Path | When | First slash command |
|---|---|---|
| **A — Full project** | You have a folder with code, data, papers, notes | Copy `templates/project_intake.md` into your folder, fill it (5 min), then `/onboard-project <path>` |
| **B — Quick scoping** | Just curious about a topic — no folder yet | `/start-project "<your topic>"` |
| **C — Non-research** | Any knowledge-management use case | Same as B — VaultLab works for any topic, not just biomedical |

The intake form has 9 sections (topic, goal, audience, what-you-have, exclusions, style, PI prefs, deadlines, free-form). Required: topic + goal + audience. Everything else is optional. After onboarding, `/lit-arc`, `/build-deck`, `/cite audit`, `/lit-report` etc. all know your context — you don't re-explain the project to Claude every session.

Full walkthrough: [`docs/getting-started.md`](docs/getting-started.md). ~10–15 minutes total from clone to first useful KB entry.

> **No Anthropic API key needed.** VaultLab is Claude-Code-native — Claude Code provides LLM access. The optional API keys are for **literature search** (NCBI, Semantic Scholar, etc.) — see [`docs/setup-api-keys.md`](docs/setup-api-keys.md). NCBI is free + 5 min and is the only one most users need.

<details>
<summary><b>Prefer to read setup docs yourself first?</b></summary>

- [`docs/getting-started.md`](docs/getting-started.md) — full first-10-minutes walkthrough + 10 best practices
- [`docs/setup-obsidian.md`](docs/setup-obsidian.md) — Obsidian + recommended plugins
- [`docs/setup-api-keys.md`](docs/setup-api-keys.md) — literature API keys (NCBI, S2, Springer, Elsevier)
- [`docs/setup-google.md`](docs/setup-google.md) — Google Cloud Console + OAuth (~10 min)
- [`docs/setup-outlook-windows.md`](docs/setup-outlook-windows.md) — Outlook (Windows only)

</details>

---

<details>
<summary><b>Specialty module</b> (in progress — accessory)</summary>

I work in a spatial-omics lab, so VaultLab has the start of an optional module covering the tools I use day-to-day — CODEX multiplex IF, MALDI imaging, spatial transcriptomics, scRNA-seq, generic imaging / flow. It's not required to use VaultLab and isn't a focus of v0.1; it's an accessory for people whose work touches the same modalities. Most of it is still being built out.

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
<summary><b>How VaultLab compares to PaperQA, scanpy, FutureHouse, scverse, Aider</b></summary>

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

## Influences

VaultLab's patterns are deliberately lifted from open-source projects already at scale, then adapted into a Claude-Code-native harness:

| What VaultLab borrowed | Source |
|---|---|
| Claude Code skill-bundle layout — slash commands as plain markdown, AGENTS.md invariants for contributors | [gstack](https://github.com/garrytan/gstack) (Garry Tan) |
| Self-contained reference implementation meant to be forked and customized, not installed as an opaque library | [nanoGPT](https://github.com/karpathy/nanoGPT) (Andrej Karpathy) |
| Multi-agent meeting structure — analyst → critic → synthesizer rounds with bounded loops | [virtual-lab](https://github.com/zou-group/virtual-lab) (Zou group, Stanford) |
| Plan → execute → verify → refine inner loop with reflection-round caps | [AI-Scientist](https://github.com/SakanaAI/AI-Scientist) (Sakana AI) |
| Literature search MCP + cross-source dedup across NCBI / S2 / Springer / Elsevier / bioRxiv / CrossRef | [paperclip](https://github.com/GXL-ai/paperclip) |

Each row is a method or interface design I read, understood, and adapted — not invented from scratch. Implementations are mine; the patterns have track records elsewhere.

Full per-component attribution: [`INSPIRATIONS.md`](INSPIRATIONS.md). For a project-level breakdown of design choices novel to VaultLab vs. synthesis vs. borrowed: [`docs/design-rationale.md`](docs/design-rationale.md).

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

**License:** [MIT](LICENSE).
