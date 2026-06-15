# vaultlab.provenance

Reproducibility receipts: every vaultlab output drops a machine-readable and a human-readable sidecar saying exactly how it was made.

> Plain-language framing: the "provenance receipts" idea in the [vaultlab subsystems guide](../../../../G:/My%20Drive/Knowledge/vaultlab/Wiki/Concepts/vaultlab-subsystems.md) (centralized-memory / trust theme). Architectural placement: [`docs/architecture.md`](../../../docs/architecture.md) (`provenance/ — write .provenance.json + method.md`).

## What it is

When vaultlab produces something a scientist might put in a paper — a figure, a manuscript paragraph, a slide deck, a citation audit, a reasoning-round summary — it writes two small companion files next to it: a JSON receipt a machine can index, and a Markdown narrative a person can paste into a Methods section. The receipt records the boring-but-load-bearing facts (which input files went in and their hashes, the code version, the parameters, the random seed, the model, when it ran) plus the investigative context (which project, which topic, which finding it supports). This package exists because trustworthiness is vaultlab's whole point: an output you can't trace back to its inputs is an output a reviewer can't trust, so the rule (from `AGENTS.md`) is that *every* output carries its own paper trail. Figure, manuscript, slide, citation, interactive-report, and analysis primitives across the repo call into here; audit and workflow tooling reads it back.

The human-readable `<output>.method.md` is a structured narrative, not a freeform note: it renders a `# Method` heading, then a **Generation** block (who generated it, when, plus code version / model / seed when present), then — each only when its fields are populated — a **Context** block (project / topic / investigation mode / meeting mode / round), an **Inputs** list (each input path with its `sha256:` digest inline), a **Parameters** list, a **Related outputs** list, a **Classification** block (kind / finding IDs / tags), and free-form **Notes**. Empty fields are simply omitted, so the sidecar never buries the reader in placeholder boilerplate. This is deliberately a small superset of what a paper's Methods section expects.

## Public surface

From `vaultlab.provenance` (`__all__`):

- `ProvenanceRecord` — the in-memory dataclass holding one output's provenance: the required `generated_by` (the tool/command) plus a `generated_at` ISO-8601 timestamp that auto-fills if left empty; investigation context (`project`, `topic`, `investigation_mode` of `directed`/`exploratory`, `meeting_mode` of `adversarial`/`round_table`, `round`); the reproducibility fields (`inputs`, `input_hashes`, `code_version`, `params`, `seed`, `model`); the linking fields (`related_outputs`, `finding_ids`); and classification (`kind`, a machine-readable `producer` tag, `tags`, free-form `notes`). It carries `to_dict()` / `from_dict()` helpers — `to_dict()` omits empty optional fields (but keeps an explicit `0` round or seed) so receipts stay terse.
- `write_receipts(output_path, record, *, index_dir=None)` — writes the two sidecars (`<output>.provenance.json` + `<output>.method.md`) next to a named output and appends one line to the directory's JSONL index; returns the two written paths. The JSON sidecar carries a top-level `output` field (the anchor path) ahead of the record fields; `read_receipt` strips it on load. Parent directories are created as needed. The output file itself need not exist — the path is just a naming anchor, so callers may write the receipts before, during, or after producing the artifact.
- `hash_inputs(paths)` — convenience that sha256-hashes a list of input files into the `{path: digest}` shape `ProvenanceRecord.input_hashes` wants; missing files record `"<missing>"` rather than raising.
- `read_receipt(output_path)` — loads the `<output>.provenance.json` sidecar back into a `ProvenanceRecord`, or `None` if it's absent or unparseable.
- `load_provenance_index(index_dir)` — reads the append-only `.vaultlab-provenance.jsonl` index in a directory into a list of dicts (one per receipt; each line carries a resolved-absolute `path` key plus the record fields). Returns `[]` when the index is absent, and skips any single line that fails to parse rather than raising.
- `filter_index(records, *, topic=None, generated_by=None, investigation_mode=None, kind=None, finding_id=None, tags=None)` — filters those index dicts for "find every output that touched X" queries; filters are AND-ed, `topic` matches as a case-insensitive substring, `tags` is conjunctive.
- `PROVENANCE_INDEX` — the index filename constant (`".vaultlab-provenance.jsonl"`).

## How it fits

Producers call `write_receipts(...)` as the last step of generating an artifact, so the receipt lands beside the artifact in the project's `Output/` area. Inputs are file paths the producer already knows; `hash_inputs` turns them into a tamper-evident fingerprint. The JSONL index accumulates per-directory, giving audit and status tooling a cheap scan — `load_provenance_index` + `filter_index` answer questions like "every figure deep-think generated for finding F001" without opening each sidecar. The read side is real, not aspirational: e.g. the `crosstalk` workflow calls `read_receipt(...)` to recover a document's provenance when it pulls a prior artifact back into a meeting.

Workflow orchestrators (`crosstalk`, `deep_think`, and friends) don't call this directly — they go through `vaultlab.workflows._provenance.write_with_provenance`, which writes provenance as YAML *frontmatter inside* the Markdown output (so an agent re-reading the file sees its own provenance) and, by default (`emit_sidecars=True`), *also* emits the canonical `write_receipts` sidecars so everything funnels into one indexable source of truth. The two systems keep *separate* indexes — the workflow form appends to `.vaultlab-workflow-provenance.jsonl`, this package's sidecars to `.vaultlab-provenance.jsonl` — and the bridge maps a frontmatter `round` of `None` to `0` so the round survives `to_dict`'s omit-empties rule. The sidecar emission is best-effort: it is wrapped in a swallow-everything `try` so a receipt failure never breaks the primary write. The sidecar form here is the canonical shape for figures, tables, slide decks, and binary exports where you can't embed frontmatter.

## What it does NOT do

- It does not gate or block anything — provenance is best-effort metadata. A missing receipt is for the caller to decide on; `hash_inputs` and the workflow bridge swallow failures rather than stop a write.
- It does not compute or verify the output's contents — it records *how* something was made, not *whether* the result is correct (that's the citation, numeric, and rigor verifiers elsewhere).
- It does not capture code versions, seeds, or hashes on its own — the caller populates `ProvenanceRecord`; empty fields are simply omitted from the receipt.
- It does not own the in-Markdown frontmatter form used by workflows — that lives in `vaultlab.workflows._provenance`; this package is the sidecar/JSON side of the bridge.

## Files

- `__init__.py` — slim barrel; module docstring + `__all__` define the public surface.
- `_record.py` — `ProvenanceRecord` dataclass plus `to_dict` / `from_dict` (empty optional fields omitted on serialize).
- `_writer.py` — `write_receipts`, `hash_inputs`, the JSONL index append, and the `_render_method_markdown` narrative renderer; defines `PROVENANCE_INDEX`.
- `_reader.py` — `read_receipt`, `load_provenance_index`, `filter_index`.

## See also

- `vaultlab/workflows/_provenance.py` — the sibling frontmatter form for workflow Markdown outputs; bridges into `write_receipts`.
- [`AGENTS.md`](../../../AGENTS.md) — "Reproducibility receipts" quality bar that mandates both sidecars per output.
- Producers that call `write_receipts(...)` to attach receipts to their outputs span most of the artifact-emitting repo:
  - **Analysis:** `vaultlab/analysis/pipeline.py` (figure + methods-section sidecars; one of the few callers that also runs `hash_inputs` for input fingerprints).
  - **Slides:** `vaultlab/slides/render.py`, `vaultlab/slides/deck.py`, and `vaultlab/slides/self_review.py` (rendered decks + review reports).
  - **Citations:** `vaultlab/citations/reporter.py` (citation-audit manifests).
  - **Manuscript:** `vaultlab/manuscript/polish.py` / `respond.py` / `data_availability.py`.
  - **Research:** `vaultlab/research/report.py`, `vaultlab/research/lineage.py` (lit-arc + project `START_HERE`), and `vaultlab/research/full_reader.py` (the bilingual `paper.md` reader).
  - **Interactive reports:** the whole `vaultlab/report/*` HTML-view family — `dispatch.py` plus `flowchart_html.py`, `incident_timeline_html.py`, `pr_writeup_html.py`, `state_dashboard_html.py`, `weekly_status_html.py`, `svg_figure_sheet_html.py`, `visual_designs_html.py`, `component_variants_html.py`, `approaches_compare_html.py`, and `feature_flag_editor.py` (each best-effort, logging on failure).
  - **CLI + onboarding:** `vaultlab/cli/demo.py` (the offline demo deck's receipt) and `vaultlab/onboarding/project_init.py`.
- Note: `vaultlab/figures/publication/save.py` deliberately does **not** write receipts — `save_fig()` only emits the PNG/PDF and leaves the receipt to its caller (the recipe layer attaches it).
- [`docs/architecture.md`](../../../docs/architecture.md) — where provenance sits in the pipeline ("Provenance receipts for every output").
