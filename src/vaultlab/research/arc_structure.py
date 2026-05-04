"""Variable-length arc structures for vaultlab lineage narratives.

Background
----------
The original lineage arc was hardcoded as three paragraphs: ``history``,
``development``, and ``sota``. That's the right shape for a 3-minute
journal-club intro on a small corpus. It's the wrong shape for:

* A serious literature review (you want 8-15 sections, sub-bucketed by
  methods / applications / theory / clinical / open questions / etc.)
* A grant aims background section (1-2 paragraphs, very different
  audience framing)
* A thesis chapter introduction (5-10 sections, builds the reader
  toward the chapter's argument)
* A landscape report (cross-cuts by sub-topic rather than by maturity)

This module makes the arc structure a first-class object: a list of
:class:`ArcSection` definitions, each with an ``id`` (binning key), a
``title`` (rendered heading), a ``criterion`` (LLM hint for which papers
belong here), and a ``target_paragraphs`` count.

The bucketer takes the structure and decides which section each paper
belongs to. The narrator takes the structure and writes the indicated
number of paragraphs per section. Downstream consumers (slide deck,
summary tables) read the section IDs from the corpus metadata.

Design choices
--------------
* **IDs are the canonical key** — used for routing in code, embedded in
  ``corpus.metrics.year_buckets``, etc. Not user-facing.
* **Titles are the heading text** — what shows up in markdown.
* **Criteria drive the LLM** — the bucketer reads this string when
  deciding which section a paper belongs to. So changing a section's
  criterion changes how papers get sorted.
* **target_paragraphs is a guide, not a hard cap** — the narrator can
  use 1 paragraph when the corpus has nothing for that section, or
  2 paragraphs when there's lots of relevant material.

Three named templates ship out of the box:

* :data:`SHORT` — 3 sections (history / development / sota), the legacy
  default. Used when ``arc_structure="short"`` or unspecified.
* :data:`STANDARD` — 6 sections covering foundations / methods / scale /
  applications / sota / open questions. Suitable for richer journal-club
  decks or short technical briefs.
* :data:`REVIEW_PAPER` — 10 sections covering full review-paper scope:
  intro / theoretical foundations / early methods / methodological
  refinements / instrumentation / large-scale applications / specialised
  domains / sota / limitations / future directions.

Custom structures are supported via :func:`make_custom_structure`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ArcSection:
    """One section in a lineage arc.

    Attributes:
        id: Canonical key used in code (snake_case, no spaces). Embedded
            in ``corpus.metrics.year_buckets`` and downstream artifacts.
        title: Human-readable section heading rendered in markdown
            (e.g. ``"State of the art"``).
        criterion: One-sentence LLM hint describing which papers belong
            to this section. Used in the bucketer's prompt.
        target_paragraphs: How many paragraphs the narrator should aim
            for in this section. The narrator may produce fewer when the
            corpus is sparse for this section.
    """

    id: str
    title: str
    criterion: str
    target_paragraphs: int = 1


@dataclass(frozen=True)
class ArcStructure:
    """A complete lineage-arc structure: ordered list of sections.

    Attributes:
        name: Human-readable structure name (e.g. ``"short"``,
            ``"review-paper"``). Used in logs and provenance receipts.
        sections: Ordered list of :class:`ArcSection`. Sections are
            rendered top-to-bottom in the output markdown.
        audience: One-line description of the intended reader, which
            the narrator uses to tune voice (e.g. ``"journal club
            audience, technical but pacing-aware"`` vs ``"grant review
            committee, results-focused"``).
    """

    name: str
    sections: list[ArcSection] = field(default_factory=list)
    audience: str = "general technical audience familiar with the field"

    @property
    def section_ids(self) -> list[str]:
        return [s.id for s in self.sections]

    @property
    def total_target_paragraphs(self) -> int:
        return sum(s.target_paragraphs for s in self.sections)

    def section_by_id(self, section_id: str) -> ArcSection | None:
        for s in self.sections:
            if s.id == section_id:
                return s
        return None


# ---------------------------------------------------------------------------
# Predefined templates
# ---------------------------------------------------------------------------


SHORT: ArcStructure = ArcStructure(
    name="short",
    audience="journal-club audience; reader knows the broad field but not the specific topic",
    sections=[
        ArcSection(
            id="history",
            title="History",
            criterion=(
                "Foundational method, precursor concept, or paradigm-defining "
                "work for the topic — regardless of publication year."
            ),
            target_paragraphs=1,
        ),
        ArcSection(
            id="development",
            title="Development",
            criterion=(
                "Intermediate refinement, scaling, methodological adaptation, "
                "mid-arc work between foundation and current frontier."
            ),
            target_paragraphs=1,
        ),
        ArcSection(
            id="sota",
            title="State of the art",
            criterion=(
                "Current frontier — most recent meaningful advance, even if "
                "not the most-recent paper by date. Incremental applications "
                "of older methods are DEVELOPMENT, not SOTA."
            ),
            target_paragraphs=1,
        ),
    ],
)


STANDARD: ArcStructure = ArcStructure(
    name="standard",
    audience="researcher new to the topic; expects a teaching-quality narrative arc with concrete citations",
    sections=[
        ArcSection(
            id="foundations",
            title="Foundations",
            criterion=(
                "The conceptual or theoretical groundwork on which the field "
                "was built — including precursor methods or formal results "
                "predating the topic's named emergence."
            ),
            target_paragraphs=1,
        ),
        ArcSection(
            id="seminal_methods",
            title="Seminal methods",
            criterion=(
                "The paradigm-defining method(s) that gave the topic its "
                "name and current shape — first-of-kind technical "
                "contributions."
            ),
            target_paragraphs=1,
        ),
        ArcSection(
            id="refinements",
            title="Refinements & scaling",
            criterion=(
                "Methodological refinements, parameter improvements, "
                "scaling-up work, and protocol simplifications that made "
                "the seminal method usable by new groups."
            ),
            target_paragraphs=1,
        ),
        ArcSection(
            id="applications",
            title="Applications",
            criterion=(
                "Domain-specific applications of the methodology — clinical "
                "studies, biological discoveries, application to new tissue "
                "types or species. The 'what was learned' rather than 'what "
                "was built'."
            ),
            target_paragraphs=1,
        ),
        ArcSection(
            id="sota",
            title="State of the art",
            criterion=(
                "Current frontier — most recent meaningful advance, including "
                "novel methodological directions, cross-modal integrations, "
                "and new analysis paradigms."
            ),
            target_paragraphs=1,
        ),
        ArcSection(
            id="open_questions",
            title="Open questions",
            criterion=(
                "Papers that explicitly identify or analyze gaps, limitations, "
                "benchmarking failures, or unresolved tensions. May overlap "
                "with SOTA but the framing is what's NOT yet solved."
            ),
            target_paragraphs=1,
        ),
    ],
)


REVIEW_PAPER: ArcStructure = ArcStructure(
    name="review-paper",
    audience="readers of a peer-reviewed methods review; expect comprehensive coverage with cross-citation depth",
    sections=[
        ArcSection(
            id="introduction",
            title="Introduction",
            criterion=(
                "Papers that frame the topic's significance, motivate the "
                "field's existence, or define its scope. Often review "
                "articles or perspective pieces rather than primary research."
            ),
            target_paragraphs=2,
        ),
        ArcSection(
            id="theoretical_foundations",
            title="Theoretical foundations",
            criterion=(
                "Mathematical, computational, or conceptual underpinnings — "
                "often older work from adjacent fields that the topic "
                "imported and adapted."
            ),
            target_paragraphs=1,
        ),
        ArcSection(
            id="early_methods",
            title="Early methods",
            criterion=(
                "First-generation methods that prefigured or directly "
                "preceded the topic's seminal moment — methodological "
                "ancestors."
            ),
            target_paragraphs=1,
        ),
        ArcSection(
            id="seminal_methods",
            title="Seminal methods",
            criterion=(
                "The paradigm-defining method(s) that gave the topic its "
                "name and its current shape."
            ),
            target_paragraphs=2,
        ),
        ArcSection(
            id="methodological_refinements",
            title="Methodological refinements",
            criterion=(
                "Improvements to the seminal method — better protocols, "
                "scaling, accuracy, throughput, ease of use."
            ),
            target_paragraphs=2,
        ),
        ArcSection(
            id="instrumentation",
            title="Instrumentation & infrastructure",
            criterion=(
                "Hardware, software, and shared-resource papers that "
                "enabled the methodology — sequencing platforms, imaging "
                "systems, analysis pipelines, public datasets."
            ),
            target_paragraphs=1,
        ),
        ArcSection(
            id="large_scale_applications",
            title="Large-scale applications",
            criterion=(
                "Applications at meaningful scale — atlas projects, "
                "consortium studies, large clinical cohorts. The 'big "
                "deliverables' the methodology has enabled."
            ),
            target_paragraphs=2,
        ),
        ArcSection(
            id="specialised_domains",
            title="Specialised domains",
            criterion=(
                "Adaptations of the methodology to specific tissues, "
                "organisms, or research questions — narrower in scope "
                "than large-scale applications."
            ),
            target_paragraphs=1,
        ),
        ArcSection(
            id="sota",
            title="State of the art",
            criterion=(
                "Current frontier — novel directions, cross-modal "
                "integrations, new analysis paradigms, and recent "
                "high-impact advances."
            ),
            target_paragraphs=2,
        ),
        ArcSection(
            id="limitations_and_future",
            title="Limitations & future directions",
            criterion=(
                "Papers that explicitly identify limitations, benchmark "
                "failures, or propose future research directions."
            ),
            target_paragraphs=1,
        ),
    ],
)


_TEMPLATES: dict[str, ArcStructure] = {
    "short": SHORT,
    "standard": STANDARD,
    "review-paper": REVIEW_PAPER,
    "review_paper": REVIEW_PAPER,  # alias
}


def get_named_structure(name: str) -> ArcStructure:
    """Return a predefined :class:`ArcStructure` by name.

    Recognised names: ``"short"``, ``"standard"``, ``"review-paper"``.

    Raises:
        KeyError: When ``name`` is not a known template.
    """
    key = name.strip().lower()
    if key not in _TEMPLATES:
        raise KeyError(
            f"Unknown arc structure {name!r}. "
            f"Known: {sorted(set(_TEMPLATES.keys()))}"
        )
    return _TEMPLATES[key]


def make_custom_structure(
    name: str,
    sections: list[dict[str, Any]],
    audience: str = "general technical audience familiar with the field",
) -> ArcStructure:
    """Build a custom :class:`ArcStructure` from raw section dicts.

    Args:
        name: A name for this structure (used in logs / provenance).
        sections: List of dicts with keys ``id``, ``title``, ``criterion``,
            and optional ``target_paragraphs`` (defaults to 1).
        audience: Audience hint for the narrator.

    Returns:
        The constructed :class:`ArcStructure`.

    Raises:
        ValueError: If a section dict is missing a required key, or if
            two sections share the same id.
    """
    seen_ids: set[str] = set()
    arc_sections: list[ArcSection] = []
    for sd in sections:
        sid = sd.get("id")
        title = sd.get("title")
        criterion = sd.get("criterion")
        if not sid or not title or not criterion:
            raise ValueError(
                f"section dict missing required field "
                f"(id/title/criterion): {sd!r}"
            )
        if sid in seen_ids:
            raise ValueError(f"duplicate section id {sid!r}")
        seen_ids.add(sid)
        arc_sections.append(
            ArcSection(
                id=str(sid),
                title=str(title),
                criterion=str(criterion),
                target_paragraphs=int(sd.get("target_paragraphs", 1)),
            )
        )
    if not arc_sections:
        raise ValueError("custom structure must have at least one section")
    return ArcStructure(
        name=str(name), sections=arc_sections, audience=audience
    )


def resolve_structure(
    structure: str | ArcStructure | None,
) -> ArcStructure:
    """Coerce a structure spec into an :class:`ArcStructure`.

    Accepts:

    * ``None`` → :data:`SHORT` (the legacy 3-paragraph default).
    * ``str`` → looked up via :func:`get_named_structure`.
    * :class:`ArcStructure` → returned as-is.
    """
    if structure is None:
        return SHORT
    if isinstance(structure, ArcStructure):
        return structure
    if isinstance(structure, str):
        return get_named_structure(structure)
    raise TypeError(
        f"Expected None, str, or ArcStructure; got {type(structure).__name__}"
    )


# ---------------------------------------------------------------------------
# Scope → depth coupling (added 2026-05-01)
# ---------------------------------------------------------------------------


# Default depth flag per scope. Bobby's principle (2026-05-01):
# review-paper scope should automatically read MORE papers, not just
# bucket the same papers into more sections. Coupling scope to depth
# encodes "want a comprehensive review? read everything cached."
#
# Users can still override with --depth explicitly. The coupling is a
# DEFAULT, not a hard constraint.
_SCOPE_TO_DEFAULT_DEPTH: dict[str, str] = {
    "short": "fast",          # 3 sections, ~3 paragraphs → 20 Tier-A enough
    "standard": "balanced",    # 6 sections, ~6 paragraphs → 50 Tier-A
    "review-paper": "thorough",  # 10 sections, ~16 paragraphs → all cached
    "review_paper": "thorough",  # alias
}


def default_depth_for_scope(scope: str | ArcStructure | None) -> str:
    """Return the recommended ``depth`` flag for a given scope.

    Args:
        scope: ``None`` / ``str`` / :class:`ArcStructure`. The scope's
            ``name`` field is consulted; falls back to ``"balanced"``
            for any unrecognized scope.

    Returns:
        One of ``"fast"`` / ``"balanced"`` / ``"thorough"`` / ``"complete"``.
        ``"balanced"`` is the conservative fallback when the scope is
        unrecognized.
    """
    if scope is None:
        return "fast"
    if isinstance(scope, ArcStructure):
        name = scope.name
    else:
        name = str(scope)
    return _SCOPE_TO_DEFAULT_DEPTH.get(name.strip().lower(), "balanced")


__all__ = [
    "ArcSection",
    "ArcStructure",
    "SHORT",
    "STANDARD",
    "REVIEW_PAPER",
    "default_depth_for_scope",
    "get_named_structure",
    "make_custom_structure",
    "resolve_structure",
]
