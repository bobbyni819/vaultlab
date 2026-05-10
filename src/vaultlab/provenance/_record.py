"""ProvenanceRecord — structured receipt for a pipeline output.

Per ``AGENTS.md`` Reproducibility receipts, every output (figure, manuscript
section, slide deck, citation, ...) writes BOTH:

- ``<output>.provenance.json`` — machine-readable (input hashes, code version,
  params, seed, model, timestamps)
- ``<output>.method.md`` — human-readable narrative for paper methods sections

This module defines the in-memory record. ``_writer`` serializes it; ``_reader``
loads it back.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class ProvenanceRecord:
    """Structured provenance for a pipeline output.

    The fields cover the AGENTS.md "machine-readable receipt" requirements
    (inputs, code version, params, seed, model, timestamps) plus the
    investigative-context fields that the bobby_ailab pipeline relied on
    (project, mode, topic, finding ids, tags).
    """

    # Required: who/when produced this output
    generated_by: str  # tool / command, e.g. "deep-think", "figure-gen"
    generated_at: str = ""  # ISO8601 timestamp; auto-filled if empty

    # Project / investigation context
    project: str = ""
    meeting_mode: str = ""  # adversarial / round_table
    investigation_mode: str = ""  # directed / exploratory
    topic: str = ""
    round: int | None = None

    # Reproducibility receipts
    inputs: list[str] = field(default_factory=list)  # input file paths / IDs
    input_hashes: dict[str, str] = field(default_factory=dict)  # path -> sha256
    code_version: str = ""  # git sha / package version
    params: dict[str, Any] = field(default_factory=dict)  # hyperparameters
    seed: int | None = None
    model: str = ""  # LLM / model identifier when relevant

    # Linking
    related_outputs: list[str] = field(default_factory=list)
    finding_ids: list[str] = field(default_factory=list)

    # Classification
    kind: str = ""  # "figure", "manuscript_section", "slide_deck", ...
    tags: list[str] = field(default_factory=list)

    # Free-form
    notes: str = ""

    def __post_init__(self) -> None:
        if not self.generated_at:
            self.generated_at = datetime.now().isoformat(timespec="seconds")

    # ------------------------------------------------------------------ dict

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a dict, omitting empty optional fields."""
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
            "input_hashes",
            "code_version",
            "params",
            "seed",
            "model",
            "related_outputs",
            "finding_ids",
            "kind",
            "tags",
            "notes",
        ):
            value = getattr(self, field_name)
            # Keep falsy ints (0) and explicit zero round; omit empty containers / strings
            if value or value == 0:
                out[field_name] = value
        return out

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ProvenanceRecord:
        return cls(
            generated_by=str(d.get("generated_by", "")),
            generated_at=str(d.get("generated_at", "")),
            project=str(d.get("project", "")),
            meeting_mode=str(d.get("meeting_mode", "")),
            investigation_mode=str(d.get("investigation_mode", "")),
            topic=str(d.get("topic", "")),
            round=d.get("round"),
            inputs=list(d.get("inputs", [])),
            input_hashes=dict(d.get("input_hashes", {})),
            code_version=str(d.get("code_version", "")),
            params=dict(d.get("params", {})),
            seed=d.get("seed"),
            model=str(d.get("model", "")),
            related_outputs=list(d.get("related_outputs", [])),
            finding_ids=list(d.get("finding_ids", [])),
            kind=str(d.get("kind", "")),
            tags=list(d.get("tags", [])),
            notes=str(d.get("notes", "")),
        )


__all__ = ["ProvenanceRecord"]
