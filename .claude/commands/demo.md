---
name: demo
description: Live narrated end-to-end vaultlab pipeline demo — curated topic, 5-min wall clock target. Pre-cached fallback if live runs fail.
arguments: [optional-topic-override]
---

# /demo [optional topic override]

> "My PI wants a 5-min demo. Show end-to-end: query → corpus → figures → slides."

Runs a complete vaultlab pipeline (literature → reading → arc → figure → optionally slide) on a curated demo topic with **explicit per-step narration**. Designed for live demos to a PI / collaborator / lab member who wants to see the harness work end-to-end. Falls back to pre-cached results if any live step fails (no awkward "demo crashed" moments).

## Lineage

Lifts:
- **gstack live-demonstration narration pattern** (Garry Tan) — explicit pre-step "I'm about to do X" announcements
- **AI-Scientist's plan → execute → verify** with reflection caps (Sakana AI) — bounds the demo at 5 min wall clock

## Pre-flight checklist

1. Resolve KB root + project config
2. Verify network connectivity (the literature search needs it)
3. State-aware preflight: glob `<kb_root>/<demo-topic>/` to see if a recent demo run exists. If yes (<24h old), surface it as the fallback option immediately so we can `--variant` it.

## Curated demo topics (pick one if user didn't specify)

The pre-cached topic catalog at `docs/demo-topics.md` (read the catalog file for the latest set):

| Topic | Why it's good for demo | Expected runtime |
|---|---|---|
| "long-chain sphingolipids in intestinal Paneth cells" | Narrow + recently published + has good open-access papers | 3-5 min |
| "tumor-associated macrophage spatial signatures" | Cross-study comparable, lots of figures available | 4-6 min |
| "single-cell atlas-vs-organoid concordance" | Method-comparison framing pairs well with the `methods_critic` role | 5-7 min |
| "cellular neighborhoods in colorectal cancer" | Schurch 2020 anchored, plays well with the heatmap recipe | 4-6 min |

If the user gave a topic that's known to be high-friction (e.g., requires paywalled-only papers, or has a tiny corpus), gently suggest one from the catalog instead.

## Execution — narrated

### Step 1 — Setup announcement

```
"For this demo I'll run vaultlab end-to-end on '<topic>'. Watch the
side panel for outputs landing. Total wall clock target: 5 min.

Step plan:
  1. Fan out 7 literature sources in parallel
  2. Dedup + citation-graph rank
  3. Picker reads top 200-400 abstracts in one batched LLM call
  4. Tier-A read top 5 picks
  5. Compose lineage arc (history -> development -> SOTA)
  6. Generate one figure (likely heatmap or marker_dot_plot, depending on topic)
  7. Optionally: build a 5-slide deck summarizing the arc

Starting now."
```

### Step 2-7 — Narrate each step before invoking

Before each step, announce what's about to happen + which primitive will run + what the user should watch for. Example for Step 3:

```
"Now the picker is reading 200-400 abstracts in one batched LLM call —
this is the killer detail vs. naive citation-graph ranking. It'll tag
each paper as ROBUST / RELEVANT / OFF-TOPIC and write the rationale
to decisions-log."
```

Then invoke the actual primitive. Wait for completion. Surface the output before moving to the next step.

### Step 8 — Wrap-up

```
"That was end-to-end: <N papers read, M Tier-A summaries, K figures
generated, deck at path/X.pptx>. Total wall clock: <actual>.
Everything's saved to the KB at <kb_root>/<demo-topic>/. Want to
deep-dive any one of the outputs?"
```

## Fallback mechanism

If any step takes >2× its expected time OR fails: switch to the **pre-cached** version of that step's output (from a prior demo run), narrate the switch transparently:

```
"Live literature search hit a network slowdown. Switching to the
pre-cached result from <date>'s demo — same topic, same pipeline.
Continuing live for the remaining steps."
```

Pre-cached outputs live at `<kb_root>/_demo-cache/<topic>/<step>-<date>.md`. Maintained by re-running `/demo --refresh-cache <topic>` periodically (e.g., weekly).

## Output

The demo run itself writes to `<kb_root>/<topic>/Output/demo-<date>.md` with:
- Per-step timing
- Per-step output reference
- Total wall clock
- Fallbacks invoked (if any)
- The user's questions during the demo (if any)

Useful as a reproducibility artifact + as the "what got generated" record for follow-up.

## When to invoke

- Live PI / collaborator / lab-member demo
- Recording a screencast
- Onboarding a new lab member by showing them the full pipeline

## When NOT to invoke

- Real research work (use `/lit-arc` + `/build-deck` + recipe primitives directly — `/demo` adds narration overhead)
- Time-constrained sessions <3 min (`/demo` can't compress below 3 min wall clock without losing fidelity)

## Caveat

**The clock is not always under our control.** A PDF acquisition that's slow, a network hiccup, a paperclip-MCP slowdown — all add latency. The 5-min target is aspirational. Demo as if you have 7 minutes; describe upfront so the audience doesn't watch the clock.
