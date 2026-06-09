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
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from vaultlab.provenance import ProvenanceRecord, hash_inputs, write_receipts
from vaultlab.roles._guardrails import enforce_hedge
from vaultlab.runner.verifiers import verify_numeric

from .methods import compose_methods_paragraph
from .stats import compare_two_groups, summarize_dataframe

if TYPE_CHECKING:
    import pandas as pd

    from vaultlab.workflows.crosstalk import RunnerCallback

logger = logging.getLogger(__name__)

__all__ = [
    "AnalysisResult",
    "PreflightResult",
    "RAW_DATA_EXTENSIONS",
    "SPREADSHEET_EXTENSIONS",
    "TIDY_RESULT_EXTENSIONS",
    "run_pipeline",
    "state_aware_preflight",
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

SPREADSHEET_EXTENSIONS: frozenset[str] = frozenset({".xlsx", ".xls"})
"""Spreadsheet formats the pipeline REJECTS as un-tidied input.

Distinct from :data:`RAW_DATA_EXTENSIONS` so the error can tell the user to
TIDY the sheet (one header row, one observation per row) rather than re-run
instrument analysis. vaultlab consumes tidy CSV / Parquet / TSV only.
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
    mode: str = "fresh"
    audit_result: dict[str, Any] | None = None
    """Optional rigor_auditor verdict (``{"passed": bool, "issues": [...]}``)
    when ``run_pipeline(audit=True, audit_runner=...)``; ``None`` otherwise."""
    interpretation_warnings: list[str] = field(default_factory=list)
    """Guardrail flags raised on authored figure conclusions (hedge /
    numeric-consistency). Empty in normal operation; a non-empty list means a
    generated interpretation tripped :func:`enforce_hedge` or
    :func:`verify_numeric` — a regression in ``_interpret_bar_figure`` surfaced
    loudly rather than swallowed."""


@dataclass
class PreflightResult:
    """State-aware preflight outcome (CLAUDE.md commitment #6).

    Read BEFORE producing artifacts so a run can build on prior work rather
    than starting from zero. ``prior_figure_names`` are the stems of figure
    outputs already present (in the KB project ``Output/`` dir and/or the
    target ``out_dir``); ``message`` is the human log line to emit when an
    ``extend`` run detects prior work.
    """

    mode: str
    kb_root: Path | None = None
    prior_figure_names: set[str] = field(default_factory=set)
    prior_stats_summary: dict[str, Any] | None = None
    message: str | None = None


def _safe_resolve_kb_root(kb_root: Path | str | None) -> Path | None:
    """Resolve the KB root, returning ``None`` when unconfigured/unavailable.

    Never raises — KB context is optional and must not block a run.
    """
    try:
        from vaultlab.context import KbRootNotConfigured, resolve_kb_root

        try:
            if kb_root is not None:
                return resolve_kb_root(explicit=kb_root, interactive=False)
            return resolve_kb_root(interactive=False)
        except KbRootNotConfigured:
            return None
    except Exception:  # noqa: BLE001 — KB context is optional; never block a run
        return None


def state_aware_preflight(
    project_name: str,
    out_dir: Path | str,
    *,
    kb_root: Path | str | None = None,
    mode: str = "fresh",
) -> PreflightResult:
    """Glob prior runs so the pipeline respects existing state.

    Resolves the KB root (gracefully no-ops when unconfigured) and scans
    ``<kb>/<project_name>/Output/`` plus ``out_dir`` for prior figure PNGs
    and a prior ``stats_summary.json``. On ``mode="extend"`` with prior
    figures found, sets a ``"found N prior figures; extending"`` message.

    This is the first concrete implementation of CLAUDE.md commitment #6's
    ``state_aware_preflight`` contract; other artifact-producing primitives
    can reuse it.
    """
    resolved = _safe_resolve_kb_root(kb_root)

    scan_dirs: list[Path] = [Path(out_dir)]
    if resolved is not None:
        scan_dirs.append(resolved / project_name / "Output")

    prior_figs: set[str] = set()
    prior_stats: dict[str, Any] | None = None
    for d in scan_dirs:
        if not d.is_dir():
            continue
        for png in d.glob("*.png"):
            prior_figs.add(png.stem)
        if prior_stats is None:
            stats_json = d / "stats_summary.json"
            if stats_json.is_file():
                try:
                    prior_stats = json.loads(stats_json.read_text(encoding="utf-8"))
                except (json.JSONDecodeError, OSError):
                    prior_stats = None

    message: str | None = None
    if mode == "extend" and prior_figs:
        message = f"found {len(prior_figs)} prior figures; extending"

    return PreflightResult(
        mode=mode,
        kb_root=resolved,
        prior_figure_names=prior_figs,
        prior_stats_summary=prior_stats,
        message=message,
    )


# ---------------------------------------------------------------------------
# Public entrypoint
# ---------------------------------------------------------------------------


def run_pipeline(
    project_dir: Path | str,
    *,
    out_dir: Path | str | None = None,
    figures_config: dict[str, dict[str, Any]] | None = None,
    project_name: str | None = None,
    kb_root: Path | str | None = None,
    mode: Literal["fresh", "extend"] = "fresh",
    audit: bool = False,
    audit_runner: "RunnerCallback | None" = None,
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
    kb_root
        Optional KB root override for the state-aware preflight. Defaults to
        the resolved KB (or no-op when unconfigured).
    mode
        ``"fresh"`` (default) reproduces prior behavior. ``"extend"`` reads
        prior runs via :func:`state_aware_preflight` and does NOT overwrite
        identically-named figure outputs already present in ``out_dir``.
    audit
        Opt-in (default ``False``). When ``True``, runs a ``rigor_auditor``
        pass over the drafted ``methods.md`` and attaches the verdict to
        ``AnalysisResult.audit_result``. Requires ``audit_runner``; raises
        ``ValueError`` if ``True`` without one. The default path imports
        nothing from ``vaultlab.workflows``.
    audit_runner
        Callback that executes the audit meeting (``RunnerCallback`` from
        ``vaultlab.workflows.crosstalk``). Only used when ``audit=True``.

    Returns
    -------
    AnalysisResult
        Paths + summary dict for the artifacts that were produced.

    Raises
    ------
    ValueError
        If any file in ``project_dir`` has an extension in
        :data:`RAW_DATA_EXTENSIONS`. vaultlab is the layer ABOVE analysis;
        raw-data processing belongs in the user's analysis code. Also raised
        for spreadsheet inputs (:data:`SPREADSHEET_EXTENSIONS` — ``.xlsx`` /
        ``.xls``), with a message directing the user to tidy the sheet to CSV
        first rather than producing empty output.
    """
    project = Path(project_dir).resolve()
    if not project.is_dir():
        raise ValueError(f"project_dir does not exist or is not a directory: {project}")
    if project_name is None:
        project_name = project.name

    # ---- Output routing ----
    # Explicit out_dir wins. Otherwise route to the canonical KB location
    # (Output/<project>/runs/<date>/ via vaultlab.kb.paths) when a KB is
    # resolvable — a date-based run id so same-day re-runs share a dir (keeps
    # mode="extend" overwrite semantics intact). Fall back to <project>/out
    # only when no KB is configured.
    if out_dir is not None:
        out = Path(out_dir).resolve()
    else:
        kb_for_out = _safe_resolve_kb_root(kb_root)
        if kb_for_out is not None:
            from vaultlab.kb.paths import run_dir

            run_id = datetime.now().strftime("%Y-%m-%d")
            out = run_dir(kb_for_out, project_name, run_id=run_id).resolve()
        else:
            out = (project / "out").resolve()
    out.mkdir(parents=True, exist_ok=True)

    # ---- 0. State-aware preflight (CLAUDE.md commitment #6) ----
    preflight = state_aware_preflight(project_name, out, kb_root=kb_root, mode=mode)
    if preflight.message:
        logger.info(preflight.message)

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
    per_figure_interpretations: dict[str, str] = {}
    manifest_paths: list[Path] = []
    interpretation_warnings: list[str] = []

    for fig_name, fig_cfg in figures_config.items():
        # Containment: fig_name becomes an output filename. Reject anything
        # that could escape out_dir — a path separator, an absolute path, or a
        # `.`/`..` component. A shared or typo'd vaultlab-analysis.json must
        # never write PNGs/sidecars outside out_dir.
        if fig_name in ("", ".", "..") or Path(fig_name).name != fig_name:
            logger.warning("figure %r has an unsafe name — skipping", fig_name)
            continue
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
        kept_existing = mode == "extend" and fig_path.exists()
        if kept_existing:
            # Additive: keep the identically-named prior output, don't clobber.
            logger.info("extend: keeping existing figure %s", fig_path.name)
        else:
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
        interpretation = _interpret_bar_figure(df, fig_cfg)
        if interpretation:
            # Defense-in-depth: an authored conclusion must be hedged AND
            # numerically self-consistent. The template's own verification
            # lines always satisfy both, so a flag here means
            # _interpret_bar_figure regressed — surface it loudly (per the
            # global fail-loud rule); never silently drop the output.
            flags = enforce_hedge(interpretation) + verify_numeric(interpretation)
            if flags:
                logger.warning(
                    "figure %r interpretation tripped guardrails: %s",
                    fig_name,
                    "; ".join(flags),
                )
                interpretation_warnings.extend(f"{fig_name}: {f}" for f in flags)
            per_figure_interpretations[fig_name] = interpretation
        prior_provenance = fig_path.parent / f"{fig_path.name}.provenance.json"
        if kept_existing:
            # A kept figure was NOT re-rendered, so do not (re)write its
            # sidecars — that would stamp provenance newer than the PNG it
            # describes. Reuse the existing sidecars if present; if the
            # provenance sidecar is missing, mark the figure unverified (it
            # surfaces as "[sidecar: missing]" in methods.md) rather than
            # fabricating fresh provenance for an unrendered figure.
            existing_sidecars = [
                p
                for p in (prior_provenance, fig_path.parent / f"{fig_path.name}.method.md")
                if p.exists()
            ]
            entry["verified"] = prior_provenance.exists()
            manifest_paths.extend(existing_sidecars)
        else:
            sidecars = _write_figure_sidecars(
                fig_path, fig_cfg, df, inputs, project_name, interpretation
            )
            # Fail loud: a figure whose provenance sidecar failed to write is NOT
            # verified — mark it so methods.md flags it rather than asserting it.
            entry["verified"] = bool(sidecars)
            manifest_paths.extend(sidecars)
        figure_entries.append(entry)

    # ---- 5. Compose methods paragraph ----
    methods_md_path: Path | None = None
    methods_text: str | None = None
    if stats_summary:
        methods_text = compose_methods_paragraph(
            stats_summary,
            figure_entries=figure_entries,
            per_figure_interpretations=per_figure_interpretations,
            project_meta={"project_name": project_name},
        )
        methods_md_path = out / "methods.md"
        methods_md_path.write_text(methods_text, encoding="utf-8")
        manifest_paths.extend(
            _write_methods_sidecars(methods_md_path, inputs, project_name, figure_entries)
        )

    # ---- 5b. Optional rigor_auditor gate (opt-in; READ_FIRST ship-gate) ----
    audit_result: dict[str, Any] | None = None
    if audit:
        if audit_runner is None:
            raise ValueError(
                "run_pipeline(audit=True) requires audit_runner (a "
                "RunnerCallback that executes the audit meeting); none supplied."
            )
        if methods_md_path is not None and methods_text is not None:
            # Lazy import: keep vaultlab.workflows off the default path.
            from vaultlab.workflows.crosstalk import rigor_audit

            audit_result = rigor_audit(
                document=methods_text,
                document_path=str(methods_md_path),
                audit_kind="methods",
                producer_kind="template-only",
                runner_callback=audit_runner,
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
        mode=mode,
        audit_result=audit_result,
        interpretation_warnings=interpretation_warnings,
    )


# ---------------------------------------------------------------------------
# Scope discipline
# ---------------------------------------------------------------------------


def _scan_files(project: Path) -> list[Path]:
    """Return files to scan: the project top level (non-recursive) plus
    everything under ``inputs/`` and ``data/`` (recursive).

    The top-level scan stays shallow so raw data in an unrelated sibling
    folder (e.g. ``project/raw_backup/x.fastq``) is NOT false-flagged.
    Recursion is confined to the explicit ``inputs/`` and ``data/`` result
    directories, where nested tidy tables (e.g. ``data/panels/Fig4A.csv``)
    are legitimate inputs.
    """
    files: list[Path] = []
    for entry in sorted(project.iterdir()):
        if entry.is_file():
            files.append(entry)
    for sub in ("inputs", "data"):
        candidate = project / sub
        if candidate.is_dir():
            for entry in sorted(candidate.rglob("*")):
                if entry.is_file():
                    files.append(entry)
    return files


def _enforce_scope_discipline(project: Path) -> None:
    """Raise :class:`ValueError` if any raw-data file is present.

    Scans ``project_dir`` (top level only) plus the full tree under its
    ``inputs/`` and ``data/`` subdirectories. We do NOT recursively walk
    the entire project tree — that would false-flag any user project that
    happens to have raw data in a sibling folder.
    """
    offenders: list[Path] = []
    spreadsheets: list[Path] = []
    for entry in _scan_files(project):
        ext = _full_extension(entry).lower()
        if ext in RAW_DATA_EXTENSIONS:
            offenders.append(entry)
        elif ext in SPREADSHEET_EXTENSIONS:
            spreadsheets.append(entry)

    if offenders:
        names = ", ".join(str(p.relative_to(project)) for p in offenders[:5])
        more = f" (+{len(offenders) - 5} more)" if len(offenders) > 5 else ""
        raise ValueError(
            "vaultlab.analysis consumes POST-analysis tidy result tables "
            "(CSV / Parquet / TSV), not raw data. Found raw-data files in "
            f"{project}: {names}{more}. Run your analysis code first and pass "
            "the tidy results to run_pipeline()."
        )

    if spreadsheets:
        names = ", ".join(str(p.relative_to(project)) for p in spreadsheets[:5])
        more = f" (+{len(spreadsheets) - 5} more)" if len(spreadsheets) > 5 else ""
        raise ValueError(
            "vaultlab.analysis consumes tidy result tables (CSV / Parquet / "
            "TSV), not raw spreadsheets. Found spreadsheet file(s) in "
            f"{project}: {names}{more}. Convert to a tidy CSV first (one header "
            "row, one observation per row) — e.g. export the sheet, or use a "
            "conversion script — then re-run."
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
    """Find tidy result tables in the project top level (non-recursive) plus
    the full tree under ``inputs/`` and ``data/``."""
    found: list[Path] = []
    seen: set[Path] = set()
    for entry in _scan_files(project):
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


def _interpret_bar_figure(df: "pd.DataFrame", fig_cfg: dict[str, Any]) -> str | None:
    """Hedged, verification-only interpretation for a two-group bar figure.

    Recomputes a Welch's t-test (via ``stats.compare_two_groups``) on the
    already-tidy values and returns one hedged sentence. Returns ``None``
    when the figure is not a two-group bar with a numeric y and a categorical
    x — in that case no comparison is fabricated and only the structural
    description is emitted.

    Group selection: the two distinct x values when there are exactly two; if
    >2 groups, an explicit ``groups: [a, b]`` pair in ``fig_cfg`` is used,
    otherwise the test is omitted.
    """
    from pandas.api import types as pdtypes

    if fig_cfg.get("kind") != "bar":
        return None
    x = fig_cfg.get("x")
    y = fig_cfg.get("y")
    if not x or not y or x not in df.columns or y not in df.columns:
        return None
    if not pdtypes.is_numeric_dtype(df[y]):
        return None

    distinct = df[x].dropna().unique().tolist()
    cfg_groups = fig_cfg.get("groups")
    if isinstance(cfg_groups, (list, tuple)) and len(cfg_groups) == 2:
        # Config values arrive as JSON strings; map back to the column's real
        # dtype values so the comparison still works for categorical / numeric
        # group columns (a raw `in` test would mismatch those).
        by_str = {str(g): g for g in distinct}
        a_key, b_key = str(cfg_groups[0]), str(cfg_groups[1])
        if a_key not in by_str or b_key not in by_str:
            return None
        group_a, group_b = by_str[a_key], by_str[b_key]
    elif len(distinct) == 2:
        group_a, group_b = sorted(distinct, key=str)
    else:
        # 0/1/>2 groups with no explicit pair → no fabricated comparison.
        return None

    res = compare_two_groups(df, x, y, group_a, group_b)
    if res["n_a"] < 2 or res["n_b"] < 2:
        return None

    direction = res["direction"]
    if direction == "a>b":
        phrase = f"higher in `{group_a}` than `{group_b}`"
    elif direction == "a<b":
        phrase = f"lower in `{group_a}` than `{group_b}`"
    else:
        phrase = f"comparable between `{group_a}` and `{group_b}`"

    p = res["p_value"]
    p_str = f"{p:.3g}" if p is not None else "undefined"
    return (
        f"`{y}` appears {phrase}; recomputed Welch's t-test "
        f"n={res['n_a']}/{res['n_b']}, p={p_str} "
        f"(hedged, verification only — not upstream inference)."
    )


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
    interpretation: str | None = None,
) -> list[Path]:
    """Emit provenance + method-md sidecars for a single figure.

    When a hedged interpretation sentence is available (two-group bar
    figures), it becomes the sidecar's ``notes`` so the receipt carries the
    figure's finding; otherwise a fixed generation note is used.
    """
    notes = interpretation or (
        f"Generated by vaultlab.analysis from a tidy result table "
        f"({df.shape[0]} rows × {df.shape[1]} columns)."
    )
    record = ProvenanceRecord(
        generated_by="vaultlab.analysis.run_pipeline",
        kind="figure",
        project=project_name,
        inputs=[str(p) for p in inputs],
        input_hashes=hash_inputs([str(p) for p in inputs]),
        params={k: v for k, v in fig_cfg.items() if k != "path"},
        notes=notes,
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
        producer="template-only",
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
