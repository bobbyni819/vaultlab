"""Result-analysis pipeline.

Consumes tidy result files (CSV / Parquet / TSV) from a project directory
and produces:

- ``stats_summary`` per file (dtype, n, summary stats)
- one figure per ``figures_config`` entry, rendered with matplotlib using
  the ``vaultlab.figures.contract`` rcParams
- a draft ``methods.md`` paragraph (template-based, no LLM)
- per-artifact provenance + method-md sidecars via
  ``vaultlab.provenance.write_receipts`` (AGENTS.md Red Line #2)

Scope discipline
----------------

vaultlab is the **layer above** analysis. Inputs MUST be tidy result
tables. Raw-data formats (FASTQ / BAM / HDF5 / microscopy / mass-spec)
are rejected with a :class:`ValueError` pointing the user to their
analysis code.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from vaultlab.provenance import ProvenanceRecord, hash_inputs, write_receipts

from .methods import compose_methods_paragraph
from .stats import summarize_dataframe

if TYPE_CHECKING:
    import pandas as pd

logger = logging.getLogger(__name__)

__all__ = [
    "AnalysisResult",
    "RAW_DATA_EXTENSIONS",
    "TIDY_RESULT_EXTENSIONS",
    "run_pipeline",
]

# ---------------------------------------------------------------------------
# Scope discipline — accepted vs rejected file extensions
# ---------------------------------------------------------------------------

TIDY_RESULT_EXTENSIONS: frozenset[str] = frozenset(
    {".csv", ".parquet", ".pq", ".tsv", ".tab"}
)
"""File extensions the pipeline will consume.

These are POST-ANALYSIS tidy result tables. CSV / TSV / Parquet only.
"""

RAW_DATA_EXTENSIONS: frozenset[str] = frozenset(
    {
        # Sequencing
        ".fastq",
        ".fq",
        ".fastq.gz",
        ".fq.gz",
        ".bam",
        ".sam",
        ".cram",
        ".vcf",
        ".bcf",
        # Single-cell / HDF5
        ".h5",
        ".h5ad",
        ".loom",
        # Microscopy
        ".nd2",
        ".czi",
        ".lif",
        ".tif",
        ".tiff",
        # Medical imaging
        ".nii",
        ".dcm",
        # Mass-spec
        ".mzml",
        ".mzxml",
        ".raw",
        ".wiff",
        # Flow cytometry
        ".fcs",
    }
)
"""File extensions the pipeline will REJECT.

If any of these are present in the project directory the pipeline raises
:class:`ValueError` and points the user back to their analysis code.
"""

# Slide-deck-friendly figure kinds. Keep this minimal so the SKILL.md scope
# stays clear: vaultlab does not host a chart library; it composes a tiny
# vocabulary of plots over tidy data and delegates everything fancier to
# ``vaultlab.figures.recipes``.
FigureKind = Literal["bar", "scatter", "histogram", "line"]


@dataclass
class AnalysisResult:
    """Return value of :func:`run_pipeline`.

    Attributes
    ----------
    project_dir
        The (resolved) project directory the pipeline consumed.
    out_dir
        Where outputs landed.
    figures
        Generated figure paths (PNG; one per ``figures_config`` entry).
    methods_md
        Path to the drafted ``methods.md`` (or ``None`` if no inputs).
    stats_summary
        Two-level dict ``{filename: {column: {dtype, n, ...}}}``.
    manifest_paths
        List of every ``.provenance.json`` sidecar written by the pipeline.
    inputs
        The tidy input files discovered (resolved paths).
    """

    project_dir: Path
    out_dir: Path
    figures: list[Path] = field(default_factory=list)
    methods_md: Path | None = None
    stats_summary: dict[str, dict[str, dict[str, Any]]] = field(default_factory=dict)
    manifest_paths: list[Path] = field(default_factory=list)
    inputs: list[Path] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Public entrypoint
# ---------------------------------------------------------------------------


def run_pipeline(
    project_dir: Path | str,
    *,
    out_dir: Path | str | None = None,
    figures_config: dict[str, dict[str, Any]] | None = None,
    project_name: str | None = None,
) -> AnalysisResult:
    """Consume project's tidy results; produce figures + methods + audit.

    Parameters
    ----------
    project_dir
        Project directory holding result tables (CSV / Parquet / TSV). May
        also contain a ``vaultlab-analysis.json`` config; if present and
        ``figures_config`` is None it is loaded from that file's
        ``"figures"`` key.
    out_dir
        Destination directory. Defaults to ``project_dir / "out"``.
    figures_config
        Mapping ``{figure_name: {kind, source, x, y?, ...}}``. ``kind`` is
        one of ``"bar" | "scatter" | "histogram" | "line"``. ``source`` is
        the input filename (relative or basename; resolved against
        discovered inputs). ``x`` and ``y`` name columns.
    project_name
        Friendly name for the methods paragraph header. Defaults to the
        project directory name.

    Returns
    -------
    AnalysisResult
        Paths + summary dict for the artifacts that were produced.

    Raises
    ------
    ValueError
        If any file in ``project_dir`` has an extension in
        :data:`RAW_DATA_EXTENSIONS`. vaultlab is the layer ABOVE analysis;
        raw-data processing belongs in the user's analysis code.
    """
    project = Path(project_dir).resolve()
    if not project.is_dir():
        raise ValueError(f"project_dir does not exist or is not a directory: {project}")
    out = Path(out_dir).resolve() if out_dir else (project / "out").resolve()
    out.mkdir(parents=True, exist_ok=True)

    if project_name is None:
        project_name = project.name

    # ---- 1. Scope-discipline pre-check + input discovery ----
    _enforce_scope_discipline(project)
    inputs = _discover_inputs(project)

    # ---- 2. Resolve figures_config (from arg or vaultlab-analysis.json) ----
    figures_config = _resolve_figures_config(figures_config, project)

    # ---- 3. Compute stats_summary per input file ----
    dataframes: dict[str, "pd.DataFrame"] = {}
    stats_summary: dict[str, dict[str, dict[str, Any]]] = {}
    for inp in inputs:
        df = _read_tidy(inp)
        dataframes[inp.name] = df
        stats_summary[inp.name] = summarize_dataframe(df)

    # ---- 4. Generate figures ----
    figure_paths: list[Path] = []
    figure_entries: list[dict[str, Any]] = []
    manifest_paths: list[Path] = []

    for fig_name, fig_cfg in figures_config.items():
        source_name = fig_cfg.get("source")
        if not source_name:
            logger.warning("figure %r has no 'source' — skipping", fig_name)
            continue
        # Resolve source to a discovered input by basename or stem
        df = _resolve_source(source_name, dataframes)
        if df is None:
            logger.warning(
                "figure %r references unknown source %r — skipping",
                fig_name,
                source_name,
            )
            continue
        fig_path = out / f"{fig_name}.png"
        try:
            _render_figure(df, fig_cfg, fig_path)
        except Exception as exc:  # noqa: BLE001 — best-effort per figure
            logger.exception("figure %r failed: %s", fig_name, exc)
            continue
        figure_paths.append(fig_path)
        # Store path relative to out_dir for portability of the methods.md
        # reference output across machines.
        try:
            rel_path = fig_path.relative_to(out)
        except ValueError:
            rel_path = fig_path
        entry = {"name": fig_name, "path": str(rel_path), **fig_cfg}
        figure_entries.append(entry)
        manifest_paths.extend(
            _write_figure_sidecars(fig_path, fig_cfg, df, inputs, project_name)
        )

    # ---- 5. Compose methods paragraph ----
    methods_md_path: Path | None = None
    if stats_summary:
        methods_text = compose_methods_paragraph(
            stats_summary,
            figure_entries=figure_entries,
            project_meta={"project_name": project_name},
        )
        methods_md_path = out / "methods.md"
        methods_md_path.write_text(methods_text, encoding="utf-8")
        manifest_paths.extend(
            _write_methods_sidecars(methods_md_path, inputs, project_name, figure_entries)
        )

    # ---- 6. Top-level stats_summary.json — convenient audit hook ----
    stats_path = out / "stats_summary.json"
    stats_path.write_text(json.dumps(stats_summary, indent=2), encoding="utf-8")

    return AnalysisResult(
        project_dir=project,
        out_dir=out,
        figures=figure_paths,
        methods_md=methods_md_path,
        stats_summary=stats_summary,
        manifest_paths=manifest_paths,
        inputs=inputs,
    )


# ---------------------------------------------------------------------------
# Scope discipline
# ---------------------------------------------------------------------------


def _enforce_scope_discipline(project: Path) -> None:
    """Raise :class:`ValueError` if any raw-data file is present.

    Scans ``project_dir`` and its immediate ``inputs/`` and ``data/``
    subdirectories. We do NOT recursively walk the entire tree — that
    would false-flag any user project that happens to have raw data in a
    sibling folder.
    """
    scan_dirs = [project]
    for sub in ("inputs", "data"):
        candidate = project / sub
        if candidate.is_dir():
            scan_dirs.append(candidate)

    offenders: list[Path] = []
    for d in scan_dirs:
        for entry in d.iterdir():
            if not entry.is_file():
                continue
            ext = _full_extension(entry).lower()
            if ext in RAW_DATA_EXTENSIONS:
                offenders.append(entry)

    if offenders:
        names = ", ".join(str(p.relative_to(project)) for p in offenders[:5])
        more = f" (+{len(offenders) - 5} more)" if len(offenders) > 5 else ""
        raise ValueError(
            "vaultlab.analysis consumes POST-analysis tidy result tables "
            "(CSV / Parquet / TSV), not raw data. Found raw-data files in "
            f"{project}: {names}{more}. Run your analysis code first and pass "
            "the tidy results to run_pipeline()."
        )


def _full_extension(path: Path) -> str:
    """Return the full extension including ``.gz`` for files like ``foo.fastq.gz``."""
    # path.suffix returns only the last suffix; we want e.g. ``.fastq.gz``
    suffixes = path.suffixes
    if len(suffixes) >= 2 and suffixes[-1].lower() == ".gz":
        return (suffixes[-2] + suffixes[-1]).lower()
    return path.suffix.lower()


# ---------------------------------------------------------------------------
# Input discovery + reading
# ---------------------------------------------------------------------------


def _discover_inputs(project: Path) -> list[Path]:
    """Find tidy result tables in the project's top-level + inputs/ + data/."""
    scan_dirs = [project]
    for sub in ("inputs", "data"):
        candidate = project / sub
        if candidate.is_dir():
            scan_dirs.append(candidate)

    found: list[Path] = []
    seen: set[Path] = set()
    for d in scan_dirs:
        for entry in sorted(d.iterdir()):
            if not entry.is_file():
                continue
            if entry.suffix.lower() in TIDY_RESULT_EXTENSIONS:
                resolved = entry.resolve()
                if resolved not in seen:
                    seen.add(resolved)
                    found.append(resolved)
    return found


def _read_tidy(path: Path) -> "pd.DataFrame":
    """Dispatch on extension to read CSV / TSV / Parquet."""
    import pandas as pd

    ext = path.suffix.lower()
    if ext == ".csv":
        return pd.read_csv(path)
    if ext in (".tsv", ".tab"):
        return pd.read_csv(path, sep="\t")
    if ext in (".parquet", ".pq"):
        return pd.read_parquet(path)
    raise ValueError(f"Unrecognized tidy extension for {path}")


def _resolve_source(
    source_name: str, dataframes: dict[str, "pd.DataFrame"]
) -> "pd.DataFrame | None":
    """Match a config's ``source`` (basename or stem) to a discovered input."""
    if source_name in dataframes:
        return dataframes[source_name]
    for name, df in dataframes.items():
        if Path(name).stem == source_name or name.lower() == source_name.lower():
            return df
    return None


# ---------------------------------------------------------------------------
# figures_config loader
# ---------------------------------------------------------------------------


def _resolve_figures_config(
    figures_config: dict[str, dict[str, Any]] | None, project: Path
) -> dict[str, dict[str, Any]]:
    if figures_config is not None:
        return figures_config
    cfg_path = project / "vaultlab-analysis.json"
    if cfg_path.is_file():
        try:
            payload = json.loads(cfg_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            logger.warning("vaultlab-analysis.json invalid JSON: %s", exc)
            return {}
        if isinstance(payload, dict):
            figs = payload.get("figures")
            if isinstance(figs, dict):
                return figs
    return {}


# ---------------------------------------------------------------------------
# Figure rendering — small vocabulary, matplotlib only
# ---------------------------------------------------------------------------


def _render_figure(
    df: "pd.DataFrame", fig_cfg: dict[str, Any], out_path: Path
) -> None:
    """Render one figure to ``out_path`` (PNG).

    The figure vocabulary is intentionally minimal (bar / scatter /
    histogram / line). For anything fancier the user should reach for
    ``vaultlab.figures.recipes`` — the SKILL bundle calls that out.
    """
    import matplotlib

    matplotlib.use("Agg", force=True)
    import matplotlib.pyplot as plt

    # Apply the publication-quality rcParams from figures.contract so the
    # figures we ship match the rest of vaultlab's visual contract.
    try:
        from vaultlab.figures.contract import apply_rcparams

        apply_rcparams()
    except Exception:  # noqa: BLE001 — rcParams are nice-to-have
        pass

    kind = fig_cfg.get("kind")
    x = fig_cfg.get("x")
    y = fig_cfg.get("y")
    title = fig_cfg.get("title") or ""
    xlabel = fig_cfg.get("xlabel", x)
    ylabel = fig_cfg.get("ylabel", y or "count")
    color = fig_cfg.get("color", "#7BA6C9")  # NMI_PASTEL[0] equivalent

    fig, ax = plt.subplots(figsize=(4.5, 3.2))

    try:
        if kind == "histogram":
            if not x or x not in df.columns:
                raise ValueError(f"histogram requires 'x' column; got {x!r}")
            ax.hist(df[x].dropna(), bins=fig_cfg.get("bins", 20), color=color)
            ax.set_xlabel(xlabel)
            ax.set_ylabel(ylabel)
        elif kind == "scatter":
            if not x or not y or x not in df.columns or y not in df.columns:
                raise ValueError(
                    f"scatter requires 'x' and 'y' columns; got x={x!r} y={y!r}"
                )
            ax.scatter(df[x], df[y], s=10, alpha=0.7, color=color)
            ax.set_xlabel(xlabel)
            ax.set_ylabel(ylabel)
        elif kind == "bar":
            if not x or not y or x not in df.columns or y not in df.columns:
                raise ValueError(
                    f"bar requires 'x' (group) and 'y' (value) columns; "
                    f"got x={x!r} y={y!r}"
                )
            grouped = df.groupby(x)[y].mean()
            ax.bar(grouped.index.astype(str), grouped.values, color=color)
            ax.set_xlabel(xlabel)
            ax.set_ylabel(f"mean({ylabel})")
            if len(grouped) > 6:
                plt.setp(ax.get_xticklabels(), rotation=30, ha="right")
        elif kind == "line":
            if not x or not y or x not in df.columns or y not in df.columns:
                raise ValueError(
                    f"line requires 'x' and 'y' columns; got x={x!r} y={y!r}"
                )
            ordered = df.sort_values(x)
            ax.plot(ordered[x], ordered[y], color=color, linewidth=1.2)
            ax.set_xlabel(xlabel)
            ax.set_ylabel(ylabel)
        else:
            raise ValueError(
                f"Unknown figure kind {kind!r}. Supported: bar, scatter, "
                "histogram, line. For anything fancier, see vaultlab.figures.recipes."
            )

        if title:
            ax.set_title(title)
        fig.tight_layout()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(out_path, dpi=200, bbox_inches="tight")
    finally:
        plt.close(fig)


# ---------------------------------------------------------------------------
# Provenance sidecars (AGENTS.md Red Line #2)
# ---------------------------------------------------------------------------


def _write_figure_sidecars(
    fig_path: Path,
    fig_cfg: dict[str, Any],
    df: "pd.DataFrame",
    inputs: list[Path],
    project_name: str,
) -> list[Path]:
    """Emit provenance + method-md sidecars for a single figure."""
    record = ProvenanceRecord(
        generated_by="vaultlab.analysis.run_pipeline",
        kind="figure",
        project=project_name,
        inputs=[str(p) for p in inputs],
        input_hashes=hash_inputs([str(p) for p in inputs]),
        params={k: v for k, v in fig_cfg.items() if k != "path"},
        notes=(
            f"Generated by vaultlab.analysis from a tidy result table "
            f"({df.shape[0]} rows × {df.shape[1]} columns)."
        ),
        tags=["analysis", "result-table", str(fig_cfg.get("kind", ""))],
    )
    try:
        json_path, method_path = write_receipts(fig_path, record)
        return [json_path, method_path]
    except Exception:  # noqa: BLE001 — receipts are best-effort
        logger.exception("Failed to write provenance for %s", fig_path)
        return []


def _write_methods_sidecars(
    methods_path: Path,
    inputs: list[Path],
    project_name: str,
    figure_entries: list[dict[str, Any]],
) -> list[Path]:
    record = ProvenanceRecord(
        generated_by="vaultlab.analysis.run_pipeline",
        kind="methods_section",
        project=project_name,
        inputs=[str(p) for p in inputs],
        input_hashes=hash_inputs([str(p) for p in inputs]),
        related_outputs=[str(e.get("path")) for e in figure_entries if e.get("path")],
        notes=(
            "Template-based draft methods paragraph composed by "
            "vaultlab.analysis.methods.compose_methods_paragraph. "
            "No LLM polish in this iteration."
        ),
        tags=["analysis", "methods-section", "template"],
    )
    try:
        json_path, method_path = write_receipts(methods_path, record)
        return [json_path, method_path]
    except Exception:  # noqa: BLE001 — receipts are best-effort
        logger.exception("Failed to write provenance for %s", methods_path)
        return []
