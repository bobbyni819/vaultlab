"""JATS labeling for the figures-filter benchmark.

Builds deterministic positive/negative labels for the image files in a PMC OA
package, using the article's JATS `.nxml` as ground truth — no human labeling, no
image-content matching.

Ground truth
------------
- **positive** — an image file whose stem matches an `xlink:href` of a `<graphic>`
  that sits inside a `<fig>` (a real figure graphic).
- **negative** — any other image file in the package (publisher logos, equation
  graphics from `<disp-formula>`/`<inline-graphic>`, icons — the junk class).
- **unmatched** — a `<fig>` graphic href with NO on-disk file, or an AMBIGUOUS href
  (matches >1 file). Never silently assigned to positive/negative; reported instead.

href→file rule
--------------
For href ``H``: ``stem_H = basename(H) with a trailing image extension removed``.
A file ``F`` matches iff ``F.stem.lower() == stem_H.lower()``. Exactly one match →
that file is the positive; zero → unmatched (no file); many → ambiguous.
"""

from __future__ import annotations

import os
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

# Security: JATS .nxml can carry DOCTYPEs/entities, so prefer defusedxml (blocks XXE
# + billion-laughs) when it is available in the environment. We do NOT add it as a
# hard dependency — fall back to stdlib ElementTree if absent (per the task's
# "stdlib otherwise" rule). Either way a rejected/unparseable file is caught and
# COUNTED as an unparseable-XML paper, never silently dropped.
try:
    from defusedxml.ElementTree import parse as _xml_parse  # type: ignore[import-untyped]
except ImportError:  # pragma: no cover - defusedxml is normally present
    _xml_parse = ET.parse

_XLINK_HREF = "{http://www.w3.org/1999/xlink}href"
_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".tif", ".tiff", ".bmp"}


@dataclass
class ImageRecord:
    """One labeled, feature-read candidate image."""

    path: Path
    article: str
    label: str  # "positive" | "negative"
    min_dim_px: int
    size_bytes: int


@dataclass
class ArticleResult:
    article: str
    images: list[ImageRecord] = field(default_factory=list)
    unmatched_hrefs: list[str] = field(default_factory=list)  # declared fig graphic, no file
    ambiguous_hrefs: list[str] = field(default_factory=list)  # declared fig graphic, >1 file
    unreadable_files: list[str] = field(default_factory=list)  # image present, dims unreadable
    n_fig_hrefs: int = 0
    n_candidate_images: int = 0
    has_xml: bool = False
    parseable_xml: bool = False

    @property
    def n_positive(self) -> int:
        return sum(1 for i in self.images if i.label == "positive")

    @property
    def n_negative(self) -> int:
        return sum(1 for i in self.images if i.label == "negative")


def _localname(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def _href_stem(href: str) -> str:
    """basename of href, minus a trailing image extension, lowercased."""
    name = Path(href.strip()).name
    p = Path(name)
    stem = p.stem if p.suffix.lower() in _IMAGE_EXTS else name
    return stem.lower()


def parse_fig_hrefs(nxml_path: str | Path) -> list[str] | None:
    """Return xlink:hrefs of `<graphic>` elements inside `<fig>` in a JATS file.

    Returns ``None`` if the XML cannot be parsed (so the caller can count it as an
    unparseable-XML paper rather than confusing it with an article that has no figs).
    """
    try:
        tree = _xml_parse(str(nxml_path))
    except Exception:
        # ParseError / OSError / defusedxml entity-forbidden — all mean "not
        # parseable for our purposes". The caller counts this as unparseable XML.
        return None
    hrefs: list[str] = []
    for el in tree.getroot().iter():
        if _localname(el.tag) != "fig":
            continue
        for g in el.iter():
            if _localname(g.tag) == "graphic":
                href = g.get(_XLINK_HREF) or g.get("href")
                if href and href.strip():
                    hrefs.append(href.strip())
    return hrefs


def match_hrefs_to_files(
    hrefs: list[str], image_files: list[Path]
) -> tuple[set[Path], list[str], list[str]]:
    """Map fig hrefs → files. Returns (positive_files, unmatched_hrefs, ambiguous_hrefs)."""
    by_stem: dict[str, list[Path]] = {}
    for f in image_files:
        by_stem.setdefault(f.stem.lower(), []).append(f)

    positives: set[Path] = set()
    unmatched: list[str] = []
    ambiguous: list[str] = []
    for h in hrefs:
        matches = by_stem.get(_href_stem(h), [])
        if len(matches) == 1:
            positives.add(matches[0])
        elif not matches:
            unmatched.append(h)
        else:
            ambiguous.append(h)
    return positives, unmatched, ambiguous


def read_image_features(path: str | Path) -> tuple[int, int] | None:
    """(min_dimension_px, size_bytes) for an image file, or None if unreadable.

    ``size_bytes`` is the **PNG-re-encoded** size, NOT the raw source-file size:
    figures.py saves each extracted raster as a PNG (``pix.save``) and stats *that*
    file, so its `min_bytes` default is calibrated against PNG sizes. A JPG on disk
    is far smaller than its PNG re-encoding, so using raw file bytes would make the
    `min_bytes` axis non-comparable to the default. We mirror the PNG-save here.
    """
    try:
        os.path.getsize(path)  # existence / readability probe
    except OSError:
        return None
    try:
        from io import BytesIO

        from PIL import Image

        with Image.open(path) as im:
            w, h = im.size
            buf = BytesIO()
            try:
                im.save(buf, format="PNG")  # native mode, as figures.py saves the pixmap
            except (OSError, ValueError, KeyError):
                buf = BytesIO()
                im.convert("RGB").save(buf, format="PNG")  # CMYK/other → RGB, as figures.py does
            png_size = buf.getbuffer().nbytes
    except Exception:
        return None
    return min(int(w), int(h)), int(png_size)


def _has_article_content(d: Path) -> bool:
    # Direct children only: a PMC OA package is flat (nxml + images in one dir).
    # Avoids grouping multiple packages or bleeding nested images across articles.
    for p in d.iterdir():
        if p.is_file() and (p.suffix.lower() == ".nxml" or p.suffix.lower() in _IMAGE_EXTS):
            return True
    return False


def discover_articles(corpus_dir: str | Path) -> list[Path]:
    """Article unit = a directory holding ≥1 `.nxml` or image file.

    Each immediate subdirectory of the corpus with content is one article; if the
    corpus dir is itself a single flat package, it is the lone article.
    """
    root = Path(corpus_dir)
    if not root.exists():
        return []
    units = [d for d in sorted(root.iterdir()) if d.is_dir() and _has_article_content(d)]
    if not units and _has_article_content(root):
        units.append(root)
    return units


def label_article(article_dir: str | Path) -> ArticleResult:
    """Parse the article's JATS, label every image file, and read its features."""
    article_dir = Path(article_dir)
    # Direct children only — a PMC OA package is flat. (rglob would risk pulling a
    # sibling package's images/nxml into this article under nested layouts.)
    nxmls = sorted(article_dir.glob("*.nxml"))
    image_files = sorted(
        p for p in article_dir.glob("*") if p.is_file() and p.suffix.lower() in _IMAGE_EXTS
    )
    has_xml = bool(nxmls)

    all_hrefs: list[str] = []
    parseable = False
    for nx in nxmls:
        hs = parse_fig_hrefs(nx)
        if hs is not None:
            parseable = True
            all_hrefs.extend(hs)

    positives, unmatched, ambiguous = match_hrefs_to_files(all_hrefs, image_files)

    result = ArticleResult(
        article=article_dir.name,
        unmatched_hrefs=unmatched,
        ambiguous_hrefs=ambiguous,
        n_fig_hrefs=len(all_hrefs),
        n_candidate_images=len(image_files),
        has_xml=has_xml,
        parseable_xml=has_xml and parseable,
    )
    for f in image_files:
        feats = read_image_features(f)
        if feats is None:
            result.unreadable_files.append(str(f))
            continue
        min_dim, size = feats
        label = "positive" if f in positives else "negative"
        result.images.append(
            ImageRecord(path=f, article=article_dir.name, label=label,
                        min_dim_px=min_dim, size_bytes=size)
        )
    return result
