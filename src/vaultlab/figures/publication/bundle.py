"""Publication figure bundles: contract, exports, audit, coverage, provenance."""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol, cast

from vaultlab.figures.contract import (
    FigureContract,
    apply_rcparams,
    triple_export,
    validate_contract,
)
from vaultlab.figures.publication.coverage import CoverageAuditResult, CoverageManifest
from vaultlab.figures.publication.save import save_fig
from vaultlab.figures.understand.layout_checks import AuditResult, run_layout_audit
from vaultlab.provenance import ProvenanceRecord, hash_inputs, write_receipts

if TYPE_CHECKING:
    from collections.abc import Sequence

    from matplotlib.figure import Figure

logger = logging.getLogger(__name__)


class _RecipeModule(Protocol):
    def render(self, data: Any, **kwargs: Any) -> Any: ...


@dataclass(frozen=True)
class PublicationBundleResult:
    """Paths and audit results emitted by :func:`save_publication_figure`."""

    png: Path
    svg: Path
    pdf: Path
    coverage_json: Path | None
    provenance_json: Path | None
    method_md: Path | None
    contract_warnings: list[str]
    layout_audit: AuditResult | None
    coverage_audit: CoverageAuditResult | None


def save_publication_figure(
    fig: Figure,
    output_stem: Path | str,
    *,
    contract: FigureContract,
    coverage: CoverageManifest | None = None,
    recipe_id: str | None = None,
    run_audit: bool = True,
) -> PublicationBundleResult:
    """Save a publication figure bundle from an in-memory matplotlib figure."""
    import matplotlib.pyplot as plt

    output = Path(output_stem)
    output.parent.mkdir(parents=True, exist_ok=True)

    contract_warnings = validate_contract(contract)
    apply_rcparams()

    main_stem = output.with_name(f"{output.name}_main")
    png = save_fig(fig, main_stem, formats=("png",), dpi=contract.dpi, close=False)[0]
    vector_paths = triple_export(fig, output, formats=("svg", "pdf"), dpi=contract.dpi)
    svg = vector_paths["svg"]
    pdf = vector_paths["pdf"]

    layout_audit = run_layout_audit(png) if run_audit else None

    coverage_json: Path | None = None
    coverage_audit: CoverageAuditResult | None = None
    if coverage is not None:
        coverage_audit = coverage.audit()
        coverage_json = coverage.to_json(output.with_suffix(".coverage.json"))

    provenance_json: Path | None = None
    method_md: Path | None = None
    try:
        record = ProvenanceRecord(
            generated_by="publication-bundle",
            inputs=coverage.source_data if coverage is not None else [],
            input_hashes=(
                coverage.source_data_sha256
                if coverage is not None and coverage.source_data_sha256 is not None
                else hash_inputs([Path(source) for source in coverage.source_data])
                if coverage is not None
                else {}
            ),
            params={
                "recipe_id": recipe_id,
                "contract": _contract_payload(contract),
                "contract_warnings": contract_warnings,
                "bundle_paths": {
                    "png": str(png),
                    "svg": str(svg),
                    "pdf": str(pdf),
                },
                "coverage_path": str(coverage_json) if coverage_json is not None else None,
                "coverage_audit": (asdict(coverage_audit) if coverage_audit is not None else None),
                "layout_audit": (layout_audit.to_json_dict() if layout_audit is not None else None),
            },
            kind="figure",
            producer="vaultlab.figures.publication.bundle",
            tags=["figure-publication-bundle"],
        )
        provenance_json, method_md = write_receipts(png, record)
    except Exception:
        logger.exception("write_receipts failed for publication bundle %s", png)
    finally:
        plt.close(fig)

    return PublicationBundleResult(
        png=png,
        svg=svg,
        pdf=pdf,
        coverage_json=coverage_json,
        provenance_json=provenance_json,
        method_md=method_md,
        contract_warnings=contract_warnings,
        layout_audit=layout_audit,
        coverage_audit=coverage_audit,
    )


def render_with_contract(
    recipe_id: str,
    data: Any,
    output_stem: Path | str,
    *,
    contract: FigureContract,
    coverage: CoverageManifest | None = None,
    run_audit: bool = True,
    **render_kwargs: Any,
) -> PublicationBundleResult:
    """Render an existing recipe and save it through the publication bundle."""
    module = _recipe_module(recipe_id)
    module_any = cast(Any, module)
    captured: list[Figure] = []
    original_save_fig = getattr(module, "save_fig", None)

    def _capture_save_fig(
        fig: Figure,
        out_path: Path | str,
        *,
        formats: Sequence[str] = ("png", "pdf"),
        dpi: int = 300,
        facecolor: str = "white",
        bbox_inches: str = "tight",
        close: bool = True,
    ) -> list[Path]:
        captured.append(fig)
        return [Path(out_path).with_suffix(f".{fmt}") for fmt in formats]

    if original_save_fig is not None:
        module_any.save_fig = _capture_save_fig
    try:
        rendered = module.render(data, output_path=output_stem, **render_kwargs)
    finally:
        if original_save_fig is not None:
            module_any.save_fig = original_save_fig

    if captured:
        fig = captured[-1]
    elif hasattr(rendered, "savefig"):
        fig = cast("Figure", rendered)
    else:
        raise TypeError(
            f"recipe {recipe_id!r} did not expose a matplotlib Figure through save_fig or return"
        )

    return save_publication_figure(
        fig,
        output_stem,
        contract=contract,
        coverage=coverage,
        recipe_id=recipe_id,
        run_audit=run_audit,
    )


def _recipe_module(recipe_id: str) -> _RecipeModule:
    from vaultlab.figures import recipes

    if recipe_id not in recipes.__all__:
        known = ", ".join(sorted(recipes.__all__))
        raise KeyError(f"unknown figure recipe {recipe_id!r}; known recipes: {known}")
    module = getattr(recipes, recipe_id)
    if not hasattr(module, "render"):
        raise TypeError(f"figure recipe {recipe_id!r} has no render() function")
    return cast(_RecipeModule, module)


def _contract_payload(contract: FigureContract) -> dict[str, Any]:
    payload = asdict(contract)
    payload["archetype"] = contract.archetype.value
    if contract.source_data_path is not None:
        payload["source_data_path"] = str(contract.source_data_path)
    return payload


__all__ = [
    "PublicationBundleResult",
    "render_with_contract",
    "save_publication_figure",
]
