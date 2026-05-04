"""User-specified required-papers list ("always-include" flag).

Background
----------
The picker ranks candidates by composite score (OG-score + abstract +
seed-status + recency). Score-based ranking is right for most
candidates, but every user has *required citations* — foundational
papers their lab/field always cites — that should bypass ranking
entirely.

Concrete case (2026-05-01): Bobby's lab at Duke (Hickey lab) cites
Black, Phillips, **Hickey** et al. 2021 *Nature Protocols* on every
CODEX paper they publish. The 2026-05-01 CODEX additive run scored
Black 2021 below the top-30 cutoff (Tier-C, paywalled, lower
recency weight) so it dropped out of the picks. A user must be able
to say "always include this DOI no matter the score."

Design
------
Two orthogonal behaviors, both controlled by a list of required DOIs:

1. **Picker bypass**: required DOIs are force-pinned to rank 1, 2, 3...
   in :func:`tier-a-picks` regardless of composite score. The picker
   still runs scoring on non-required candidates; the required ones
   just jump to the top.

2. **Acquisition retry escalation**: required DOIs that fail the
   normal OA waterfall get retried at ``depth=complete`` (paywall-
   tier) automatically, without needing the user to set
   ``--depth=complete`` for everything. This is the right default —
   if the user said "I require this," they're indicating the paper
   is high-value enough to spend extra acquisition effort.

3. **Tier-B fallback**: if ``depth=complete`` still can't get the PDF
   (e.g., the paper is genuinely paywalled at a publisher without an
   institutional license), the orchestrator emits a Tier-B summary
   from the abstract instead of letting the paper drop to Tier-C. A
   required paper should never be invisible to the narrator.

Usage
-----
::

    /lit-arc "CODEX multiplexed imaging" \\
        --always-include 10.1038/s41596-021-00556-8 \\
        --always-include 10.1016/j.cell.2018.07.010

The list is also persisted in ``.vaultlab-project.json`` so it
applies to future runs in the same project.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RequiredPaperSpec:
    """A user-required paper specification.

    Attributes:
        doi: Lower-cased DOI.
        rationale: Free-form note (optional). Persisted in the
            project config for documentation.
    """

    doi: str
    rationale: str = ""


def normalize_dois(dois: Iterable[str]) -> list[str]:
    """Normalize a list of DOI strings: lowercase, strip whitespace,
    drop common prefixes like ``doi:`` and ``https://doi.org/``.

    Args:
        dois: Iterable of raw DOI strings.

    Returns:
        Deduplicated, normalized list (preserves first-occurrence order).
    """
    out: list[str] = []
    seen: set[str] = set()
    for raw in dois:
        if not raw:
            continue
        d = raw.strip().lower()
        # Strip common prefixes
        for prefix in ("https://doi.org/", "http://doi.org/", "doi:"):
            if d.startswith(prefix):
                d = d[len(prefix):]
        d = d.strip("/")
        if not d or d in seen:
            continue
        seen.add(d)
        out.append(d)
    return out


def apply_required_to_picks(
    *,
    picks: list[dict],
    required_dois: Iterable[str],
    candidate_pool: dict[str, dict] | None = None,
) -> list[dict]:
    """Re-rank picks so required DOIs sit at the top.

    Args:
        picks: The picker's top-N output, list of dicts with at minimum
            ``doi`` and ``rank`` keys.
        required_dois: DOIs that must appear at the top, regardless
            of original rank.
        candidate_pool: Optional dict ``{doi -> candidate metadata}`` —
            if a required DOI isn't in ``picks`` but IS in the
            candidate pool, we synthesize a pick entry for it. When
            None, required DOIs not in ``picks`` are silently dropped
            (the caller should handle this case explicitly).

    Returns:
        New picks list with required DOIs at ranks 1..N_required and
        non-required picks following at ranks N_required+1..end.
        Original ``rank`` keys are rewritten to reflect the new order.
    """
    required_normalized = set(normalize_dois(required_dois))
    if not required_normalized:
        return picks

    # Index existing picks by DOI for fast lookup.
    by_doi = {(p.get("doi") or "").lower(): p for p in picks}

    # Build the required-first prefix.
    required_picks: list[dict] = []
    for req_doi in required_normalized:
        if req_doi in by_doi:
            entry = dict(by_doi[req_doi])
            entry["required"] = True
            required_picks.append(entry)
        elif candidate_pool is not None and req_doi in candidate_pool:
            cand = candidate_pool[req_doi]
            synth = {
                "doi": req_doi,
                "rank": 0,  # rewritten below
                "rationale": (
                    "User-specified required paper "
                    "(forced into picks via --always-include)"
                ),
                "title": cand.get("title", ""),
                "year": cand.get("year", 0),
                "og_score": cand.get("og_score", 0.0),
                "forward_influence": cand.get("forward_influence", 0),
                "has_pdf": cand.get("has_pdf", False),
                "has_real_abstract": cand.get("has_real_abstract", False),
                "is_seed": cand.get("is_seed", False),
                "composite_score": float("inf"),
                "required": True,
            }
            required_picks.append(synth)
        else:
            logger.warning(
                "required DOI %s not in picks or candidate pool; "
                "the lit-arc orchestrator should attempt independent "
                "acquisition + Tier-B fallback for this DOI.",
                req_doi,
            )

    # Append non-required picks in original order.
    non_required_picks = [
        p for p in picks
        if (p.get("doi") or "").lower() not in required_normalized
    ]

    merged = required_picks + non_required_picks

    # Rewrite ranks.
    for i, entry in enumerate(merged, start=1):
        entry["rank"] = i

    return merged


def load_required_dois_from_project_config(
    *,
    project_dir: Path,
) -> list[str]:
    """Load required DOIs from a project's ``.vaultlab-project.json``.

    Returns:
        List of normalized DOIs from the ``always_include`` field of
        the project config. Empty list if no config file or no
        ``always_include`` field is present.
    """
    config_path = project_dir / ".vaultlab-project.json"
    if not config_path.is_file():
        return []
    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        logger.warning("could not parse %s — ignoring required-papers list", config_path)
        return []
    raw = data.get("always_include", [])
    if not isinstance(raw, list):
        return []
    return normalize_dois(raw)


def save_required_dois_to_project_config(
    *,
    project_dir: Path,
    required_dois: Iterable[str],
) -> None:
    """Persist required DOIs into a project's ``.vaultlab-project.json``.

    Loads the existing config (if any), updates the ``always_include``
    field, and writes back. Idempotent — running with the same list
    is a no-op.

    Args:
        project_dir: The project root containing ``.vaultlab-project.json``.
        required_dois: DOIs to persist. Will be normalized + deduped.
    """
    config_path = project_dir / ".vaultlab-project.json"
    if config_path.is_file():
        try:
            data = json.loads(config_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            data = {}
    else:
        data = {}
    data["always_include"] = normalize_dois(required_dois)
    project_dir.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        json.dumps(data, indent=2) + "\n",
        encoding="utf-8",
    )


__all__ = [
    "RequiredPaperSpec",
    "apply_required_to_picks",
    "load_required_dois_from_project_config",
    "normalize_dois",
    "save_required_dois_to_project_config",
]
