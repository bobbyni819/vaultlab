# vaultlab.prompts

Reserved slot for a future shared prompt loader. **Not yet implemented** — today it is an empty placeholder with no public API.

Plain-language subsystem context: **none** — this package ships nothing user-facing, so the plain-language subsystems guide (`Wiki/Concepts/vaultlab-subsystems.md`) has no entry for it. The "prompts-as-markdown" idea it is *meant* to serve is a system-wide invariant (`CLAUDE.md` / `docs/architecture.md`, "Markdown is the user-facing interface"), not a feature of this slot. Architecture sketch: [`docs/architecture.md`](../../../docs/architecture.md), whose top-level map lists `prompts/` as the intended "Prompt loader."

## What it is

This package is a **named-but-empty reservation** for a system-wide prompt loader — the place where, eventually, the generic "read a `.md` prompt file off disk and hand it to the LLM" machinery would live, shared across roles, workflows, and recipes. Right now it does nothing: `__init__.py` is a one-line placeholder docstring with no exports. The repo's top-level map (`CLAUDE.md`, `docs/architecture.md`) lists `prompts/` as the "Prompt loader," but that describes the *intended* role of this slot, not shipped code.

In practice, the prompt-loading job it is meant to own already happens elsewhere — most concretely in `vaultlab.roles._loader`, which reads each role's `prompt.md` + `metadata.yaml` off disk and projects them into a `Role`. Until this package is populated by a migration commit, treat it as a stub: import nothing from it, and reach for the existing per-area loaders instead.

## Public surface

**None.** `vaultlab.prompts` exports no symbols — there is no `__all__`, no classes, and no functions. `__init__.py` contains only a placeholder docstring (`"Placeholder. Will be populated by migration commits."`). Do not import from this package; nothing here is callable yet.

## How it fits

- **Reads from:** nothing today. The intended future shape is to read markdown prompt files from disk (the convention every vaultlab role, workflow, and recipe already follows — prompts live in sibling `.md` files, never as triple-quoted Python strings).
- **Consumed by:** nothing today. When implemented, a shared loader here would be called by the runner / roles / workflows in place of each subsystem rolling its own file-read.
- **Where prompt loading actually lives now:** `vaultlab.roles._loader` (`load_role`, `list_roles`, `load_all_roles`) reads `roles/<id>/prompt.md` + `metadata.yaml`; figure recipes and workflows read their own sibling `.md` files directly. This package would centralize that pattern if and when it is filled in.

## What it does NOT do

- It does **not** load prompts yet — despite the name and the architecture-map label, there is no loader function in this package.
- It does **not** store prompt *content* — vaultlab's prompts live as `.md` files next to the code that uses them (roles, recipes, workflows), not inside this package.
- It does **not** replace `vaultlab.roles._loader` or any existing per-area markdown reader; those remain the real entry points.
- It is **not** safe to depend on — the public surface is empty and the shape is unspecified until a migration commit lands.

## Files

- `__init__.py` — placeholder module; a single docstring, no exports.
- `README.md` — this file.

## See also

- [`src/vaultlab/roles/_loader.py`](../roles/_loader.py) — where role-prompt loading actually happens today (`load_role`, `list_roles`, `load_all_roles`).
- [`src/vaultlab/roles/README.md`](../roles/README.md) — the role package, whose `prompt.md` + `metadata.yaml` pairs are the canonical prompt-as-markdown pattern.
- [`docs/architecture.md`](../../../docs/architecture.md) — the architectural map that reserves this slot.
- `CLAUDE.md` META PRINCIPLE #1 ("Markdown is the user-facing interface; Python is the engine") — the invariant this package is meant to serve.
