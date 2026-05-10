"""Read + filter provenance receipts.

Loads ``.provenance.json`` sidecars back into :class:`ProvenanceRecord`
instances and filters the JSONL index for queries like "all deep-think
outputs touching finding F001".
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from ._record import ProvenanceRecord
from ._writer import PROVENANCE_INDEX

# ---------------------------------------------------------------------------
# Single-receipt reads
# ---------------------------------------------------------------------------


def read_receipt(output_path: str | os.PathLike[str]) -> ProvenanceRecord | None:
    """Load the ``<output>.provenance.json`` sidecar for ``output_path``.

    Returns ``None`` if the sidecar does not exist or cannot be parsed —
    callers decide whether the missing receipt is a failure mode.
    """
    sidecar = Path(output_path).with_name(Path(output_path).name + ".provenance.json")
    if not sidecar.is_file():
        return None
    try:
        data = json.loads(sidecar.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    # The sidecar payload includes a top-level "output" field that's not part
    # of ProvenanceRecord — drop it before deserializing.
    data = {k: v for k, v in data.items() if k != "output"}
    return ProvenanceRecord.from_dict(data)


# ---------------------------------------------------------------------------
# Index reads + filters
# ---------------------------------------------------------------------------


def load_provenance_index(index_dir: str | os.PathLike[str]) -> list[dict[str, Any]]:
    """Read the JSONL index in ``index_dir`` into a list of dicts."""
    path = Path(index_dir) / PROVENANCE_INDEX
    if not path.is_file():
        return []
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return records


def filter_index(
    records: list[dict[str, Any]],
    *,
    topic: str | None = None,
    generated_by: str | None = None,
    investigation_mode: str | None = None,
    kind: str | None = None,
    finding_id: str | None = None,
    tags: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Filter index records — supports the common "find what touched X" queries.

    All filters are AND-ed; ``tags`` requires every listed tag to be present
    (conjunctive). ``topic`` is matched as a case-insensitive substring;
    everything else is matched exactly.
    """
    out = records
    if topic:
        needle = topic.lower()
        out = [r for r in out if needle in str(r.get("topic", "")).lower()]
    if generated_by:
        out = [r for r in out if generated_by == r.get("generated_by")]
    if investigation_mode:
        out = [r for r in out if investigation_mode == r.get("investigation_mode")]
    if kind:
        out = [r for r in out if kind == r.get("kind")]
    if finding_id:
        out = [r for r in out if finding_id in (r.get("finding_ids") or [])]
    if tags:
        out = [r for r in out if all(t in (r.get("tags") or []) for t in tags)]
    return out


__all__ = [
    "filter_index",
    "load_provenance_index",
    "read_receipt",
]
