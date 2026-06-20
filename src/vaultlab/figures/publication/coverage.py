"""Coverage manifests for publication figures."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

SCHEMA = "vaultlab-coverage-manifest/v1"


@dataclass(frozen=True)
class CoverageAuditResult:
    """Result of validating a coverage manifest."""

    ok: bool
    problems: list[str]


@dataclass
class CoverageManifest:
    """What a figure covers and what it deliberately excludes."""

    figure_id: str
    script_path: str
    timestamp: str | None = None
    panel_role: str | None = None

    regions_included: list[str] = field(default_factory=list)
    donors_included: list[str] = field(default_factory=list)
    cell_types_included: list[str] = field(default_factory=list)

    exclusions: list[str] = field(default_factory=list)
    exclusion_reasons: dict[str, str] = field(default_factory=dict)

    analysis_params: dict[str, Any] = field(default_factory=dict)
    params: dict[str, Any] = field(default_factory=dict)
    source_data: list[str] = field(default_factory=list)
    source_data_sha256: dict[str, str] | None = None
    footer: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-ready dict."""
        return {
            "schema": SCHEMA,
            "figure_id": self.figure_id,
            "script_path": self.script_path,
            "timestamp": self.timestamp,
            "panel_role": self.panel_role,
            "regions_included": list(self.regions_included),
            "donors_included": list(self.donors_included),
            "cell_types_included": list(self.cell_types_included),
            "exclusions": list(self.exclusions),
            "exclusion_reasons": dict(self.exclusion_reasons),
            "analysis_params": dict(self.analysis_params),
            "params": dict(self.params),
            "source_data": list(self.source_data),
            "source_data_sha256": (
                dict(self.source_data_sha256) if self.source_data_sha256 is not None else None
            ),
            "footer": self.footer,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> CoverageManifest:
        """Build a manifest from a parsed JSON payload."""
        params = dict(payload.get("params", {}))
        analysis_params = dict(payload.get("analysis_params", {}))
        if not params and analysis_params:
            params = dict(analysis_params)
        source_hashes = payload.get("source_data_sha256")
        return cls(
            figure_id=str(payload.get("figure_id", "")),
            script_path=str(payload.get("script_path", "")),
            timestamp=_optional_str(payload.get("timestamp")),
            panel_role=_optional_str(payload.get("panel_role")),
            regions_included=_string_list(payload.get("regions_included", [])),
            donors_included=_string_list(payload.get("donors_included", [])),
            cell_types_included=_string_list(payload.get("cell_types_included", [])),
            exclusions=_string_list(payload.get("exclusions", [])),
            exclusion_reasons={
                str(k): str(v) for k, v in dict(payload.get("exclusion_reasons", {})).items()
            },
            analysis_params=analysis_params,
            params=params,
            source_data=_string_list(payload.get("source_data", [])),
            source_data_sha256=(
                {str(k): str(v) for k, v in dict(source_hashes).items()}
                if isinstance(source_hashes, dict)
                else None
            ),
            footer=_optional_str(payload.get("footer")),
        )

    def to_json(self, path: Path | str) -> Path:
        """Atomically write the manifest JSON sidecar."""
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_name(f".{target.name}.tmp")
        tmp.write_text(
            json.dumps(self.to_dict(), ensure_ascii=False, indent=2, sort_keys=False) + "\n",
            encoding="utf-8",
        )
        os.replace(tmp, target)
        return target

    @classmethod
    def read_json(cls, path: Path | str) -> CoverageManifest:
        """Read a coverage manifest JSON sidecar."""
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError(f"coverage manifest must be a JSON object: {path}")
        return cls.from_dict(payload)

    def validate(self) -> list[str]:
        """Return coverage-manifest problems without raising."""
        problems: list[str] = []
        if not self.figure_id.strip():
            problems.append("missing required field: figure_id")
        if not self.script_path.strip():
            problems.append("missing required field: script_path")
        for source_path in self.source_data:
            if not source_path.strip():
                problems.append("source_data contains an empty path")
        if self.source_data_sha256 is not None:
            for source_path in self.source_data:
                if source_path not in self.source_data_sha256:
                    problems.append(f"missing sha256 for source_data path: {source_path}")
        problems.extend(_negative_number_problems("params", self.params))
        problems.extend(_negative_number_problems("analysis_params", self.analysis_params))
        if self.footer is not None and self.footer.strip() != self.footer_text():
            problems.append("footer does not match manifest-derived coverage footer")
        return problems

    def audit(self) -> CoverageAuditResult:
        """Validate and wrap the result in a structured audit record."""
        problems = self.validate()
        return CoverageAuditResult(ok=not problems, problems=problems)

    def footer_text(self) -> str:
        """Render the manifest as a one-line figure-footer string."""
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

    def as_footer_text(self) -> str:
        """Backward-compatible alias for :meth:`footer_text`."""
        return self.footer_text()


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def _negative_number_problems(prefix: str, value: Any) -> list[str]:
    problems: list[str] = []
    if isinstance(value, bool):
        return problems
    if isinstance(value, (int, float)) and value < 0:
        problems.append(f"negative count/value at {prefix}: {value}")
        return problems
    if isinstance(value, dict):
        for key, nested in value.items():
            problems.extend(_negative_number_problems(f"{prefix}.{key}", nested))
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            problems.extend(_negative_number_problems(f"{prefix}[{index}]", nested))
    return problems


__all__ = ["CoverageAuditResult", "CoverageManifest"]
