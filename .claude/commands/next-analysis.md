---
name: next-analysis
description: "Pick up where I left off — what's the next analysis to run." Reads project state + cross-project analogs + ranked candidate analyses via multi-agent deep-think round.
arguments: [optional-focus-hint]
---

# /next-analysis [optional focus hint]

> "I'm 4 weeks into the project. I have new CODEX data + 50 cached PDFs. What's the most impactful analysis to run next?"

Reads the user's project state, queries cross-project KB for related work, runs a multi-agent meeting (analyst → domain expert → methods critic → synthesizer) over the actual project context, and returns a ranked list of candidate analyses with hypothesis + method + expected outcome + risks per candidate.

## Lineage

Lifts the **plan → execute → verify → refine** inner loop with reflection-round caps from **AI-Scientist** (Sakana AI). The analyst → domain-expert → critic → synthesizer rounds with structured-JSON-only output and bounded-loops follow **virtual-lab** (Swanson et al., *Nature* 2025).

## Pre-flight checklist

1. Resolve KB root via `vaultlab.context.resolve_kb_root`
2. Read project state: `START_HERE.md` + `decisions-log.md` + recent `Output/*.md`
3. **Auto-fetch collaborator commits** (per READ_FIRST.md Step 2): `git fetch && git log <branch>..origin/<base> --since='14d'`. Surface anything new before proceeding.
4. State-aware preflight: glob prior `Output/next-analysis-*.md` runs. If a recent one (<3 days) exists, default to mode `--extend` (build on its conclusions).

## Execution

### Step 1 — Project context load

Build a context bundle:

```python
context = {
    "project_topic": <from .vaultlab-project.json>,
    "current_aim": <last entry in decisions-log.md>,
    "open_questions": <from grill-*.md>,
    "recent_findings": <last 5 Output/*.md by mtime>,
    "data_state": <list files in <project>/data/ with sizes>,
    "collaborator_recent_pushes": <git log of OTHER authors, last 14d>,
}
```

### Step 2 — Cross-project priors

Run `/find-analogs <project_topic>` internally (or invoke its underlying logic) to surface related concept docs across other KBs. These become "what we already know from sibling projects."

### Step 3 — Multi-agent deep-think round

Spawn 4 sub-agents per `plan_deep_think_round`:

| Role | Task |
|---|---|
| **analyst** | Given the project state + cross-project priors, propose 5-7 candidate analyses. For each: hypothesis, method (specific real package + function + canonical-method paper from `vaultlab.stats` index), expected outcome, sample-size feasibility check. |
| **domain_expert** | Apply biological/scientific domain knowledge: which candidates are biologically plausible? Which would the field find novel vs incremental? |
| **methods_critic** | For each candidate: rate ROBUST / NEEDS_VALIDATION / WEAK / UNSUPPORTED. Flag confounds, statistical assumptions that don't hold, sample-size shortfalls. |
| **synthesizer** | Rank the surviving candidates 1..N with explicit tradeoff reasoning. Surface 1-2 *"this also pairs with X analog from sibling project"* notes from Step 2. |

Each role's system prompt MUST include the KB-context preamble (per CLAUDE.md commitment #7).

### Step 4 — Render output

Write to `<kb_root>/<current-project>/Output/next-analysis-<date>.md`:

```markdown
# Next analysis recommendations — <project>

Generated <date> by /next-analysis. Context: <one-line summary>.

## Top 3 candidates

### 1. <analysis name> — RECOMMENDED

- **Hypothesis:** <1-2 sentences>
- **Method:** `<specific function from real package>` (cite paper)
- **Expected outcome:** <prediction>
- **Why this rank:** <synthesizer reasoning>
- **Sibling-project pairing:** <link to analog from Step 2 if any>
- **Risks:** <from methods_critic>

(repeat for #2 and #3)

## Lower-ranked candidates (4-N)

(brief 1-line reasoning per drop)

## Open questions for Bobby

<from synthesizer — design decisions worth chat>
```

### Step 5 — Reply

*"Recommended next analysis: **<name>**. Why: <one sentence>. Want me to scaffold the script and run it? Full reasoning: `bobby-kb open ...`"*

## When to invoke

- After `/catch-up` shows the user is mid-project with clean state
- When the user explicitly asks "what's next" or "what should I do"
- After completing an analysis — to surface follow-up paths

## Follow-up

If the user says yes to the scaffolding question, proceed to scaffold the script in the project repo, run it, write results back to `Output/`, then auto-trigger `methods_critic` per the role-pass discipline (READ_FIRST Step 4).
