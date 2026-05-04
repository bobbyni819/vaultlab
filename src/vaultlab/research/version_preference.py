"""Preprint → published version preference.

Background
----------
When a paper exists as both a bioRxiv / medRxiv / arXiv preprint and
a peer-reviewed published version, CrossRef stores the preprint→published
relationship in the ``relation.is-preprint-of`` and
``relation.is-published-version-of`` fields. The picker today treats
the two DOIs as independent candidates, which has two failure modes:

1. **Coverage gap**: when only one version is acquired (typically the
   preprint, since bioRxiv is born-OA but Nature/Cell/Science are
   paywalled), the published version that the user *should* be citing
   stays Tier-C.
2. **Double-counting**: when both versions get into the corpus, the
   picker counts the same study twice, distorting OG-score and
   diversity calculations.

Concrete case (2026-05-01): Phillips et al. 2020 medRxiv preprint
(``10.1101/2020.12.06.20244913``) and the corresponding Phillips et al.
2024 *Nature Communications* published version are *both* relevant to
CODEX immunotherapy biomarker work. The 2026-05-01 CODEX additive run
acquired the preprint (Tier-A) but didn't pick up the published
version. The narrator wrote "Phillips et al. 2020 medRxiv preprint" in
the arc — accurate but the user almost always wants to cite the
published version when it exists.

Design
------
The module exposes three functions:

* :func:`find_preprint_published_pairs` — query CrossRef's relation
  metadata to discover preprint↔published pairs in a candidate set.
* :func:`prefer_published_version` — given pairs, mark the published
  version as canonical and the preprint as the fallback target. When
  the published has a PDF, it wins; when only the preprint has a PDF,
  we still cite the published DOI but read the preprint PDF as a
  proxy and add a provenance caveat.
* :func:`unify_preprint_published_in_corpus` — applies the preference
  in-place to a Corpus instance + the picker's candidate list.

The behavior is non-breaking for users without preprint↔published
pairs: when no relations are found, the corpus is unchanged.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Iterable

logger = logging.getLogger(__name__)


# Hostnames / DOI prefixes that indicate a preprint server.
_PREPRINT_DOI_PREFIXES = (
    "10.1101/",  # bioRxiv + medRxiv
    "10.48550/",  # arXiv (CrossRef-registered)
    "10.21203/",  # Research Square
    "10.31219/",  # OSF Preprints
    "10.31234/",  # PsyArXiv
)


@dataclass(frozen=True)
class PreprintPublishedPair:
    """A preprint↔published-version DOI pair.

    Attributes:
        preprint_doi: Lower-cased DOI of the preprint.
        published_doi: Lower-cased DOI of the published version.
        relation_source: Which CrossRef field contributed the relation
            (``is-preprint-of`` or ``is-published-version-of``).
            Useful for debugging.
    """

    preprint_doi: str
    published_doi: str
    relation_source: str = ""


def is_preprint_doi(doi: str) -> bool:
    """Return True if the DOI prefix matches a known preprint server."""
    if not doi:
        return False
    d = doi.strip().lower()
    return any(d.startswith(prefix) for prefix in _PREPRINT_DOI_PREFIXES)


def find_pairs_from_crossref_relations(
    *,
    candidates: Iterable[dict],
) -> list[PreprintPublishedPair]:
    """Find preprint↔published pairs from CrossRef ``relation`` metadata.

    The candidate dicts are expected to carry an optional ``relation``
    field in CrossRef's shape::

        relation = {
            "is-preprint-of": [{"id": "10.1038/...", "id-type": "doi"}],
            "has-preprint": [{"id": "10.1101/...", "id-type": "doi"}],
        }

    Args:
        candidates: Iterable of candidate dicts. Each must have a
            ``doi`` field; ``relation`` is optional.

    Returns:
        List of :class:`PreprintPublishedPair` objects, deduped by
        ``(preprint_doi, published_doi)``.
    """
    pairs: dict[tuple[str, str], PreprintPublishedPair] = {}

    for cand in candidates:
        doi = (cand.get("doi") or "").strip().lower()
        if not doi:
            continue
        relations = cand.get("relation") or {}
        if not isinstance(relations, dict):
            continue

        # is-preprint-of: this DOI is a preprint OF the listed published DOIs
        for rel in relations.get("is-preprint-of", []) or []:
            if not isinstance(rel, dict):
                continue
            other = (rel.get("id") or "").strip().lower()
            if not other or other == doi:
                continue
            pair = PreprintPublishedPair(
                preprint_doi=doi,
                published_doi=other,
                relation_source="is-preprint-of",
            )
            pairs[(doi, other)] = pair

        # has-preprint: this DOI is the PUBLISHED version of listed preprints
        for rel in relations.get("has-preprint", []) or []:
            if not isinstance(rel, dict):
                continue
            other = (rel.get("id") or "").strip().lower()
            if not other or other == doi:
                continue
            pair = PreprintPublishedPair(
                preprint_doi=other,
                published_doi=doi,
                relation_source="has-preprint",
            )
            pairs[(other, doi)] = pair

    return list(pairs.values())


@dataclass
class VersionPreferenceDecision:
    """Result of applying preprint→published preference to a pair.

    Attributes:
        canonical_doi: Which DOI to cite (always the published DOI
            when known).
        canonical_pdf_path: Path to the PDF the narrator should read.
            If the published version has a PDF, it's that one. If
            only the preprint PDF was acquired, this points to the
            preprint PDF as a *proxy* with a provenance caveat.
        fallback_doi: The other DOI in the pair (i.e., the one NOT
            chosen as canonical).
        proxy_caveat: Non-empty string when the canonical DOI's PDF
            wasn't acquired and the preprint PDF is being substituted.
    """

    canonical_doi: str
    canonical_pdf_path: str
    fallback_doi: str
    proxy_caveat: str = ""


def decide_version_preference(
    *,
    pair: PreprintPublishedPair,
    pdf_paths: dict[str, str],
) -> VersionPreferenceDecision:
    """Apply preprint→published preference to a single pair.

    Logic:
    * If both DOIs have PDFs: canonical = published, read its PDF.
    * If only published has a PDF: canonical = published, read its PDF.
    * If only preprint has a PDF: canonical = published (still — that's
      what the user wants to cite), read the preprint PDF as a proxy
      with a provenance caveat.
    * If neither has a PDF: canonical = published, no PDF available
      (will fall through to Tier-B abstract summarization on whichever
      version has a usable abstract).

    Args:
        pair: The preprint↔published pair.
        pdf_paths: Mapping of DOI → local PDF path for papers that
            have been successfully acquired. Missing DOIs aren't in
            the mapping.

    Returns:
        A :class:`VersionPreferenceDecision`.
    """
    has_published_pdf = pair.published_doi in pdf_paths
    has_preprint_pdf = pair.preprint_doi in pdf_paths

    if has_published_pdf:
        return VersionPreferenceDecision(
            canonical_doi=pair.published_doi,
            canonical_pdf_path=pdf_paths[pair.published_doi],
            fallback_doi=pair.preprint_doi,
        )
    if has_preprint_pdf:
        return VersionPreferenceDecision(
            canonical_doi=pair.published_doi,
            canonical_pdf_path=pdf_paths[pair.preprint_doi],
            fallback_doi=pair.preprint_doi,
            proxy_caveat=(
                f"PDF not acquired for the published version "
                f"({pair.published_doi}); reading the preprint PDF "
                f"({pair.preprint_doi}) as a proxy. Specific numbers, "
                f"figures, or analyses may differ between the preprint "
                f"and final published version. Verify against the "
                f"published version when relying on quantitative claims."
            ),
        )
    return VersionPreferenceDecision(
        canonical_doi=pair.published_doi,
        canonical_pdf_path="",
        fallback_doi=pair.preprint_doi,
    )


def filter_duplicates_from_picks(
    *,
    picks: list[dict],
    pairs: Iterable[PreprintPublishedPair],
) -> list[dict]:
    """Drop preprint entries from picks when the published version is also picked.

    Args:
        picks: Picker output (list of dicts with ``doi``).
        pairs: Known preprint↔published pairs.

    Returns:
        Filtered picks: when both versions appear, the preprint is
        removed in favor of the published version.
    """
    pair_lookup: dict[str, str] = {}  # preprint_doi → published_doi
    for pair in pairs:
        pair_lookup[pair.preprint_doi] = pair.published_doi

    picked_dois = {(p.get("doi") or "").lower() for p in picks}

    out: list[dict] = []
    for entry in picks:
        doi = (entry.get("doi") or "").lower()
        # If this is a preprint AND its published version is also in picks, drop it.
        if doi in pair_lookup and pair_lookup[doi] in picked_dois:
            logger.info(
                "dropping preprint %s in favor of published version %s",
                doi, pair_lookup[doi],
            )
            continue
        out.append(entry)

    # Re-rank.
    for i, entry in enumerate(out, start=1):
        entry["rank"] = i
    return out


__all__ = [
    "PreprintPublishedPair",
    "VersionPreferenceDecision",
    "decide_version_preference",
    "filter_duplicates_from_picks",
    "find_pairs_from_crossref_relations",
    "is_preprint_doi",
]
