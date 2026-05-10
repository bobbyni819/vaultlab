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
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

__all__ = [
    "INDEX_FILENAME",
    "find_figure_pairs",
    "load_figure_index",
    "update_figure_index",
]


INDEX_FILENAME = "figure-index.json"
_DEFAULT_TOP_N = 3
_COLOR_BIN_SIZE = 32  # 8x8x8 = 512 bins
_DOMINANT_COLOR_TOP_K = 16  # keep top-16 dominant bins


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
            return data
        if isinstance(data, dict) and "entries" in data:
            return data["entries"]
        logger.warning("figure-index at %s has unknown shape; treating as empty", path)
        return []
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("figure-index at %s unreadable: %s", path, exc)
        return []


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
    bins_a = sig_a.get("dominant_bins") or []
    counts_a = sig_a.get("dominant_bin_counts") or []
    bins_b = sig_b.get("dominant_bins") or []
    counts_b = sig_b.get("dominant_bin_counts") or []

    if not bins_a or not bins_b:
        return 1.0

    # Build sparse vectors keyed by tuple(bin_key)
    def to_dict(bins, counts):
        out = {}
        for k, c in zip(bins, counts, strict=False):
            out[tuple(k)] = float(c)
        return out

    da = to_dict(bins_a, counts_a)
    db = to_dict(bins_b, counts_b)
    keys = set(da) | set(db)
    if not keys:
        return 1.0

    # Cosine similarity
    dot = sum(da.get(k, 0.0) * db.get(k, 0.0) for k in keys)
    norm_a = sum(v * v for v in da.values()) ** 0.5
    norm_b = sum(v * v for v in db.values()) ** 0.5
    if norm_a == 0 or norm_b == 0:
        return 1.0
    sim = dot / (norm_a * norm_b)
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

    candidates = []
    for entry in index:
        if entry.get("path_hash") == query_hash:
            continue
        sig = entry.get("pixel_signature") or {}
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

    candidates.sort(key=lambda c: -c["similarity"])
    return candidates[:top_n]
