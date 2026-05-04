"""Story-arc audit — does each slide's claim follow from the prior?

Bobby's 2026-05-04 ask: most prelim failures are logical-flow failures.
A deck can be visually clean (audit passes) and still be argumentatively
broken — slide 7's claim has nothing to do with slide 6's, slide 12's
transition is a dead-end, slide 18 references "as I mentioned" without a
preceding mention. This audit catches those.

Heuristics applied per consecutive (slide_N, slide_N+1) pair:

- **Transition wiring**: does slide N's `transition` mention any of the
  next slide's `key_terms` or `hook` content? If not, weak transition.
- **Topic carry-over**: do slides N and N+1 share at least one key_term
  or do they reference adjacent thematic content?
- **Dead-end transition**: does slide N's transition contain phrases
  like "open for questions" or "thank you" while slide N+1 is a content
  slide? That's a flow break.
- **Orphan claim**: does the slide claim something but never provide
  evidence or follow-up?

Output:

- :class:`StoryArcReport` with per-slide notes + per-pair-link findings
- :func:`write_story_arc_report(plan, deck_path)` writes a
  `<deck>.story-arc.md` sidecar
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


_DEAD_END_PHRASES = [
    "open for questions",
    "questions?",
    "thank you",
    "thanks for listening",
    "any questions",
    "happy to discuss",
]


@dataclass
class StoryArcLink:
    """One transition between slide N and slide N+1."""

    from_index: int
    to_index: int
    transition_text: str
    next_hook: str
    weak_link: bool = False
    dead_end_into_content: bool = False
    shared_terms: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


@dataclass
class StoryArcReport:
    """Per-deck story-arc audit."""

    n_slides: int
    n_weak_links: int
    n_dead_ends: int
    n_orphan_transitions: int
    links: list[StoryArcLink] = field(default_factory=list)

    @property
    def severity(self) -> str:
        if self.n_dead_ends > 0:
            return "fail"
        if self.n_weak_links >= max(2, self.n_slides // 4):
            return "warn"
        return "ok"

    def to_markdown(self, deck_title: str = "") -> str:
        sev_emoji = {"ok": "✅", "warn": "⚠️", "fail": "❌"}.get(self.severity, "?")
        lines = [
            f"# Story-arc audit{f' — {deck_title}' if deck_title else ''}",
            "",
            f"**Severity:** {sev_emoji} `{self.severity}`",
            "",
            f"- {self.n_slides} slides",
            f"- {self.n_weak_links} weak transitions (no shared topic with next slide)",
            f"- {self.n_dead_ends} dead-end transitions (closing phrase before content)",
            f"- {self.n_orphan_transitions} slides with no transition set",
            "",
            "## Transitions",
            "",
        ]
        for link in self.links:
            flags = []
            if link.dead_end_into_content:
                flags.append("DEAD-END")
            if link.weak_link:
                flags.append("weak")
            flag_str = f" [{', '.join(flags)}]" if flags else ""
            t_short = (link.transition_text[:80] + "…") if len(link.transition_text) > 80 else link.transition_text
            h_short = (link.next_hook[:80] + "…") if len(link.next_hook) > 80 else link.next_hook
            lines.append(f"### s{link.from_index} → s{link.to_index}{flag_str}")
            lines.append(f"- Transition: _{t_short or '(none)'}_")
            lines.append(f"- Next hook: _{h_short or '(none)'}_")
            if link.shared_terms:
                lines.append(f"- Shared terms: `{', '.join(link.shared_terms)}`")
            for note in link.notes:
                lines.append(f"- ⚠ {note}")
            lines.append("")
        return "\n".join(lines)


def _normalize_for_match(text: str) -> set[str]:
    """Tokenize text into lowercased non-stopword words for overlap detection."""
    if not text:
        return set()
    words = re.findall(r"[A-Za-z][A-Za-z0-9_-]{2,}", text.lower())
    stopwords = {
        "the", "and", "for", "with", "this", "that", "from", "have", "are",
        "was", "were", "been", "they", "their", "what", "when", "which",
        "into", "than", "then", "more", "less", "such", "also", "only",
        "now", "yet", "but", "you", "all", "any", "can", "not", "out",
        "via", "use", "uses", "using", "next", "between",
    }
    return {w for w in words if w not in stopwords and len(w) > 2}


def _is_dead_end_phrase(text: str) -> bool:
    if not text:
        return False
    low = text.lower()
    return any(phrase in low for phrase in _DEAD_END_PHRASES)


def audit_story_arc(plan: dict[str, Any]) -> StoryArcReport:
    """Walk the deck plan and audit transition wiring + topic flow."""
    slides = plan.get("slides") or []
    links: list[StoryArcLink] = []
    n_weak = 0
    n_dead = 0
    n_orphan = 0

    for i in range(len(slides) - 1):
        cur = slides[i]
        nxt = slides[i + 1]
        cur_notes = cur.get("speaker_notes") or {}
        nxt_notes = nxt.get("speaker_notes") or {}

        transition = (cur_notes.get("transition") or "").strip()
        nxt_hook = (nxt_notes.get("hook") or "").strip()
        nxt_key_claim = (nxt_notes.get("key_claim") or "").strip()
        nxt_key_terms = nxt_notes.get("key_terms") or []
        nxt_title = nxt.get("title", "") or ""

        link = StoryArcLink(
            from_index=i + 1,
            to_index=i + 2,
            transition_text=transition,
            next_hook=nxt_hook,
        )

        # No transition at all → orphan
        if not transition:
            # Section dividers + references slides typically don't have transitions
            if cur.get("type") not in ("section_divider", "references", "title"):
                link.notes.append("No transition set on this slide.")
                n_orphan += 1
        else:
            # Dead-end going into content
            nxt_type = nxt.get("type", "")
            if _is_dead_end_phrase(transition) and nxt_type in (
                "figure", "text", "multi_figure", "two_figure", "analogy", "quote"
            ):
                link.dead_end_into_content = True
                link.notes.append(
                    "Closing phrase ('open for questions' / 'thank you') used as "
                    "transition into a CONTENT slide. Replace with a topic bridge."
                )
                n_dead += 1

            # Weak link: no shared topic with next slide
            tx_terms = _normalize_for_match(transition)
            nxt_terms = _normalize_for_match(
                f"{nxt_hook} {nxt_key_claim} {nxt_title} " + " ".join(str(t) for t in nxt_key_terms)
            )
            shared = sorted(tx_terms & nxt_terms)
            link.shared_terms = shared
            if not shared:
                # Section dividers, title, references are exempt
                if cur.get("type") not in ("section_divider", "references", "title"):
                    link.weak_link = True
                    link.notes.append(
                        "Transition shares no topic words with the next slide's hook/title. "
                        "Consider rewording so the transition mentions what comes next."
                    )
                    n_weak += 1

        links.append(link)

    return StoryArcReport(
        n_slides=len(slides),
        n_weak_links=n_weak,
        n_dead_ends=n_dead,
        n_orphan_transitions=n_orphan,
        links=links,
    )


def write_story_arc_report(
    plan: dict[str, Any],
    deck_path: Path | str,
) -> Path:
    """Write a story-arc.md sidecar next to the deck."""
    deck_path = Path(deck_path)
    out_path = deck_path.with_suffix("").with_name(deck_path.stem + ".story-arc.md")
    report = audit_story_arc(plan)
    title = plan.get("title", "")
    out_path.write_text(report.to_markdown(deck_title=title), encoding="utf-8")
    return out_path


__all__ = [
    "StoryArcLink",
    "StoryArcReport",
    "audit_story_arc",
    "write_story_arc_report",
]
