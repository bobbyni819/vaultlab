# vaultlab.parsers

Turns the Critic's free-form markdown verdicts into structured data the orchestrators can act on.

> Plain-language subsystem guide: the multi-agent-meetings (crosstalk) and deep-think sections of [`vaultlab-subsystems.md`](../../../docs/architecture.md) describe the panel this package serves. Architectural context: [`docs/architecture.md`](../../../docs/architecture.md) (META PRINCIPLE #1 — Python is the engine, markdown is the interface).

## What it is

When vaultlab convenes an internal panel, the Critic role writes its assessment as ordinary markdown prose — ratings like `ROBUST` or `CONTESTED` against each finding, and a list of priority-tagged tests (numbered or bulleted) for the next round. Something has to read that prose and hand the orchestrator clean Python objects: which finding got which rating, and which `[CRITICAL]`/`[HIGH]` checks to schedule next. That is all this package does. It is the one place the regex lives, so every slash command and workflow parses the Critic the same way instead of each reinventing its own brittle string-matching. It was lifted verbatim (apart from the namespace) from `bobby_ailab._parsers`.

## Public surface

- `parse_critic_ratings(text)` — pull `{finding_id: rating}` out of Critic markdown. It splits the text on per-finding H2–H4 headings (a heading counts as a finding section when it contains an `F###` id or begins with "finding"), then reads each section's `Rating:` line (tolerating bold wrappers like `**Rating:** ROBUST`); if no labelled line is present it falls back to any accepted rating word standing alone on a line. Unrecognized words (e.g. `AMAZING`) are ignored, and a section with no valid rating is skipped. Headings carrying no `F###` id get an ordinal key (`F_1`, `F_2`, ...) so positional callers can still map them. Returns `{}` when nothing parses.
- `parse_finding_ratings(text, known_ids)` — the same extraction, but constrained to a caller-supplied list of finding ids; headings naming an unknown id are dropped, and unlabeled sections map onto `known_ids` in encounter order.
- `parse_next_round_tests(text)` — extract priority-tagged next-round test items into ordered records carrying `priority` (uppercased), `description` (the item's first line), `detail` (any indented continuation lines joined with newlines), and source `position` (1-based line number). It accepts numbered (`1. [CRITICAL] Recompute ...`), dash, and asterisk bullets; tolerates bold markup around the tag (`**[HIGH]**`); and matches the tag case-insensitively (`[critical]` is read as `CRITICAL`). A blank line or a non-indented line closes the current item.
- `summarize_ratings(ratings)` — collapse a rating map into a one-line count string (e.g. `"1 WEAK, 2 ROBUST"`) for progress reporting; counts are ordered alphabetically by rating word.
- `summarize_tests(records)` — collapse parsed test records into a one-line count string ordered by priority severity (`CRITICAL` → `HIGH` → `MEDIUM` → `LOW`), omitting any priority with no tests.
- `ALL_RATINGS` — the full vocabulary of accepted rating keywords: five data-analysis ratings (`ROBUST`, `NEEDS_VALIDATION`, `WEAK`, `UNSUPPORTED`, `NEEDS_FOLLOWUP`) plus four literature-consensus ratings (`STRONG_CONSENSUS`, `EMERGING_EVIDENCE`, `SINGLE_STUDY`, `CONTESTED`). A rating word is only accepted if it is in this set.
- `PRIORITY_LEVELS` — the accepted priority tags, in order: `CRITICAL`, `HIGH`, `MEDIUM`, `LOW`.

## How it fits

It reads **text only** — the raw markdown string a Critic agent produced inside a meeting. It holds no KB state and reaches out to nothing; you pass it a string, it returns dicts and lists. Its output feeds the round-to-round orchestration: `vaultlab.workflows.deep_think.plan_round_from_critic_tests` calls `parse_next_round_tests` to turn last round's Critic verdict into the next round's agenda questions (optionally filtered to a subset of priorities via that builder's `priority_filter`, e.g. `["CRITICAL", "HIGH"]`), raising `ValueError` if nothing parses. The rating vocabulary it recognizes is the contract shared with the Critic role prompt (`ROBUST`/`NEEDS_VALIDATION`/`WEAK`/`UNSUPPORTED`/`NEEDS_FOLLOWUP` for data findings, `STRONG_CONSENSUS`/`EMERGING_EVIDENCE`/`SINGLE_STUDY`/`CONTESTED` for literature) and the `F###` finding ids minted upstream by `/research-reason`. The parser reports the rating as written; it imposes no strength ordering of its own — the analyst-vs-critic strength ranking (`ROBUST < NEEDS_VALIDATION = NEEDS_FOLLOWUP < WEAK < UNSUPPORTED`) lives downstream in `vaultlab.workflows.ensemble`.

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
