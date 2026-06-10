"""KB-context preamble for spawned sub-agents (Phase 5 of figure-stack roadmap).

Closes CLAUDE.md commitment #7 (Context preservation invariant): no
session zero-shoots, every spawned sub-agent has the relevant KB
excerpts loaded as part of its system prompt.

Public surface:
    compose_preamble(project_slug, *, kb_root=None, role=None,
                     max_tokens=4000) -> str

Public exception:
    KbStateUnreadable — raised when the project's KB state can't be
    read (path doesn't exist, START_HERE.md missing, etc.). Callers
    are expected to surface this as a hard refusal-to-proceed rather
    than silently fall back to "guess what the project state is."

Lineage:
    - virtual-lab "team_lead distributes shared context to all
      role-agents" pattern (Swanson Nature 2025; Zou group, Stanford)
    - AI-Scientist verifier-driven termination + PaperQA2 refuse-to-
      ship-without-evidence — applied here as refuse-to-spawn-without-
      KB-context
    - LiteLLM context-window-fitting patterns — token-budget
      truncation with hedged voice
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)

__all__ = ["KbContextBundle", "KbStateUnreadable", "compose_preamble"]


_TOKEN_CHARS_RATIO = 4  # approx — 4 chars per token for English
_MAX_TOKENS_DEFAULT = 4000
_DEFAULT_RECENT_OUTPUTS_N = 3
_DEFAULT_TIER_A_N = 5
_DEFAULT_DECISIONS_LOOKBACK_DAYS = 30


class KbStateUnreadable(RuntimeError):
    """Project KB state can't be read.

    Raised when ``compose_preamble`` is called on a project whose
    canonical state files (``START_HERE.md``) are missing or unreadable.
    Callers MUST refuse to spawn sub-agents in this case rather than
    silently fall through to no-context invocation.
    """


@dataclass(frozen=True)
class KbContextBundle:
    """Structured snapshot of the KB context fed to a sub-agent.

    Attributes:
        project_slug: Slug for the project (e.g. "metabolism").
        kb_root: Resolved KB root path.
        start_here_text: Full ``START_HERE.md`` content (or empty if missing).
        decisions_text: ``decisions-log.md`` entries from the lookback
            window (or empty).
        tier_a_summaries: List of ``(doi_slug, first_400_chars)`` for the
            top-N Tier-A summaries by topic semantic match (or empty).
        recent_outputs: List of ``(filename, first_300_chars)`` for the
            most-recent ``Output/*.md`` files (or empty).
        token_estimate: Approximate token count of the assembled preamble.
        truncated: Whether token-budget truncation kicked in.
    """

    project_slug: str
    kb_root: Path
    start_here_text: str
    decisions_text: str
    tier_a_summaries: list[tuple[str, str]]
    recent_outputs: list[tuple[str, str]]
    token_estimate: int
    truncated: bool


def _estimate_tokens(text: str) -> int:
    """Approximate token count via 4-char-per-token heuristic."""
    return max(1, len(text) // _TOKEN_CHARS_RATIO)


def _truncate_to_budget(
    text: str,
    *,
    max_tokens: int,
    label: str,
) -> tuple[str, bool]:
    """Truncate text to fit a token budget; return (text, was_truncated)."""
    est = _estimate_tokens(text)
    if est <= max_tokens:
        return text, False
    keep_chars = max_tokens * _TOKEN_CHARS_RATIO
    truncated = text[:keep_chars]
    last_para = truncated.rfind("\n\n")
    if last_para > keep_chars * 0.7:  # only break on paragraph if reasonable
        truncated = truncated[:last_para]
    return (
        truncated.rstrip() + f"\n\n[{label} truncated — {est - max_tokens} tokens dropped]\n",
        True,
    )


def _read_start_here(project_dir: Path) -> str:
    path = project_dir / "START_HERE.md"
    if not path.exists():
        raise KbStateUnreadable(
            f"START_HERE.md missing at {path} — cannot compose KB context preamble. "
            f"Run /onboard-me or /start-project to initialize this project's "
            f"START_HERE first."
        )
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        raise KbStateUnreadable(f"START_HERE.md unreadable at {path}: {exc}") from exc


def _read_decisions_log(
    project_dir: Path,
    *,
    lookback_days: int = _DEFAULT_DECISIONS_LOOKBACK_DAYS,
) -> str:
    path = project_dir / "decisions-log.md"
    if not path.exists():
        return ""
    try:
        full_text = path.read_text(encoding="utf-8")
    except OSError as exc:
        logger.warning("decisions-log.md unreadable at %s: %s", path, exc)
        return ""
    cutoff = (datetime.now() - timedelta(days=lookback_days)).strftime("%Y-%m-%d")
    lines = full_text.splitlines()
    out_lines: list[str] = []
    keep = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("## "):
            date_token = stripped[3:].split(" ", 1)[0]
            keep = date_token >= cutoff
        if keep:
            out_lines.append(line)
    return "\n".join(out_lines).strip()


def _list_recent_outputs(
    output_dir: Path,
    *,
    n: int = _DEFAULT_RECENT_OUTPUTS_N,
) -> list[tuple[str, str]]:
    if not output_dir.exists():
        return []
    md_files = sorted(
        output_dir.glob("*.md"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    out: list[tuple[str, str]] = []
    for path in md_files[:n]:
        try:
            content = path.read_text(encoding="utf-8")[:300]
        except OSError:
            continue
        out.append((path.name, content))
    return out


def _list_tier_a_summaries(
    kb_root: Path,
    *,
    project_slug: str,
    topic_keywords: list[str] | None = None,
    n: int = _DEFAULT_TIER_A_N,
) -> list[tuple[str, str]]:
    """Return up to N Tier-A summaries most relevant to the project topic.

    Relevance = simple keyword-overlap score (no embedding model — keeps
    this dependency-free). When ``topic_keywords`` is None, returns the
    most-recently modified summaries.
    """
    summaries_dir = kb_root / "Wiki" / "Summaries"
    if not summaries_dir.exists():
        # Fall back to project-local summaries if any
        summaries_dir = kb_root / project_slug / "Wiki" / "Summaries"
    if not summaries_dir.exists():
        return []
    md_files = list(summaries_dir.glob("*.md"))
    if topic_keywords:
        kw_lower = {k.lower() for k in topic_keywords}

        def score(p: Path) -> int:
            try:
                head = p.read_text(encoding="utf-8")[:1500].lower()
            except OSError:
                return 0
            return sum(1 for k in kw_lower if k in head)

        md_files.sort(key=lambda p: (score(p), p.stat().st_mtime), reverse=True)
    else:
        md_files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    out: list[tuple[str, str]] = []
    for path in md_files[:n]:
        try:
            content = path.read_text(encoding="utf-8")[:400]
        except OSError:
            continue
        out.append((path.stem, content))
    return out


def _resolve_kb_root(kb_root: Path | str | None) -> Path:
    if kb_root is not None:
        return Path(kb_root).expanduser()
    from vaultlab.context.locations import resolve_kb_root as _resolve

    return _resolve(interactive=False)


def _project_topic_keywords(project_dir: Path) -> list[str]:
    """Pull rough topic keywords from .vaultlab-project.json or START_HERE.md."""
    config_path = project_dir / ".vaultlab-project.json"
    if config_path.exists():
        import json

        try:
            data = json.loads(config_path.read_text(encoding="utf-8"))
            topic = str(data.get("topic", ""))
            if topic:
                return [w.strip().lower() for w in topic.split() if len(w.strip()) > 3]
        except (OSError, json.JSONDecodeError):
            pass
    # Fall back: project-folder name
    return [project_dir.name.replace("-", " ").replace("_", " ")]


def compose_preamble(
    project_slug: str,
    *,
    kb_root: Path | str | None = None,
    role: str | None = None,
    max_tokens: int = _MAX_TOKENS_DEFAULT,
    return_bundle: bool = False,
) -> str | KbContextBundle:
    """Compose a KB-context preamble for a spawned sub-agent.

    Reads the project's canonical state files + the most-relevant
    Tier-A summaries, formats as a single prepended-to-system-prompt
    block, and returns the string. When ``return_bundle=True``, returns
    the structured :class:`KbContextBundle` instead so callers can
    inspect what was loaded.

    Parameters
    ----------
    project_slug
        Project folder name under ``<kb_root>``.
    kb_root
        Override resolved KB root. Defaults to
        :func:`vaultlab.context.locations.resolve_kb_root`.
    role
        Role being spawned (e.g., ``"methods_critic"``). Used in the
        preamble's leading line so the sub-agent knows whose system
        prompt this is. Optional.
    max_tokens
        Approximate token budget for the assembled preamble. Default
        4000. Truncation is hedged — when applied, an explicit
        ``[<section> truncated — N tokens dropped]`` marker is left
        in place so the sub-agent knows it isn't seeing everything.
    return_bundle
        If True, return :class:`KbContextBundle` instead of the
        formatted string. Useful for ``/context-check``.

    Returns
    -------
    str | KbContextBundle
        Preamble ready to prepend to a sub-agent system prompt
        (default), or the structured bundle.

    Raises
    ------
    KbStateUnreadable
        When ``<kb_root>/Wiki/Projects/<project_slug>/START_HERE.md`` is
        missing or unreadable (with a legacy flat ``<kb_root>/<project_slug>/``
        fallback). Callers MUST refuse to spawn sub-agents in this case
        (per CLAUDE.md commitment #7).
    """
    kb_root_path = _resolve_kb_root(kb_root)

    # Resolve the project's state directory the SAME way onboarding +
    # update_start_here write it: <kb>/Wiki/Projects/<slug>/ (the parent of the
    # canonical project_state_path). Reading <kb>/<slug>/ instead — as this did
    # before — meant a correctly-onboarded project raised KbStateUnreadable on
    # every spawn (CLAUDE.md commitment #7 was unenforceable). A flat
    # <kb>/<slug>/ layout is still honoured as a fallback when it is the folder
    # that actually holds START_HERE.md; otherwise the canonical path drives the
    # error message.
    from vaultlab.kb.paths import project_dir as _kb_output_dir
    from vaultlab.kb.paths import project_state_path

    canonical_dir = project_state_path(kb_root_path, project_slug).parent
    legacy_dir = kb_root_path / project_slug
    if (canonical_dir / "START_HERE.md").exists():
        state_dir = canonical_dir
    elif (legacy_dir / "START_HERE.md").exists():
        state_dir = legacy_dir
    else:
        state_dir = canonical_dir  # canonical path drives the KbStateUnreadable message

    # Outputs live at <kb>/Output/<slug>/ canonically; fall back to a flat
    # <state_dir>/Output/ for legacy-layout projects.
    output_dir = _kb_output_dir(kb_root_path, project_slug)
    if not output_dir.exists():
        output_dir = state_dir / "Output"

    start_here = _read_start_here(state_dir)
    decisions = _read_decisions_log(state_dir)
    topic_keywords = _project_topic_keywords(state_dir)
    tier_a = _list_tier_a_summaries(
        kb_root_path,
        project_slug=project_slug,
        topic_keywords=topic_keywords,
    )
    recent_outputs = _list_recent_outputs(output_dir)

    # Section budgets (approximate split of total budget)
    sh_budget = max_tokens // 3
    dec_budget = max_tokens // 4
    tier_a_budget = max_tokens // 4
    output_budget = max_tokens - sh_budget - dec_budget - tier_a_budget

    sh_text, sh_trunc = _truncate_to_budget(start_here, max_tokens=sh_budget, label="START_HERE")
    dec_text, dec_trunc = _truncate_to_budget(
        decisions, max_tokens=dec_budget, label="decisions-log"
    )
    truncated_any = sh_trunc or dec_trunc

    sections: list[str] = []
    sections.append(
        f"## Project context preamble — {project_slug}" + (f" (role: {role})" if role else "")
    )
    sections.append(
        "You are operating inside a vaultlab project. The KB excerpts below "
        "are the project's known state. **Do NOT redo work that's already "
        "represented here. Build on it.** This preamble fulfils CLAUDE.md "
        "commitment #7 (Context preservation invariant)."
    )

    sections.append("### START_HERE.md (project daily brief)")
    sections.append(sh_text or "(empty)")

    if dec_text:
        sections.append("### decisions-log.md (recent design decisions)")
        sections.append(dec_text)

    if tier_a:
        sections.append("### Top-relevant Tier-A summaries")
        per_summary_chars = max(200, (tier_a_budget * _TOKEN_CHARS_RATIO) // max(len(tier_a), 1))
        for slug, body in tier_a:
            sections.append(f"#### {slug}")
            sections.append(body[:per_summary_chars])

    if recent_outputs:
        sections.append("### Recent project Output/*.md (most-recent first)")
        per_output_chars = max(
            150, (output_budget * _TOKEN_CHARS_RATIO) // max(len(recent_outputs), 1)
        )
        for fname, body in recent_outputs:
            sections.append(f"#### {fname}")
            sections.append(body[:per_output_chars])

    sections.append(
        "**Reminder:** if any prior artifact already covers the user's question, "
        "answer from it (mode `--query-existing`) rather than redoing the work."
    )

    preamble = "\n\n".join(sections)
    token_estimate = _estimate_tokens(preamble)

    if return_bundle:
        return KbContextBundle(
            project_slug=project_slug,
            kb_root=kb_root_path,
            start_here_text=sh_text,
            decisions_text=dec_text,
            tier_a_summaries=tier_a,
            recent_outputs=recent_outputs,
            token_estimate=token_estimate,
            truncated=truncated_any,
        )
    return preamble
