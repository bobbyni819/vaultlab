"""Deterministic plain-words explainers for publication figures."""

from __future__ import annotations

import os
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from vaultlab.figures.contract import FigureContract
from vaultlab.figures.publication.coverage import CoverageManifest
from vaultlab.manuscript.claim_ledger import Claim


@dataclass(frozen=True)
class FigureExplainer:
    """Five-part plain-language explanation for a figure."""

    figure_id: str
    one_breath: str
    what_it_is: str
    how_to_read: str
    method_plain: str
    what_it_means: str
    caveat: str

    def to_dict(self) -> dict[str, str]:
        """Serialize the explainer to a plain dictionary."""
        return asdict(self)

    def to_markdown(self) -> str:
        """Render the explainer as the standard five-part markdown block."""
        return (
            f"> 🟢 In one breath: {self.one_breath}\n\n"
            "### What it is\n"
            f"{self.what_it_is}\n\n"
            "### How to read it\n"
            f"{self.how_to_read}\n\n"
            "### Method in plain words\n"
            f"{self.method_plain}\n\n"
            "### What it means\n"
            f"{self.what_it_means}\n\n"
            "### Caveat\n"
            f"{self.caveat}\n"
        )


def explain_figure(
    *,
    figure_id: str | None = None,
    contract: FigureContract | None = None,
    coverage: CoverageManifest | None = None,
    claims: list[Claim] | None = None,
    refine_fn: Callable[[FigureExplainer], FigureExplainer] | None = None,
) -> FigureExplainer:
    """Build a deterministic five-part explainer from structured figure inputs."""
    if contract is None and coverage is None and not claims:
        raise ValueError("explain_figure requires at least one of contract, coverage, or claims")

    resolved_figure_id = _resolve_figure_id(figure_id, coverage)
    claim_texts = [_clean(claim.text) for claim in claims or [] if _clean(claim.text)]
    conclusion = _clean(contract.conclusion) if contract is not None else ""
    primary_point = conclusion or (claim_texts[0] if claim_texts else "")

    seed = FigureExplainer(
        figure_id=resolved_figure_id,
        one_breath=_one_breath(resolved_figure_id, primary_point),
        what_it_is=_what_it_is(contract, primary_point),
        how_to_read=_how_to_read(contract),
        method_plain=_method_plain(contract, coverage),
        what_it_means=_what_it_means(primary_point, claim_texts),
        caveat=_caveat(contract, coverage),
    )
    if refine_fn is not None:
        return refine_fn(seed)
    return seed


def explain_from_bundle(
    coverage_path: str | Path,
    *,
    contract: FigureContract | None = None,
    claims: list[Claim] | None = None,
    refine_fn: Callable[[FigureExplainer], FigureExplainer] | None = None,
) -> FigureExplainer:
    """Read a coverage sidecar and return its deterministic explainer."""
    coverage = CoverageManifest.read_json(_coverage_json_path(coverage_path))
    return explain_figure(
        contract=contract,
        coverage=coverage,
        claims=claims,
        refine_fn=refine_fn,
    )


def write_explainer(png_or_stem: str | Path, explainer: FigureExplainer) -> Path:
    """Atomically write ``<stem>.explainer.md`` for a figure or stem path."""
    base = Path(png_or_stem)
    target = base.with_suffix(".explainer.md") if base.suffix else base.with_name(
        f"{base.name}.explainer.md"
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_name(f".{target.name}.tmp")
    tmp.write_text(explainer.to_markdown(), encoding="utf-8")
    os.replace(tmp, target)
    return target


def _resolve_figure_id(
    figure_id: str | None,
    coverage: CoverageManifest | None,
) -> str:
    explicit = _clean(figure_id)
    if explicit:
        return explicit
    if coverage is not None:
        from_coverage = _clean(coverage.figure_id)
        if from_coverage:
            return from_coverage
    return "figure"


def _one_breath(figure_id: str, primary_point: str) -> str:
    if primary_point:
        return _sentence(f"{figure_id} appears consistent with {primary_point}")
    return (
        f"{figure_id} provides a structured visual summary, but the main interpretation "
        "needs author review"
    )


def _what_it_is(contract: FigureContract | None, primary_point: str) -> str:
    if contract is None:
        return "A figure-level visual summary with no figure contract supplied yet."
    archetype = _humanize_archetype(contract.archetype.value)
    article = _article_for(archetype)
    if primary_point:
        return _sentence(f"{article} {archetype} showing evidence relevant to {primary_point}")
    return _sentence(f"{article} {archetype} with the conclusion still to be specified")


def _how_to_read(contract: FigureContract | None) -> str:
    parts: list[str] = []
    if contract is not None and contract.evidence_chain:
        panel_lines = [
            f"Panel {panel}: use this panel to assess {_lower_first(_strip_sentence(statement))}."
            for panel, statement in contract.evidence_chain.items()
            if _clean(panel) and _clean(statement)
        ]
        if panel_lines:
            parts.append(" ".join(panel_lines))
    if contract is not None and _clean(contract.color_policy):
        parts.append(_sentence(f"Color should be read using this policy: {_clean(contract.color_policy)}"))
    if not parts:
        parts.append(
            "Read the figure by matching each visual element to the caption and any panel labels."
        )
    return " ".join(parts)


def _method_plain(contract: FigureContract | None, coverage: CoverageManifest | None) -> str:
    parts: list[str] = []
    if coverage is not None:
        coverage_parts = _coverage_parts(coverage)
        if coverage_parts:
            parts.append(f"Computed from {', '.join(coverage_parts)}.")
        params = _combined_params(coverage)
        if params:
            parts.append(f"Key analysis settings: {_format_mapping(params)}.")
        if coverage.source_data:
            parts.append(f"Coverage source data: {', '.join(coverage.source_data)}.")
        footer = coverage.footer_text()
        if footer != "(coverage unspecified)":
            parts.append(f"Coverage footer: {footer}.")
    if contract is not None:
        if contract.source_data_path is not None and _clean(str(contract.source_data_path)):
            parts.append(f"Source data path: {contract.source_data_path}.")
        if _clean(contract.stats_block):
            parts.append(f"Statistic: {_clean(contract.stats_block)}.")
    if not parts:
        parts.append("Method details are not yet specified in the structured coverage or contract.")
    return " ".join(parts)


def _what_it_means(primary_point: str, claim_texts: Sequence[str]) -> str:
    parts: list[str] = []
    if primary_point:
        parts.append(_sentence(f"The pattern remains consistent with {primary_point}"))
    if claim_texts:
        claims = "; ".join(claim_texts)
        parts.append(_sentence(f"It can support discussion of these hedged claims: {claims}"))
    if not parts:
        parts.append(
            "The figure can support interpretation once a conclusion or linked claim is supplied."
        )
    return " ".join(parts)


def _caveat(contract: FigureContract | None, coverage: CoverageManifest | None) -> str:
    parts: list[str] = []
    if coverage is not None and coverage.exclusions:
        exclusions = ", ".join(coverage.exclusions)
        parts.append(f"Coverage excludes {exclusions}.")
    if coverage is not None and coverage.exclusion_reasons:
        parts.append(f"Exclusion reasons: {_format_mapping(coverage.exclusion_reasons)}.")
    if contract is not None and _clean(contract.image_integrity_notes):
        parts.append(
            f"Image or display integrity note: {_strip_sentence(contract.image_integrity_notes)}."
        )
    if contract is not None and _clean(contract.notes):
        parts.append(f"Author note: {_strip_sentence(contract.notes)}.")
    if not parts:
        parts.append("Interpret this figure within the stated coverage and analysis settings.")
    return " ".join(parts)


def _coverage_parts(coverage: CoverageManifest) -> list[str]:
    parts: list[str] = []
    if coverage.donors_included:
        parts.append(_count_phrase(len(coverage.donors_included), "donor"))
    if coverage.regions_included:
        parts.append(
            f"{_count_phrase(len(coverage.regions_included), 'region')} "
            f"({', '.join(coverage.regions_included)})"
        )
    if coverage.cell_types_included:
        parts.append(
            f"{_count_phrase(len(coverage.cell_types_included), 'cell type')} "
            f"({', '.join(coverage.cell_types_included)})"
        )
    return parts


def _combined_params(coverage: CoverageManifest) -> dict[str, Any]:
    params: dict[str, Any] = dict(coverage.analysis_params)
    params.update(coverage.params)
    return params


def _coverage_json_path(path: str | Path) -> Path:
    candidate = Path(path)
    if candidate.suffix == ".json":
        return candidate
    if candidate.suffix:
        return candidate.with_suffix(".coverage.json")
    return candidate.with_name(f"{candidate.name}.coverage.json")


def _humanize_archetype(value: str) -> str:
    names = {
        "quantitative_grid": "quantitative grid",
        "schematic_led_composite": "schematic-led composite",
        "image_plate_and_quant": "image plate with quantification",
        "asymmetric_mixed_modality": "asymmetric mixed-modality figure",
    }
    return names.get(value, value.replace("_", " "))


def _article_for(phrase: str) -> str:
    first = phrase[:1].lower()
    return "An" if first in {"a", "e", "i", "o", "u"} else "A"


def _format_mapping(mapping: Mapping[str, Any]) -> str:
    items = [f"{key}={value}" for key, value in mapping.items()]
    return ", ".join(items) if items else "not specified"


def _count_phrase(count: int, singular: str) -> str:
    suffix = "" if count == 1 else "s"
    return f"{count} {singular}{suffix}"


def _clean(value: str | None) -> str:
    return "" if value is None else value.strip()


def _strip_sentence(value: str) -> str:
    return _clean(value).rstrip(".")


def _sentence(value: str) -> str:
    text = _strip_sentence(value)
    return f"{text}." if text else ""


def _lower_first(value: str) -> str:
    text = _clean(value)
    if not text:
        return ""
    return text[0].lower() + text[1:]


__all__ = [
    "FigureExplainer",
    "explain_figure",
    "explain_from_bundle",
    "write_explainer",
]
