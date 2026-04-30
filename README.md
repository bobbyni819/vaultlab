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

I've used OpenClaw to automate workflows. Token cost doesn't justify the lift. I've found more value operating inside Claude Code. The push to ship this came from watching what [Garry Tan](https://github.com/garrytan/gstack), [Andrej Karpathy](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f), [James Zou](https://github.com/zou-group/virtual-lab), and others have built — open-source, opinionated, hackable. Most of what's here adapts beyond research; the KB, citation auditing, and slide composition work on any topic.

---

**VaultLab lives inside [Claude Code](https://claude.com/claude-code).** Open Claude Code in a folder. VaultLab adds ~30 slash commands (`/lit-arc`, `/build-deck`, `/cite audit`, `/onboard-project`, `/lit-report`) that Claude Code reads as plain markdown. No Anthropic API key needed — Claude Code provides the LLM. KB is plain markdown on Google Drive, OneDrive, a lab NAS, or any folder that syncs. **If you've used Claude Code, you already know how to use VaultLab.**

---

## Centralized memory

Inside Claude Code, VaultLab reads your whole research ecosystem and writes back into it. Five context sources, one place the LLM looks:

| Source | What VaultLab does with it |
|---|---|
| **Knowledge base** (Obsidian-native markdown) | Per-paper summaries with citation graph, lineage arcs, project pages, manuscript drafts — all linked by `[[wikilinks]]`. Grows with your work. |
| **Literature** (NCBI, Semantic Scholar, Springer, Elsevier, bioRxiv, CrossRef) | Multi-source search → citation-graph metrics (OG-score, forward-influence, year-buckets) → LLM-driven lineage binning → grounded summaries with `[pN]` page markers. |
| **Built-in meeting recorder** | Captures any meeting on your machine — Zoom, Teams, in-person — and transcribes locally (Whisper) or via cloud. Ask *"what did we decide about cluster 7 last Tuesday?"* and the answer comes from the transcript. |
| **Inbox + calendar + work log** | Outlook (Windows) or Gmail + Google Docs lab log + Calendar. *"Brief me on this morning"* works without you setting context. |
| **Project state** | Every project has a `START_HERE.md` VaultLab maintains. Read one file, you're caught up in 30 seconds. Cross-project insights surface automatically: *"You saw a similar exhausted-T-cell phenotype in your 2026-03 tonsil run."* |

Onboard a lab member by sharing the Drive folder. That's the whole onboarding.

---

## Features

### Multi-agent crosstalk

For decisions where one-shot LLM output isn't enough — `/lit-report` (deep-research mode), the picker step in `/lit-arc`, the rigor pass in `/build-deck` — VaultLab runs an adversarial meeting: an analyst proposes, a critic challenges, a synthesizer integrates. Bounded at five rounds, 10-minute wall-clock cap, structured-JSON-only outputs to prevent the spiral.

The picker meeting catches off-topic seminal papers that a pure citation-graph rank would miss (the spatial-transcriptomics run nearly used a cancer-testis-antigen paper as the foundational figure because it had a cached PMC figure — the literature critic caught that). The rigor auditor walks the finished output before it's saved, flagging claims without page-marker evidence and references that aren't actually cited in the body. The bigger the question, the more agents weigh in.

### Slide decks from anything

`/build-deck <source>` composes a deck — figures, captions, speaker notes, click-through animations — from whatever you point it at:

- A paper PDF — auto-extracts figures, summarizes claims, drafts speaker notes
- Your wet-lab data — picks a recipe, renders the figure, drafts caption + interpretation
- A manuscript draft — turns each section into a slide block
- Just a topic — VaultLab pulls relevant context from your KB and composes from scratch

Exports `.pptx` using native PowerPoint shapes (animatable, editable post-export — not rasterized images). Works for journal clubs, lab meetings, conference talks, dissertation defenses. Speaker notes come in two formats: a tight outline for talks and a paragraph script for rehearsal.

### Drafts figures from your data

Not just "wraps matplotlib." VaultLab carries a recipe library — every recipe cites at least three published examples. Tell it *"make a marker dot-plot for these clusters"* and you get a publication-tight figure rendered from a recipe (axis ticks, colorbar position, font sizes drawn from a layout used in real Cell or Nature papers), plus an auto-generated caption that references the source method paper.

Recipes cover marker dot-plots, UMAP embeddings with cluster overlays, neighborhood-enrichment plots, statistical-test result panels, and multi-panel composites. No invented visualizations — every layout traces back to published work, and the recipe metadata records which paper each pattern came from.

### Citations with traceable evidence

Drafts methods or background sections with `[N]` markers, then verifies every one *semantically* against the actual source paper. For each citation: VaultLab pulls the candidate sentence from the draft, reads the relevant passages in the cited PDF, and checks that the source actually supports the specific claim being made.

Hover a citation in your draft to see the exact passage. Hallucinated citations get flagged automatically. VaultLab refuses to ship a manuscript section if any citations are unresolved — no "trust me" output where the reader has to chase down whether the citations are real.

### LLM-driven lineage binning

Reads the abstract of every paper in a corpus and decides *history* / *development* / *state-of-the-art* by conceptual lineage, not just publication year. A 2018 method paper goes in *history* if it's foundational. A 2024 incremental application goes in *development*, not *sota*. The LLM gets the deterministic year-quartile assignment as a hint, then overrides it where conceptual lineage and chronology disagree.

Solves the empty-history-bin failure that pure-quartile binning produces. When every paper in a CODEX corpus is from 2018 onward, there's still a foundational method in there somewhere — the LLM finds it. The arc-generation step then has real history-bucket content to work with instead of placeholder text.

### Wraps the analysis tools you trust

scanpy, squidpy, scikit-image, Cellpose, scipy.stats, statsmodels, pingouin — VaultLab carries a curated index so the LLM picks *real functions from real packages*, not raw web searches that hallucinate function names. Ask for *"a Wilcoxon rank-sum test on these two groups"* and you get `scipy.stats.ranksums` with the right argument order, not a made-up signature.

The index records which package version each function lives in and which papers cite that function as the canonical method. New tools get added via PRs; the curation step is what keeps the choices defensible.

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

Three ways to invoke any of these:

- **Natural language** — describe what you want. *"Build me a journal-club deck on cellular neighborhoods in tonsil tissue."* Claude Code routes to the right slash command automatically. This is the default mode and the one most people stay in.
- **Slash commands** — type `/lit-arc <topic>` or `/build-deck <source>` directly when you know exactly what you want.
- **Python API** — `import vaultlab` and call the modules directly for scripted workflows.

You don't have to memorize the slash commands. Just talk.

Full walkthrough: [`docs/getting-started.md`](docs/getting-started.md). ~10–15 minutes total from clone to first useful KB entry.

> **Cost: just your Claude Code subscription.** No separate Anthropic API key — Claude Code provides LLM access. Optional API keys for literature search (NCBI, Semantic Scholar, Springer, Elsevier) are free or have generous free tiers; NCBI takes five minutes and covers most users. For a second LLM in adversarial cross-checks, Gemini's free API key wires in. Local models work too if you'd rather not call out. Full setup: [`docs/setup-api-keys.md`](docs/setup-api-keys.md).

### Setup docs

If you'd rather read the setup docs first before installing:

- [`docs/getting-started.md`](docs/getting-started.md) — full first-10-minutes walkthrough + 10 best practices
- [`docs/setup-obsidian.md`](docs/setup-obsidian.md) — Obsidian + recommended plugins
- [`docs/setup-api-keys.md`](docs/setup-api-keys.md) — literature API keys (NCBI, S2, Springer, Elsevier)
- [`docs/setup-google.md`](docs/setup-google.md) — Google Cloud Console + OAuth (~10 min)
- [`docs/setup-outlook-windows.md`](docs/setup-outlook-windows.md) — Outlook (Windows only)

---

## Specialty module (in progress)

I work in a spatial-omics lab, so VaultLab has the start of an optional module covering the tools I use day-to-day — CODEX multiplex IF, MALDI imaging, spatial transcriptomics, scRNA-seq, generic imaging / flow. It's not required to use VaultLab and isn't a focus of v0.1; it's an accessory for people whose work touches the same modalities. Most of it is still being built out.

---

## Architecture philosophy

Four commitments that shape every design decision:

1. **Markdown is the user-facing interface; Python is the engine.** Slash commands, role prompts, recipes are markdown — Claude Code reads them directly.
2. **Anti-laziness on semantic reading.** Every LLM call requires quoted evidence. No surface-skim.
3. **Result-oriented agentic loop.** You describe a goal; VaultLab plans + verifies + refines internally; you see the finished result.
4. **KB is the smartness.** No vector DBs, no hidden state. Markdown grows with your work; cross-project reasoning emerges via retrieval.

Full spec: [`docs/architecture.md`](docs/architecture.md). Invariants for contributors: [`AGENTS.md`](AGENTS.md).

---

## How VaultLab compares

Against tools that overlap on one or two capabilities — PaperQA, scanpy, FutureHouse, scverse, Aider:

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

---

## Docs

**Reference:** [`docs/architecture.md`](docs/architecture.md) · [`.claude/commands/COMMANDS.md`](.claude/commands/COMMANDS.md) · [`AGENTS.md`](AGENTS.md) · [`CLAUDE.md`](CLAUDE.md)

**Use cases & workflows:** [`docs/use-cases.md`](docs/use-cases.md)

**Privacy:** [`docs/data-privacy.md`](docs/data-privacy.md) · [`docs/compliance.md`](docs/compliance.md) · [`docs/long-term-reproducibility.md`](docs/long-term-reproducibility.md)

**Lineage:** [`INSPIRATIONS.md`](INSPIRATIONS.md) · [`docs/design-rationale.md`](docs/design-rationale.md)

**Contributors:** [`CONTRIBUTING.md`](CONTRIBUTING.md) · [`docs/graphics-guide.md`](docs/graphics-guide.md)

---

## Influences

VaultLab's patterns are deliberately lifted from open-source projects already at scale, then adapted into a Claude-Code-native harness:

| What VaultLab borrowed | Source |
|---|---|
| The whole conceptual foundation — persistent, compounding wiki maintained by the LLM, three-layer split of raw sources / wiki / schema, with ingest / query / lint as the core operations | [LLM Wiki gist](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f) (Andrej Karpathy) |
| Vault model, wikilinks, frontmatter conventions, plugin ecosystem (Advanced URI / Dataview / Templater) the KB layer assumes | [Obsidian](https://obsidian.md) |
| Claude Code skill-bundle layout — slash commands as plain markdown, AGENTS.md invariants for contributors | [gstack](https://github.com/garrytan/gstack) (Garry Tan) |
| Per-paper grounded summaries with `[pN]` page-marker citations and refuse-to-ship-when-evidence-is-missing | [PaperQA2](https://github.com/Future-House/paper-qa) (FutureHouse) |
| Hover-to-see-quote citation UX — inline evidence visible in draft mode, stripped for final output | [NotebookLM](https://notebooklm.google) (Google) |
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
