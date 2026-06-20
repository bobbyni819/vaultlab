# Figure Lifecycle Registry

The figure lifecycle registry extends `figure-index.json` with optional metadata for Bobby's
two-figure-system:

- keep exploratory/candidate figures in the registry so prior work is discoverable;
- before deriving a new figure for a manuscript claim, query the registry for an existing figure;
- when a better version replaces an older one, mark the old registry entry as superseded and keep the
  file on disk.

Archive means metadata only. The lifecycle helpers never move, rename, or delete figure files.

## Stages

`FigureStage` has six states:

- `EXPLORATORY` - default for legacy entries and early analysis figures.
- `CANDIDATE` - plausible for a deck or manuscript but not locked.
- `MANUSCRIPT` - accepted into the main manuscript/deck figure set.
- `SUPPLEMENTARY` - accepted as supplement material.
- `ARCHIVED` - intentionally retired from active use.
- `SUPERSEDED` - replaced by a newer figure, with `superseded_by` recording the replacement id.

Legacy entries that lack `lifecycle_stage` read as `EXPLORATORY`. Existing `update_figure_index`
callers do not need to pass lifecycle fields.

## Guard Before Re-Deriving

Use `find_existing_for_claim(kb_root, project_slug, claim_id=..., claim_text=...)` before generating a
new figure. It checks `claims` and `related_claims` metadata in the index and returns active entries by
default. `ARCHIVED` and `SUPERSEDED` entries are excluded unless `include_archived=True`.

## Archive-Never-Delete

Use `archive_superseded(..., superseded_by=...)` when a new figure replaces an old one. This marks the
old entry `SUPERSEDED`, records the replacement, and appends to `stage_history`. It does not touch the
image file.

