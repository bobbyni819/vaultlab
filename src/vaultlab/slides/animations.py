"""OOXML-level animation engine for vaultlab.slides.

Lifted from ``bobby_slides._animation`` (bobby-tools, 2026-04).

python-pptx does not support animations natively (it's explicitly out of
scope in the library's design). We build animation XML directly and inject
it into the slide's ``p:timing`` element.

Public surface:

- :func:`appear_on_click` — show shape on the Nth click.
- :func:`fade_on_click` — fade-in entrance on Nth click.
- :func:`bullet_reveal` — each paragraph appears on its own click.
- :func:`panel_buildup` — each shape (or shape group) appears on a click.
- :func:`appear_together_on_click` — multiple shapes share one click.

Click indices are 0-indexed. A shape with no animation is shown from slide
start.

References:
- ECMA-376 Part 1 §19.5 (PresentationML animations).
- "presetID/presetClass" preset codes from MS Office reference.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

# OOXML namespace map — needed for lxml element creation
_NSMAP: dict[str, str] = {
    "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
}

_P = f"{{{_NSMAP['p']}}}"


# Preset IDs from MS Office reference
# https://docs.microsoft.com/en-us/openspecs/office_standards/ms-oi29500-1/
_PRESET_APPEAR = ("1", "entr", "0")  # presetID, presetClass, presetSubtype
_PRESET_FADE = ("10", "entr", "0")


def _next_id(start: int = 100) -> Any:
    """Return a counter that yields unique sequential IDs."""
    counter = [start]

    def _gen() -> int:
        counter[0] += 1
        return counter[0]

    return _gen


def appear_on_click(slide: Any, shape: Any, click_index: int = 0) -> None:
    """Make ``shape`` appear on the (click_index)-th click within ``slide``."""
    _add_click_effect(slide, shape, click_index, _PRESET_APPEAR)


def fade_on_click(slide: Any, shape: Any, click_index: int = 0) -> None:
    """Fade ``shape`` in on the (click_index)-th click within ``slide``."""
    _add_click_effect(slide, shape, click_index, _PRESET_FADE)


def bullet_reveal(slide: Any, text_frame: Any) -> None:
    """Reveal each paragraph in a text frame on a separate click.

    The first paragraph appears on click 1, second on click 2, etc.
    """
    from lxml import etree

    sp = text_frame._txBody.getparent()  # shape XML element
    shape_id = _shape_id(sp)
    n_paragraphs = len(text_frame.paragraphs)
    if n_paragraphs == 0:
        return

    timing = _ensure_timing(slide)
    main_seq = _ensure_main_seq(timing)
    next_id = _next_id(_max_id(timing))

    for i in range(n_paragraphs):
        click_xml = _build_click_effect_xml(
            shape_id=shape_id,
            preset=_PRESET_APPEAR,
            next_id=next_id,
            paragraph_index=i,
        )
        main_seq.append(etree.fromstring(click_xml))


def panel_buildup(slide: Any, shape_groups: Iterable[Any]) -> None:
    """Build up shapes on consecutive clicks.

    Args:
        slide: python-pptx Slide.
        shape_groups: iterable. Each entry is either a single shape or a
            list/tuple of shapes. Single shape → appears on its own click.
            Group of shapes → all shapes in the group appear together on
            the same click.
    """
    for i, group in enumerate(shape_groups):
        if isinstance(group, (list, tuple)):
            appear_together_on_click(slide, group, click_index=i)
        else:
            appear_on_click(slide, group, click_index=i)


def appear_together_on_click(
    slide: Any,
    shapes: Iterable[Any],
    click_index: int = 0,
) -> None:
    """Multiple shapes appear together on the same click.

    The first shape uses the click-trigger effect; the rest fire alongside
    (``nodeType="withEffect"``). Useful for grouping a picture with its
    label and caption so they animate as one panel.
    """
    from lxml import etree

    shape_list = list(shapes)
    if not shape_list:
        return

    timing = _ensure_timing(slide)
    main_seq = _ensure_main_seq(timing)
    next_id = _next_id(_max_id(timing))

    targets = [(_shape_id(s._element if hasattr(s, "_element") else s), None) for s in shape_list]
    click_xml = _build_grouped_click_effect_xml(
        shape_targets=targets,
        preset=_PRESET_APPEAR,
        next_id=next_id,
    )

    children = list(main_seq)
    if click_index >= len(children):
        main_seq.append(etree.fromstring(click_xml))
    else:
        main_seq.insert(click_index, etree.fromstring(click_xml))


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def _add_click_effect(
    slide: Any,
    shape: Any,
    click_index: int,
    preset: tuple[str, str, str],
) -> None:
    """Add a click-effect entry to the slide's main animation sequence."""
    from lxml import etree

    shape_id = _shape_id(shape._element if hasattr(shape, "_element") else shape)
    timing = _ensure_timing(slide)
    main_seq = _ensure_main_seq(timing)

    next_id = _next_id(_max_id(timing))
    click_xml = _build_click_effect_xml(
        shape_id=shape_id,
        preset=preset,
        next_id=next_id,
        paragraph_index=None,
    )

    children = list(main_seq)
    if click_index >= len(children):
        main_seq.append(etree.fromstring(click_xml))
    else:
        main_seq.insert(click_index, etree.fromstring(click_xml))


def _shape_id(shape_element: Any) -> str:
    """Extract the shape's id attribute from its OOXML element."""
    cnvpr = shape_element.find(f".//{_P}cNvPr")
    if cnvpr is None:
        raise ValueError("Shape has no cNvPr element — cannot determine id")
    return cnvpr.get("id", "")


def _ensure_timing(slide: Any) -> Any:
    """Return the slide's ``<p:timing>`` element, creating it if missing."""
    from lxml import etree

    sld = slide._element
    timing = sld.find(f"{_P}timing")
    if timing is not None:
        return timing

    timing_xml = """
<p:timing xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
  <p:tnLst>
    <p:par>
      <p:cTn id="1" dur="indefinite" restart="never" nodeType="tmRoot">
        <p:childTnLst>
          <p:seq concurrent="1" nextAc="seek">
            <p:cTn id="2" dur="indefinite" nodeType="mainSeq">
              <p:childTnLst/>
            </p:cTn>
            <p:prevCondLst>
              <p:cond evt="onPrev" delay="0">
                <p:tgtEl><p:sldTgt/></p:tgtEl>
              </p:cond>
            </p:prevCondLst>
            <p:nextCondLst>
              <p:cond evt="onNext" delay="0">
                <p:tgtEl><p:sldTgt/></p:tgtEl>
              </p:cond>
            </p:nextCondLst>
          </p:seq>
        </p:childTnLst>
      </p:cTn>
    </p:par>
  </p:tnLst>
</p:timing>
""".strip()
    timing = etree.fromstring(timing_xml)
    sld.append(timing)
    return timing


def _ensure_main_seq(timing: Any) -> Any:
    """Return the ``<p:cTn nodeType="mainSeq">`` child's ``<p:childTnLst>``."""
    main_seq_ctn = None
    for ctn in timing.iter(f"{_P}cTn"):
        if ctn.get("nodeType") == "mainSeq":
            main_seq_ctn = ctn
            break
    if main_seq_ctn is None:
        raise RuntimeError("Could not find mainSeq in timing tree")
    child_list = main_seq_ctn.find(f"{_P}childTnLst")
    if child_list is None:
        from lxml import etree

        child_list = etree.SubElement(main_seq_ctn, f"{_P}childTnLst")
    return child_list


def _max_id(timing: Any) -> int:
    """Return the largest numeric id present in the timing tree (or 100)."""
    max_id = 100
    for ctn in timing.iter(f"{_P}cTn"):
        try:
            cid = int(ctn.get("id", "0"))
            if cid > max_id:
                max_id = cid
        except (TypeError, ValueError):
            continue
    return max_id


def _build_click_effect_xml(
    shape_id: str,
    preset: tuple[str, str, str],
    next_id: Any,
    paragraph_index: int | None = None,
) -> str:
    """Build the XML for a single-shape click-effect (entry in mainSeq)."""
    return _build_grouped_click_effect_xml(
        shape_targets=[(shape_id, paragraph_index)],
        preset=preset,
        next_id=next_id,
    )


def _build_grouped_click_effect_xml(
    shape_targets: list[tuple[str, int | None]],
    preset: tuple[str, str, str],
    next_id: Any,
) -> str:
    """Build a click-effect that animates multiple shapes on the same click.

    First shape uses ``nodeType="clickEffect"`` (the click trigger).
    Subsequent shapes use ``nodeType="withEffect"`` so they fire alongside.
    """
    id1 = next_id()
    id2 = next_id()

    inner_pars = []
    for i, (shape_id, paragraph_index) in enumerate(shape_targets):
        node_type = "clickEffect" if i == 0 else "withEffect"
        inner_pars.append(_build_effect_par(shape_id, paragraph_index, preset, node_type, next_id))

    return f"""
<p:par xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
  <p:cTn id="{id1}" fill="hold">
    <p:stCondLst><p:cond delay="indefinite"/></p:stCondLst>
    <p:childTnLst>
      <p:par>
        <p:cTn id="{id2}" fill="hold">
          <p:stCondLst><p:cond delay="0"/></p:stCondLst>
          <p:childTnLst>
            {chr(10).join(inner_pars)}
          </p:childTnLst>
        </p:cTn>
      </p:par>
    </p:childTnLst>
  </p:cTn>
</p:par>
""".strip()


def _build_effect_par(
    shape_id: str,
    paragraph_index: int | None,
    preset: tuple[str, str, str],
    node_type: str,
    next_id: Any,
) -> str:
    """One ``<p:par>`` wrapping a single shape's effect inside a click step."""
    pid, pclass, psub = preset
    id_outer = next_id()
    id_inner = next_id()

    if paragraph_index is None:
        target_xml = f'<p:tgtEl><p:spTgt spid="{shape_id}"/></p:tgtEl>'
    else:
        target_xml = (
            f'<p:tgtEl><p:spTgt spid="{shape_id}">'
            f'<p:txEl><p:pRg st="{paragraph_index}" end="{paragraph_index}"/></p:txEl>'
            f"</p:spTgt></p:tgtEl>"
        )

    return f"""<p:par>
  <p:cTn id="{id_outer}" presetID="{pid}" presetClass="{pclass}" presetSubtype="{psub}" fill="hold" grpId="0" nodeType="{node_type}">
    <p:stCondLst><p:cond delay="0"/></p:stCondLst>
    <p:childTnLst>
      <p:set>
        <p:cBhvr>
          <p:cTn id="{id_inner}" dur="1" fill="hold">
            <p:stCondLst><p:cond delay="0"/></p:stCondLst>
          </p:cTn>
          {target_xml}
          <p:attrNameLst><p:attrName>style.visibility</p:attrName></p:attrNameLst>
        </p:cBhvr>
        <p:to><p:strVal val="visible"/></p:to>
      </p:set>
    </p:childTnLst>
  </p:cTn>
</p:par>"""


__all__ = [
    "appear_on_click",
    "appear_together_on_click",
    "bullet_reveal",
    "fade_on_click",
    "panel_buildup",
]
