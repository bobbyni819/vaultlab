"""Skip-on-policy-refusal pattern for vaultlab batch processing.

Background
----------

During the 2026-05-01 multiscale-tissue-simulation lit-arc run, five
subagents in a row hit Anthropic Usage Policy refusals when asked to
summarize host-pathogen / infection-themed batches. The error text
was generic ("appears to violate our Usage Policy") with no specific
clause cited. Bobby's PhD work is legitimate biomedical research —
the filter is a false-positive triggered on cumulative pathogen-keyword
density.

Mitigation pattern (this module): when a paper triggers a policy
refusal, mark it as ``tier: skipped_policy`` in the per-paper summary
file frontmatter, append the DOI to a project-level
``policy_skipped.json`` log, and continue processing. The user can
later run ``vaultlab list-policy-skipped`` to get a human-review
report of refused papers.

This is parallel to the ``failed_paywalled`` mitigation: in both
cases the paper isn't lost — it's flagged for the user with a clear
reason and an actionable next step.

Detection
---------

The Anthropic API returns refusals as one of:

* ``API Error: ... Usage Policy ...`` — direct CC of the AUP refusal
* ``API Error: ... Internal server error`` — sometimes manifests as a
  500 after the model has refused
* The agent's response text containing certain phrases

Use :func:`is_policy_refusal_error` on a raw error string to detect.

Reference: ``claude-config/Sources/Notes/policy-refusal-on-host-
pathogen-batch-2026-05-02.md`` for the original incident debug log.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


_POLICY_REFUSAL_SIGNALS = (
    "violate our usage policy",
    "anthropic.com/legal/aup",
    "claude code is unable to respond",
    "policy refusal",
)


def is_policy_refusal_error(error_text: str | None) -> bool:
    """Return True if ``error_text`` looks like an Anthropic AUP refusal.

    The error message is matched case-insensitively against a list of
    known refusal signals. Internal-server-error 500s are NOT matched —
    those have many causes other than policy.
    """
    if not error_text:
        return False
    s = str(error_text).lower()
    return any(signal in s for signal in _POLICY_REFUSAL_SIGNALS)


def mark_skipped(
    doi: str,
    *,
    project_dir: Path,
    reason: str = "Anthropic Usage Policy refusal",
    batch: str | None = None,
    notes: str = "",
    summaries_dir: Path | None = None,
    error_text: str | None = None,
) -> Path:
    """Record a policy-skipped paper.

    Two artifacts are written:

    1. ``<project_dir>/policy_skipped.json`` — append-only log; one
       entry per skip with ``{doi, reason, batch, skipped_at,
       error_text, notes}``.
    2. ``<summaries_dir>/<doi-slug>.md`` — minimal stub with
       ``tier: skipped_policy`` frontmatter + a TL;DR pointing the user
       to the human-review queue. Only written when ``summaries_dir``
       is provided AND no existing summary exists at that path.

    Args:
        doi: The skipped paper's DOI.
        project_dir: Project workspace (where ``policy_skipped.json``
            lives).
        reason: Short reason string (e.g. "Anthropic Usage Policy
            refusal" or "manual skip — duplicate work").
        batch: Optional batch-id label (e.g. "B5-host-pathogen-bridge").
        notes: Free-text notes for human review (e.g. "second attempt
            crashed at synthesis stage; foreground-process top 5
            instead").
        summaries_dir: When provided, also write the stub summary file.
        error_text: Optional original error message for the log.

    Returns:
        Path to the updated ``policy_skipped.json`` file.
    """
    project_dir = Path(project_dir)
    project_dir.mkdir(parents=True, exist_ok=True)
    log_path = project_dir / "policy_skipped.json"

    entries: list[dict[str, Any]] = []
    if log_path.exists():
        try:
            entries = json.loads(log_path.read_text(encoding="utf-8")) or []
            if not isinstance(entries, list):
                entries = []
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Could not read existing policy_skipped.json: %s", exc)
            entries = []

    # Skip duplicate DOIs (additive — keep first record)
    doi_lower = doi.strip().lower()
    if any((e.get("doi") or "").lower() == doi_lower for e in entries):
        logger.info("DOI %s already in policy_skipped.json — leaving as-is", doi_lower)
    else:
        entries.append({
            "doi": doi_lower,
            "reason": reason,
            "batch": batch,
            "skipped_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "error_text": (error_text or "")[:500],  # truncate long stack traces
            "notes": notes,
            "needs_human_review": True,
        })

    log_path.write_text(json.dumps(entries, indent=2), encoding="utf-8")

    # Optionally write the stub summary
    if summaries_dir is not None:
        summaries_dir = Path(summaries_dir)
        summaries_dir.mkdir(parents=True, exist_ok=True)
        slug = doi_lower.replace("/", "_")
        stub_path = summaries_dir / f"{slug}.md"
        if not stub_path.exists():
            stub_path.write_text(
                _stub_template(
                    doi=doi_lower,
                    reason=reason,
                    batch=batch,
                    notes=notes,
                ),
                encoding="utf-8",
            )

    return log_path


def list_skipped(project_dir: Path) -> list[dict[str, Any]]:
    """Return the list of policy-skipped papers for a project.

    Args:
        project_dir: Project workspace (where ``policy_skipped.json``
            lives).

    Returns:
        List of skip-records (newest first). Empty when no skips.
    """
    log_path = Path(project_dir) / "policy_skipped.json"
    if not log_path.exists():
        return []
    try:
        entries = json.loads(log_path.read_text(encoding="utf-8")) or []
    except (json.JSONDecodeError, OSError):
        return []
    if not isinstance(entries, list):
        return []
    # Sort newest-first for human review
    entries.sort(key=lambda e: e.get("skipped_at", ""), reverse=True)
    return entries


def is_skipped(doi: str, project_dir: Path) -> bool:
    """True if ``doi`` is in the project's policy_skipped log."""
    doi_lower = (doi or "").strip().lower()
    if not doi_lower:
        return False
    return any(
        (e.get("doi") or "").lower() == doi_lower
        for e in list_skipped(project_dir)
    )


def _stub_template(
    *, doi: str, reason: str, batch: str | None, notes: str,
) -> str:
    """Render the minimal stub summary file for a skipped paper."""
    batch_line = f"\nbatch: {batch}" if batch else ""
    notes_line = f"\n\n## Notes\n\n{notes}\n" if notes else "\n"
    return (
        f"---\n"
        f"doi: {doi}\n"
        f"tier: skipped_policy\n"
        f"reason: {reason!r}{batch_line}\n"
        f"extracted_at: '{datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}'\n"
        f"needs_human_review: true\n"
        f"---\n"
        f"\n"
        f"## TL;DR\n"
        f"\n"
        f"This paper was skipped during automated processing due to a\n"
        f"policy-class error from the LLM. The skip is recorded in\n"
        f"``<project>/policy_skipped.json`` and surfaces in\n"
        f"``vaultlab list-policy-skipped`` for human review.\n"
        f"\n"
        f"**Recommended action**: read the paper manually, OR retry\n"
        f"the summary in a fresh foreground session, OR exclude it from\n"
        f"the arc if it's low-priority.\n"
        f"{notes_line}"
        f"## Why this happens\n"
        f"\n"
        f"Per ``claude-config/Sources/Notes/policy-refusal-on-host-\n"
        f"pathogen-batch-2026-05-02.md``, large host-pathogen / infection-\n"
        f"themed batches sometimes trip Anthropic's content filter on\n"
        f"cumulative keyword density even though the underlying research\n"
        f"is legitimate. Smaller batches and foreground-orchestrator\n"
        f"processing typically work.\n"
    )


def fetch_list_paywalled(
    acquisition_log: dict[str, Any] | Path,
) -> list[dict[str, Any]]:
    """Build the manual-fetch shopping list from acquisition results.

    Filters an acquisition-results JSON (mapping doi -> result dict)
    down to the entries with ``outcome == "failed_paywalled"`` and
    augments each with a best-guess source-URL hint for the user.

    Args:
        acquisition_log: Either a dict mapping ``doi -> result`` or a
            Path to a JSON file with the same structure (the file
            written by acquisition batch helpers).

    Returns:
        List of ``{doi, title, journal, year, publisher_url,
        cache_target_path, why_paywalled}`` dicts. Sorted by publisher
        cluster (Nature → Cell → Science → Wiley → Springer → Elsevier
        → other) so the user can group manual fetches by their
        institutional access strategy.
    """
    if isinstance(acquisition_log, Path):
        try:
            data = json.loads(acquisition_log.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Could not read acquisition log: %s", exc)
            return []
    else:
        data = acquisition_log
    if not isinstance(data, dict):
        return []

    out: list[dict[str, Any]] = []
    for doi, rec in data.items():
        if not isinstance(rec, dict):
            continue
        # We classify as paywalled either via explicit ``outcome`` or
        # by inspecting the legacy ``source`` + ``tier_errors`` fields.
        outcome = rec.get("outcome")
        if outcome is None:
            # Legacy log without outcome: replicate the heuristic
            tier_errors = rec.get("tier_errors") or {}
            for err in tier_errors.values():
                e = str(err).lower()
                if "401" in e or "403" in e or "subscription" in e or "forbidden" in e:
                    outcome = "failed_paywalled"
                    break
            if outcome is None:
                if any(t in tier_errors for t in ("elsevier", "springer")):
                    err_str = str(
                        tier_errors.get("elsevier", "")
                        or tier_errors.get("springer", "")
                    ).lower()
                    if "key missing" not in err_str and "no api key" not in err_str:
                        outcome = "failed_paywalled"
        if outcome != "failed_paywalled":
            continue
        out.append({
            "doi": doi,
            "title": rec.get("title") or "",
            "journal": rec.get("journal") or "",
            "year": rec.get("year") or 0,
            "publisher_url": rec.get("publisher_url")
                or f"https://doi.org/{doi}",
            "cache_target_path": rec.get("cache_target_path") or "",
            "why_paywalled": _summarize_why_paywalled(rec.get("tier_errors") or {}),
        })
    # Sort by publisher cluster heuristic
    out.sort(key=_publisher_sort_key)
    return out


def _summarize_why_paywalled(tier_errors: dict[str, str]) -> str:
    """One-sentence reason for the manual-fetch report."""
    parts: list[str] = []
    for tier, err in tier_errors.items():
        e = str(err).lower()
        if "401" in e or "403" in e:
            parts.append(f"{tier}: 401/403 (no access)")
        elif "subscription" in e or "forbidden" in e:
            parts.append(f"{tier}: subscription required")
        elif "key missing" in e or "no api key" in e:
            continue  # not a paywall reason
        elif tier in ("elsevier", "springer"):
            parts.append(f"{tier}: {str(err)[:60]}")
    if not parts:
        return "all tiers failed without explicit paywall signal"
    return "; ".join(parts)


def _publisher_sort_key(entry: dict[str, Any]) -> tuple[int, str]:
    """Group entries by publisher cluster for the shopping list."""
    journal = (entry.get("journal") or "").lower()
    doi = (entry.get("doi") or "").lower()
    if "nature" in journal or doi.startswith("10.1038"):
        return (0, doi)
    if "cell" in journal or "cell.com" in (entry.get("publisher_url") or "").lower() or doi.startswith("10.1016/j.cels") or doi.startswith("10.1016/j.cell"):
        return (1, doi)
    if "science" in journal or doi.startswith("10.1126"):
        return (2, doi)
    if "wiley" in journal or doi.startswith("10.1002"):
        return (3, doi)
    if "springer" in journal or doi.startswith("10.1007"):
        return (4, doi)
    if doi.startswith("10.1016"):  # Other Elsevier
        return (5, doi)
    return (9, doi)


__all__ = [
    "is_policy_refusal_error",
    "mark_skipped",
    "list_skipped",
    "is_skipped",
    "fetch_list_paywalled",
]
