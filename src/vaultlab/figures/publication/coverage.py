"""CoverageManifest dataclass — placeholder for P0.2.

This module currently provides a minimal `CoverageManifest` skeleton. The full
implementation (regions/donors/cell-types accounting, JSON sidecar I/O,
verdict integration with `/figure-audit`) lands in commit 3 (P0.2).

See:
- File 14 (cap-wet-lab-data-ingest) Q14.5 — provenance receipts
- File 06 (bobby_figures) Q6.1 — publication submodule layout
- ailab/Sources/Notes/figure-audit-capability-spec.md — the full spec
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class CoverageManifest:
    """What a figure covers (and what it deliberately excludes).

    A figure-audit sidecar that lets `/figure-audit` (P0.3) verdict the figure
    as PASS / PARTIAL_JUSTIFIED / PARTIAL_UNJUSTIFIED / BROKEN_MANIFEST /
    FABRICATED / UNVERIFIABLE.

    PLACEHOLDER — full schema lands in P0.2 commit. The fields below capture
    the minimum spec from figure-audit-capability-spec.md but don't yet have
    JSON I/O, validation, or auditor integration.
    """

    figure_id: str
    script_path: str
    timestamp: str

    regions_included: list[str] = field(default_factory=list)
    donors_included: list[str] = field(default_factory=list)
    cell_types_included: list[str] = field(default_factory=list)

    exclusions: list[str] = field(default_factory=list)
    exclusion_reasons: dict[str, str] = field(default_factory=dict)

    analysis_params: dict[str, Any] = field(default_factory=dict)

    def as_footer_text(self) -> str:
        """Render the manifest as a one-line figure-footer string.

        Convention: the in-figure footer reads from the manifest (never
        hardcoded). Per AGENTS.md (figure-audit Invariant 2).
        """
        parts: list[str] = []
        if self.regions_included:
            parts.append(f"regions: {', '.join(self.regions_included)}")
        if self.donors_included:
            parts.append(f"donors: n={len(self.donors_included)}")
        if self.cell_types_included:
            parts.append(f"cell types: n={len(self.cell_types_included)}")
        if self.exclusions:
            parts.append(f"excluded: {', '.join(self.exclusions)}")
        return " | ".join(parts) if parts else "(coverage unspecified)"
