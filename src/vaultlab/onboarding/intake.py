"""vaultlab.onboarding.intake — fillable project intake form.

The intake form is a structured markdown the user fills out *before*
running ``/onboard-project``. It captures the 9 sections from the
onboarding audit (topic, goal, audience, what-they-have, exclusions,
style, PI prefs, deadlines, free-form) so the slash command can ask
3-5 follow-up questions instead of 30.

The on-disk format is human-readable markdown with a YAML frontmatter
header. This module provides the round-trip:

- :func:`render_intake_template` — emit the empty template.
- :func:`parse_intake_md` — read a filled markdown and return an
  :class:`IntakeForm` dataclass.
- :meth:`IntakeForm.to_markdown` — render a form back to markdown
  (so vaultlab can write the saved KB-side copy).

Design notes
------------
- Required fields: ``topic``, ``goals`` (≥1), ``audiences`` (≥1).
  :func:`parse_intake_md` raises ``IntakeValidationError`` if missing.
- Checkbox parsing is lenient: ``- [x]``, ``- [X]``, ``- [✓]`` all
  count as checked. Anything else (``- [ ]``, ``- []``, etc.) is
  unchecked.
- Free-form "YOUR ANSWER:" sections are read greedily until the next
  ``## `` heading or end-of-document.
- "Other: ____________" with non-default text is folded into the
  list as a free-form entry (e.g., ``goals=['draft_manuscript_section',
  'Other: figure for grant']``).

The dataclass field names use snake_case ASCII tokens that map to the
checkbox labels — this keeps the on-disk markdown readable while
giving callers a stable Python API.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from pathlib import Path

import frontmatter

__all__ = [
    "INTAKE_SCHEMA",
    "IntakeForm",
    "IntakeValidationError",
    "parse_intake_md",
    "render_intake_template",
]

INTAKE_SCHEMA = "vaultlab-intake/v1"


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class IntakeValidationError(ValueError):
    """Raised when a parsed intake form is missing required fields."""


# ---------------------------------------------------------------------------
# Dataclass
# ---------------------------------------------------------------------------


@dataclass
class IntakeForm:
    """Structured representation of a filled-in ``project_intake.md``.

    The 9 sections from the onboarding audit are mapped onto typed
    fields. Multi-select sections (goals / audiences / etc.) become
    ``list[str]``; single free-form prose sections become ``str``;
    structured filters (exclusions) become a ``dict``.
    """

    # 1. Topic
    topic: str = ""

    # 2. Goal (multi-select)
    goals: list[str] = field(default_factory=list)

    # 3. Audience (multi-select)
    audiences: list[str] = field(default_factory=list)

    # 4. What you already have (multi-select with embedded paths/info)
    have: list[str] = field(default_factory=list)

    # 5. What you don't want (structured filters)
    exclusions: dict[str, str | bool] = field(default_factory=dict)

    # 6. Style / voice (multi-select)
    style: list[str] = field(default_factory=list)

    # 7. PI preferences (free-form prose)
    pi_preferences: str = ""

    # 8. Deadlines (multi-select with optional date)
    deadlines: list[str] = field(default_factory=list)

    # 9. Anything else (free-form prose)
    free_form: str = ""

    # Provenance metadata (not user-edited, but round-tripped)
    schema: str = INTAKE_SCHEMA

    # ---------------------------------------------------------------
    # Validation
    # ---------------------------------------------------------------

    def validate(self) -> None:
        """Raise :class:`IntakeValidationError` if required fields are blank."""
        missing: list[str] = []
        if not self.topic or not self.topic.strip():
            missing.append("topic")
        if not self.goals:
            missing.append("goals (need ≥1 checked)")
        if not self.audiences:
            missing.append("audiences (need ≥1 checked)")
        if missing:
            raise IntakeValidationError(
                "Intake form missing required fields: " + ", ".join(missing)
            )

    # ---------------------------------------------------------------
    # Round-trip
    # ---------------------------------------------------------------

    def to_dict(self) -> dict[str, object]:
        """Plain-dict representation (for JSON / config serialization)."""
        return asdict(self)

    def to_markdown(self) -> str:
        """Render this form back to filled-in markdown.

        The output follows the same structure as
        :func:`render_intake_template` so a round-trip
        ``parse_intake_md(form.to_markdown())`` is lossless for the
        major fields. Free-form prose is preserved verbatim; checkbox
        lists are re-rendered with the user's selections checked.
        """
        post = frontmatter.Post(
            _render_filled_body(self),
            template="project_intake",
            schema=self.schema,
        )
        return frontmatter.dumps(post)


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


def render_intake_template() -> str:
    """Return the empty template markdown — the contents users fill in.

    This is the same string that ships at
    ``templates/project_intake.md``; rendering it via Python lets the
    slash command write a fresh copy to the user's project folder
    without depending on the install location of the template file.
    """
    return _EMPTY_TEMPLATE


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------


_CHECKED = re.compile(r"^\s*-\s*\[\s*[xX✓]\s*\]\s*(.+?)\s*$")
_UNCHECKED = re.compile(r"^\s*-\s*\[\s*\]\s*(.+?)\s*$")
_HEADING = re.compile(r"^##\s+(\d+)\.\s+(.+?)(?:\s*\(.+\))?\s*$")


def parse_intake_md(path: str | Path) -> IntakeForm:
    """Parse a filled ``project_intake.md`` and return an :class:`IntakeForm`.

    Raises
    ------
    FileNotFoundError
        If the file doesn't exist.
    IntakeValidationError
        If the parsed form is missing required fields (topic, ≥1 goal,
        ≥1 audience).
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Intake form not found: {p}")
    raw = p.read_text(encoding="utf-8")
    form = _parse_intake_text(raw)
    form.validate()
    return form


def _parse_intake_text(raw: str) -> IntakeForm:
    """Internal: parse a markdown string (no validation)."""
    # Strip frontmatter if present
    try:
        post = frontmatter.loads(raw)
        body = post.content
        schema = str(post.get("schema", INTAKE_SCHEMA))
    except Exception:  # pragma: no cover — frontmatter is lenient
        body = raw
        schema = INTAKE_SCHEMA

    sections = _split_into_sections(body)
    form = IntakeForm(schema=schema)

    for n, _label, section_body in sections:
        if n == 1:
            form.topic = _read_your_answer(section_body)
        elif n == 2:
            form.goals = _parse_goal_checkboxes(section_body)
        elif n == 3:
            form.audiences = _parse_audience_checkboxes(section_body)
        elif n == 4:
            form.have = _parse_have_checkboxes(section_body)
        elif n == 5:
            form.exclusions = _parse_exclusions(section_body)
        elif n == 6:
            form.style = _parse_style_checkboxes(section_body)
        elif n == 7:
            form.pi_preferences = _read_your_answer(section_body)
        elif n == 8:
            form.deadlines = _parse_deadline_checkboxes(section_body)
        elif n == 9:
            form.free_form = _read_your_answer(section_body)
    return form


def _split_into_sections(body: str) -> list[tuple[int, str, str]]:
    """Split the body into ``[(section_number, label, body_text), ...]``."""
    lines = body.splitlines()
    sections: list[tuple[int, str, list[str]]] = []
    current: tuple[int, str, list[str]] | None = None
    for line in lines:
        m = _HEADING.match(line)
        if m:
            if current is not None:
                sections.append(current)
            current = (int(m.group(1)), m.group(2).strip(), [])
        elif current is not None:
            current[2].append(line)
    if current is not None:
        sections.append(current)
    return [(n, label, "\n".join(body_lines)) for n, label, body_lines in sections]


def _read_your_answer(section_body: str) -> str:
    """Grab text after ``YOUR ANSWER:`` up to the next ``## `` or end.

    If a ``YOUR ANSWER:`` marker is present, return ONLY content after
    it (even if empty — empty answer == "user didn't fill in"). If no
    marker, fall back to the first non-blockquote, non-list paragraph
    (covers casual fills that omit the marker).
    """
    lines = section_body.splitlines()
    has_marker = any(
        line.strip().upper().startswith("YOUR ANSWER:") for line in lines
    )
    answer_lines: list[str] = []

    if has_marker:
        # Marker-based mode: only collect lines after the marker
        in_answer = False
        for line in lines:
            stripped = line.strip()
            if not in_answer:
                if stripped.upper().startswith("YOUR ANSWER:"):
                    in_answer = True
                    tail = line.split(":", 1)[1].strip() if ":" in line else ""
                    if tail:
                        answer_lines.append(tail)
            else:
                answer_lines.append(line)
    else:
        # Marker-free mode: pick up free prose, skip questions / blockquotes
        for line in lines:
            stripped = line.strip()
            if (
                stripped
                and not stripped.startswith(">")
                and not stripped.startswith("-")
                and not stripped.startswith("#")
                and not stripped.endswith("?")  # likely a question prompt
            ):
                answer_lines.append(stripped)

    text = "\n".join(answer_lines).strip()
    # Strip trailing horizontal-rule / next-section markers
    text = re.sub(r"\n---\s*$", "", text).strip()
    return text


def _checked_lines(section_body: str) -> list[str]:
    """Return the labels of lines marked ``- [x]`` (any case / ✓)."""
    out: list[str] = []
    for line in section_body.splitlines():
        m = _CHECKED.match(line)
        if m:
            out.append(m.group(1).strip())
    return out


_GOAL_KEYS = {
    "Understand a literature field": "understand_literature",
    "Write a journal-club deck": "build_journal_club_deck",
    "Draft a manuscript section": "draft_manuscript_section",
    "Build a deep research report": "build_deep_research_report",
    "Analyze your own wet-lab data": "analyze_wet_lab_data",
    "Ongoing knowledge-management": "ongoing_kb",
}

_AUDIENCE_KEYS = {
    "Yourself": "self",
    "Lab members": "lab_members",
    "PI": "pi",
    "Journal club": "journal_club",
    "Conference talk": "conference",
    "Manuscript reviewers": "manuscript_reviewers",
    "Grant reviewers": "grant_reviewers",
}

_HAVE_KEYS = {
    "PDFs": "pdfs",
    "Notes": "notes",
    "Wet-lab data": "wet_lab_data",
    "Prior drafts": "prior_drafts",
    "Citations file": "citations_file",
    "Nothing": "nothing",
}

_STYLE_KEYS = {
    "Conservative": "hedged",
    "Direct": "direct",
    "Match the style of these papers": "match_papers",
    "Match my prior writing": "match_prior_writing",
    "No preference": "no_preference",
}

_DEADLINE_KEYS = {
    "One-shot": "one_shot",
    "Weekly check-ins": "weekly",
    "Specific date": "specific_date",
}


def _match_key(label: str, keymap: dict[str, str]) -> str:
    """Map a checkbox label to a snake_case key by prefix substring match."""
    for prefix, key in keymap.items():
        if label.lower().startswith(prefix.lower()):
            return key
    # Embedded "Other: <text>" or unknown — keep as free-form
    return f"other:{label.strip()}"


def _parse_goal_checkboxes(body: str) -> list[str]:
    return [_match_key(lbl, _GOAL_KEYS) for lbl in _checked_lines(body)]


def _parse_audience_checkboxes(body: str) -> list[str]:
    return [_match_key(lbl, _AUDIENCE_KEYS) for lbl in _checked_lines(body)]


def _parse_have_checkboxes(body: str) -> list[str]:
    return [_match_key(lbl, _HAVE_KEYS) for lbl in _checked_lines(body)]


def _parse_style_checkboxes(body: str) -> list[str]:
    return [_match_key(lbl, _STYLE_KEYS) for lbl in _checked_lines(body)]


def _parse_deadline_checkboxes(body: str) -> list[str]:
    return [_match_key(lbl, _DEADLINE_KEYS) for lbl in _checked_lines(body)]


def _parse_exclusions(body: str) -> dict[str, str | bool]:
    """Parse §5 — convert checked guard-rails into a dict."""
    exclusions: dict[str, str | bool] = {}
    for label in _checked_lines(body):
        low = label.lower()
        if "preprint" in low:
            exclusions["exclude_preprints"] = True
        elif "older than" in low:
            m = re.search(r"\b(19|20)\d{2}\b", label)
            if m:
                exclusions["min_year"] = int(m.group(0))
            else:
                exclusions["exclude_old_papers"] = True
        elif "non-english" in low or "non english" in low:
            exclusions["english_only"] = True
        elif "from" in low and "journal" in low:
            exclusions["exclude_journals_raw"] = label
        else:
            exclusions[f"other:{label}"] = True
    return exclusions


# ---------------------------------------------------------------------------
# Round-trip rendering helpers
# ---------------------------------------------------------------------------


def _checkbox(checked: bool, label: str) -> str:
    return f"- [{'x' if checked else ' '}] {label}"


def _render_filled_body(form: IntakeForm) -> str:
    """Render an :class:`IntakeForm` back into the template structure."""
    goal_set = set(form.goals)
    aud_set = set(form.audiences)
    have_set = set(form.have)
    style_set = set(form.style)
    deadline_set = set(form.deadlines)

    def _sec(keymap: dict[str, str], picks: set[str]) -> list[str]:
        out: list[str] = []
        for label, key in keymap.items():
            full_label_for_template = _FULL_LABELS.get(key, label)
            out.append(_checkbox(key in picks, full_label_for_template))
        # Add "Other:" entries
        for k in picks:
            if k.startswith("other:"):
                out.append(_checkbox(True, k.removeprefix("other:")))
        return out

    parts: list[str] = []
    parts.append(f"# Project intake — {form.topic or '<your project name>'}")
    parts.append("")
    parts.append("## 1. Topic (required)")
    parts.append("")
    parts.append("YOUR ANSWER: " + (form.topic or ""))
    parts.append("")
    parts.append("## 2. Goal (required)")
    parts.append("")
    parts.extend(_sec(_GOAL_KEYS, goal_set))
    parts.append("")
    parts.append("## 3. Audience (required)")
    parts.append("")
    parts.extend(_sec(_AUDIENCE_KEYS, aud_set))
    parts.append("")
    parts.append("## 4. What you already have")
    parts.append("")
    parts.extend(_sec(_HAVE_KEYS, have_set))
    parts.append("")
    parts.append("## 5. What you don't want")
    parts.append("")
    # Render exclusions in parser-friendly form so round-trip recovers them
    if form.exclusions.get("exclude_preprints"):
        parts.append("- [x] Don't include preprints")
    if "min_year" in form.exclusions:
        parts.append(
            f"- [x] Don't summarize papers older than {form.exclusions['min_year']}"
        )
    if form.exclusions.get("english_only"):
        parts.append("- [x] Skip non-English papers")
    if form.exclusions.get("exclude_old_papers"):
        parts.append("- [x] Don't summarize papers older than (unspecified)")
    # Anything else: write as a freeform other:
    for key, val in form.exclusions.items():
        if key in {
            "exclude_preprints",
            "min_year",
            "english_only",
            "exclude_old_papers",
        }:
            continue
        if key.startswith("other:"):
            parts.append(f"- [x] {key.removeprefix('other:')}")
        else:
            parts.append(f"- [x] {key} = {val}")
    parts.append("")
    parts.append("## 6. Style / voice")
    parts.append("")
    parts.extend(_sec(_STYLE_KEYS, style_set))
    parts.append("")
    parts.append("## 7. PI preferences (if relevant)")
    parts.append("")
    parts.append("YOUR ANSWER: " + (form.pi_preferences or ""))
    parts.append("")
    parts.append("## 8. Deadlines")
    parts.append("")
    parts.extend(_sec(_DEADLINE_KEYS, deadline_set))
    parts.append("")
    parts.append("## 9. Anything else")
    parts.append("")
    parts.append("YOUR ANSWER: " + (form.free_form or ""))
    parts.append("")
    return "\n".join(parts)


_FULL_LABELS = {
    "understand_literature": "Understand a literature field",
    "build_journal_club_deck": "Write a journal-club deck",
    "draft_manuscript_section": "Draft a manuscript section",
    "build_deep_research_report": "Build a deep research report",
    "analyze_wet_lab_data": "Analyze your own wet-lab data",
    "ongoing_kb": "Ongoing knowledge-management for an active project",
    "self": "Yourself (personal notes)",
    "lab_members": "Lab members (informal)",
    "pi": "PI / weekly meeting",
    "journal_club": "Journal club",
    "conference": "Conference talk",
    "manuscript_reviewers": "Manuscript reviewers / journal submission",
    "grant_reviewers": "Grant reviewers",
    "pdfs": "PDFs you've already collected",
    "notes": "Notes / outlines",
    "wet_lab_data": "Wet-lab data",
    "prior_drafts": "Prior drafts",
    "citations_file": "Citations file (.bib / .ris)",
    "nothing": "Nothing — vaultlab starts from scratch",
    "hedged": "Conservative / hedged",
    "direct": "Direct / declarative",
    "match_papers": "Match the style of these papers",
    "match_prior_writing": "Match my prior writing",
    "no_preference": "No preference",
    "one_shot": "One-shot — output delivered ASAP",
    "weekly": "Weekly check-ins",
    "specific_date": "Specific date",
}


# ---------------------------------------------------------------------------
# Empty template constant
# ---------------------------------------------------------------------------


_EMPTY_TEMPLATE = """\
---
template: project_intake
schema: vaultlab-intake/v1
fill_time_estimate: ~5 minutes
required_fields: [topic, goal, audience]
---

# Project intake — <your project name>

Copy this file to `<your-project-folder>/project_intake.md` and fill it
in. Then run `/onboard-project [path-to-project-folder]` — vaultlab
will read your answers, scan the folder, and ask only 3-5 follow-up
questions instead of 30.

> **5 minutes is the budget.** Skip anything that doesn't apply.

## 1. Topic (required)

What's this project about, in one sentence?

YOUR ANSWER:

## 2. Goal (required)

What are you trying to accomplish? Pick all that apply.

- [ ] Understand a literature field
- [ ] Write a journal-club deck
- [ ] Draft a manuscript section (Background / Methods / Results / Discussion)
- [ ] Build a deep research report (3000-5000 word review)
- [ ] Analyze your own wet-lab data
- [ ] Ongoing knowledge-management for an active project (live updates)

## 3. Audience (required)

Who's the output for? Pick all that apply.

- [ ] Yourself (personal notes)
- [ ] Lab members (informal)
- [ ] PI / weekly meeting
- [ ] Journal club
- [ ] Conference talk
- [ ] Manuscript reviewers / journal submission
- [ ] Grant reviewers

## 4. What you already have

Anything vaultlab should read first? Tick + path/info.

- [ ] PDFs you've already collected: <path or list of DOIs>
- [ ] Notes / outlines: <path>
- [ ] Wet-lab data: <type, e.g. "CODEX TIFF stacks at Z:/lab/data/2026-03/">
- [ ] Prior drafts: <path>
- [ ] Citations file (.bib / .ris): <path>
- [ ] Nothing — vaultlab starts from scratch

## 5. What you don't want

Helpful guard-rails. Tick all that apply.

- [ ] Don't include preprints
- [ ] Don't summarize papers older than <year>
- [ ] Don't include papers from <journal>
- [ ] Skip non-English papers

## 6. Style / voice

If outputs include writing, any voice preferences?

- [ ] Conservative / hedged ("X may suggest Y")
- [ ] Direct / declarative ("X shows Y")
- [ ] Match the style of these papers: <DOIs>
- [ ] Match my prior writing at <path>
- [ ] No preference

## 7. PI preferences (if relevant)

Things to mirror or avoid for your PI's review:

YOUR ANSWER:

## 8. Deadlines

- [ ] One-shot — output delivered ASAP, no follow-up
- [ ] Weekly check-ins — vaultlab updates the project page weekly
- [ ] Specific date: <when>

## 9. Anything else

Free-form. What would a smart collaborator need to know?

YOUR ANSWER:

---

When you're done, save this file IN your project folder and run:

    /onboard-project [path-to-project-folder]
"""
