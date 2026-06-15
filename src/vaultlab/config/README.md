# vaultlab.config

The typed reader for a project's `.bobby-project.json` — the small settings file that tells every vaultlab step which knowledge base to use, what domain you work in, and how strict to be about findings.

Plain-language background: the "Onboarding + setup" section of `G:\My Drive\Knowledge\vaultlab\Wiki\Concepts\vaultlab-subsystems.md` covers where this file comes from. Architectural sketch: `docs/architecture.md` (the `config/` line in the package tree).

## What it is

Every research project carries a tiny per-project settings file (`.bobby-project.json`) — its name, where its knowledge base lives, what scientific domain it's in, which journal it's aimed at, and the numeric cutoffs the system uses to decide whether a result is worth flagging. This package is the one place that file is read and turned into a typed Python object, so that library code and slash commands all see the **same shape** instead of each re-parsing the JSON by hand. It exists so project settings are loaded once, validated at the file boundary, and handed around as a plain dataclass — including a short text summary the orchestrator can drop in as a shared context header for a session.

This is the loader for the **legacy slash-command schema** (`.bobby-project.json`), lifted verbatim from `bobby_ailab._config`. The companion-mode onboarding flow uses a separate, newer loader (`vaultlab.onboarding.config`, which reads `.vaultlab-project.json`); the two coexist. Import the symbols directly from this package: `from vaultlab.config import ProjectConfig, SignificanceThresholds, load_project_config`. They are **not** re-exported from the top-level `vaultlab` barrel (which exports only `__version__`), so always import from `vaultlab.config`.

## Public surface

- `ProjectConfig` — a dataclass holding one project's settings: `name`, `kb_path`, `domain`, `domain_context` (free-text vocabulary the agents inherit), `target_journal`, `data_dirs`, `figure_dirs`, `output_dirs` (a name→path map, e.g. `private`/`shared`), `hypotheses`, `significance_thresholds`, and `source_path` (where it was loaded from, filled in automatically by the loader). Built from the JSON via `ProjectConfig.from_dict(d, source_path="")`, which fills in defaults for every optional field, so a config with only `name` + `kb_path` loads cleanly.
  - `.context_summary()` — emits a short (~500-token-budget) plain-text project header — name, domain, target journal, domain context, the hypotheses list, and a one-line thresholds string (rho / FDR / Cramér's V; note the minimum effect size is held on the dataclass but **not** echoed in this line). Empty fields are dropped, so a bare project produces just `PROJECT: <name>` plus the thresholds line. This text is what the orchestrators actually inject as the shared session header — `plan_lit_dive`, the synthesis / ensemble-critic / deep-think workflows, and the narrative + figure-brainstorm builders all pass `cfg.context_summary()` (sometimes concatenated with prior outputs or a session summary) into the runner as `session_context`. It warns to stderr if the summary overflows the budget (checked as ~2000 chars).
  - `.validate()` — a caller-invoked sanity check that returns a list of human-readable warnings (empty `kb_path`, a `kb_path` / `data_dirs` / `figure_dirs` entry that isn't a real directory, empty `domain` or `domain_context`, empty `data_dirs` — which it flags because the pipeline then defaults to LITERATURE_REVIEW mode). An empty list means OK. It checks paths and required fields at the file boundary only; it does **not** raise, and no primitive runs it automatically — surfacing the warnings is the caller's job.
- `SignificanceThresholds` — the numeric cutoffs used when rating a finding: `correlation_rho` (default 0.2), `fdr_alpha` (0.05), `cramers_v_meaningful` (0.3), and `effect_size_min` (0.1). Its `.from_dict(...)` coerces each value to `float` and back-fills any field the JSON omits with its default, so a partial `significance_thresholds` block keeps sane values for the rest. In current code these cutoffs reach the critic roles *through the `context_summary()` text the agents read*, not via a separate numeric API.
- `load_project_config(repo_root=None)` — reads `.bobby-project.json` from a repo root (cwd if omitted) and returns a `ProjectConfig` with `source_path` set to the file it read. Raises `FileNotFoundError` (with a "create one with at least name + kb_path" hint) when the file is missing, rather than silently defaulting.

## How it fits

- **Reads from:** a single `.bobby-project.json` file on disk at the repo/project root. Nothing else — no network, no KB scan, no LLM.
- **Feeds into:** any vaultlab step that needs project settings. Concretely: the dataclass's `context_summary()` becomes the `session_context` header passed to the runner by the lit-dive, synthesis, ensemble-critic, deep-think, narrative, and figure-brainstorm workflows; `kb_path` is the root those same workflows write their `Output/` and `Wiki/Concepts/` artifacts under; `significance_thresholds` reach the critic roles via that summary text (rho / FDR / Cramér's V appear in the header the agents read); and `data_dirs` / `figure_dirs` / `output_dirs` tell later stages where to read and write. Consumers import these symbols straight from `vaultlab.config` (e.g. `from vaultlab.config import load_project_config`); the top-level `vaultlab` barrel deliberately stays slim and re-exports only `__version__`.
- **Anchors the output-routing split (Invariant 5):** AGENTS.md names `vaultlab.config.ProjectConfig` as the place that encodes the private-vs-final split — private reasoning and drafts go under `kb_path`, final user-facing outputs go to the user-controlled paths in `output_dirs` (e.g. a `shared` repo or Box path). The dataclass is the typed carrier for both sides of that routing decision.
- **Sits at:** the very start of the pipeline — the system-boundary read that turns a file into typed settings before any analysis, figure, or literature work begins.

## What it does NOT do

- It does **not** discover or create the config file — `load_project_config` only reads an existing `.bobby-project.json`; if it's missing you get a `FileNotFoundError` telling you to create one (onboarding is a different package's job).
- It does **not** read the newer `.vaultlab-project.json` companion-mode schema — that's handled by `vaultlab.onboarding.config`; this package is the legacy `.bobby-project.json` reader only.
- It does **not** check your data files' contents — `validate()` only checks that paths exist and required fields are present at load time; verifying what's *inside* the data is a later phase's job.
- It does **not** raise on a bad-but-loadable config — `validate()` returns warnings as a list for the caller to surface, and nothing calls it automatically; only a genuinely missing file is fatal.
- It does **not** *enforce* the significance thresholds itself — it carries the numbers and surfaces three of them in `context_summary()`, but it runs no statistics and gates no decision; acting on the cutoffs is the critic roles' job (and the minimum effect size is currently carried but not surfaced anywhere).
- It does **not** route outputs — it *holds* the `kb_path` / `output_dirs` split (Invariant 5) but does no file I/O of its own beyond reading the one JSON; the actual write-here-vs-there decisions live in the consuming steps.

## Files

- `__init__.py` — the entire package: the `ProjectConfig` and `SignificanceThresholds` dataclasses (with `from_dict`, `context_summary`, and `validate`) plus the `load_project_config` loader. No submodules; everything is in this one file.

## See also

- `src/vaultlab/onboarding/` — the companion-mode setup flow and the newer `.vaultlab-project.json` loader (`load_project_config_from_cwd`), the loader the slash commands and orchestrators actually call today.
- `src/vaultlab/context/` — RAG context assembly, the next consumer of project settings downstream.
- `src/vaultlab/workflows/` — the lit-dive, synthesis, ensemble, deep-think, narrative, and brainstorm steps that consume `cfg.context_summary()` and `cfg.kb_path`.
- `src/vaultlab/roles/` — the critic roles whose ratings the `significance_thresholds` (carried in the session header) are meant to inform, alongside the project's target journal.
- `AGENTS.md` (Invariant 5) — the private-vs-final output-routing split this dataclass anchors.
- `_Ubiquitous_Language.md` — the project glossary entry distinguishing legacy `.bobby-project.json` (this package) from the newer companion-mode `.vaultlab-project.json`.
- `docs/architecture.md` — where `config/` sits in the full package tree and the additive-schema forward-compat promise.
