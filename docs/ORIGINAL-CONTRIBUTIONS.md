# Original contributions vs borrowed patterns

**Companion document to [`INSPIRATIONS.md`](../INSPIRATIONS.md).**

`INSPIRATIONS.md` records what vaultlab borrowed from external sources. This document is its mirror — what's **uniquely Bobby's** vs what's borrowed. Useful for:
- Internship interviews (*"what did YOU build vs what did you wrap?"*)
- arXiv preprint Section 1 (*"contributions of this work"*)
- Honest self-assessment of where the novel work is

## Three categories

Every component of vaultlab fits in one of three buckets:

| Category | What it means | Example |
|---|---|---|
| **🟢 Bobby's original** | Designed by Bobby; no direct external precedent | The "research-companion vs autonomous-lab" framing; the KB-mediated agent state pattern; the figure-recipe corpus-backed-provenance discipline |
| **🟡 Bobby's synthesis** | Combination is original; component patterns borrowed | The 9-module bobby_ailab structure; the 4 META PRINCIPLES; the 6-stage hallucination handling stack |
| **🔵 Borrowed** | Pattern or code from an external source; documented in INSPIRATIONS.md | Multi-agent meetings (virtual-lab); fork-and-clone primary distribution (Karpathy); grep-map-reduce paradigm (paperclip); typed shared state (process-bigraph) |

The honest framing: vaultlab is mostly 🟡 (synthesis) with islands of 🟢 (original) over a foundation of 🔵 (borrowed). That's normal for a research-tool repo built on top of an OSS ecosystem. The value is in the synthesis + the islands.

---

## 🟢 Bobby's original contributions

These are the parts where Bobby designed something with no direct external precedent. They're the most interview-worthy and the most worth highlighting in a preprint.

### 1. The "research companion vs autonomous lab" framing

**What:** vaultlab's positioning as a research COMPANION (accompanies the researcher through their actual work) rather than an autonomous AI scientist (generates questions and writes papers).

**Why it's original:** Most current AI lab tools (FutureHouse, AI-Scientist, OpenDevin-for-bio) optimize for autonomy. vaultlab inverts: optimize for *being useful to a working researcher today*. This makes it journal-compatible (no "AI wrote my paper" liability), institution-compatible (no autonomy concerns), and adoption-friendly (researchers don't have to change how they work).

**Where in vaultlab:** README hero + use-cases doc + the entire architecture grill master plan.

**Why it matters:** Most AI labs are built for the *future* researcher who delegates everything; vaultlab is built for the *current* researcher who delegates the rote work and keeps the science.

### 2. The KB-as-memory architecture for cross-project reasoning

**What:** vaultlab's strict rule that every analysis writes to the KB, and every analysis reads from it. The KB grows project-by-project; cross-project insights emerge via retrieval.

**Why it's original:** Other tools use vector DBs (ChromaDB, Weaviate) or proprietary memory layers (Anthropic Memory). vaultlab uses **plain markdown files** in an Obsidian-compatible folder, addressable by Claude Code. The smartness comes from the corpus growing, not from a clever vector index.

**Where in vaultlab:** `vaultlab.kb`, `vaultlab.context`, `vaultlab.runner.bounded_loop`. Master plan section 3.4 ("KB is the smartness").

**Inspiration adjacent:** NotebookLM uses notebooks-as-context (CONCEPT borrow). But the strict KB-as-the-only-memory rule + Obsidian-native compatibility is Bobby's.

### 3. The corpus-backed figure recipe discipline

**What:** Every figure recipe in `vaultlab.figures.recipes/` MUST cite ≥3 published examples in the corpus. No "Claude guessed this would look good" recipes.

**Why it's original:** No other figure-helper library does this. scanpy's plot library doesn't cite specific papers per plot type. seaborn's gallery is illustrative, not auditable. vaultlab's corpus discipline (every recipe has a `corpus/sources.json` entry with DOIs + GitHub repos) makes the visual choices defensible.

**Where in vaultlab:** `vaultlab.figures.corpus`, `vaultlab.figures.recipes/<recipe>.md` template, `templates/recipe/`.

**Why it matters:** Reviewers ask "why did you pick this visualization?" vaultlab can answer concretely.

### 4. The Rule 14 figure-color discipline + post-regen visual audit

**What:** Default to neutral grey for categorical bars when row labels already name the category. Only opt in to color for sign / cross-panel-tracking / secondary axis. Plus: every figure regeneration triggers a post-regen visual audit (Read the PNG; walk a 7-point checklist).

**Why it's original:** This rule emerged from Bobby's actual review of metabolism-pipeline figures over 14 rounds. It's documented in `tools/Wiki/Methodology/figure-design-rules-learned.md`. It's lab-tested empirical, not adopted from elsewhere.

**Where in vaultlab:** `vaultlab.figures.publication.color.bar_fill()` enforces it; `figure-audit-capability-spec.md` mandates the visual audit.

**Why it matters:** Most figure-style libraries just provide colormaps. vaultlab provides *discipline* — the rule that prevents 6 rainbow plots surviving 12 rounds of review.

### 5. The hedged-voice enforcement for ALL LLM outputs

**What:** A guardrail layer (`vaultlab.roles._guardrails.enforce_hedge()`) that flags assertions which should be hedged. *"X IS Y"* gets suggested as *"X is consistent with Y."* Applied to every LLM-generated interpretation, no exceptions.

**Why it's original:** Most LLM tools encourage confident output. vaultlab inverts: confident voice is a bug. This isn't a bolt-on prompt; it's a structural commitment baked into AGENTS.md as a quality bar.

**Where in vaultlab:** `roles/<role>/prompt.md` files, `vaultlab.roles._guardrails`, AGENTS.md "Hedged voice" section.

**Why it matters:** Reviewers can tell when an LLM wrote something. Hedged voice + quoted evidence makes vaultlab outputs read like a careful researcher's notes.

### 6. The 6-stage hallucination handling stack

**What:** Constrained generation → semantic citation audit → numeric audit → cross-doc consistency → self-critique → hedged-voice enforcement. Every output passes through all six. Refusal to mark task complete if N issues unresolved.

**Why it's original:** Most LLM tools have ONE of these (e.g., PaperQA does the citation audit; Claude does self-critique on demand). vaultlab combines all six and refuses-to-ship on failure. The combination + the refusal-gate is the novel pattern.

**Where in vaultlab:** Master plan §6.1 + `vaultlab.runner.bounded_loop` + AGENTS.md.

### 7. The strict markdown-is-the-interface meta principle

**What:** All prompts, role definitions, workflow descriptions, slash commands, and skill bundles live as **markdown files** in the repo. Python contains orchestration; markdown contains content. *"If you find yourself writing a triple-quoted prompt in Python, that's a bug."*

**Why it's original:** gstack uses markdown for skill descriptions, but Garry's prompt content still lives in Python. virtual-lab embeds prompts in Python. AI-Scientist uses JSON+Python. vaultlab strictly separates: **prompts are markdown, period**. This is what makes vaultlab Claude-Code-readable end-to-end.

**Where in vaultlab:** AGENTS.md Invariant 7, every `roles/<role>/{role.py, prompt.md}` pair, every `<recipe>.py + <recipe>.md` pair.

---

## 🟡 Bobby's synthesis (combinations of borrowed patterns)

These are valuable but not *novel* — they combine borrowed ingredients in a useful way.

### 1. The 9-module `bobby_ailab` orchestration core

**Synthesis of:** virtual-lab's meeting structure + AI-Scientist's role-distribution + bigraph-process's typed shared state + Bobby's own architectural tastes.

**Documented in:** Architecture grill file 02; master plan §5.

### 2. The 4 META PRINCIPLES

- Markdown-is-interface (Bobby original)
- Anti-laziness on semantic reading (Bobby's framing of a common LLM problem)
- Result-oriented agentic loop (synthesis of bounded-loop + virtual-lab refinement)
- KB is the smartness (Bobby's framing + NotebookLM-adjacent concept)

**Documented in:** README + AGENTS.md + master plan §3.

### 3. The Hybrid C distribution model (fork-and-clone primary)

**Synthesis of:** Karpathy's nanoGPT philosophy + bobby-tools' existing repo pattern. Bobby's contribution: applying it to a multi-package research tool (Karpathy's was always single-file).

**Documented in:** README install section + master plan §2.

### 4. The 23-slash-command inventory

**Synthesis of:** gstack's sprint-workflow skills (think/plan/build/review/test/ship) + Bobby's research-pipeline phases (verify-data → reasoning → figures → write → review).

**Documented in:** Architecture grill file 10 Q10.2; planned `.claude/commands/`.

### 5. The vaultlab demo trio (pbmc3k + Visium + CODEX HuBMAP)

**Synthesis of:** standard-dataset choices (pbmc3k from scanpy tutorials, Visium from 10x examples, CODEX from HuBMAP). Bobby's contribution: choosing this specific trio (covers scRNA-seq + spatial-transcriptomics + spatial-imaging) and the wet-lab → manuscript framing per dataset.

**Documented in:** `examples/` directories + README + file 16.

### 6. The "research companion" workflow positioning vs autonomous mode

**Synthesis of:** Aider's companion-not-autonomous philosophy (concept borrow) + Bobby's framing for biological research (original application).

**Documented in:** README "Companion mode, not autonomous mode" section.

---

## 🔵 Pure borrowing (documented in INSPIRATIONS.md)

These are external patterns or code that vaultlab uses without significant modification.

| Source | What we borrowed | Category |
|---|---|---|
| virtual-lab | Multi-agent meeting structure, temperature control, Scientific Critic role | PATTERN |
| AI-Scientist | Numbered round structure, EvidenceBundle, reflection loops | PATTERN |
| paperclip | Grep-map-reduce literature paradigm, virtual filesystem framing | PATTERN |
| gstack | Sprint workflow framing, /office-hours, /codex, /learn, /retro | PATTERN/CONCEPT |
| Karpathy nanoGPT | Code-as-documentation philosophy, fork-and-clone primary | CONCEPT |
| NotebookLM | Citation evidence UX (hover-to-quote) | CONCEPT |
| scanpy/squidpy/Cellpose/Mesmer | Wrapped, not modified | TOOL |
| Schürch et al. 2020 | Cellular neighborhood methodology | PATTERN |
| process-bigraph | Typed shared state, dependency-driven step networks | PATTERN |
| MultiAgent (Bobby's own) | Three-layer error defense, BSS YAML, deterministic eval | PATTERN |
| CODEX_MALDIIMS (Bobby's own) | Figure helpers ported (P0.1) | CODE |
| bobby_google + bobby_outlook (Bobby's own) | Google + Outlook integration code lifted | CODE |

See [`INSPIRATIONS.md`](../INSPIRATIONS.md) for full attribution per source.

---

## Honest TL;DR

If asked "what did you actually build vs what did you wrap":

> *"vaultlab is built on the shoulders of multiple OSS projects. The novel work is in five places: (1) the research-companion-vs-autonomous-lab framing, (2) the strict markdown-is-the-interface meta principle that makes the entire repo Claude-Code-readable, (3) the corpus-backed figure recipe discipline (every recipe cites ≥3 published examples), (4) the 6-stage hallucination handling stack with refuse-to-ship gating, and (5) the Rule 14 figure color discipline that emerged from 14 rounds of empirical review. Around those originals, I synthesized the orchestration architecture by adapting patterns from virtual-lab (multi-agent meetings), AI-Scientist (role distribution + reflection), paperclip (grep/map/reduce), gstack (sprint workflow), and process-bigraph (typed shared state). The wet-lab analysis layer wraps scanpy / squidpy / Cellpose / Mesmer; the figure-helper layer was ported from my CODEX_MALDIIMS work; the Google + Outlook integration was lifted from my bobby-tools personal toolkit. The whole is a research companion, not a research replacement."*

That's the elevator pitch when an interviewer asks. Use as needed.

## Pending Bobby review

This document is a starting point. To finalize:

- [ ] Bobby reviews each 🟢 entry — confirm "no direct external precedent" claim or downgrade to 🟡
- [ ] Bobby adds anything 🟢 that I missed
- [ ] Once finalized, link from README + use in arXiv preprint Section 1
