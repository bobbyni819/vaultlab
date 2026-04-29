"""Slide and Deck data classes — declarative deck representation.

Backend-independent. The renderer (``vaultlab.slides.render``) is the only
module that talks to ``python-pptx``; everything else operates on these
dataclasses.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

# Layout names supported by the starter layouts module
SUPPORTED_LAYOUTS: frozenset[str] = frozenset(
    {"title", "content_with_bullets", "figure_with_caption"}
)


@dataclass
class Slide:
    """One slide in a deck.

    Fields are deliberately layout-agnostic — each layout reads only the fields
    it needs. Unused fields are ignored.

    Attributes
    ----------
    layout
        Layout name from ``SUPPORTED_LAYOUTS``.
    title
        Slide title (rendered as the H1 of the slide).
    subtitle
        Subtitle for ``title`` layout. Ignored elsewhere.
    bullets
        Bullet-list content for ``content_with_bullets``.
    figure_path
        Path to a ``.png`` / ``.jpg`` for ``figure_with_caption``. Resolved
        relative to ``Deck.working_dir`` if not absolute.
    caption
        Caption text for ``figure_with_caption``.
    speaker_notes
        Optional speaker notes (rendered into the .pptx notes panel).
    """

    layout: str
    title: str = ""
    subtitle: str = ""
    bullets: list[str] = field(default_factory=list)
    figure_path: str | None = None
    caption: str = ""
    speaker_notes: str = ""

    def __post_init__(self) -> None:
        if self.layout not in SUPPORTED_LAYOUTS:
            raise ValueError(
                f"Unsupported layout {self.layout!r}. Supported: {sorted(SUPPORTED_LAYOUTS)}"
            )


@dataclass
class Deck:
    """A complete slide deck.

    Attributes
    ----------
    title
        Deck title (used in the .pptx properties + as a default for the
        opening title slide).
    slides
        Ordered list of slides.
    theme
        Theme name. Defaults to ``"default"``.
    working_dir
        Used to resolve relative ``figure_path`` values.
    metadata
        Free-form provenance attached to the deck — kept in the file
        properties (``vaultlab_provenance`` key when supported by the backend).
    """

    title: str
    slides: list[Slide] = field(default_factory=list)
    theme: str = "default"
    working_dir: Path | None = None
    metadata: dict[str, str] = field(default_factory=dict)

    def add(self, slide: Slide) -> None:
        """Append a slide. Useful for building decks programmatically."""
        self.slides.append(slide)

    def __len__(self) -> int:  # convenience
        return len(self.slides)
