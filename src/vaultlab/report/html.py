"""vaultlab.report.html — single-file HTML report renderer.

Public entrypoint: ``render_report(title, sections, ...) -> str``.

The output is a self-contained HTML document — inline CSS, inline JS, no
external assets. Save the string to a ``.html`` file and open in any browser.

The page shell follows the "printed lab notebook on warm paper" visual system:
a thin ``.vl-masthead`` branding strip with a dark-theme toggle, a ``.vl-head``
page header (breadcrumb, title, lede, meta, status chips), the section body,
and a two-part ``.vl-foot``.

Background: see ``SKILL.md`` in this package + Thariq Shihipar,
"The Unreasonable Effectiveness of HTML" (Anthropic, 2026) for the design
rationale.
"""

from __future__ import annotations

import html as _html
from datetime import datetime
from pathlib import Path
from typing import Literal

from vaultlab.report._css import CSS
from vaultlab.report._js import JS

Theme = Literal["light", "dark", "auto"]


def _breadcrumb_html(segments: list[str]) -> str:
    """Render breadcrumb segments separated by hairline slashes."""
    parts: list[str] = []
    for i, seg in enumerate(segments):
        if i:
            parts.append('<span class="sep">/</span>')
        last = i == len(segments) - 1
        cur = ' aria-current="page"' if last else ""
        parts.append(f"<span{cur}>{_html.escape(seg)}</span>")
    return f'<div class="breadcrumb">{"".join(parts)}</div>'


def render_report(
    title: str,
    sections: list[str],
    *,
    eyebrow: str | None = None,
    subtitle: str | None = None,
    meta: str | None = None,
    breadcrumb: list[str] | str | None = None,
    chips: list[str] | None = None,
    version: str | None = None,
    screen_label: str | None = None,
    theme: Theme = "light",
    include_js: bool = True,
    footer: str | None = None,
    lang: str = "en",
) -> str:
    """Render a complete HTML report document.

    Parameters
    ----------
    title:
        Report title (becomes the <title> + <h1>).
    sections:
        Pre-rendered HTML strings (typically from
        :mod:`vaultlab.report.components`). Joined verbatim into the body.
    eyebrow:
        Legacy small-label argument. When ``breadcrumb`` is not given it is
        split on ``·`` / ``/`` to seed the breadcrumb trail.
    subtitle:
        Subtitle line under the H1 — rendered as the italic serif ``.lede``.
    meta:
        Free-form HTML for the header meta band (dates, repo refs, links).
    breadcrumb:
        Breadcrumb trail — a list of segments, or a single string. The last
        segment is marked ``aria-current="page"``.
    chips:
        Pre-rendered status-chip HTML strings (see
        :func:`vaultlab.report.components.status_chip`) for the header
        ``.chip-row``.
    version:
        Version label shown in the masthead meta strip.
    screen_label:
        Optional ``data-screen-label`` on the page header (used by tooling).
    theme:
        "light", "dark", or "auto". The runtime theme toggle persists the
        user's choice in ``localStorage`` regardless of this default.
    include_js:
        Whether to bundle the interactive JS. Set False for static reports.
    footer:
        Optional footer HTML (replaces the left-hand footer cell).
    lang:
        ``lang`` attribute on <html>.

    Returns
    -------
    str
        A complete, self-contained HTML document string.
    """
    theme_attr = ' data-theme="dark"' if theme == "dark" else ""

    # ── Breadcrumb ──────────────────────────────────────────
    if breadcrumb is None:
        if eyebrow:
            segs = [s.strip() for s in eyebrow.replace("/", "·").split("·") if s.strip()]
        else:
            segs = ["vaultlab"]
    elif isinstance(breadcrumb, str):
        segs = [breadcrumb]
    else:
        segs = list(breadcrumb)
    breadcrumb_html = _breadcrumb_html(segs) if segs else ""

    lede_html = (
        f'<p class="lede">{_html.escape(subtitle)}</p>' if subtitle else ""
    )
    meta_html = f'<div class="meta">{meta}</div>' if meta else ""
    chip_row_html = (
        f'<div class="chip-row">{"".join(chips)}</div>' if chips else ""
    )
    screen_attr = (
        f' data-screen-label="{_html.escape(screen_label)}"' if screen_label else ""
    )

    # ── Masthead ────────────────────────────────────────────
    mast_bits = []
    if version:
        mast_bits.append(f"<span>{_html.escape(version)}</span><span>·</span>")
    mast_bits.append(f"<span>{datetime.now():%Y-%m-%d}</span><span>·</span>")
    mast_bits.append("<span>offline</span>")
    masthead = (
        '<div class="vl-masthead"><div class="vl-wrap">'
        '<a href="index.html" class="vl-mark">vaultlab.report</a>'
        '<div class="vl-mast-meta">'
        f'{"".join(mast_bits)}'
        '<button class="vl-theme-toggle" type="button" data-vl-theme>'
        "☾ Dark</button>"
        "</div></div></div>"
    )

    # ── Footer ──────────────────────────────────────────────
    left = footer or (
        f"vaultlab.report · generated {datetime.now():%Y-%m-%d %H:%M}"
    )
    footer_html = (
        '<footer class="vl-foot">'
        f"<div>{left}</div>"
        '<div><a href="index.html">Gallery</a></div>'
        "</footer>"
    )

    js_block = f"<script>{JS}</script>" if include_js else ""

    return f"""<!doctype html>
<html lang="{_html.escape(lang)}"{theme_attr}>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_html.escape(title)}</title>
<style>{CSS}</style>
</head>
<body>
{masthead}
<main class="vl-wrap">
<header class="vl-head"{screen_attr}>
{breadcrumb_html}
<h1>{_html.escape(title)}</h1>
{lede_html}
{meta_html}
{chip_row_html}
</header>
{chr(10).join(sections)}
{footer_html}
</main>
{js_block}
</body>
</html>
"""


def write_report(
    path: str | Path,
    title: str,
    sections: list[str],
    **kwargs,
) -> Path:
    """Render and write the report to ``path``. Returns the resolved Path."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(render_report(title, sections, **kwargs), encoding="utf-8")
    return p


__all__ = ["render_report", "write_report", "Theme"]
