"""PR / release-notes HTML writeup consumer — Thariq's pattern #5.

Renders a structured release-notes / iterate-session / overnight-session
report as a single-file HTML document. Composes existing primitives from
:mod:`vaultlab.report._components`:

- :func:`tldr_box` for the headline summary
- :func:`matrix_table` for the per-file change table
- :func:`compare_panel` (optional) for "before / after" highlight pairs
  (e.g. tests-before vs tests-after, perf-before vs perf-after)
- :func:`collapsible_step` for per-commit detail blocks
- :func:`status_chip` for breaking-change + summary badges

Pattern source: ``docs/html-pattern-coverage.md`` (#5 "PR Writeup for
Reviewers"). Use cases inside vaultlab:

- Release notes for v0.0.5+ (formerly authored as raw markdown).
- ``/iterate`` session summaries (what changed across many commits).
- ``/goodnight`` overnight-session reports.

Composition follows the same shape as
:mod:`vaultlab.report.weekly_status_html` and
:mod:`vaultlab.report.state_dashboard_html`: ``build_<name>`` returns the
HTML string; ``write_<name>`` writes to disk plus AGENTS.md Red Line #2
provenance sidecars via :func:`vaultlab.provenance.write_receipts`.

No new primitives are introduced.
"""

from __future__ import annotations

import html as _html
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from vaultlab.report import _components as c
from vaultlab.report.html import render_report


# ---------------------------------------------------------------------------
# Public dataclasses


@dataclass
class FileChange:
    """One file touched by the PR / session.

    Attributes
    ----------
    path:
        Repository-relative path, e.g. ``src/vaultlab/report/foo.py``.
    change_kind:
        One of ``"added"`` / ``"modified"`` / ``"deleted"``. Drives the
        per-row severity chip in the file table.
    lines_added:
        Number of lines added.
    lines_removed:
        Number of lines removed.
    summary:
        Optional one-line summary of what changed in this file. Rendered
        as the right-most column in the file table.
    """

    path: str
    change_kind: str  # "added" | "modified" | "deleted"
    lines_added: int
    lines_removed: int
    summary: str = ""


@dataclass
class CommitEntry:
    """One commit in the PR / session.

    Attributes
    ----------
    sha:
        Short SHA (caller chooses how many chars).
    title:
        Commit title (first line of the commit message).
    body:
        Optional commit body. Rendered as a ``<pre>``-style block inside
        the collapsible commit step.
    files:
        Optional list of :class:`FileChange` items scoped to this commit.
        When non-empty, the commit's expanded step shows a per-file mini
        table. Top-level :attr:`PRWriteup.files` is preferred for the
        overall summary; this is for callers who want per-commit detail.
    """

    sha: str
    title: str
    body: str = ""
    files: list[FileChange] = field(default_factory=list)


@dataclass
class PRWriteup:
    """Top-level structured input for the PR / release-notes view.

    Attributes
    ----------
    title:
        Headline, e.g. ``"v0.0.5 release notes"`` or
        ``"iterate session 2026-05-15"``.
    summary:
        Paragraph summary rendered in the TL;DR box.
    commits:
        Ordered list of commits. Renders newest-first by convention; the
        renderer preserves input order.
    files:
        Repo-wide file change roll-up (optional but recommended for PRs).
        Rendered as a ``matrix_table`` above the commit list. When empty
        and commits supply per-commit files, the renderer aggregates
        across commits to produce a roll-up automatically.
    test_summary:
        Free-form test-suite summary, e.g. ``"2046 passed, 6 deselected"``.
        Rendered as a ``compare_panel`` (alongside ``test_summary_before``
        when provided) so reviewers see the delta. Empty omits the
        compare panel entirely.
    test_summary_before:
        Optional pre-PR test-suite summary for the ``compare_panel``
        before/after view. Empty falls back to a one-sided card.
    breaking_changes:
        Bullet list of breaking changes. Each item renders as a ``bad``
        severity chip + line in the breaking-changes section. Empty
        omits the section.
    """

    title: str
    summary: str = ""
    commits: list[CommitEntry] = field(default_factory=list)
    files: list[FileChange] = field(default_factory=list)
    test_summary: str = ""
    test_summary_before: str = ""
    breaking_changes: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Internal helpers


def _safe(text: Any) -> str:
    return _html.escape(str(text or ""))


_KIND_SEVERITY = {"added": "good", "modified": "neutral", "deleted": "bad"}


def _kind_chip(kind: str) -> str:
    """Render a ``change_kind`` value as a coloured status chip."""
    sev = _KIND_SEVERITY.get(kind, "neutral")
    return c.status_chip(kind or "modified", sev)  # type: ignore[arg-type]


def _files_to_rows(files: list[FileChange]) -> list[list[str]]:
    """Convert FileChange records to ``matrix_table`` rows (pre-escaped)."""
    rows: list[list[str]] = []
    for f in files:
        rows.append(
            [
                f"<code>{_safe(f.path)}</code>",
                _kind_chip(f.change_kind),
                f'<span style="color:var(--good);">+{int(f.lines_added)}</span>',
                f'<span style="color:var(--bad);">-{int(f.lines_removed)}</span>',
                _safe(f.summary),
            ]
        )
    return rows


def _aggregate_commit_files(commits: list[CommitEntry]) -> list[FileChange]:
    """Roll up per-commit file lists into a single sorted change list.

    Multiple touches of the same path are summed in additions/deletions;
    the kind picks the most "severe" status: ``deleted`` > ``added`` >
    ``modified``. Summaries are concatenated with ``"; "`` separators.
    """
    by_path: dict[str, FileChange] = {}
    rank = {"deleted": 2, "added": 1, "modified": 0}
    for commit in commits:
        for f in commit.files:
            existing = by_path.get(f.path)
            if existing is None:
                by_path[f.path] = FileChange(
                    path=f.path,
                    change_kind=f.change_kind,
                    lines_added=f.lines_added,
                    lines_removed=f.lines_removed,
                    summary=f.summary,
                )
                continue
            existing.lines_added += f.lines_added
            existing.lines_removed += f.lines_removed
            if rank.get(f.change_kind, 0) > rank.get(existing.change_kind, 0):
                existing.change_kind = f.change_kind
            if f.summary and f.summary not in existing.summary:
                existing.summary = (
                    f"{existing.summary}; {f.summary}".strip("; ")
                    if existing.summary
                    else f.summary
                )
    return sorted(by_path.values(), key=lambda x: x.path)


def _commit_step(commit: CommitEntry) -> str:
    """Render a commit as a :func:`collapsible_step`."""
    body_parts: list[str] = []
    if commit.body:
        body_parts.append(
            '<pre style="margin:6px 0;padding:8px 10px;background:var(--bg-soft);'
            "border-radius:4px;font-size:12px;color:var(--ink-soft);"
            'white-space:pre-wrap;">'
            f"{_safe(commit.body)}"
            "</pre>"
        )
    if commit.files:
        body_parts.append(
            c.matrix_table(
                ["Path", "Kind", "+", "-", "Summary"],
                _files_to_rows(commit.files),
            )
        )
    if not body_parts:
        body_parts.append(
            '<p style="margin:0;color:var(--muted);font-size:12px;">'
            "No body or per-file detail recorded.</p>"
        )
    return c.collapsible_step(
        f"{commit.sha}  ·  {commit.title}",
        "".join(body_parts),
    )


def _breaking_changes_block(items: list[str]) -> str:
    """Render a bullet list of breaking changes with a leading bad chip."""
    if not items:
        return ""
    bullets = "".join(
        f"<li>{c.status_chip('breaking', 'bad')} {_safe(item)}</li>" for item in items
    )
    return (
        '<ul style="margin:6px 0 0;padding-left:18px;font-size:14px;'
        'color:var(--ink-soft);list-style:none;">'
        f"{bullets}"
        "</ul>"
    )


# ---------------------------------------------------------------------------
# Public API


def build_pr_writeup_html(pr: PRWriteup) -> str:
    """Compose the PR writeup as a self-contained HTML string.

    Section order: TL;DR + chip band, breaking-changes (if any),
    test-summary compare panel (if any), per-file change table (rolled
    up across commits if ``pr.files`` is empty), per-commit collapsible
    steps. Empty sections are silently omitted.
    """
    report_title = pr.title or "PR writeup"

    # Header chips
    header_chips: list[str] = []
    if pr.commits:
        header_chips.append(
            c.status_chip(
                f"{len(pr.commits)} commit" + ("s" if len(pr.commits) != 1 else ""),
                "neutral",
            )
        )
    aggregated_files = (
        list(pr.files) if pr.files else _aggregate_commit_files(pr.commits)
    )
    if aggregated_files:
        header_chips.append(
            c.status_chip(
                f"{len(aggregated_files)} file"
                + ("s" if len(aggregated_files) != 1 else ""),
                "neutral",
            )
        )
    if pr.breaking_changes:
        header_chips.append(
            c.status_chip(
                f"{len(pr.breaking_changes)} breaking", "bad"
            )
        )
    if pr.test_summary:
        header_chips.append(c.status_chip("tests reported", "good"))

    sections: list[str] = []

    # TL;DR + chip band
    intro_parts: list[str] = []
    if pr.summary:
        intro_parts.append(c.tldr_box(pr.summary))
    if header_chips:
        intro_parts.append(
            f'<div style="margin:14px 0;">{"".join(header_chips)}</div>'
        )
    if intro_parts:
        sections.append(c.section(None, *intro_parts))

    # Breaking changes
    if pr.breaking_changes:
        sections.append(
            c.section(
                "Breaking changes",
                _breaking_changes_block(pr.breaking_changes),
            )
        )

    # Test summary (compare-panel before/after, or one-sided)
    if pr.test_summary:
        if pr.test_summary_before:
            sections.append(
                c.section(
                    "Test suite",
                    c.compare_panel(
                        "Before",
                        f'<p style="margin:0;color:var(--ink-soft);">'
                        f"{_safe(pr.test_summary_before)}</p>",
                        "After",
                        f'<p style="margin:0;color:var(--ink-soft);">'
                        f"{_safe(pr.test_summary)}</p>",
                    ),
                )
            )
        else:
            sections.append(
                c.section(
                    "Test suite",
                    f'<p style="margin:0;color:var(--ink-soft);font-size:14px;">'
                    f"{_safe(pr.test_summary)}</p>",
                )
            )

    # File change table (roll-up)
    if aggregated_files:
        sections.append(
            c.section(
                "Files changed",
                c.matrix_table(
                    ["Path", "Kind", "+", "-", "Summary"],
                    _files_to_rows(aggregated_files),
                ),
            )
        )

    # Commits
    if pr.commits:
        commit_html = "".join(_commit_step(commit) for commit in pr.commits)
        sections.append(c.section("Commits", commit_html))

    eyebrow = "vaultlab · PR writeup"
    return render_report(
        title=report_title,
        eyebrow=eyebrow,
        meta=f"{len(pr.commits)} commit"
        + ("s" if len(pr.commits) != 1 else "")
        + f" · {len(aggregated_files)} file"
        + ("s" if len(aggregated_files) != 1 else ""),
        sections=sections,
    )


def write_pr_writeup_html(
    pr: PRWriteup,
    output_path: Path | str,
) -> Path:
    """Render and write the PR writeup to ``output_path``.

    Also writes AGENTS.md Red Line #2 sidecars (``.provenance.json`` +
    ``.method.md``) next to the output. Provenance is best-effort —
    failure to write receipts does not block the HTML write.

    Returns the resolved output Path.
    """
    p = Path(output_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(build_pr_writeup_html(pr), encoding="utf-8")

    try:
        from vaultlab.provenance import ProvenanceRecord, write_receipts

        aggregated_files = (
            list(pr.files) if pr.files else _aggregate_commit_files(pr.commits)
        )
        record = ProvenanceRecord(
            generated_by="vaultlab.report.pr_writeup_html",
            kind="pr_writeup_html",
            inputs=[],
            params={
                "title": pr.title,
                "commit_count": len(pr.commits),
                "file_count": len(aggregated_files),
                "breaking_change_count": len(pr.breaking_changes),
                "has_test_summary": bool(pr.test_summary),
                "has_test_summary_before": bool(pr.test_summary_before),
            },
        )
        write_receipts(str(p), record)
    except Exception:  # pragma: no cover — defensive
        import logging

        logging.getLogger(__name__).exception(
            "write_receipts failed for pr-writeup %s", p
        )

    return p


__all__ = [
    "CommitEntry",
    "FileChange",
    "PRWriteup",
    "build_pr_writeup_html",
    "write_pr_writeup_html",
]
