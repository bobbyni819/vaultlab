"""vaultlab.provenance — reproducibility receipts for every output.

Per ``AGENTS.md`` Reproducibility receipts (Quality bars), every vaultlab
output (figure, manuscript section, slide deck, citation, ...) writes BOTH
sidecars next to the output file:

- ``<output>.provenance.json`` — machine-readable (input hashes, code version,
  params, seed, model, timestamps)
- ``<output>.method.md`` — human-readable narrative for paper methods sections

Public API
----------

>>> from vaultlab.provenance import ProvenanceRecord, write_receipts
>>> record = ProvenanceRecord(
...     generated_by="figure-gen",
...     kind="figure",
...     inputs=["data/correlations.csv"],
...     params={"n_clusters": 8, "method": "leiden"},
...     seed=42,
... )
>>> json_path, method_path = write_receipts("outputs/fig1.png", record)

The module also keeps an append-only ``.vaultlab-provenance.jsonl`` index in
the output directory for cheap "find every output that touched finding F001"
queries.
"""

from ._reader import filter_index, load_provenance_index, read_receipt
from ._record import ProvenanceRecord
from ._writer import PROVENANCE_INDEX, hash_inputs, write_receipts

__all__ = [
    "PROVENANCE_INDEX",
    "ProvenanceRecord",
    "filter_index",
    "hash_inputs",
    "load_provenance_index",
    "read_receipt",
    "write_receipts",
]
