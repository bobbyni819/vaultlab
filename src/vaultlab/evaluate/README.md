# vaultlab.evaluate

Benchmarks that measure whether vaultlab's outputs are actually trustworthy — citation hallucination rate, cluster-naming accuracy, figure-caption faithfulness.

> Plain-language subsystem overview: `G:/My Drive/Knowledge/vaultlab/Wiki/Concepts/vaultlab-subsystems.md`.
> Architectural sketch: [`docs/architecture.md`](../../../docs/architecture.md) → section `vaultlab.evaluate`.

> **Status: placeholder.** As of this writing the package is a stub — `__init__.py` carries only `"""Placeholder. Will be populated by migration commits."""`, there is no `__all__`, and no benchmark code has landed yet. Everything in *Planned scope* below describes intended behaviour from the architecture doc, **not** code you can call today. Treat this README as the design contract the migration commits should fill in.

## What it is

`vaultlab.evaluate` is the package that grades vaultlab on its own promises. Trust is the whole point of the harness — hedged voice, verified citations, KB grounding — so there needs to be a place that turns "we claim our citations aren't hallucinated" into a number you can watch over time. That's this package: a small suite of benchmarks plus an LLM-as-judge scaffold (with the same anti-laziness, quote-the-evidence discipline the rest of vaultlab uses) that scores citation reliability, cluster-naming accuracy, and figure-caption faithfulness. It exists so regressions in trustworthiness show up as a failing benchmark rather than as a reviewer catching a fabricated reference. Today it is scaffolding only — the directory holds the namespace and this contract; the benchmark modules are still to come.

## Public surface

**None yet.** The package exports no public symbols — `__init__.py` is a placeholder docstring with no `__all__` and no importable functions or classes. There is nothing to call here right now; importing `vaultlab.evaluate` gives you an empty namespace.

When the migration commits land, the intended public surface (per `docs/architecture.md` and `INSPIRATIONS.md`) is three benchmark suites:

- *(planned)* citation hallucination-rate benchmark — measure how often a cited paper either does not exist or does not support the claim attached to it.
- *(planned)* cluster-naming accuracy benchmark — score LLM cell-type / cluster labels against a ground-truth panel (the architecture doc names the HuBMAP tonsil dataset as the reference case).
- *(planned)* figure-caption faithfulness benchmark — check that a generated caption only states what the figure actually shows.

Each is described as running in two modes: a cheap deterministic pass (no LLM API needed — structural / existence / schema-style checks that run in CI without keys or network) and an expensive LLM-judge pass (the semantic "does this claim actually hold" grading, with the same anti-laziness, quote-the-evidence discipline the rest of vaultlab enforces). The deterministic-first split is lifted, per `INSPIRATIONS.md`, from Bobby's MultiAgent code-generation pipeline (3,251 deterministic tests across nine suites, run before any LLM grading) — not invented here.

## How it fits

*Planned, once implemented:* the benchmarks read ground-truth fixtures and KB-grounded reference material (e.g. the HuBMAP tonsil annotations for cluster naming) and consume the outputs of other vaultlab packages — citations produced under `citations/` and `research/`, cluster labels from the `data/` modality pipelines, captions from `figures/` and `slides/`. The intended entry point is a CLI surface (`vaultlab evaluate --no-llm` for the deterministic checks, `--with-llm` to add the LLM-judge passes, per `docs/architecture.md`); its scores are what a maintainer or CI run watches to catch trustworthiness regressions.

As scaffolding, none of these wires are connected yet — and the CLI side is a placeholder too: `src/vaultlab/cli/evaluate/__init__.py` carries the same `"""Placeholder..."""` docstring, and `cli/README.md` lists `cli/evaluate/` among the placeholder subdirectories awaiting the full click-based dispatch. So while `evaluate` appears in the CLI's subcommand-name list, **there is no working `vaultlab evaluate` command today**; the `--no-llm` / `--with-llm` split is the intended design, not a live capability.

## What it does NOT do

- It does **not** currently expose any callable API — it is an empty namespace today, so don't import symbols from it.
- It is **not** a runtime guardrail. Per-output enforcement (hedge voice, citation verification, numeric checks) lives in `roles/_guardrails.py`, `citations/`, and `runner/verifiers`. This package *measures* quality across a benchmark set; it does not gate individual outputs.
- It does **not** re-run upstream analysis or generation — like `analysis`, the intent is to consume already-produced outputs and score them, not to recompute them.
- It does **not** invent its own metrics or methods; the benchmark designs are meant to be lifted from established evaluation practice and recorded in `INSPIRATIONS.md` before they ship (META PRINCIPLE #8).

## Files

- `__init__.py` — placeholder module docstring; no exports yet.
- `README.md` — this file (the design contract for the package).

## See also

- [`docs/architecture.md`](../../../docs/architecture.md) — the `vaultlab.evaluate` sketch and the `--no-llm` / `--with-llm` mode split.
- [`INSPIRATIONS.md`](../../../INSPIRATIONS.md) — sources the deterministic-first evaluation pattern (Bobby's MultiAgent pipeline) and is where new benchmark lineage must be recorded before any suite ships (META PRINCIPLE #8).
- `src/vaultlab/cli/evaluate/` — the (also-placeholder) CLI subcommand directory that will eventually back `vaultlab evaluate`; see `src/vaultlab/cli/README.md` for the placeholder-subdirectory note.
- `src/vaultlab/citations/` and `src/vaultlab/research/` — produce the citations the hallucination benchmark will score.
- `src/vaultlab/figures/` and `src/vaultlab/slides/` — produce the captions the faithfulness benchmark will score.
- `examples/codex_hubmap_tonsil/` — the dataset the architecture doc names for the cluster-naming benchmark.
