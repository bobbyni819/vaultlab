"""Project configuration for vaultlab.

Loads ``.bobby-project.json`` (the same schema the legacy slash-command
pipeline used) into a typed :class:`ProjectConfig` so library code and
slash commands share one shape.

Lifted from ``bobby_ailab._config`` — behaviourally identical apart from
namespace and docstring polish.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class SignificanceThresholds:
    """Numerical thresholds the Critic uses when rating findings."""

    correlation_rho: float = 0.2
    fdr_alpha: float = 0.05
    cramers_v_meaningful: float = 0.3
    effect_size_min: float = 0.1

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "SignificanceThresholds":
        return cls(
            correlation_rho=float(d.get("correlation_rho", 0.2)),
            fdr_alpha=float(d.get("fdr_alpha", 0.05)),
            cramers_v_meaningful=float(d.get("cramers_v_meaningful", 0.3)),
            effect_size_min=float(d.get("effect_size_min", 0.1)),
        )


@dataclass
class ProjectConfig:
    """Typed view of ``.bobby-project.json``."""

    name: str
    kb_path: str
    domain: str = ""
    domain_context: str = ""
    data_dirs: list[str] = field(default_factory=list)
    figure_dirs: list[str] = field(default_factory=list)
    output_dirs: dict[str, str] = field(default_factory=dict)
    significance_thresholds: SignificanceThresholds = field(default_factory=SignificanceThresholds)
    target_journal: str = ""
    hypotheses: list[str] = field(default_factory=list)
    source_path: str = ""

    @classmethod
    def from_dict(cls, d: dict[str, Any], source_path: str = "") -> "ProjectConfig":
        return cls(
            name=d["name"],
            kb_path=d["kb_path"],
            domain=d.get("domain", ""),
            domain_context=d.get("domain_context", ""),
            data_dirs=list(d.get("data_dirs", [])),
            figure_dirs=list(d.get("figure_dirs", [])),
            output_dirs=dict(d.get("output_dirs", {})),
            significance_thresholds=SignificanceThresholds.from_dict(
                d.get("significance_thresholds", {})
            ),
            target_journal=d.get("target_journal", ""),
            hypotheses=list(d.get("hypotheses", [])),
            source_path=source_path,
        )

    def context_summary(self) -> str:
        """~500-token summary used as the shared session context header.

        Emits a warning to ``stderr`` if the summary exceeds the ~500-token
        budget the spec prescribes (checked as ~2000 chars ~= 500 tokens).
        """
        parts = [
            f"PROJECT: {self.name}",
            f"Domain: {self.domain}" if self.domain else "",
            f"Target journal: {self.target_journal}" if self.target_journal else "",
        ]
        if self.domain_context:
            parts.append(f"Domain context: {self.domain_context}")
        if self.hypotheses:
            parts.append("Hypotheses:")
            parts.extend(f"- {h}" for h in self.hypotheses)
        parts.append(
            "Thresholds: "
            f"rho>={self.significance_thresholds.correlation_rho}, "
            f"FDR<={self.significance_thresholds.fdr_alpha}, "
            f"Cramer's V>={self.significance_thresholds.cramers_v_meaningful}"
        )
        summary = "\n".join(p for p in parts if p)
        if len(summary) > 2000:
            import warnings
            warnings.warn(
                f"context_summary is {len(summary)} chars (~{len(summary) // 4} tokens); "
                f"budget is ~500 tokens. Consider shortening domain_context or hypotheses.",
                stacklevel=2,
            )
        return summary

    def validate(self) -> list[str]:
        """Check config for common problems. Returns list of warnings (empty = OK).

        Validates at the system boundary (file loading time). Does not check
        data file contents — that's Phase 1's job.
        """
        warnings: list[str] = []
        if not self.kb_path:
            warnings.append("kb_path is empty")
        elif not os.path.isdir(self.kb_path):
            warnings.append(f"kb_path does not exist: {self.kb_path}")
        for d in self.data_dirs:
            if not os.path.isdir(d):
                warnings.append(f"data_dirs entry not found: {d}")
        for d in self.figure_dirs:
            if not os.path.isdir(d):
                warnings.append(f"figure_dirs entry not found: {d}")
        if not self.domain:
            warnings.append("domain is empty — agents will reason in generic terms")
        if not self.domain_context:
            warnings.append(
                "domain_context is empty — no project-specific vocabulary will be injected"
            )
        if not self.data_dirs:
            warnings.append(
                "data_dirs is empty — pipeline will default to LITERATURE_REVIEW mode"
            )
        return warnings


def load_project_config(repo_root: Optional[str] = None) -> ProjectConfig:
    """Load ``.bobby-project.json`` from ``repo_root`` (cwd if ``None``).

    Raises :class:`FileNotFoundError` if the config is missing. Callers
    should ask the user to create one rather than silently falling back to
    defaults.
    """
    root = repo_root or os.getcwd()
    path = os.path.join(root, ".bobby-project.json")
    if not os.path.isfile(path):
        raise FileNotFoundError(
            f".bobby-project.json not found at {path}. "
            "Create one with at least name + kb_path fields."
        )
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return ProjectConfig.from_dict(data, source_path=path)


__all__ = [
    "ProjectConfig",
    "SignificanceThresholds",
    "load_project_config",
]
