"""Verify the JATS href→file labeling on a tiny synthetic fixture.

One positive (referenced graphic with a file), one negative (image not referenced),
one unmatched (graphic referenced in XML but no file on disk).
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image

# Make the sibling `labeling` module importable when pytest collects this file.
sys.path.insert(0, str(Path(__file__).resolve().parent))

import labeling  # noqa: E402


_NXML = """<?xml version="1.0" encoding="UTF-8"?>
<article xmlns:xlink="http://www.w3.org/1999/xlink">
  <body>
    <fig id="f1"><label>Figure 1</label>
      <graphic xlink:href="art.g001"/>
    </fig>
    <fig id="f2"><label>Figure 2</label>
      <graphic xlink:href="art.g002"/>
    </fig>
    <disp-formula><graphic xlink:href="art.e001"/></disp-formula>
  </body>
</article>
"""


def _png(path: Path, w: int, h: int) -> None:
    Image.new("RGB", (w, h), (123, 200, 50)).save(path)


def _build_article(tmp_path: Path) -> Path:
    art = tmp_path / "PMC_art"
    art.mkdir()
    (art / "art.nxml").write_text(_NXML, encoding="utf-8")
    _png(art / "art.g001.png", 600, 400)   # positive: referenced by <fig> Figure 1
    _png(art / "art.logo.png", 80, 40)      # negative: not referenced anywhere
    _png(art / "art.e001.png", 300, 30)     # negative: equation graphic (<disp-formula>, not <fig>)
    # art.g002 is referenced by <fig> Figure 2 but NO file exists -> unmatched href
    return art


def test_labeling_positive_negative_unmatched(tmp_path: Path) -> None:
    art = _build_article(tmp_path)
    result = labeling.label_article(art)

    by_name = {Path(i.path).name: i for i in result.images}

    # Positive: the file matching a <fig>//<graphic> href.
    assert by_name["art.g001.png"].label == "positive"
    # Negative: an image not referenced by any <fig> graphic...
    assert by_name["art.logo.png"].label == "negative"
    # ...including a <disp-formula> equation graphic (referenced, but not inside <fig>).
    assert by_name["art.e001.png"].label == "negative"

    # Unmatched: <fig> graphic href art.g002 has no on-disk file — counted, not assigned.
    assert result.unmatched_hrefs == ["art.g002"]
    assert "art.g002" not in {Path(i.path).stem for i in result.images}

    # Exactly one positive, two negatives, three candidate images.
    assert result.n_positive == 1
    assert result.n_negative == 2
    assert result.n_candidate_images == 3
    assert result.has_xml and result.parseable_xml
    # Features are read for the positive.
    assert by_name["art.g001.png"].min_dim_px == 400
    assert by_name["art.g001.png"].size_bytes > 0


def test_discover_articles_finds_the_package(tmp_path: Path) -> None:
    _build_article(tmp_path)
    arts = labeling.discover_articles(tmp_path)
    assert [a.name for a in arts] == ["PMC_art"]


def test_no_xml_article_is_flagged(tmp_path: Path) -> None:
    art = tmp_path / "PMC_noxml"
    art.mkdir()
    _png(art / "something.png", 500, 500)  # image but no .nxml
    result = labeling.label_article(art)
    assert result.has_xml is False
    assert result.parseable_xml is False
    # With no XML there are no positives; the lone image is a negative.
    assert result.n_positive == 0
    assert result.n_negative == 1
