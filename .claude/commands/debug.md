---
name: debug
description: Multi-agent debug round for tracebacks / failing scripts. Analyst hypothesizes, methods_critic challenges, synthesizer proposes fix. Auto-logs lessons to decisions-log.
arguments: <traceback-or-symptom-description>
---

# /debug <traceback-or-description>

> "My script throws `KeyError: 'CD11c'` on row 4012 of the segmentation pipeline. Help."

Multi-agent debug round: analyst forms hypotheses, methods_critic challenges them with the project's existing conventions (read from decisions-log), synthesizer proposes a concrete fix. Auto-appends a debug-lesson entry to `decisions-log.md` so the same class of bug doesn't recur silently.

## Lineage

Lifts the **multi-agent meeting** pattern (analyst → critic → synthesizer) from **virtual-lab** (Zou group, Stanford). The verifier-driven termination — fix accepted only when the synthesizer's proposed fix runs cleanly + the analyst's hypothesis is confirmed — follows **AI-Scientist** (Sakana AI).

## Pre-flight checklist

1. Resolve KB root + project config
2. **Read the relevant code:** the script around the failing line, plus its imports + tests
3. Read `decisions-log.md` — the project may have prior conventions about this class of issue (e.g., panel-version branching, FDR thresholds, sample-stratification defaults)
4. State-aware preflight: search `Output/debug-*.md` for prior debug runs on this script — has this exact issue been seen before?

## Execution

### Step 1 — Symptom + context capture

Parse the user's traceback or description. Record:

```python
{
    "symptom": <user's description>,
    "traceback": <full traceback if provided>,
    "failing_line": <file:line>,
    "scope_around_failure": <±20 lines>,
    "imports_in_failing_module": <list>,
    "related_test_files": <list>,
    "decisions_log_relevant_entries": <text>,
}
```

### Step 2 — Multi-agent round

| Role | Task |
|---|---|
| **analyst** | Generate 3-5 hypotheses for the failure. For each: what conditions trigger it, what fix would address it, what evidence in the data would confirm. Hedged voice ("consistent with X" not "is X"). |
| **methods_critic** | For each hypothesis: cross-reference against the project's decisions-log. Does any prior decision contradict the proposed fix? E.g., "decisions-log says we use spearman after Round 8; proposed fix uses pearson — flag as potential regression." Rank hypotheses ROBUST / NEEDS_VALIDATION / WEAK / UNSUPPORTED. |
| **synthesizer** | Pick the highest-rated robust hypothesis. Propose a concrete fix as a code snippet with: (a) the change, (b) a regression test that would have caught the original bug, (c) what to add to decisions-log. |

### Step 3 — Apply + verify

If the synthesizer's confidence is HIGH (no NEEDS_VALIDATION caveats):

1. Write the fix to the script (with explicit confirmation prompt before any `Edit`)
2. Run the script — does the original error go away?
3. Run any existing tests — do they all still pass?
4. If both green: commit suggestion (don't auto-commit; prompt user)

If confidence is MIXED: surface the top hypothesis + the test-it-with-this-data plan. Don't apply the fix.

### Step 4 — Auto-update decisions-log

Append to `<kb_root>/<project>/decisions-log.md`:

```markdown
## <date> — Debug fix: <one-line summary>

**Symptom:** <from Step 1>
**Root cause:** <from synthesizer>
**Fix:** <concrete change>
**Heuristic:** <generalizable lesson — "if X class of error, check Y first">
**Regression test:** <test path>
```

This makes the lesson durable across sessions.

### Step 5 — Render full output

Write to `<kb_root>/<project>/Output/debug-<symptom-slug>-<date>.md` (full multi-agent transcript + decision).

### Step 6 — Reply

*"Top hypothesis: **<root cause>**. Confidence: <high/mixed>. Proposed fix: <code snippet>. Apply now? Or read full reasoning: `bobby-kb open ...`"*

## When to invoke

- User pastes a traceback
- User says *"this throws on row N"*, *"why does this fail"*, *"help me figure out X bug"*
- A test suite reports a regression and the user asks for analysis

## When NOT to invoke

- Quick syntax-error fixes obvious from one read (just fix them)
- Test-failure debugging where reading the test + the code is enough (no multi-agent round needed)
- Type-check errors caught by mypy/pyright (lower stakes; one-shot fix)

## Follow-up

After every debug run, suggest adding a regression test if one doesn't already exist. Per CLAUDE.md commitment #2 (anti-laziness), the fix without a test is incomplete.
