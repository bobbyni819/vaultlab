# READ FIRST — vaultlab quick-start for Claude Code

You (Claude Code) are entering a project that uses vaultlab. **This file tells you what to do first and how to be smart about which vaultlab primitives to invoke as the user talks to you.**

If you find yourself defaulting to *"let me write a markdown doc"* without checking whether vaultlab has a primitive that does the job better, **stop and re-read the dispatch table below.** That's the failure mode this file exists to prevent.

## Step 1 — First-encounter checklist (run BEFORE anything else)

Three checks. Run them in order. If any fails, fix it and re-run before invoking ANY vaultlab command.

```python
# 1. Importable?
try:
    import vaultlab  # noqa: F401
except ImportError:
    print("vaultlab not installed. Run: pwsh scripts/bootstrap.ps1  (or bash scripts/bootstrap.sh)")
    raise SystemExit(1)

# 2. KB root resolvable?
from vaultlab.context import resolve_kb_root, KbRootNotConfigured
try:
    kb_root = resolve_kb_root()
except KbRootNotConfigured as exc:
    print(f"KB not configured. Run `vaultlab init` (default: {exc.suggested_default}).")
    raise SystemExit(1)

# 3. Project onboarded?
from vaultlab.onboarding import load_project_config_from_cwd
project_cfg = load_project_config_from_cwd()
# If None: suggest /onboard-me (natural-language) or /onboard-project (structured) or /start-project (topic-only)
```

## Step 2 — Collaborator-activity check (run on FIRST turn of any session)

Before doing the user's task, check whether collaborators have pushed since the user was last here:

```bash
git fetch --all 2>&1 | tail -3
base=$(git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's@^refs/remotes/origin/@@' || echo main)
git log "$(git branch --show-current)..origin/$base" --pretty='%an %ai %s' --since='14 days ago' | head -20
```

If there's recent activity by another author, **surface it in your first response.** Don't silently skip it. Example: *"Note: Rachel pushed 2 commits to origin/main overnight including a publication-ready Crypt panel — `git pull` first, then we'll proceed."*

The `/catch-up` slash command does this automatically with KB + memory + Box folder context. Prefer that on first turn.

## Step 3 — Dispatch table: natural-language ask → vaultlab primitive

This is the most important table in this file. The user converses in natural language. **Your job as Claude is to map their ask to the right primitive instead of defaulting to "write a markdown doc."**

The table is grouped by capability area, and the order reflects vaultlab's three load-bearing strengths: **literature → data analysis → figure generation**. Slide decks come after — they're an output format, not the core work.

### Literature search + paper reading

| If the user says... | Invoke... | Don't... |
|---|---|---|
| "find papers on X" / "what's been published about X" / "literature on X" | `/lit-arc <X>` (orchestrated 7-source corpus + dedup + citation graph + Tier-A reads + lineage arc) | Read existing PDFs + write a synthesis from your training data |
| "do a deeper literature search" / "make sure you cover the field" | `/lit-arc <topic> --depth=thorough` (reads 200-400 abstracts in batched LLM call before ranking) | Recall the field from training |
| "summarize this paper at <DOI>" | `vaultlab.research.summarize` reader callback (returns structured JSON with `[pN]` page-marker citations) | Write a free-form prose summary |
| "compare papers A, B, C" / "what do these three papers say differently" | `vaultlab.research.batched_reader` (≥2 PDFs in one LLM call, leverages 1M-context for cross-paper synthesis) | Read each separately |
| "verify these citations" / "audit this draft for hallucinated refs" | `/cite audit <draft.md>` (refuses to ship if any citation is unsupported) | Spot-check a few |
| "explore citations of <DOI>" / "who cites this / what does this cite" | `/dig-deeper <doi>` (forward + backward citation network) | Manual graph |

### Data analysis + methodology critique (your most-used path for wet-lab work)

| If the user says... | Invoke... | Don't... |
|---|---|---|
| "analyze / explore my data" / "what's interesting in this dataset" | `plan_deep_think_round` (Analyst → Domain Expert → Methods Critic → Synthesizer) — multi-agent adversarial reasoning over actual data | Single-author exploration |
| "is this finding rigorous?" / "would this survive review" | `methods_critic` role pass (rates ROBUST / NEEDS_VALIDATION / WEAK / UNSUPPORTED with a specific test for each) | Give your opinion |
| "audit my methodology / draft" / "check for overclaims" | `rigor_auditor` role pass (claim grounding + page-marker integrity + overclaim detection; outputs structured JSON) | Skim and comment |
| "give me a second opinion on X" | `plan_ensemble_critic` (N parallel critics + Area Chair meta-reviewer) | Just answer yourself |
| "use a Wilcoxon test on these two groups" / specific stats request | `vaultlab.stats` curated index (real package + version + canonical-method paper) | Hallucinate a function name |
| "is this analysis leaky / has bugs" | Analyst → Critic crosstalk via `plan_deep_think_round` | Eyeball the code |

### Figure generation (publication-tight, recipe-backed)

| If the user says... | Invoke... | Don't... |
|---|---|---|
| "make a figure for X" / "plot Y vs Z" | `vaultlab.figures.recipes.<recipe>` — named recipe with axis ticks / colorbar / fontsizes drawn from a real *Cell* or *Nature* layout | Inline matplotlib |
| "draft a figure plan" / "what should I plot" | `figure_lead` role (proposes panels + recipes + supporting evidence) → `methods_critic` to validate | Free-form list |
| "build a multi-panel figure" / "compose panels A-D" | `vaultlab.figures.panel` + `vaultlab.figures.collage` | DIY axes |
| "caption this figure" | Recipe metadata → auto-caption referencing the source method paper | Write from scratch |
| "explore which figure to use for this claim" | `figure_picker` (aspect-aware, tries multiple panels, reads pixels) | Guess |

### Slide decks (output format — comes AFTER the analysis)

| If the user says... | Invoke... | Don't... |
|---|---|---|
| "build a journal-club deck" / "deck on this paper" | `/build-deck <topic-or-doi>` (auto-layouts, 3-tier speaker notes, click animations, audit) | Write slide-bullet markdown |
| "rehearse / practice this deck" | The auto-generated `practice-script.md` + `flashcards.md` sidecars next to the .pptx | Read slides aloud |

### Project + life-context

| If the user says... | Invoke... | Don't... |
|---|---|---|
| "onboard me to a project" / "set up this project" | `/onboard-me` (natural-language) or `/onboard-project` (structured) | Manually create folders |
| "what's the status of project X" | `/research-status` | Skim files |
| "what's new since last session" / "I just got back" | `/catch-up` (git + KB + Box + memory + synthesis line) | Re-read everything |
| "brief me on today" | `/brief` (calendar + emails + tasks + work log) | Manually check each source |
| "log this to my work doc" | `/update <description>` | Open Google Doc directly |
| "send the EOD to John" | `/eod` | Compose by hand |

### The pattern

If there's a vaultlab primitive that's purpose-built for the ask, **invoke it.** If not, write the doc. **Default order of precedence: primitive > role pass > free-form doc.** When in doubt, glance at `.claude/commands/COMMANDS.md` for the full slash-command inventory; never invent a name.

## Step 3.5 — State-aware additive defaults (BEFORE invoking any artifact-producing primitive)

**Every primitive that produces an artifact (lit-arc, figure-from-data, deck-build, deep-think-round, EDA, code-review) must FIRST read existing KB state for prior runs on the same topic / project / claim.** vaultlab is additive over user state by design: building on prior work, not redoing it.

Pre-flight glob (run before the primitive's main work):

```python
# Conceptual — each primitive does its own version of this
from pathlib import Path

def state_aware_preflight(topic: str, kb_root: Path, project_slug: str) -> dict:
    return {
        "existing_arcs": list((kb_root / "Wiki/Concepts").glob(f"*{topic_slug}*lineage*")),
        "tier_a_count": count_summaries_with_topic_tag(kb_root, topic),
        "decisions": (kb_root / project_slug / "decisions-log.md").read_text() if exists else None,
        "prior_outputs": list((kb_root / project_slug / "Output").glob(f"*{topic_slug}*")),
        "related_concepts": semantic_search_concept_docs(topic, kb_root),
    }
```

Branch on what state finds. Default mode + announce it:

| State found | Default mode | Behavior |
|---|---|---|
| Nothing relevant | `--fresh` | Full new corpus / full new analysis. Standard pipeline. |
| Existing arc + ≥30 Tier-A summaries on same topic | `--extend` | Add to existing: only fetch papers NOT already in corpus; rerun picker on combined; rebuild arc with augmented bins. |
| Near-topic existing arc (≥0.7 conceptual overlap) | `--branch` | Start new arc but pre-seed with the related arc's foundational papers; cross-link arcs. |
| Same-topic + existing corpus + this is a follow-up question | `--query-existing` | Answer from existing corpus first; only fan out new search if existing doesn't cover. |
| Existing figures using same recipe | `--variant` | Render new figure but cross-link to prior; note recipe-version + parameter delta. |

**Always announce the choice:** *"You have a 47-paper corpus on cancer spatial transcriptomics from 2026-04-29. I'll extend it (`--extend` mode) — fetching only new papers since, then rerunning the picker on combined."* User can override with `--fresh` if they explicitly want a clean run.

**Maximum-context principle.** Even when the task seems narrow (e.g., "refactor this script"), the primitive should pull cross-domain context: relevant lit summaries, prior decisions, recent commits, related concept docs. Side context yields the unique vaultlab value — *"FYI, your manuscript draft references this function; Schurch 2020 uses a similar pattern."* Don't isolate.

## Step 4 — Role-pass discipline (BEFORE shipping high-stakes claims)

Every "shippable" doc gets the appropriate role pass before you consider it done. Skipping this is the single biggest quality leak in the harness — a `rigor_auditor` pass on a methodology doc once caught a `major` overclaim that had already been written and was about to ship.

| Doc type | Role to invoke | Saves to |
|---|---|---|
| Methodology / Methods doc | `rigor_auditor` (claim grounding, page-marker integrity, overclaim detection) | `<kb>/Output/<project>/rigor-audit-<target>-<date>.md` |
| Concept doc with novelty / "first-to-show" / ranking claim | `methods_critic` (statistical rigor, null comparison, reproducibility rating) | `<kb>/Output/<project>/critic-pass-<target>-<date>.md` |
| Manuscript Results paragraph | `methods_critic` THEN `rigor_auditor` (sequential — content first, then form) | both |
| Lineage arc / lit-arc narrative | `methods_critic` + `literature_critic` | both |
| Figure plan | `figure_lead` → `methods_critic` | per-panel review |
| Deck plan before .pptx ship | Built into `/build-deck` rigor_audit step | inline |

Mechanics: read `src/vaultlab/roles/<name>/prompt.md` and execute the role's TASKS contract verbatim. Output per the role's mandated schema (e.g., `rigor_auditor` MUST output JSON `{passed, issues[]}`; `methods_critic` MUST output per-finding rating + a specific test for any NEEDS_VALIDATION items).

The artifact saved to `Output/` IS the audit trail. If the user asks "did you check this?", point at the file.

## Step 5 — Safety guarantees the user can rely on

If the user is a new lab member trying vaultlab for the first time, surface these proactively when they ask "is this safe to point at my project folder?":

- **Additive-only invariants (AGENTS.md).** vaultlab orchestrators never overwrite or delete user files without explicit confirmation. New artifacts go to `Output/`, `Wiki/Summaries/`, `Sources/Papers/` etc. — never on top of existing user content. Destructive operations (delete, force push, send email, post to external services) require explicit confirmation in chat; they are never silent.
- **Per-output provenance receipts.** Every shipped artifact (deck, lit-arc, audit, figure) writes a sibling `<output>.provenance.json` recording the exact prompt, role, model, and inputs used. Audit-trail by default, no opt-in.
- **No proprietary lock-in.** The KB is plain markdown on whatever cloud sync the user already has (Drive, OneDrive, lab NAS). Any user can read / move / delete it without vaultlab installed. No vector DB, no hidden state, no proprietary format.
- **Hedged voice.** Every LLM-generated claim uses *"consistent with X"* not *"is X"* (see CLAUDE.md commitment #2). Surface-skim is the enemy; quoted page-marker evidence is required.
- **Privacy boundary.** Prompt content goes to Anthropic's Claude API via Claude Code (the user's own subscription). **Not HIPAA-compliant.** Don't put PHI / PII / IRB-restricted data through it. See `docs/data-privacy.md`.
- **Failsafe defaults.** Bounded loops (max 3 iterations on result-oriented agentic loop, 5 rounds on crosstalk meetings), 10-minute wall-clock cap on adversarial meetings, structured-JSON-only outputs to prevent prompt drift.

Quote the relevant guarantee when answering an adoption-barrier question — don't make the user dig through AGENTS.md.

## Step 6 — Async-first writing discipline

When you do produce KB content, write it **asynchronously** to the KB rather than blocking the user with mid-flight questions. Channels:

- `START_HERE.md` per project — daily brief, newest day on top
- `Sources/Notes/grill-<topic>-<date>.md` — open-question docs when N+ decisions are pending
- `decisions-log.md` per project — append-only design/scope decisions
- **Chat** — reserved for genuinely blocking events: destructive ops, GPU compute requests, scope changes that contradict stated goals, IRB/PHI/compliance gates

End every turn with one line: if a grill doc, decisions-log entry, or START_HERE update was written, surface it as a path the user can open at their leisure.

## Step 7 — Where the rest of the docs live

- `CLAUDE.md` — architectural philosophy + the six core commitments (read after this file)
- `AGENTS.md` — invariants and conventions; required reading before any code change
- `.claude/commands/COMMANDS.md` — full slash-command inventory (read when uncertain about a primitive's existence or exact name)
- `src/vaultlab/roles/<name>/prompt.md` — role contracts (read when invoking a role)
- `docs/architecture.md` — full architectural spec
- `docs/getting-started.md` — first-10-min user walkthrough
- `Sources/Notes/friction-findings-from-metabolism-run-2026-05-05.md` (in KB) — what NOT to do; lessons from the dogfood run

## The single most important rule

**Don't default to "write a markdown doc" without checking the dispatch table.** That's the failure mode this file is engineered to prevent. If you find yourself about to write a 500+ word doc, pause: is there a vaultlab primitive that does this? If yes, invoke it. If no, proceed with the doc and own the choice.

vaultlab's value isn't in the docs Claude writes — it's in the structured primitives (lit-arc, role-passes, recipe-backed figures, deep-think rounds) that produce verifiable, reproducible work. Use them.
