# vaultlab.plan

The place where a study gets written down *before* you run it — a pre-registration drafting helper, so the analysis you promised is the analysis you report.

> Plain-language subsystem overview: `G:/My Drive/Knowledge/vaultlab/Wiki/Concepts/vaultlab-subsystems.md`.
> Architectural sketch: [`docs/architecture.md`](../../../docs/architecture.md) → the `plan/` line in the top-level structure ("Pre-registration drafting").

> **Status: placeholder.** As of this writing the package is a stub — `__init__.py` carries only `"""Placeholder. Will be populated by migration commits."""`, there is no `__all__`, and no drafting or comparison code has landed yet. Everything in *Planned scope* below describes intended behaviour from the architecture doc and the slash-command catalogue, **not** code you can call today. The matching `.claude/commands/plan.md` does not exist yet either. Treat this README as the design contract the migration commits should fill in.

## What it is

`vaultlab.plan` is the package for writing down a study's hypothesis, design, and analysis plan *before* the data comes in — the pre-registration step that keeps a project honest. The whole harness is built around trustworthiness (hedged voice, verified citations, KB grounding), and a pre-registered plan is the upstream version of that discipline: you commit to "here is the test I will run and the outcome that would count" first, so that later, when results are in, nobody can quietly swap the question to fit the answer. It exists so a project has a durable record of intent that the analysis pipeline and the manuscript can be checked *against*. Today it is scaffolding only — the directory holds the namespace and this contract; the drafting and deviation-checking modules are still to come.

## Public surface

**None yet.** The package exports no public symbols — `__init__.py` is a placeholder docstring with no `__all__` and no importable functions or classes. There is nothing to call here right now; importing `vaultlab.plan` gives you an empty namespace.

When the migration commits land, the intended surface (per the slash-command catalogue in `.claude/commands/COMMANDS.md`) is a small pre-registration workflow exposed through two CLI subcommands:

- *(planned)* `/plan draft <topic>` — draft a pre-registration plan for a study: the hypothesis, design, planned analysis, and the outcomes that would confirm or refute it, written to the project KB as a markdown artifact.
- *(planned)* `/plan compare-to-actual <plan> <run>` — diff a pre-registered plan against what an analysis run actually did, surfacing deviations as warnings (the analysis you ran versus the analysis you promised).

## How it fits

*Planned, once implemented:* the drafting step would read project context from the KB (`START_HERE.md`, `decisions-log.md`, prior concept docs, literature summaries) so a plan is grounded in what the project already knows, and write the plan back into the project's KB folder as a markdown artifact — consistent with the rest of vaultlab, where markdown is the user-facing interface and the KB is the persistence layer. The comparison step would consume that plan plus the output of the result-analysis pipeline (`vaultlab.analysis` / `/run-analysis`) and emit a deviation report. Its place in the pipeline is *before* analysis (draft the plan) and *after* analysis (compare to actual). As scaffolding, none of these wires are connected yet.

## What it does NOT do

- It does **not** currently expose any callable API — it is an empty namespace today, so don't import symbols from it.
- It does **not** run the analysis or test the hypothesis. Pre-registration records *intent*; the actual statistics and result-analysis live in `vaultlab.analysis`. This package would draft and later compare the plan, not execute it.
- It is **not** an autonomous research-question generator. Consistent with companion-mode (CLAUDE.md), it would help a user write down *their* study, not invent one in a vacuum.
- It does **not** invent its own pre-registration methodology; the plan structure and deviation-checking discipline are meant to be lifted from established practice (e.g. OSF-style pre-registration / registered-report conventions) and recorded in `INSPIRATIONS.md` before they ship (META PRINCIPLE #8).

## Files

- `__init__.py` — placeholder module docstring; no exports yet.
- `README.md` — this file (the design contract for the package).

## See also

- [`docs/architecture.md`](../../../docs/architecture.md) — the top-level structure where `plan/` is listed as "Pre-registration drafting".
- [`.claude/commands/COMMANDS.md`](../../../.claude/commands/COMMANDS.md) — the "Pre-registration" section naming the intended `/plan draft` and `/plan compare-to-actual` subcommands.
- `src/vaultlab/analysis/` — the result-analysis pipeline a pre-registered plan would be compared against.
- `src/vaultlab/evaluate/README.md` — sibling placeholder package documented under the same "design-contract" convention.
- [`INSPIRATIONS.md`](../../../INSPIRATIONS.md) — where the pre-registration methodology lineage must be recorded before this package ships.
