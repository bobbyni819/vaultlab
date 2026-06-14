# vaultlab.provenance

Reproducibility receipts: every vaultlab output drops a machine-readable and a human-readable sidecar saying exactly how it was made.

> Plain-language framing: the "provenance receipts" idea in the [vaultlab subsystems guide](../../../../G:/My%20Drive/Knowledge/vaultlab/Wiki/Concepts/vaultlab-subsystems.md) (centralized-memory / trust theme). Architectural placement: [`docs/architecture.md`](../../../docs/architecture.md) (`provenance/ — write .provenance.json + method.md`).

## What it is

When vaultlab produces something a scientist might put in a paper — a figure, a manuscript paragraph, a slide deck, a citation audit, a reasoning-round summary — it writes two small companion files next to it: a JSON receipt a machine can index, and a Markdown narrative a person can paste into a Methods section. The receipt records the boring-but-load-bearing facts (which input files went in and their hashes, the code version, the parameters, the random seed, the model, when it ran) plus the investigative context (which project, which topic, which finding it supports). This package exists because trustworthiness is vaultlab's whole point: an output you can't trace back to its inputs is an output a reviewer can't trust, so the rule (from `AGENTS.md`) is that *every* output carries its own paper trail. Figure, manuscript, slide, citation, and analysis primitives across the repo call into here; audit tooling reads it back.

## Public surface

From `vaultlab.provenance` (`__all__`):

- `ProvenanceRecord` — the in-memory dataclass holding one output's provenance: how/when it was produced, project/topic context, input hashes, code version, params, seed, model, and linking fields (`related_outputs`, `finding_ids`, `tags`).
- `write_receipts(output_path, record, *, index_dir=None)` — writes the two sidecars (`<output>.provenance.json` + `<output>.method.md`) next to a named output and appends one line to the directory's JSONL index; returns the two written paths. The output file itself need not exist — the path is just a naming anchor.
- `hash_inputs(paths)` — convenience that sha256-hashes a list of input files into the `{path: digest}` shape `ProvenanceRecord.input_hashes` wants; missing files record `"<missing>"` rather than raising.
- `read_receipt(output_path)` — loads the `<output>.provenance.json` sidecar back into a `ProvenanceRecord`, or `None` if it's absent or unparseable.
- `load_provenance_index(index_dir)` — reads the append-only `.vaultlab-provenance.jsonl` index in a directory into a list of dicts (one per receipt).
- `filter_index(records, *, topic=None, generated_by=None, investigation_mode=None, kind=None, finding_id=None, tags=None)` — filters those index dicts for "find every output that touched X" queries; filters are AND-ed, `topic` matches as a case-insensitive substring, `tags` is conjunctive.
- `PROVENANCE_INDEX` — the index filename constant (`".vaultlab-provenance.jsonl"`).

## How it fits

Producers call `write_receipts(...)` as the last step of generating an artifact, so the receipt lands beside the artifact in the project's `Output/` area. Inputs are file paths the producer already knows; `hash_inputs` turns them into a tamper-evident fingerprint. The JSONL index accumulates per-directory, giving audit and status tooling a cheap scan — `load_provenance_index` + `filter_index` answer questions like "every figure deep-think generated for finding F001" without opening each sidecar.

Workflow orchestrators (`crosstalk`, `deep_think`, and friends) don't call this directly — they go through `vaultlab.workflows._provenance.write_with_provenance`, which writes provenance as YAML *frontmatter inside* the Markdown output (so an agent re-reading the file sees its own provenance) and, by default, *also* emits the canonical `write_receipts` sidecars so everything funnels into one indexable source of truth. The sidecar form here is the canonical shape for figures, tables, and binary exports where you can't embed frontmatter.

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
- Representative producers that call `write_receipts(...)` to attach receipts to their outputs: `vaultlab/analysis/pipeline.py` (figure + methods-section sidecars), `vaultlab/slides/render.py` and `vaultlab/slides/deck.py` (decks), `vaultlab/citations/reporter.py` (citation audits), `vaultlab/manuscript/polish.py` / `respond.py` / `data_availability.py` (manuscript outputs), `vaultlab/research/report.py` and `vaultlab/research/lineage.py` (lit-arc / research reports). Note: `vaultlab/figures/publication/save.py` deliberately does **not** write receipts — `save_fig()` only emits the PNG/PDF and leaves the receipt to its caller.
- [`docs/architecture.md`](../../../docs/architecture.md) — where provenance sits in the pipeline ("Provenance receipts for every output").
