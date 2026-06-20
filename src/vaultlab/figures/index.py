"""figure-index.json — cross-figure pattern recognition.

Closes Phase 3 of the figure-stack-and-orchestrators roadmap. Maintains
a per-project index of every figure (own + paper-extracted) the project
has touched, so we can answer *"this figure pairs with..."* queries.

Public surface:
    update_figure_index(kb_root, project_slug, figure_path, ...) -> dict
    find_figure_pairs(figure_path, kb_root, project_slug, *, top_n=3) -> list[dict]
    load_figure_index(kb_root, project_slug) -> list[dict]

Lineage:
    - Hover-to-see-quote citation UX adapted for figures: NotebookLM (Google)
    - Wiki-style cross-linking via [[wikilinks]]: Karpathy LLM Wiki + Obsidian
    - Pixel-signature similarity (cosine over color-motif vectors): scanpy
      clustering primitives + standard sklearn
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, cast

logger = logging.getLogger(__name__)

__all__ = [
    "FigureStage",
    "INDEX_FILENAME",
    "archive_superseded",
    "default_stage",
    "find_existing_for_claim",
    "find_figure_pairs",
    "get_figure_stage",
    "list_by_stage",
    "load_figure_index",
    "manuscript_figures",
    "set_figure_stage",
    "update_figure_index",
]


INDEX_FILENAME = "figure-index.json"
_DEFAULT_TOP_N = 3
_COLOR_BIN_SIZE = 32  # 8x8x8 = 512 bins
_DOMINANT_COLOR_TOP_K = 16  # keep top-16 dominant bins


class FigureStage(str, Enum):
    """Lifecycle state for a registered figure."""

    EXPLORATORY = "exploratory"
    CANDIDATE = "candidate"
    MANUSCRIPT = "manuscript"
    SUPPLEMENTARY = "supplementary"
    ARCHIVED = "archived"
    SUPERSEDED = "superseded"


def default_stage() -> FigureStage:
    """Default lifecycle stage for legacy entries without metadata."""
    return FigureStage.EXPLORATORY


def _hash_path(path: Path) -> str:
    """Stable hash of figure-path bytes for index lookup."""
    return hashlib.sha1(str(path.resolve()).encode("utf-8")).hexdigest()[:12]


def _compute_pixel_signature(image_path: Path) -> dict[str, Any]:
    """Cheap pixel signature: dominant-color bins + aspect + size.

    Returns a JSON-serializable dict ready to drop into the index.
    """
    try:
        import numpy as np
        from PIL import Image
    except ImportError:
        return {"error": "PIL/numpy not installed"}

    img = Image.open(image_path).convert("RGB")
    w, h = img.size
    arr = np.asarray(img).reshape(-1, 3)
    arr = arr[~np.all(arr >= 250, axis=1)]  # drop white background
    if len(arr) == 0:
        return {
            "size_px": [w, h],
            "aspect": w / h if h else 0.0,
            "dominant_bins": [],
            "n_pixels_non_bg": 0,
        }

    bins = (arr // _COLOR_BIN_SIZE).astype(int)
    bin_keys, bin_counts = np.unique(bins, axis=0, return_counts=True)
    sort_idx = np.argsort(-bin_counts)
    top_keys = bin_keys[sort_idx[:_DOMINANT_COLOR_TOP_K]].tolist()
    top_counts = bin_counts[sort_idx[:_DOMINANT_COLOR_TOP_K]].tolist()

    return {
        "size_px": [int(w), int(h)],
        "aspect": round(float(w / h) if h > 0 else 0.0, 3),
        "dominant_bins": top_keys,
        "dominant_bin_counts": [int(c) for c in top_counts],
        "n_pixels_non_bg": len(arr),
    }


def _index_path(kb_root: Path, project_slug: str) -> Path:
    return Path(kb_root) / project_slug / INDEX_FILENAME


def _as_entry_list(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [cast("dict[str, Any]", item) for item in value if isinstance(item, dict)]


def _write_figure_index(
    kb_root: Path | str,
    project_slug: str,
    entries: list[dict[str, Any]],
) -> None:
    """Atomically write a project's figure index."""
    path = _index_path(Path(kb_root), project_slug)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.write_text(json.dumps(entries, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def load_figure_index(
    kb_root: Path | str,
    project_slug: str,
) -> list[dict[str, Any]]:
    """Load the project's figure-index.json (or empty list if missing)."""
    path = _index_path(Path(kb_root), project_slug)
    if not path.exists():
        return []
    try:
        with path.open(encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return _as_entry_list(data)
        if isinstance(data, dict) and "entries" in data:
            return _as_entry_list(data["entries"])
        logger.warning("figure-index at %s has unknown shape; treating as empty", path)
        return []
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("figure-index at %s unreadable: %s", path, exc)
        return []


def _entry_stage(entry: dict[str, Any]) -> FigureStage:
    raw = entry.get("lifecycle_stage")
    if isinstance(raw, FigureStage):
        return raw
    if isinstance(raw, str):
        normalized = raw.strip().lower()
        for stage in FigureStage:
            if normalized in {stage.value, stage.name.lower()}:
                return stage
    return default_stage()


def _stage_history(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    history: list[dict[str, str]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        stage = item.get("stage")
        ts = item.get("ts")
        if stage is None or ts is None:
            continue
        history.append({"stage": str(stage), "ts": str(ts)})
    return history


def _figure_identifier_matches(entry: dict[str, Any], figure_id_or_path: Path | str) -> bool:
    identifier = str(figure_id_or_path)
    direct_fields = (
        "path_hash",
        "figure_path",
        "path",
        "figure_id",
        "id",
    )
    if any(str(entry.get(field)) == identifier for field in direct_fields if entry.get(field) is not None):
        return True

    metadata = entry.get("extra_metadata")
    if isinstance(metadata, dict):
        metadata_id = metadata.get("figure_id") or metadata.get("id")
        if metadata_id is not None and str(metadata_id) == identifier:
            return True

    entry_path = entry.get("figure_path") or entry.get("path")
    if not isinstance(entry_path, str):
        return False
    try:
        query_path = Path(figure_id_or_path).resolve()
    except (OSError, RuntimeError):
        return False
    try:
        indexed_path = Path(entry_path).resolve()
    except (OSError, RuntimeError):
        return False
    return indexed_path == query_path


def _claim_values(entry: dict[str, Any]) -> list[str]:
    values: list[str] = []
    for key in ("claims", "related_claims"):
        raw = entry.get(key)
        if isinstance(raw, list):
            values.extend(_claim_list_values(raw))

    metadata = entry.get("extra_metadata")
    if isinstance(metadata, dict):
        for key in ("claims", "related_claims"):
            raw = metadata.get(key)
            if isinstance(raw, list):
                values.extend(_claim_list_values(raw))
        for key in ("claim_id", "claim_text"):
            raw = metadata.get(key)
            if raw is not None:
                values.append(str(raw))

    metadata = entry.get("metadata")
    if isinstance(metadata, dict):
        for key in ("claims", "related_claims"):
            raw = metadata.get(key)
            if isinstance(raw, list):
                values.extend(_claim_list_values(raw))
        for key in ("claim_id", "claim_text"):
            raw = metadata.get(key)
            if raw is not None:
                values.append(str(raw))
    return values


def _claim_list_values(items: list[Any]) -> list[str]:
    values: list[str] = []
    for item in items:
        if isinstance(item, dict):
            for key in ("claim_id", "claim_text", "text", "id"):
                raw = item.get(key)
                if raw is not None:
                    values.append(str(raw))
        else:
            values.append(str(item))
    return values


def set_figure_stage(
    kb_root: Path | str,
    project_slug: str,
    *,
    figure_id_or_path: Path | str,
    stage: FigureStage,
    ts: str | None = None,
) -> bool:
    """Set a figure lifecycle stage and append a history event."""
    index = load_figure_index(kb_root, project_slug)
    timestamp = ts or datetime.now().isoformat(timespec="seconds")
    changed = False
    for entry in index:
        if not _figure_identifier_matches(entry, figure_id_or_path):
            continue
        entry["lifecycle_stage"] = stage.value
        entry.setdefault("superseded_by", None)
        history = _stage_history(entry.get("stage_history"))
        history.append({"stage": stage.value, "ts": timestamp})
        entry["stage_history"] = history
        changed = True
        break
    if changed:
        _write_figure_index(kb_root, project_slug, index)
    return changed


def get_figure_stage(
    kb_root: Path | str,
    project_slug: str,
    *,
    figure_id_or_path: Path | str,
) -> FigureStage | None:
    """Return a figure's lifecycle stage, defaulting legacy entries to exploratory."""
    for entry in load_figure_index(kb_root, project_slug):
        if _figure_identifier_matches(entry, figure_id_or_path):
            return _entry_stage(entry)
    return None


def list_by_stage(
    kb_root: Path | str,
    project_slug: str,
    stage: FigureStage,
) -> list[dict[str, Any]]:
    """List index entries at a lifecycle stage."""
    return [entry for entry in load_figure_index(kb_root, project_slug) if _entry_stage(entry) is stage]


def find_existing_for_claim(
    kb_root: Path | str,
    project_slug: str,
    *,
    claim_id: str | None = None,
    claim_text: str | None = None,
    include_archived: bool = False,
) -> list[dict[str, Any]]:
    """Find registered figures that already reference a manuscript claim."""
    if claim_id is None and claim_text is None:
        return []

    matches: list[dict[str, Any]] = []
    excluded = {FigureStage.ARCHIVED, FigureStage.SUPERSEDED}
    for entry in load_figure_index(kb_root, project_slug):
        if not include_archived and _entry_stage(entry) in excluded:
            continue
        claims = _claim_values(entry)
        claim_id_match = claim_id is not None and claim_id in claims
        claim_text_match = claim_text is not None and claim_text in claims
        if claim_id_match or claim_text_match:
            matches.append(entry)
    return matches


def archive_superseded(
    kb_root: Path | str,
    project_slug: str,
    *,
    figure_id_or_path: Path | str,
    superseded_by: str,
    ts: str | None = None,
) -> bool:
    """Mark a figure as superseded without moving or deleting its file."""
    index = load_figure_index(kb_root, project_slug)
    timestamp = ts or datetime.now().isoformat(timespec="seconds")
    changed = False
    for entry in index:
        if not _figure_identifier_matches(entry, figure_id_or_path):
            continue
        entry["lifecycle_stage"] = FigureStage.SUPERSEDED.value
        entry["superseded_by"] = superseded_by
        history = _stage_history(entry.get("stage_history"))
        history.append({"stage": FigureStage.SUPERSEDED.value, "ts": timestamp})
        entry["stage_history"] = history
        changed = True
        break
    if changed:
        _write_figure_index(kb_root, project_slug, index)
    return changed


def manuscript_figures(kb_root: Path | str, project_slug: str) -> list[dict[str, Any]]:
    """Return figures promoted to the manuscript stage."""
    return list_by_stage(kb_root, project_slug, FigureStage.MANUSCRIPT)


def update_figure_index(
    kb_root: Path | str,
    project_slug: str,
    figure_path: Path | str,
    *,
    source: str = "own",
    recipe_id: str | None = None,
    related_claims: list[str] | None = None,
    doi_or_data_source: str | None = None,
    extra_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Append (or refresh) an entry for ``figure_path`` in the project's
    figure-index.json.

    Each entry records:
        - path_hash (stable lookup key)
        - figure_path (absolute)
        - source ("own" / "paper")
        - recipe_id (if own; e.g. "marker_dot_plot")
        - pixel_signature (from _compute_pixel_signature)
        - related_claims (list of claim strings — from Tier-A summary refs)
        - doi_or_data_source
        - registered_at (ISO timestamp)
        - extra_metadata (free-form dict)

    Idempotent: a figure already in the index is updated in place
    (matches by ``path_hash``).

    Returns the new/updated entry.
    """
    fig = Path(figure_path).resolve()
    if not fig.exists():
        raise FileNotFoundError(f"figure not found: {fig}")

    path_hash = _hash_path(fig)
    entry = {
        "path_hash": path_hash,
        "figure_path": str(fig),
        "source": source,
        "recipe_id": recipe_id,
        "pixel_signature": _compute_pixel_signature(fig),
        "related_claims": related_claims or [],
        "doi_or_data_source": doi_or_data_source,
        "registered_at": datetime.now().isoformat(timespec="seconds"),
        "extra_metadata": extra_metadata or {},
    }

    index_path = _index_path(Path(kb_root), project_slug)
    index_path.parent.mkdir(parents=True, exist_ok=True)
    existing = load_figure_index(kb_root, project_slug)

    seen_hashes = {e.get("path_hash") for e in existing}
    if path_hash in seen_hashes:
        existing = [e if e.get("path_hash") != path_hash else entry for e in existing]
    else:
        existing.append(entry)

    with index_path.open("w", encoding="utf-8") as f:
        json.dump(existing, f, indent=2, ensure_ascii=False)
    return entry


def _signature_distance(sig_a: dict[str, Any], sig_b: dict[str, Any]) -> float:
    """Cosine distance over dominant-color-bin frequency vectors.

    Returns 0.0 (identical) → 1.0 (orthogonal). Returns 1.0 if either
    signature is empty.
    """
    raw_bins_a = sig_a.get("dominant_bins")
    raw_counts_a = sig_a.get("dominant_bin_counts")
    raw_bins_b = sig_b.get("dominant_bins")
    raw_counts_b = sig_b.get("dominant_bin_counts")
    bins_a = raw_bins_a if isinstance(raw_bins_a, list) else []
    counts_a = raw_counts_a if isinstance(raw_counts_a, list) else []
    bins_b = raw_bins_b if isinstance(raw_bins_b, list) else []
    counts_b = raw_counts_b if isinstance(raw_counts_b, list) else []

    if not bins_a or not bins_b:
        return 1.0

    # Build sparse vectors keyed by tuple(bin_key)
    def to_dict(bins: list[Any], counts: list[Any]) -> dict[tuple[Any, ...], float]:
        out: dict[tuple[Any, ...], float] = {}
        for k, c in zip(bins, counts, strict=False):
            out[tuple(k)] = float(c)
        return out

    da = to_dict(bins_a, counts_a)
    db = to_dict(bins_b, counts_b)
    keys = set(da) | set(db)
    if not keys:
        return 1.0

    # Cosine similarity
    dot: float = sum(da.get(k, 0.0) * db.get(k, 0.0) for k in keys)
    norm_a: float = sum(v * v for v in da.values()) ** 0.5
    norm_b: float = sum(v * v for v in db.values()) ** 0.5
    if norm_a == 0 or norm_b == 0:
        return 1.0
    sim: float = dot / (norm_a * norm_b)
    return 1.0 - max(0.0, min(1.0, sim))


def find_figure_pairs(
    figure_path: Path | str,
    kb_root: Path | str,
    project_slug: str,
    *,
    top_n: int = _DEFAULT_TOP_N,
    same_recipe_bonus: float = 0.10,
) -> list[dict[str, Any]]:
    """Find the top-N most similar figures in the project's index.

    Similarity = (1 - cosine_distance over dominant-color-bin vectors)
    plus a small bonus when both figures share the same ``recipe_id``.

    Returns a list of dicts: ``{entry, similarity, reasoning}``. The
    queried figure itself is excluded.
    """
    fig = Path(figure_path).resolve()
    if not fig.exists():
        raise FileNotFoundError(f"figure not found: {fig}")
    query_hash = _hash_path(fig)

    # Compute signature for query (don't require it to be in index already)
    query_sig = _compute_pixel_signature(fig)

    index = load_figure_index(kb_root, project_slug)
    if not index:
        return []

    # Find query's recipe_id if it's in the index
    query_entry = next((e for e in index if e.get("path_hash") == query_hash), None)
    query_recipe = (query_entry or {}).get("recipe_id")

    candidates: list[dict[str, Any]] = []
    for entry in index:
        if entry.get("path_hash") == query_hash:
            continue
        raw_sig = entry.get("pixel_signature")
        sig = raw_sig if isinstance(raw_sig, dict) else {}
        dist = _signature_distance(query_sig, sig)
        sim = 1.0 - dist
        bonus = 0.0
        recipe_match = False
        if query_recipe and entry.get("recipe_id") == query_recipe:
            bonus = same_recipe_bonus
            recipe_match = True
        adjusted_sim = min(1.0, sim + bonus)

        reasoning_bits = [f"pixel-signature similarity {sim:.2f}"]
        if recipe_match:
            reasoning_bits.append(f"both use {query_recipe} recipe")
        if entry.get("doi_or_data_source") and (query_entry or {}).get("doi_or_data_source"):
            if entry.get("doi_or_data_source") == (query_entry or {}).get("doi_or_data_source"):
                reasoning_bits.append("same source paper / dataset")

        candidates.append(
            {
                "entry": entry,
                "similarity": round(adjusted_sim, 3),
                "reasoning": "; ".join(reasoning_bits),
            }
        )

    candidates.sort(key=lambda c: -float(c["similarity"]))
    return candidates[:top_n]
