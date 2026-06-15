# vaultlab.onboarding

The intake-form engine behind `/onboard-project`: it turns a 5-minute fillable form plus a folder scan into a project the rest of vaultlab can pick up and run with.

Plain-language subsystem write-up: the "Onboarding + setup" section of `Wiki/Concepts/vaultlab-subsystems.md` in the KB. Architectural context: the project-lifecycle state machine in [`docs/architecture.md`](../../../docs/architecture.md) (step 1, "Onboard").

## What it is

When a scientist first points vaultlab at a project, the old pattern was a long back-and-forth conversation with Claude Code — thirty questions before any real work started. This package replaces that with a structured markdown form the user fills in once (topic, goal, audience, what they already have, what to exclude, voice, deadlines), plus a deterministic Python orchestrator that reads the filled form, scans the project folder to see what's actually there, and writes the canonical onboarding artifacts to the knowledge base. After that the slash command only has to ask three-to-five targeted follow-up questions instead of thirty.

The whole package is **deliberately LLM-free** — it is pure parsing, classification, and file-writing. The Claude-driven judgement (asking the follow-ups, interpreting answers) lives in the slash-command markdown, not here. That split keeps the failure modes obvious and the test surface small. The outputs it writes — a `START_HERE.md` resume page, a saved intake copy, an initial `decisions-log.md`, and a machine-readable `.vaultlab-project.json` — are what every later vaultlab command reads to recover project context without re-interviewing the user.

The folder scan is the part that earns vaultlab the right to ask only a handful of follow-ups: it walks the project tree, skips noise directories (`.git`, `__pycache__`, `.venv`, `node_modules`, build/dist caches, IDE folders), and buckets every file into a coarse category by extension — code (`.py`, `.ipynb`, `.r`, `.rmd`), wet-lab and tabular data (AnnData `.h5ad`, HDF5, imaging `.tiff` / `.czi` / `.nd2` / `.ome.tif`, `.csv` / `.parquet` / `.xlsx`, flow `.fcs`, MALDI `.imzml` / `.ibd`), papers and citations (`.pdf`, `.bib`, `.ris`), manuscripts (`.docx`, `.tex`), notes, and figures. It records per-category counts plus up to five sample paths each, and flags whether a `README` / `CLAUDE.md` / `pyproject.toml` is present — enough for the START_HERE page to say "here's what's in your folder, here's what to read first" at a glance. From the inventory it also infers `data_dirs` (any directory that actually contains a data file) so later commands know where the wet-lab data lives without asking. The follow-up questions are likewise generated from gaps the scan reveals — e.g. the intake claims wet-lab data but no data files are present, or the goal is manuscript drafting but no draft is in the folder, or the audience includes the PI but no PI preferences were given — capped at five and never fewer than three.

## Public surface

Intake form (the fillable template and its round-trip):

- `IntakeForm` — dataclass for a filled-in `project_intake.md`; the nine intake sections mapped onto typed fields, with `validate()`, `to_dict()`, and `to_markdown()`.
- `parse_intake_md` — read a filled intake markdown file and return a validated `IntakeForm` (raises if topic / goals / audiences are missing).
- `render_intake_template` — return the empty template markdown the user fills in.
- `IntakeValidationError` — raised when a parsed form is missing a required field.
- `INTAKE_SCHEMA` — the intake schema version string (`vaultlab-intake/v1`).

Project init (the orchestrator):

- `init_project_from_intake` — the main entry point: read + validate an intake form, derive the slug (or take an explicit `slug=` override), resolve the KB root (explicit `kb_root=` or auto via `vaultlab.context.locations.resolve_kb_root`), default the project path to the cwd when none is passed, scan the folder, infer `data_dirs`, write all four onboarding artifacts, and return a `ProjectInit`.
- `ProjectInit` — result bundle: the resolved slug, the parsed intake, the folder inventory, the built `VaultLabProjectConfig`, the paths of every file written (with a `files_written()` helper), and the 3–5 follow-up questions the slash command should ask.
- `scan_project_folder` — walk a folder and classify its files by extension (multi-suffix types like `.ome.tif` take priority), skipping noise directories; returns a `FolderInventory`. Raises on a missing path or a non-directory.
- `FolderInventory` — at-a-glance summary of a folder's contents: per-category counts, up-to-five sample paths per category, the classified-file total, and `has_readme` / `has_claude_md` / `has_pyproject` flags. `summary_lines()` renders it as the bullet block for START_HERE.md.
- `copy_intake_template_to` — drop a blank `project_intake.md` into a project folder so the user has something to fill in.
- `FILE_TYPE_PATTERNS` — the file-extension → category map used to classify a folder's contents.

Project config (the machine-readable handoff):

- `VaultLabProjectConfig` — dataclass schema for `.vaultlab-project.json`: `slug`, `topic`, `goal`, `audience`, `kb_root`, `project_path`, `data_dirs`, `validation_files`, `exclusions`, `voice`, `pi_preferences`, `deadlines`, `free_form`, an optional `linked_repo` (a code repo associated with the project, set by `/link-repo` and read by the crosstalk machinery), plus provenance keys (`schema`, `created`, `last_updated`). Round-trips via `to_dict` / `to_json` and a `from_dict` classmethod that silently drops unknown keys for forward-compat.
- `save_config` — write a config to `<project>/.vaultlab-project.json` (creates the parent dir, re-stamps `last_updated` to today).
- `load_config` — read a project's config, or `None` if absent.
- `load_project_config_from_cwd` — walk up from the current directory to find the nearest `.vaultlab-project.json`, so a command run from inside a project folder can recover its slug / topic / KB root.
- `PROJECT_CONFIG_FILENAME` — the config filename constant (`.vaultlab-project.json`).
- `PROJECT_CONFIG_SCHEMA` — the config schema version string (`vaultlab-project/v1`).

## How it fits

**Reads from:** the user's filled `project_intake.md` (usually at the project root), the project folder itself (scanned file-by-file), and the KB root — resolved explicitly when passed, otherwise via `vaultlab.context.locations.resolve_kb_root`. Slug derivation and the KB output paths come from `vaultlab.kb.paths`.

**Writes:** four artifacts per onboarding — `<kb>/Wiki/Projects/<slug>/START_HERE.md` (the auto-resume page), `<kb>/Wiki/Projects/<slug>/intake.md` (the saved intake copy), `<kb>/Wiki/Projects/<slug>/decisions-log.md` (the initial entry), and `<project>/.vaultlab-project.json` (the machine handoff). The START_HERE write also drops best-effort provenance receipts via `vaultlab.provenance`.

**Consumed by:** the `/onboard-project` and `/onboard-me` slash commands drive `init_project_from_intake` and then ask its returned follow-up questions (`/onboard-me` parses freeform prose into the `IntakeForm` first; `/onboard-project` walks the 9 structured sections). `/start-project` reuses `IntakeForm` + `slugify_topic` but writes its minimal KB scaffold directly rather than calling the full orchestrator (no folder to scan). `/link-repo` calls `load_project_config_from_cwd` to find the project, then writes the `linked_repo` field back into the config. Every later command recovers project context by reading the artifacts written here — the START_HERE / decisions-log on session resume, and `.vaultlab-project.json` (via `load_project_config_from_cwd`) to thread `slug` / `kb_root` into orchestrators like `run_lit_arc` and the deck builder (which calls the helper as a best-effort fallback when no slug is passed). It sits at the very front of the project lifecycle: nothing else runs until a project has been onboarded.

## What it does NOT do

- It does not call an LLM. All the Claude-driven interpretation (asking the follow-ups, judging answers) happens in the slash-command markdown; this package only parses, classifies, and writes files.
- It does not read or summarize the project's papers or data — it only counts and categorizes files by extension for the inventory. Understanding contents is a later subsystem's job.
- It does not interview the user. It surfaces a short list of `follow_up_questions`; asking them and acting on the replies is the slash command's responsibility.
- It does not resolve the KB root by magic when one is passed. The literature / figure orchestrators (`run_lit_arc`, `run_lit_report`, the lineage builders) deliberately do not call `load_project_config_from_cwd` themselves — they require explicit `slug=` / `kb_root=` kwargs, which the slash-command bodies supply after calling the helper. (The deck builder is the one exception: it calls the helper as a best-effort fallback when no slug is threaded in.)
- It does not maintain the artifacts after seeding them. It writes the *initial* START_HERE / decisions-log; keeping them current as work proceeds is later KB tooling's job (e.g. `vaultlab.kb.start_here`). It also does not version or migrate an existing `.vaultlab-project.json` — re-running simply rewrites it (re-stamping `last_updated`), and the reader tolerates older / newer schemas by dropping unknown keys.

## Files

- `intake.py` — the `IntakeForm` dataclass, the empty-template constant, and the markdown round-trip (parse / render / re-render), including lenient checkbox and "YOUR ANSWER:" parsing.
- `project_init.py` — the orchestrator (`init_project_from_intake`), the folder scanner (`scan_project_folder` / `FolderInventory`), the START_HERE / decisions-log / intake-copy writers, and the follow-up-question heuristics.
- `config.py` — the `VaultLabProjectConfig` schema for `.vaultlab-project.json` plus its read / write / walk-up-from-cwd helpers.
- `__init__.py` — the package barrel re-exporting the public surface above.

(No sibling `.md` docs ship inside this package; the fillable template itself lives at `templates/project_intake.md` and is mirrored by `render_intake_template`.)

## See also

- `.claude/commands/onboard-project.md`, `.claude/commands/onboard-me.md`, `.claude/commands/start-project.md`, and `.claude/commands/link-repo.md` — the slash commands that drive this package (structured onboarding, freeform-prose onboarding, topic-only scaffold, and code-repo linking respectively).
- `scripts/_trial_onboarding.py` — the dry-run harness that exercises the full intake → init round-trip end-to-end.
- [`docs/architecture.md`](../../../docs/architecture.md) — the project-lifecycle state machine (onboard → daily work → resume → submit).
- `src/vaultlab/kb/` — `kb.paths` supplies the slug and KB output paths; the START_HERE / decisions-log files this package seeds are maintained by later KB tooling (e.g. `kb.start_here`).
- `src/vaultlab/context/locations.py` — KB-root resolution used when `kb_root` is not passed explicitly.
- `src/vaultlab/provenance/` — the receipts dropped alongside the START_HERE page.
