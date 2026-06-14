# vaultlab.config

The typed reader for a project's `.bobby-project.json` — the small settings file that tells every vaultlab step which knowledge base to use, what domain you work in, and how strict to be about findings.

Plain-language background: the "Onboarding + setup" section of `G:\My Drive\Knowledge\vaultlab\Wiki\Concepts\vaultlab-subsystems.md` covers where this file comes from. Architectural sketch: `docs/architecture.md` (the `config/` line in the package tree).

## What it is

Every research project carries a tiny per-project settings file (`.bobby-project.json`) — its name, where its knowledge base lives, what scientific domain it's in, which journal it's aimed at, and the numeric cutoffs the system uses to decide whether a result is worth flagging. This package is the one place that file is read and turned into a typed Python object, so that library code and slash commands all see the **same shape** instead of each re-parsing the JSON by hand. It exists so project settings are loaded once, validated at the file boundary, and handed around as a plain dataclass — including a short text summary the orchestrator can drop in as a shared context header for a session.

This is the loader for the **legacy slash-command schema** (`.bobby-project.json`), lifted verbatim from `bobby_ailab._config`. The companion-mode onboarding flow uses a separate, newer loader (`vaultlab.onboarding.config`, which reads `.vaultlab-project.json`); the two coexist. Import the symbols directly from this package: `from vaultlab.config import ProjectConfig, SignificanceThresholds, load_project_config`. They are **not** re-exported from the top-level `vaultlab` barrel (which exports only `__version__`), so always import from `vaultlab.config`.

## Public surface

- `ProjectConfig` — a dataclass holding one project's settings (name, KB path, domain, target journal, data/figure/output dirs, hypotheses, significance thresholds). Built from the JSON via `ProjectConfig.from_dict(...)`.
  - `.context_summary()` — emits a ~500-token plain-text project header (name, domain, journal, hypotheses, thresholds) meant to be injected as the shared session context; warns to stderr if it overflows the budget.
  - `.validate()` — checks the config at load time and returns a list of human-readable warnings (missing KB path, non-existent data dirs, empty domain, etc.); an empty list means OK. It does **not** raise.
- `SignificanceThresholds` — the numeric cutoffs a critic uses when rating a finding: correlation rho, FDR alpha, Cramér's V, minimum effect size. Has its own `.from_dict(...)` with sensible defaults.
- `load_project_config(repo_root=None)` — reads `.bobby-project.json` from a repo root (cwd if omitted) and returns a `ProjectConfig`. Raises `FileNotFoundError` (with a fix hint) when the file is missing, rather than silently defaulting.

## How it fits

- **Reads from:** a single `.bobby-project.json` file on disk at the repo/project root. Nothing else — no network, no KB scan, no LLM.
- **Feeds into:** any vaultlab step that needs project settings. The dataclass's `context_summary()` becomes a session context header; `significance_thresholds` informs how the critic roles rate findings; `kb_path`, `data_dirs`, and `output_dirs` tell later stages where to read and write. Consumers import these symbols straight from `vaultlab.config` (e.g. `from vaultlab.config import load_project_config`); the top-level `vaultlab` barrel deliberately stays slim and re-exports only `__version__`.
- **Sits at:** the very start of the pipeline — the system-boundary read that turns a file into typed settings before any analysis, figure, or literature work begins.

## What it does NOT do

- It does **not** discover or create the config file — `load_project_config` only reads an existing `.bobby-project.json`; if it's missing you get a `FileNotFoundError` telling you to create one (onboarding is a different package's job).
- It does **not** read the newer `.vaultlab-project.json` companion-mode schema — that's handled by `vaultlab.onboarding.config`; this package is the legacy `.bobby-project.json` reader only.
- It does **not** check your data files' contents — `validate()` only checks that paths exist and required fields are present at load time; verifying what's *inside* the data is a later phase's job.
- It does **not** raise on a bad-but-loadable config — `validate()` returns warnings as a list for the caller to surface; only a genuinely missing file is fatal.

## Files

- `__init__.py` — the entire package: `ProjectConfig`, `SignificanceThresholds`, `load_project_config`, and their `from_dict` constructors. No submodules.

## See also

- `src/vaultlab/onboarding/` — the companion-mode setup flow and the newer `.vaultlab-project.json` loader (`load_project_config_from_cwd`).
- `src/vaultlab/context/` — RAG context assembly, the next consumer of project settings downstream.
- `src/vaultlab/roles/` — the critic roles that act on `significance_thresholds` and the project's target journal.
- `docs/architecture.md` — where `config/` sits in the full package tree and the additive-schema forward-compat promise.
