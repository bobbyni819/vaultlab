"""Audit Tier-A summaries for empty / placeholder TL;DR content.

Background
----------
The picker tags a paper as Tier-A based on PDF availability and
ranking criteria. But several Tier-A summaries in the cumulative
``Wiki/Summaries/`` corpus have empty or placeholder TL;DR content
because the read step never completed (LLM call timed out, output
parsing failed, or the summary was generated before the current
schema was finalized). The narrator then includes these papers in
the arc but has nothing substantive to say about them — Bobby's
2026-05-01 review of the strict-style CODEX arc surfaced this as
an unresolved corpus-quality issue.

This module provides the audit. It does NOT re-read PDFs (that's the
narrator's / orchestrator's responsibility); it just identifies which
summaries need attention.

Public API
----------
* :func:`audit_summaries` — scan a list of summary files and classify
  each as ``ok`` / ``empty_tldr`` / ``unreadable``.
* :func:`recoverable_paths` — partition empty-TL;DR results into
  those that have cached PDFs (recoverable via re-read) vs. those
  that don't (require re-acquisition).

Heuristics
----------
A TL;DR is considered "empty" when:

* Missing entirely (no ``## TL;DR`` heading)
* Contains only ``_(empty)_``, ``_(none)_``, ``_(not extracted)_``,
  ``_No full-text PDF available;...`` or similar Tier-C placeholder
* Body text under the heading is ≤ ``MIN_TLDR_CHARS`` after stripping
  whitespace (default 50 chars — anything shorter is almost certainly
  a stub)

These are conservative — false positives (real but very short TL;DRs)
are preferable to false negatives because re-reading a PDF is cheap
relative to letting a thin summary into the narrator's prompt.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Iterable

import yaml

from vaultlab.kb.paths import slugify_doi


MIN_TLDR_CHARS = 50
"""Below this length, a TL;DR is considered too thin to support an
arc citation. 50 chars is roughly one short sentence."""


# Tier-C placeholder strings the corpus emits for unread papers.
# A TL;DR that consists only of these is treated as empty.
_PLACEHOLDER_PATTERNS = [
    r"_\(empty\)_",
    r"_\(none\)_",
    r"_\(not extracted\)_",
    r"_No full-text PDF available;",
    r"^_+\s*$",
]


class TLDRStatus(str, Enum):
    """Classification of a summary file's TL;DR section."""

    OK = "ok"  # Substantive TL;DR present
    EMPTY_TLDR = "empty_tldr"  # Tier-A flagged but TL;DR is missing/placeholder/short
    UNREADABLE = "unreadable"  # File can't be parsed (broken YAML, etc.)


@dataclass(frozen=True)
class AuditResult:
    """Outcome of auditing one summary file.

    Attributes:
        path: Path to the summary file.
        doi: DOI extracted from frontmatter (lower-cased).
        tier: Tier letter from frontmatter (``"A"``, ``"B"``, or ``"C"``).
        status: :class:`TLDRStatus` classification.
        tldr_length: Character count of the body text under the
            ``## TL;DR`` heading, or 0 if the heading is missing.
        reason: Short human-readable diagnostic.
    """

    path: Path
    doi: str
    tier: str
    status: TLDRStatus
    tldr_length: int
    reason: str


@dataclass
class AuditSummary:
    """Aggregated results from auditing many summary files.

    Attributes:
        ok: Files classified as having substantive TL;DRs.
        empty_tldr_tier_a: Tier-A files with empty/placeholder TL;DRs
            (the actionable category).
        empty_tldr_tier_b: Tier-B files with empty TL;DRs (less
            actionable since Tier-B is abstract-derived).
        unreadable: Files that couldn't be parsed.
        total: Total files audited.
    """

    ok: list[AuditResult] = field(default_factory=list)
    empty_tldr_tier_a: list[AuditResult] = field(default_factory=list)
    empty_tldr_tier_b: list[AuditResult] = field(default_factory=list)
    unreadable: list[AuditResult] = field(default_factory=list)
    total: int = 0


# ---------------------------------------------------------------------------
# Per-file classifier
# ---------------------------------------------------------------------------


def classify_summary(path: Path) -> AuditResult:
    """Classify one summary file's TL;DR status.

    Args:
        path: Path to a ``Wiki/Summaries/<doi-slug>.md`` file.

    Returns:
        :class:`AuditResult` with the file's classification.
    """
    if not path.is_file():
        return AuditResult(
            path=path, doi="", tier="", status=TLDRStatus.UNREADABLE,
            tldr_length=0, reason="file does not exist",
        )

    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return AuditResult(
            path=path, doi="", tier="", status=TLDRStatus.UNREADABLE,
            tldr_length=0, reason=f"read error: {exc}",
        )

    if not text.startswith("---"):
        return AuditResult(
            path=path, doi="", tier="", status=TLDRStatus.UNREADABLE,
            tldr_length=0, reason="missing YAML frontmatter",
        )

    try:
        _, fm_text, body = text.split("---", 2)
        fm = yaml.safe_load(fm_text) or {}
    except (ValueError, yaml.YAMLError) as exc:
        return AuditResult(
            path=path, doi="", tier="", status=TLDRStatus.UNREADABLE,
            tldr_length=0, reason=f"frontmatter parse error: {exc}",
        )

    doi = str(fm.get("doi", "")).strip().lower()
    tier = str(fm.get("tier", "")).strip().upper()

    # Find the TL;DR section body.
    match = re.search(
        r"^##\s+TL;DR\s*\n+(?P<body>.+?)(?=\n##\s+|\Z)",
        body,
        re.MULTILINE | re.DOTALL,
    )
    if match is None:
        return AuditResult(
            path=path, doi=doi, tier=tier,
            status=TLDRStatus.EMPTY_TLDR, tldr_length=0,
            reason="no '## TL;DR' heading",
        )

    tldr_body = match.group("body").strip()

    # Check placeholder patterns.
    for pattern in _PLACEHOLDER_PATTERNS:
        if re.search(pattern, tldr_body, re.MULTILINE):
            return AuditResult(
                path=path, doi=doi, tier=tier,
                status=TLDRStatus.EMPTY_TLDR, tldr_length=len(tldr_body),
                reason="TL;DR contains only Tier-C placeholder text",
            )

    # Length check.
    if len(tldr_body) < MIN_TLDR_CHARS:
        return AuditResult(
            path=path, doi=doi, tier=tier,
            status=TLDRStatus.EMPTY_TLDR, tldr_length=len(tldr_body),
            reason=f"TL;DR shorter than {MIN_TLDR_CHARS} chars (got {len(tldr_body)})",
        )

    return AuditResult(
        path=path, doi=doi, tier=tier,
        status=TLDRStatus.OK, tldr_length=len(tldr_body),
        reason="ok",
    )


# ---------------------------------------------------------------------------
# Multi-file aggregator
# ---------------------------------------------------------------------------


def audit_summaries(paths: Iterable[Path]) -> AuditSummary:
    """Audit a collection of summary files.

    Args:
        paths: Iterable of paths to summary markdown files.

    Returns:
        :class:`AuditSummary` with results bucketed by status + tier.
    """
    summary = AuditSummary()
    for path in paths:
        summary.total += 1
        result = classify_summary(path)
        if result.status == TLDRStatus.OK:
            summary.ok.append(result)
        elif result.status == TLDRStatus.EMPTY_TLDR:
            if result.tier == "A":
                summary.empty_tldr_tier_a.append(result)
            elif result.tier == "B":
                summary.empty_tldr_tier_b.append(result)
            else:
                # Tier-C empty TL;DR is expected; don't flag.
                summary.ok.append(result)
        else:  # UNREADABLE
            summary.unreadable.append(result)
    return summary


# ---------------------------------------------------------------------------
# Recoverability split
# ---------------------------------------------------------------------------


def recoverable_paths(
    *,
    audit_results: Iterable[AuditResult],
    pdf_cache_dir: Path,
) -> tuple[list[AuditResult], list[AuditResult]]:
    """Partition empty-TL;DR results into recoverable vs. unrecoverable.

    A summary is *recoverable* when its corresponding PDF is cached on
    disk — the orchestrator can re-read it via the standard reader
    callback without re-running PDF acquisition. Unrecoverable
    summaries need the acquisition waterfall to fetch the PDF first.

    Args:
        audit_results: Results from :func:`audit_summaries` (typically
            the ``empty_tldr_tier_a`` list).
        pdf_cache_dir: Path to ``Sources/Papers/`` (where PDFs cache).

    Returns:
        ``(recoverable, unrecoverable)`` tuple. Each is a list of
        :class:`AuditResult` instances.
    """
    recoverable: list[AuditResult] = []
    unrecoverable: list[AuditResult] = []

    for result in audit_results:
        if not result.doi:
            unrecoverable.append(result)
            continue
        pdf_path = pdf_cache_dir / f"{slugify_doi(result.doi)}.pdf"
        if pdf_path.is_file() and pdf_path.stat().st_size > 0:
            recoverable.append(result)
        else:
            unrecoverable.append(result)

    return recoverable, unrecoverable


__all__ = [
    "AuditResult",
    "AuditSummary",
    "MIN_TLDR_CHARS",
    "TLDRStatus",
    "audit_summaries",
    "classify_summary",
    "recoverable_paths",
]
