# SPEC — `<feature name>`

> **Canonical SPEC.md template for vaultlab.** Copy this file into `Sources/Notes/SPEC-<feature-slug>-<date>.md` (or wherever you want the spec to live in the KB), fill in every section, then hand it to `/iterate` or `/goodnight` as the rubric. The template enforces "spec-first" discipline — author-the-rubric-once, walk-away, agent runs against it.

## 1. Goal (one sentence)

A single sentence describing what this feature accomplishes. If you can't say it in one sentence, you don't understand the feature yet — go think about it more before writing the rest of the spec.

## 2. Acceptance criteria (testable bullets)

Concrete, verifiable, binary-pass-or-fail. Each criterion should be runnable as a check.

- [ ] Criterion 1 — *what to do, expected outcome*
- [ ] Criterion 2
- [ ] ...

Bad: "the feature should be intuitive."
Good: "running `/lit-arc <topic>` on a never-seen topic returns ≥ 8 Tier-A summaries with non-empty `[pN]` page-marker citations within 90 seconds."

## 3. What "good" looks like (concrete examples)

Real worked examples — *if I run this on input X, the output should look like Y*. Multiple examples spanning easy / medium / hard cases. Concrete is better than abstract.

### Example 1 — easy case
- Input: ...
- Expected output: ...
- Why this is the easy case: ...

### Example 2 — medium case
- Input: ...
- Expected output: ...

### Example 3 — hard case
- Input: ...
- Expected output: ...

## 4. Edge cases I want handled

What happens when things go sideways. Each edge case should have an explicit expected behavior.

- **Empty / missing input** → ...
- **Malformed input** → ...
- **External dependency unavailable** (API down, paywall blocks, etc.) → ...
- **Existing artifact already covers this** (state-aware additive principle) → ...
- **User overrides default** → ...
- **Resource exhaustion** (token budget, time budget, file size) → ...
- **Concurrent runs** (idempotency) → ...

## 5. What's explicitly OUT of scope

What this feature does NOT do. Important — keeps scope contained.

- Not building X (that's Phase Y of the roadmap)
- Not addressing Z friction (separate work)
- Not retrofitting old artifacts (new-only)

## 6. How to verify (the rubric `/iterate` runs against)

The runnable verification protocol. `/iterate` will run these in order and only declare "done" when all pass.

### Step 1 — `<verifier action 1>`
- Run: `<exact command>`
- Expect: `<exact expected output / file / behavior>`
- If fails: `<diagnostic step or fall-through>`

### Step 2 — `<verifier action 2>`
- Run: ...
- Expect: ...

### Step 3 — Role-pass audit (per CLAUDE.md commitment #7)
- Invoke: `<methods_critic | rigor_auditor | journal_reviewer | ...>` on the produced artifact
- Expect: severity ≤ "warn"
- If "fail": agent must address the surfaced issues + re-run

## 7. References / lineage (per CLAUDE.md commitment #8)

Every external pattern this feature lifts from. Cite the source so `INSPIRATIONS.md` can be updated when shipped.

| Pattern | Source | Where applied |
|---|---|---|
| ... | ... | ... |

## 8. Implementation steps (ordered)

The sequence the agent should follow when running against this spec. Each step has its own internal acceptance check before moving to the next.

1. Step 1 — *do X*. Verify by *Y* before continuing.
2. Step 2 — ...
3. ...

Steps that depend on earlier steps' outputs must reference the dependency explicitly.

## 9. Risk + mitigation

Known risks with this approach + what to do if they materialize.

- **Risk:** ... → **Mitigation:** ...
- **Risk:** ... → **Mitigation:** ...

## 10. Open questions (if any) — for Bobby async

Decisions the agent shouldn't make alone. Author these as concrete forks Bobby can answer in one line.

- **Q1:** Option A vs B for ...? → My vote: ... → Bobby: ___
- **Q2:** ...

If there are no open questions, delete this section.

## 11. Definition of done

When all criteria in §2 pass AND all verification steps in §6 pass AND all open questions in §10 are answered. Agent should commit + push at this point and report back with:

- Summary of what shipped
- Per-criterion pass/fail evidence
- Anything deferred (with reasoning)
- Updated `INSPIRATIONS.md` entries

---

## Why this template exists

vaultlab's value depends on being **disciplined enough to defend its outputs against journal-grade scrutiny.** Spec-first authoring is the upstream lever: a feature built against a written rubric is easier to verify, easier to debug, and easier for a meta-agent (`journal_reviewer`, `pi_evaluator`) to audit. Reactive task execution skips this lever and produces "looks plausible" outputs that don't survive scrutiny.

Per Bobby 2026-05-07: *"give me tasks with acceptance criteria, not vague asks. Spec it once, walk away."*
