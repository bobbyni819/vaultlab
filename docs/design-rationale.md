# VaultLab — design rationale

This document explains **what VaultLab decided to do differently** from comparable tools (PaperQA, AI-Scientist, FutureHouse, scanpy, scverse, Aider) and **why those decisions matter for the user**.

It is not an authorship audit — see [`INSPIRATIONS.md`](../INSPIRATIONS.md) for the lineage of patterns the project draws on. This document focuses on *project-level design choices* rather than who made them.

Future contributors are welcome to extend this with new design choices that emerge as the project grows.

---

## Three categories

Every architectural decision in VaultLab fits one of three buckets:

| Category | What it means | Examples |
|---|---|---|
| **🟢 Novel choices** | Design decisions with no direct precedent in the comparable-tools landscape | Async-first feedback loop with four channels; centralized memory as a first-class commitment; per-user locations registry; pluggable judge-as-config |
| **🟡 Synthesis** | Combinations of established patterns assembled in a project-specific way | The orchestration core (multi-agent meetings + plan-execute-verify-refine + typed shared state); the demo trio (PBMC3k + Visium + CODEX HuBMAP); the slash-command inventory |
| **🔵 Borrowed** | Established patterns or wrapped tools used without significant modification | scanpy / squidpy / Cellpose for analysis; multi-agent meeting structure from virtual-lab; fork-and-clone distribution from nanoGPT; documented in `INSPIRATIONS.md` |

The honest framing: VaultLab is mostly 🟡 (synthesis) with islands of 🟢 (novel choices) over a foundation of 🔵 (borrowed). That's normal for any research tool built on top of an OSS ecosystem. The value is in the synthesis + the islands.

---

## 🟢 Novel design choices

These are decisions where VaultLab took a different path than the comparable-tools landscape. Each is documented with what / why-this-design-choice / where-in-vaultlab / why-it-matters-to-the-user.

### 1. Research companion, not autonomous lab

**What:** VaultLab is positioned as a research **companion** that accompanies the researcher through their actual work, rather than as an autonomous AI scientist that generates questions and writes papers.

**Why this design choice:** Most current AI lab tools (FutureHouse, AI-Scientist, OpenDevin-for-bio) optimize for autonomy. VaultLab inverts: optimize for *being useful to a working researcher today*. This makes it journal-compatible (no "AI wrote my paper" liability), institution-compatible (no autonomy concerns), and adoption-friendly (researchers don't have to change how they work).

**Where in VaultLab:** README hero + `docs/use-cases.md` + master plan §1 / §3.6.

**Why it matters to the user:** Most AI labs are built for the *future* researcher who delegates everything; VaultLab is built for the *current* researcher who delegates the rote work and keeps the science.

### 2. KB-as-memory architecture for cross-project reasoning

**What:** Every analysis writes to the KB; every analysis reads from it. The KB grows project-by-project; cross-project insights emerge via retrieval.

**Why this design choice:** Other tools use vector DBs (ChromaDB, Weaviate) or proprietary memory layers. VaultLab uses **plain markdown files** in an Obsidian-compatible folder, addressable by Claude Code. The smartness comes from the corpus growing, not from a clever vector index.

**Where in VaultLab:** `vaultlab.kb`, `vaultlab.context`, `vaultlab.runner.bounded_loop`, master plan §3.4.

**Adjacent precedent:** NotebookLM uses notebooks-as-context (concept influence). The strict KB-as-the-only-memory rule + Obsidian-native compatibility is the project-specific addition.

### 3. Corpus-backed figure recipe discipline

**What:** Every figure recipe in `vaultlab.figures.recipes/` MUST cite ≥3 published examples in the corpus. No "the LLM guessed this would look good" recipes.

**Why this design choice:** No other figure-helper library does this. scanpy's plot library doesn't cite specific papers per plot type; seaborn's gallery is illustrative, not auditable. VaultLab's corpus discipline (every recipe has a `corpus/sources.json` entry with DOIs + GitHub repos) makes the visual choices defensible.

**Where in VaultLab:** `vaultlab.figures.corpus`, `vaultlab.figures.recipes/<recipe>.md` template, `templates/recipe/`.

**Why it matters to the user:** Reviewers ask *"why did you pick this visualization?"* VaultLab can answer concretely.

### 4. Rule-14 figure color discipline + post-regen visual audit

**What:** Default to neutral grey for categorical bars when row labels already name the category. Only opt in to color for sign / cross-panel-tracking / secondary axis. Plus: every figure regeneration triggers a post-regen visual audit (Read the PNG; walk a 7-point checklist).

**Why this design choice:** Most figure-style libraries provide colormaps. VaultLab provides *discipline* — the rule that prevents 6 rainbow plots surviving 12 rounds of review. The rule is empirical: it emerged from real-world figure review feedback over many rounds.

**Where in VaultLab:** `vaultlab.figures.publication.color.bar_fill()` enforces it; `figure-audit-capability-spec.md` mandates the visual audit.

### 5. Hedged-voice enforcement for ALL LLM outputs

**What:** A guardrail layer (`vaultlab.roles._guardrails.enforce_hedge()`) flags assertions that should be hedged. *"X IS Y"* gets suggested as *"X is consistent with Y."* Applied to every LLM-generated interpretation, no exceptions.

**Why this design choice:** Most LLM tools encourage confident output. VaultLab inverts: confident voice is a bug. This isn't a bolt-on prompt; it's a structural commitment baked into AGENTS.md as a quality bar.

**Where in VaultLab:** `roles/<role>/prompt.md` files, `vaultlab.roles._guardrails`, AGENTS.md "Hedged voice" section.

**Why it matters to the user:** Reviewers can tell when an LLM wrote something. Hedged voice + quoted evidence makes outputs read like a careful researcher's notes.

### 6. Six-stage hallucination-handling stack with refuse-to-ship gating

**What:** Constrained generation → semantic citation audit → numeric audit → cross-doc consistency → self-critique → hedged-voice enforcement. Every output passes through all six. The runner refuses to mark a task complete if N issues remain unresolved.

**Why this design choice:** Most LLM tools have ONE of these (e.g., PaperQA does the citation audit; Claude does self-critique on demand). VaultLab combines all six and refuses-to-ship on failure. The combination + the refusal-gate is the integrative pattern.

**Where in VaultLab:** Master plan §6.1, `vaultlab.runner.bounded_loop`, AGENTS.md.

### 7. Strict markdown-is-the-interface meta principle

**What:** All prompts, role definitions, workflow descriptions, slash commands, and skill bundles live as **markdown files** in the repo. Python contains orchestration; markdown contains content. *"If you find yourself writing a triple-quoted prompt in Python, that's a bug."*

**Why this design choice:** gstack uses markdown for skill descriptions, but its prompt content still lives in Python. virtual-lab embeds prompts in Python. AI-Scientist uses JSON+Python. VaultLab strictly separates: **prompts are markdown, period**. This is what makes the project Claude-Code-readable end-to-end.

**Where in VaultLab:** AGENTS.md Invariant 7, every `roles/<role>/{role.py, prompt.md}` pair, every `<recipe>.py + <recipe>.md` pair.

### 8. Async-first feedback loop (the four channels)

**What:** Open questions and design decisions go to **markdown documents in the KB**, not blocking chat questions. Four distinct channels: `START_HERE.md` (auto-maintained current state), `grill-<topic>-<date>.md` (numbered open-question docs), `decisions-log.md` (append-only design record), and chat (reserved for *immediately blocking* events only — destructive actions, IRB/PHI gates, cost-tier escalation). Every command auto-surfaces unread KB docs as `bobby-kb open <path>` at end-of-turn.

**Why this design choice:** No comparable AI research tool is known to separate blocking vs non-blocking interaction this way. PaperQA, AI-Scientist, FutureHouse all work synchronously — block when uncertain. VaultLab inverts: keep working, queue questions in markdown the user reads at their leisure. The four-channel split (with explicit boundary criteria for what stays blocking) is the project-specific pattern.

**Where in VaultLab:** AGENTS.md Invariant 10, CLAUDE.md commitment 5, `vaultlab.kb.feedback`, master plan §3.5.

**Why it matters to the user:** It's the only design that scales when a researcher uses VaultLab across many parallel projects — they don't get pinged 20 times a day with mid-flight clarifications. The system batches the questions; the user answers in batches.

### 9. Centralized memory as a first-class architectural commitment

**What:** Six fragmented sources of context — knowledge base, meeting transcripts, inbox + calendar + work log, local files, project state files, per-user locations registry — stitched into one place the LLM reads. Made into a META PRINCIPLE (commitment 6) so every new VaultLab feature must answer *"how does this read from / write to centralized memory?"*

**Why this design choice:** Most AI research tools have ONE memory channel — typically a vector index over papers, or a private session memory (model context window). VaultLab's commitment to **integrating six** plus the rule that every feature must engage with centralized memory is structurally different. Closest precedent is NotebookLM's notebooks-as-context, but NotebookLM is single-channel; VaultLab adds inbox / calendar / meetings / project state.

**Where in VaultLab:** README flagship section, CLAUDE.md commitment 6, master plan §3.6, `vaultlab.context.*` subpackages.

### 10. Per-user locations registry — `locations.toml`

**What:** A per-user, per-machine config (`~/.config/vaultlab/locations.toml`) that names the user's standard file paths once: where their meeting transcripts live (Drive folder + local video dir), which Google Doc is their work log, which Drive folders correspond to which research projects, which Google Docs to read by named alias. VaultLab consults this registry instead of asking the user every session.

**Why this design choice:** No equivalent in other research tools. Most either (a) ask the user each session where things live, or (b) hardcode paths in source. The locations registry — declarative, named, queryable — is novel for AI research tooling. Plays directly with the async-first principle: when a path is missing, VaultLab writes a grill doc rather than blocking the chat.

**Where in VaultLab:** Master plan §4b, `vaultlab.context.locations` (in build).

### 11. Pluggable adversary / judge model

**What:** Adversary, judge, and verifier roles in the runner do not hardcode a specific model identifier. Users plug in OpenAI, Gemini, local Llama, Claude variants, etc. via `~/.config/vaultlab/models.toml`. Role implementations call `vaultlab.runner.judge_for(role)` instead of hardcoding. Capability requirements (vision, long context, tool use) are declared in role frontmatter so the config layer warns on incompatible substitutions.

**Why this design choice:** Most multi-agent research tools (virtual-lab, AI-Scientist) bake the model choice into the code. Switching judges = forking. VaultLab's *judge-as-config* pattern is the cleanest precedent for letting researchers compare LLMs on their own data without forking.

**Where in VaultLab:** AGENTS.md Invariant 11, `vaultlab.runner.judge_for()` (planned).

---

## 🟡 Synthesis (combinations of established patterns)

Valuable but not novel — these combine borrowed ingredients in a useful way.

### 1. The orchestration core

Combines virtual-lab's meeting structure + AI-Scientist's role distribution + process-bigraph's typed shared state + project-specific architectural choices. Documented in master plan §5.

### 2. The 6 META PRINCIPLES

- Markdown-is-interface (novel to VaultLab)
- Anti-laziness on semantic reading (project-specific framing of a common LLM problem)
- Result-oriented agentic loop (synthesis of bounded-loop + virtual-lab refinement)
- KB is the smartness (project-specific framing + NotebookLM-adjacent concept)
- Async-first feedback loop (novel to VaultLab — see entry #8 above)
- Centralized memory is the flagship (novel to VaultLab — see entry #9 above)

Documented in README + AGENTS.md + master plan §3.

### 3. The Hybrid C distribution model (fork-and-clone primary)

Synthesis of nanoGPT philosophy + project-specific repo pattern. The contribution: applying it to a multi-package research tool (nanoGPT was always single-file). Documented in README install section + master plan §2.

### 4. The slash-command inventory

Synthesis of gstack's sprint-workflow skills (think/plan/build/review/test/ship) + research-pipeline phases (verify-data → reasoning → figures → write → review). Documented in architecture grill file 10 + planned `.claude/commands/`.

### 5. The demo trio (PBMC3k + Visium + CODEX HuBMAP)

Synthesis of standard-dataset choices (PBMC3k from scanpy tutorials, Visium from 10x examples, CODEX from HuBMAP). The contribution: choosing this specific trio (covers scRNA-seq + spatial-transcriptomics + spatial-imaging) and the wet-lab → manuscript framing per dataset. Documented in `examples/` + README + master plan §7.

### 6. Companion-mode positioning

Synthesis of Aider's companion-not-autonomous philosophy (concept influence) + project-specific framing for biological research. Documented in README "Companion mode, not autonomous mode" section.

---

## 🔵 Borrowed components

Established patterns or wrapped tools used without significant modification.

| Source | What VaultLab borrows | Category |
|---|---|---|
| virtual-lab | Multi-agent meeting structure, temperature control, Scientific Critic role | PATTERN |
| AI-Scientist | Numbered round structure, EvidenceBundle, reflection loops | PATTERN |
| paperclip | Grep-map-reduce literature paradigm, virtual filesystem framing | PATTERN |
| gstack | Sprint workflow framing, skill bundle organization | PATTERN/CONCEPT |
| nanoGPT | Code-as-documentation philosophy, fork-and-clone primary | CONCEPT |
| NotebookLM | Citation evidence UX (hover-to-quote) | CONCEPT |
| scanpy / squidpy / Cellpose | Wrapped, not modified | TOOL |
| Schürch et al. 2020 | Cellular neighborhood methodology | PATTERN |
| process-bigraph | Typed shared state, dependency-driven step networks | PATTERN |

See [`INSPIRATIONS.md`](../INSPIRATIONS.md) for full attribution per source.

---

## Where the substance is

| Tier | Count | Substance |
|---|---|---|
| 🟢 Novel choices | **11** | Each documented above with rationale + where-in-vaultlab. Several have *no precedent* in any AI research tool audited (async-first four-channel feedback, the centralized-memory architectural rule, locations registry, judge-as-config). |
| 🟡 Synthesis | **6** | Combinations of borrowed components into VaultLab-specific architectures. Documented above. |
| 🔵 Borrowed | many | Wrapped tools (scanpy, etc.), referenced patterns (multi-agent meetings, plan-execute loops). Always credited via `INSPIRATIONS.md` and the README lineage table. |

The 11 novel choices + 6 syntheses are the answer to *"is this just a wrapper around existing tools?"* — no, the wrapping pattern itself is novel in several specific places.

---

## Contributing to this document

If you contribute a design pattern that you believe is novel to VaultLab vs the comparable-tools landscape, add an entry under §"🟢 Novel design choices" with the four-section format (What / Why this design choice / Where in VaultLab / Why it matters to the user). Be willing to defend the "no precedent" claim — link to a literature search or the closest adjacent tool.

For pure synthesis or pure borrowing, the corresponding §🟡 / §🔵 sections are the right home.
