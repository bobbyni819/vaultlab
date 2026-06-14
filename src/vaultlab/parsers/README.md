# vaultlab.parsers

Turns the Critic's free-form markdown verdicts into structured data the orchestrators can act on.

> Plain-language subsystem guide: the multi-agent-meetings (crosstalk) and deep-think sections of [`vaultlab-subsystems.md`](../../../docs/architecture.md) describe the panel this package serves. Architectural context: [`docs/architecture.md`](../../../docs/architecture.md) (META PRINCIPLE #1 — Python is the engine, markdown is the interface).

## What it is

When vaultlab convenes an internal panel, the Critic role writes its assessment as ordinary markdown prose — ratings like `ROBUST` or `CONTESTED` against each finding, and a numbered list of priority-tagged tests for the next round. Something has to read that prose and hand the orchestrator clean Python objects: which finding got which rating, and which `[CRITICAL]`/`[HIGH]` checks to schedule next. That is all this package does. It is the one place the regex lives, so every slash command and workflow parses the Critic the same way instead of each reinventing its own brittle string-matching. It was lifted verbatim (apart from the namespace) from `bobby_ailab._parsers`.

## Public surface

- `parse_critic_ratings(text)` — pull `{finding_id: rating}` out of Critic markdown, splitting on per-finding headings and reading each section's `Rating:` line; falls back to ordinal keys (`F_1`, `F_2`) when a heading carries no `F###` id.
- `parse_finding_ratings(text, known_ids)` — the same extraction, but constrained to a caller-supplied list of finding ids; headings naming an unknown id are dropped, and unlabeled sections map onto `known_ids` in encounter order.
- `parse_next_round_tests(text)` — extract priority-tagged next-round test items (`1. [CRITICAL] Recompute ...`) into ordered records carrying `priority`, `description`, `detail`, and source `position`.
- `summarize_ratings(ratings)` — collapse a rating map into a one-line count string (e.g. `"2 ROBUST, 1 WEAK"`) for progress reporting.
- `summarize_tests(records)` — collapse parsed test records into a one-line count string ordered by priority.
- `ALL_RATINGS` — the full vocabulary of accepted rating keywords (data-analysis ratings plus literature-consensus ratings).
- `PRIORITY_LEVELS` — the accepted priority tags, in order: `CRITICAL`, `HIGH`, `MEDIUM`, `LOW`.

## How it fits

It reads **text only** — the raw markdown string a Critic agent produced inside a meeting. It holds no KB state and reaches out to nothing; you pass it a string, it returns dicts and lists. Its output feeds the round-to-round orchestration: `vaultlab.workflows.deep_think.plan_round_from_critic_tests` calls `parse_next_round_tests` to turn last round's Critic verdict into the next round's agenda questions, raising if nothing parses. The rating vocabulary it recognizes is the contract shared with the Critic role prompt (`ROBUST`/`NEEDS_VALIDATION`/`WEAK`/`UNSUPPORTED` for data findings, `STRONG_CONSENSUS`/`EMERGING_EVIDENCE`/`SINGLE_STUDY`/`CONTESTED` for literature) and the `F###` finding ids minted upstream by `/research-reason`.

## What it does NOT do

- It does not call an LLM, hit the network, or touch the knowledge base — it is a pure text-to-structure transform.
- It does not validate or score the findings; it reports the rating the Critic wrote, not whether that rating is correct.
- It does not generate agenda items or plan rounds itself — `vaultlab.workflows` owns that; this package only supplies the parse.
- It returns an empty result rather than guessing when nothing matches; callers are told to treat an empty rating map as a failed round, not a valid one.

## Files

- `__init__.py` — the entire package: the parsers, the one-line summarizers, the `ALL_RATINGS` / `PRIORITY_LEVELS` vocabulary constants, and the private regexes/section-splitter behind them.

## See also

- `src/vaultlab/workflows/deep_think.py` — primary consumer; turns parsed Critic tests into the next deep-think round.
- `src/vaultlab/workflows/crosstalk_policy.md` — the meeting/round orchestration these parsers serve.
- `src/vaultlab/runner/meetings.py` — `Meeting` / `Mode` / `Role`, where the Critic output being parsed originates.
- `src/vaultlab/roles/` — the Critic role prompt that emits the ratings and priority tags this package recognizes.
