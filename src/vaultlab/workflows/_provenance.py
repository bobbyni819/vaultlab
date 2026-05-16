"""Internal provenance writer for workflow outputs (YAML frontmatter form).

Workflow outputs prefix each ``.md`` file with a YAML frontmatter block
describing what produced it::

    ---
    generated_by: deep-think
    generated_at: 2026-04-29T15:42:10
    project: <project>
    meeting_mode: adversarial
    investigation_mode: directed
    topic: <topic>
    round: 1
    kind: synthesizer_output
    tags: [deep-think, directed]
    ---

    <body of the output goes here>

This is the legacy ``bobby_ailab._provenance`` shape — frontmatter inline
in the markdown file plus an append-only JSONL index for refinement-
over-time queries.

Note
----
The repo-wide :mod:`vaultlab.provenance` module ships a different shape
(``ProvenanceRecord`` with sidecar files ``<output>.provenance.json`` +
``<output>.method.md``). The two systems coexist for now because:

* Workflows want the receipt INSIDE the markdown so the agent reading
  it sees its own provenance — sidecar files would be invisible to the
  Agent tool reading the path.
* The sidecar form is for figures, tables, and data exports where the
  output is binary.

A future cleanup pass should reconcile the two — likely by having
:func:`write_with_provenance` ALSO emit the JSON sidecar so the rest of
the pipeline can index a single source of truth. Tracked as a TODO; not
blocking for the workflows lift.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import yaml

PROVENANCE_INDEX = ".vaultlab-workflow-provenance.jsonl"


@dataclass
class Provenance:
    """Structured provenance for a workflow output (frontmatter form)."""

    generated_by: str  # command or tool that produced the file, e.g. "deep-think"
    generated_at: str = ""  # ISO8601 timestamp; filled by post_init if empty
    project: str = ""
    meeting_mode: str = ""
    investigation_mode: str = ""
    topic: str = ""
    round: int | None = None
    inputs: list[str] = field(default_factory=list)
    related_outputs: list[str] = field(default_factory=list)
    kind: str = ""  # e.g. "synthesizer_output", "figure_plan", "narration"
    tags: list[str] = field(default_factory=list)
    finding_ids: list[str] = field(default_factory=list)
    notes: str = ""
    # Structured key/value receipt parameters. Mirrors
    # ``vaultlab.provenance.ProvenanceRecord.params`` — the workflow form was
    # tags+notes-only historically, so call-sites encoded structured decisions
    # (e.g. crosstalk-policy outcomes) into tag strings. This field gives them
    # a typed home and lets ``to_dict`` / ``from_dict`` / frontmatter / the
    # sidecar bridge all round-trip the same shape as ``ProvenanceRecord``.
    params: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.generated_at:
            self.generated_at = datetime.now().isoformat(timespec="seconds")

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "generated_by": self.generated_by,
            "generated_at": self.generated_at,
        }
        for field_name in (
            "project",
            "meeting_mode",
            "investigation_mode",
            "topic",
            "round",
            "inputs",
            "related_outputs",
            "kind",
            "tags",
            "finding_ids",
            "notes",
            "params",
        ):
            value = getattr(self, field_name)
            if value or value == 0:
                out[field_name] = value
        return out

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Provenance:
        return cls(
            generated_by=str(d.get("generated_by", "")),
            generated_at=str(d.get("generated_at", "")),
            project=str(d.get("project", "")),
            meeting_mode=str(d.get("meeting_mode", "")),
            investigation_mode=str(d.get("investigation_mode", "")),
            topic=str(d.get("topic", "")),
            round=d.get("round"),
            inputs=list(d.get("inputs", [])),
            related_outputs=list(d.get("related_outputs", [])),
            kind=str(d.get("kind", "")),
            tags=list(d.get("tags", [])),
            finding_ids=list(d.get("finding_ids", [])),
            notes=str(d.get("notes", "")),
            params=dict(d.get("params", {})),
        )

    def render_frontmatter(self) -> str:
        """Render as markdown frontmatter — the YAML block that prefixes a file."""
        body = yaml.safe_dump(
            self.to_dict(),
            sort_keys=False,
            default_flow_style=False,
            allow_unicode=True,
        ).rstrip()
        return f"---\n{body}\n---\n"


def write_with_provenance(
    path: str,
    body: str,
    provenance: Provenance,
    index_dir: str | None = None,
    *,
    emit_sidecars: bool = True,
) -> str:
    """Write a file with a provenance frontmatter block + append to index.

    ``index_dir`` defaults to the directory containing ``path``. The index
    is a JSONL file so refinement-over-time queries stay cheap.

    When ``emit_sidecars`` is True (default), ALSO writes the canonical
    ``<path>.provenance.json`` + ``<path>.method.md`` sidecars via
    :mod:`vaultlab.provenance`. This unifies the workflow-frontmatter form
    with the project-wide sidecar form so audit tools have a single
    source of truth. The frontmatter form remains primary for in-file
    visibility (so an Agent reading the file sees its own provenance).
    """
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    frontmatter = provenance.render_frontmatter()
    if not body.endswith("\n"):
        body = body + "\n"
    with open(path, "w", encoding="utf-8") as f:
        f.write(frontmatter)
        f.write("\n")
        f.write(body)
    _append_to_index(path, provenance, index_dir)

    if emit_sidecars:
        try:
            from pathlib import Path

            from vaultlab.provenance import ProvenanceRecord, write_receipts

            record = ProvenanceRecord(
                generated_by=provenance.generated_by,
                generated_at=provenance.generated_at,
                project=provenance.project,
                meeting_mode=provenance.meeting_mode,
                investigation_mode=provenance.investigation_mode,
                topic=provenance.topic,
                round=provenance.round if provenance.round is not None else 0,
                inputs=list(provenance.inputs),
                related_outputs=list(provenance.related_outputs),
                kind=provenance.kind,
                tags=list(provenance.tags),
                finding_ids=list(provenance.finding_ids),
                notes=provenance.notes,
                params=dict(provenance.params),
            )
            write_receipts(Path(path), record)
        except Exception:
            # Sidecar emission is best-effort — never fail the primary write.
            pass

    return path


def _append_to_index(
    path: str,
    provenance: Provenance,
    index_dir: str | None,
) -> None:
    directory = index_dir or os.path.dirname(os.path.abspath(path))
    os.makedirs(directory, exist_ok=True)
    index_path = os.path.join(directory, PROVENANCE_INDEX)
    record = {"path": os.path.abspath(path), **provenance.to_dict()}
    with open(index_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def read_provenance(path: str) -> Provenance | None:
    """Extract provenance from a markdown file with a frontmatter block."""
    if not os.path.isfile(path):
        return None
    with open(path, encoding="utf-8") as f:
        content = f.read(8192)
    if not content.startswith("---"):
        return None
    end = content.find("\n---", 3)
    if end == -1:
        return None
    body = content[3:end].strip()
    try:
        data = yaml.safe_load(body) or {}
    except yaml.YAMLError:
        return None
    return Provenance.from_dict(data)


__all__ = [
    "PROVENANCE_INDEX",
    "Provenance",
    "read_provenance",
    "write_with_provenance",
]
