"""Reviewer response letter scaffolding.

Absorbed from the nature-response skill (Yuan Yizhe, SJTU) at
nature-skills/skills/nature-response/.

A reviewer response letter is an editor-facing verification document:
every reviewer concern is assigned a stable ID, classified, mapped to an
action, and tied to manuscript evidence (a revised passage, a new
analysis, a figure update) — or flagged with ``AUTHOR_INPUT_NEEDED``
when the response requires the author's judgment call.

Public API
----------

- :class:`CommentKind` — taxonomy of reviewer-comment types
- :class:`ActionType` — what the author does in response
- :class:`ReviewerComment` — one comment + planned action
- :class:`ResponseLetter` — full letter for one reviewer
- :func:`classify_comment` — heuristic classifier from comment text
- :func:`stable_id` — assign R<reviewer>-C<n> ID
- :func:`render_response_letter` — emit the letter as markdown

See ``SKILL.md`` for the tone, structure, and difficult-case playbook.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from vaultlab.provenance import ProvenanceRecord, write_receipts


class CommentKind(str, Enum):
    """Reviewer comment taxonomy."""

    METHOD_QUESTION = "method_question"
    METHOD_CRITIQUE = "method_critique"
    RESULT_QUESTION = "result_question"
    RESULT_CHALLENGE = "result_challenge"
    OVERCLAIM = "overclaim"
    NOVELTY_QUESTION = "novelty_question"
    MISSING_CITATION = "missing_citation"
    MISSING_EXPERIMENT = "missing_experiment"
    PRESENTATION = "presentation"
    SCOPE = "scope"
    POSITIVE = "positive"
    EDITORIAL = "editorial"


class ActionType(str, Enum):
    """How the author plans to respond."""

    ACCEPT_TEXT = "ACCEPT_TEXT"  # Revise prose / clarify
    ACCEPT_ANALYSIS = "ACCEPT_ANALYSIS"  # Add new analysis on existing data
    ACCEPT_EXPERIMENT = "ACCEPT_EXPERIMENT"  # Run new wet-lab work
    ACCEPT_FIGURE = "ACCEPT_FIGURE"  # Update / add figure
    ACCEPT_CITATION = "ACCEPT_CITATION"  # Add the missing reference
    SOFTEN_CLAIM = "SOFTEN_CLAIM"  # Hedge or scope down the claim
    DISAGREE_WITH_RATIONALE = "DISAGREE_WITH_RATIONALE"  # Push back, evidence-led
    AUTHOR_INPUT_NEEDED = "AUTHOR_INPUT_NEEDED"  # Cannot draft until the author decides
    DEFER_TO_FUTURE_WORK = "DEFER_TO_FUTURE_WORK"  # Acknowledge + cite as limitation


@dataclass
class ReviewerComment:
    """One reviewer comment + the planned response.

    Attributes
    ----------
    stable_id:
        ``R<reviewer-number>-C<comment-number>`` — never reordered.
    reviewer:
        Reviewer index (1, 2, 3, ...).
    quote:
        The reviewer's verbatim quote (or a faithful paraphrase).
    kind:
        One of :class:`CommentKind`.
    action:
        One of :class:`ActionType`.
    evidence_ref:
        Where in the revised manuscript the response lives — e.g. ``"§Results, p.7 lines 12-18"`` or ``"Fig. 3c"``. Empty string is acceptable only when
        ``action == AUTHOR_INPUT_NEEDED``.
    response_text:
        The author-facing response prose.
    open_question:
        Free-form note for the author when ``action == AUTHOR_INPUT_NEEDED``.
    """

    stable_id: str
    reviewer: int
    quote: str
    kind: CommentKind
    action: ActionType
    evidence_ref: str = ""
    response_text: str = ""
    open_question: str = ""


@dataclass
class ResponseLetter:
    """Full point-by-point response letter for one reviewer."""

    reviewer: int
    comments: list[ReviewerComment] = field(default_factory=list)
    opening: str = ""
    closing: str = ""


# ---------------------------------------------------------------------------
# Classification


def stable_id(reviewer: int, comment_index: int) -> str:
    """Assign the stable comment ID. comment_index is 1-based."""
    return f"R{reviewer}-C{comment_index}"


_KIND_KEYWORDS: list[tuple[CommentKind, tuple[str, ...]]] = [
    (
        CommentKind.MISSING_EXPERIMENT,
        ("should perform", "additional experiment", "in vivo", "knockout", "control experiment"),
    ),
    (
        CommentKind.MISSING_CITATION,
        (
            "authors miss",
            "they fail to cite",
            "should cite",
            "important reference",
            "missing citation",
        ),
    ),
    (
        CommentKind.OVERCLAIM,
        ("overclaim", "too strong", "evidence does not support", "cannot conclude"),
    ),
    (
        CommentKind.METHOD_CRITIQUE,
        ("statistical", "method is flawed", "sample size", "underpowered", "n=", "p-value"),
    ),
    (
        CommentKind.RESULT_CHALLENGE,
        ("disagree with", "contradicts", "the data do not show", "i am not convinced"),
    ),
    (
        CommentKind.RESULT_QUESTION,
        ("clarify", "could the authors explain", "what does the data show"),
    ),
    (
        CommentKind.NOVELTY_QUESTION,
        ("novelty", "incremental", "what is new", "already shown"),
    ),
    (
        CommentKind.SCOPE,
        ("out of scope", "scope of the paper", "beyond the claim"),
    ),
    (
        CommentKind.PRESENTATION,
        ("typo", "figure quality", "table legend", "format", "grammar"),
    ),
    (
        CommentKind.POSITIVE,
        ("excellent", "impressive", "well-written", "i enjoyed", "compelling"),
    ),
    (
        CommentKind.EDITORIAL,
        ("editor", "scope of journal", "fits the journal"),
    ),
]


def classify_comment(text: str) -> CommentKind:
    """Heuristic classifier. Returns the first matching kind, or
    METHOD_QUESTION as the most common default.
    """
    lowered = text.lower()
    for kind, keywords in _KIND_KEYWORDS:
        if any(k in lowered for k in keywords):
            return kind
    return CommentKind.METHOD_QUESTION


def suggest_action(kind: CommentKind) -> ActionType:
    """Best-guess default action mapping. Author overrides as needed."""
    return {
        CommentKind.METHOD_QUESTION: ActionType.ACCEPT_TEXT,
        CommentKind.METHOD_CRITIQUE: ActionType.ACCEPT_ANALYSIS,
        CommentKind.RESULT_QUESTION: ActionType.ACCEPT_TEXT,
        CommentKind.RESULT_CHALLENGE: ActionType.DISAGREE_WITH_RATIONALE,
        CommentKind.OVERCLAIM: ActionType.SOFTEN_CLAIM,
        CommentKind.NOVELTY_QUESTION: ActionType.ACCEPT_TEXT,
        CommentKind.MISSING_CITATION: ActionType.ACCEPT_CITATION,
        CommentKind.MISSING_EXPERIMENT: ActionType.AUTHOR_INPUT_NEEDED,
        CommentKind.PRESENTATION: ActionType.ACCEPT_TEXT,
        CommentKind.SCOPE: ActionType.SOFTEN_CLAIM,
        CommentKind.POSITIVE: ActionType.ACCEPT_TEXT,
        CommentKind.EDITORIAL: ActionType.AUTHOR_INPUT_NEEDED,
    }[kind]


# ---------------------------------------------------------------------------
# Render


def render_response_letter(letter: ResponseLetter) -> str:
    """Emit the response letter as markdown.

    Format (one block per comment)::

        ### R1-C1
        > [reviewer quote]

        **Action:** ACCEPT_ANALYSIS
        **Where in revision:** §Results, p.7 lines 12-18

        [response prose]
    """
    parts: list[str] = []
    parts.append(f"# Response to Reviewer {letter.reviewer}")
    if letter.opening:
        parts.append(letter.opening)
    parts.append("")
    for cm in letter.comments:
        parts.append(f"### {cm.stable_id}")
        if cm.quote:
            parts.append(f"> {cm.quote}")
            parts.append("")
        parts.append(f"**Kind:** `{cm.kind.value}`  **Action:** `{cm.action.value}`")
        if cm.evidence_ref:
            parts.append(f"**Where in revision:** {cm.evidence_ref}")
        parts.append("")
        if cm.response_text:
            parts.append(cm.response_text)
            parts.append("")
        if cm.action == ActionType.AUTHOR_INPUT_NEEDED and cm.open_question:
            parts.append(f"⚠️ **AUTHOR INPUT NEEDED:** {cm.open_question}")
            parts.append("")
    if letter.closing:
        parts.append(letter.closing)
    return "\n".join(parts).rstrip() + "\n"


def parse_reviewer_block(text: str, reviewer_index: int = 1) -> list[ReviewerComment]:
    """Parse a numbered-list reviewer block into a list of comments.

    Looks for lines starting with ``1.``, ``2.``, ``(1)``, ``Comment 1:`` etc.
    and produces one :class:`ReviewerComment` per item, with kind +
    suggested action auto-filled.

    This is a *scaffolder* — the author/agent fills in response_text +
    evidence_ref afterward.
    """
    pattern = re.compile(
        r"^\s*(?:\(?(\d+)\)?\.?\s+|Comment\s+(\d+)\s*[:\.]\s*)(.*?)$",
        re.MULTILINE,
    )
    matches: list[tuple[int, str]] = []
    current_idx = 0
    current_buf: list[str] = []
    for line in text.splitlines():
        m = pattern.match(line)
        if m:
            if current_idx and current_buf:
                matches.append((current_idx, " ".join(current_buf).strip()))
            current_idx = int(m.group(1) or m.group(2) or 0)
            tail = m.group(3) or ""
            current_buf = [tail] if tail.strip() else []
        else:
            if current_idx:
                current_buf.append(line.strip())
    if current_idx and current_buf:
        matches.append((current_idx, " ".join(current_buf).strip()))

    out: list[ReviewerComment] = []
    for idx, body in matches:
        kind = classify_comment(body)
        out.append(
            ReviewerComment(
                stable_id=stable_id(reviewer_index, idx),
                reviewer=reviewer_index,
                quote=body,
                kind=kind,
                action=suggest_action(kind),
            )
        )
    return out


def write_response_letter(
    out_path: Path | str,
    letter: ResponseLetter,
    *,
    inputs: list[str] | None = None,
) -> Path:
    """Render the response letter and write it to disk with provenance receipts.

    Emits ``<out_path>.provenance.json`` and ``<out_path>.method.md`` sidecars
    next to the markdown output (Red Line #2: no silent failures).
    """
    md = render_response_letter(letter)
    p = Path(out_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(md, encoding="utf-8")

    # Audit-manifest contract (red line #2: no silent failures).
    record = ProvenanceRecord(
        generated_by="vaultlab.manuscript.respond.write_response_letter",
        kind="manuscript_response",
        inputs=list(inputs or []),
        params={
            "reviewer": letter.reviewer,
            "n_comments": len(letter.comments),
            "n_author_input_needed": sum(
                1 for c in letter.comments if c.action == ActionType.AUTHOR_INPUT_NEEDED
            ),
        },
    )
    write_receipts(str(p), record)
    return p


__all__ = [
    "ActionType",
    "CommentKind",
    "ResponseLetter",
    "ReviewerComment",
    "classify_comment",
    "parse_reviewer_block",
    "render_response_letter",
    "stable_id",
    "suggest_action",
    "write_response_letter",
]
