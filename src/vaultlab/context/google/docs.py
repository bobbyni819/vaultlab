"""Google Docs helpers for the lab work log.

Designed for a reverse-chronological work log document where each day's entries
live under a HEADING_1 with the date formatted as YYYYMMDD (e.g., "20260223").
New days are inserted at the top; entries are appended as formatted bullet points.

Supports Google Docs tabs — specify tab_name to target a specific tab.

Text supports simple markdown:
    **bold**, *italic*, __underline__
    Indented lines (2-space increments) become nested bullets.

Usage:
    from vaultlab.context.google.docs import append_to_today, read_today_entries

    # Set DOC_ID to your own work-log Google Doc.
    # Find it in the URL: docs.google.com/document/d/<DOC_ID>/edit
    DOC_ID = "<your-google-doc-id>"
    append_to_today(DOC_ID, "Fixed **segmentation bug** in *pipeline*",
                    tab_name="daily updates")

    # Nested bullets:
    append_to_today(DOC_ID, \"\"\"Refactored auth module
      Moved token refresh to background thread
      Added __retry logic__ for expired creds\"\"\",
                    tab_name="daily updates")
"""

from __future__ import annotations

from datetime import date

from vaultlab.context.google.auth import build_service

# ---------------------------------------------------------------------------
# Markdown parsing
# ---------------------------------------------------------------------------


def _parse_inline(text: str) -> tuple[str, list[dict]]:
    """Strip **bold**, *italic*, __underline__ markers from *text*.

    Returns ``(plain_text, spans)`` where each span is a dict with keys
    ``start``, ``end`` (offsets into *plain_text*) and one of
    ``bold``, ``italic``, or ``underline`` set to True.
    """
    spans: list[dict] = []
    plain: list[str] = []
    i = 0

    while i < len(text):
        # Bold: **...**
        if text[i : i + 2] == "**":
            end = text.find("**", i + 2)
            if end != -1:
                pos = sum(len(p) for p in plain)
                content = text[i + 2 : end]
                plain.append(content)
                spans.append({"start": pos, "end": pos + len(content), "bold": True})
                i = end + 2
                continue

        # Underline: __...__
        if text[i : i + 2] == "__":
            end = text.find("__", i + 2)
            if end != -1:
                pos = sum(len(p) for p in plain)
                content = text[i + 2 : end]
                plain.append(content)
                spans.append({"start": pos, "end": pos + len(content), "underline": True})
                i = end + 2
                continue

        # Italic: *...* (single asterisk, not part of **)
        if (
            text[i] == "*"
            and (i + 1 < len(text) and text[i + 1] != "*")
            and (i == 0 or text[i - 1] != "*")
        ):
            end = text.find("*", i + 1)
            if end != -1 and (end + 1 >= len(text) or text[end + 1] != "*"):
                pos = sum(len(p) for p in plain)
                content = text[i + 1 : end]
                plain.append(content)
                spans.append({"start": pos, "end": pos + len(content), "italic": True})
                i = end + 1
                continue

        plain.append(text[i])
        i += 1

    return "".join(plain), spans


def _parse_entry_lines(text: str) -> list[dict]:
    """Split entry text into lines with nesting levels.

    Indentation (2 spaces per level) determines nesting.
    Leading ``- `` or ``* `` is stripped from each line.

    Returns list of ``{"text": str, "level": int}``.
    """
    lines = []
    for raw in text.split("\n"):
        if not raw.strip():
            continue
        stripped = raw.lstrip()
        indent = len(raw) - len(stripped)
        level = indent // 2
        # Strip optional bullet prefix
        if stripped.startswith(("- ", "* ")):
            stripped = stripped[2:]
        lines.append({"text": stripped, "level": level})
    return lines


# ---------------------------------------------------------------------------
# Internal helpers — document structure
# ---------------------------------------------------------------------------


def _get_tab(doc: dict, tab_name: str | None) -> tuple[dict, str]:
    """Find a tab by title and return (body, tab_id).

    If *tab_name* is None, returns the first tab.
    """
    tabs = doc.get("tabs", [])
    if not tabs:
        raise ValueError("Document has no tabs")

    if tab_name is None:
        tab = tabs[0]
    else:
        for tab in tabs:
            if tab["tabProperties"]["title"].lower() == tab_name.lower():
                break
        else:
            available = [t["tabProperties"]["title"] for t in tabs]
            raise ValueError(f"Tab '{tab_name}' not found. Available: {available}")

    return tab["documentTab"]["body"], tab["tabProperties"]["tabId"]


def _para_text(paragraph: dict) -> str:
    """Extract plain text from a paragraph element."""
    parts = []
    for run in paragraph.get("elements", []):
        text_run = run.get("textRun")
        if text_run:
            parts.append(text_run["content"])
    return "".join(parts)


def _find_heading_range(body: dict, heading_text: str) -> tuple[int, int] | None:
    """Find the index range of a section under a HEADING_1.

    Returns ``(heading_para_end, section_end)``:
    - *heading_para_end*: index right after the heading paragraph — the insert
      point for new entries (so newest entries appear at the top of the section).
    - *section_end*: index of the next HEADING_1, or end of body — used for
      reading all entries in the section.

    Returns None if the heading is not found.
    """
    content = body.get("content", [])
    heading_end: int | None = None

    for element in content:
        para = element.get("paragraph")
        if not para:
            continue

        style = para.get("paragraphStyle", {}).get("namedStyleType", "")
        text = _para_text(para).strip()

        if style == "HEADING_1":
            if heading_end is not None:
                # Found the next heading after our target — section ends here
                return (heading_end, element["startIndex"])
            if text == heading_text:
                heading_end = element["endIndex"]

    if heading_end is not None:
        # Target heading was the last one — section extends to end of body
        body_end = content[-1]["endIndex"]
        return (heading_end, body_end - 1)

    return None


# ---------------------------------------------------------------------------
# Internal helpers — Google Docs API request builders
# ---------------------------------------------------------------------------


def _normal_para_style(start: int, end: int, tab_id: str) -> dict:
    return {
        "updateParagraphStyle": {
            "range": {"startIndex": start, "endIndex": end, "tabId": tab_id},
            "paragraphStyle": {"namedStyleType": "NORMAL_TEXT"},
            "fields": "namedStyleType",
        }
    }


def _heading_para_style(start: int, end: int, tab_id: str) -> dict:
    return {
        "updateParagraphStyle": {
            "range": {"startIndex": start, "endIndex": end, "tabId": tab_id},
            "paragraphStyle": {"namedStyleType": "HEADING_1"},
            "fields": "namedStyleType",
        }
    }


def _arial_11_style(start: int, end: int, tab_id: str) -> dict:
    return {
        "updateTextStyle": {
            "range": {"startIndex": start, "endIndex": end, "tabId": tab_id},
            "textStyle": {
                "fontSize": {"magnitude": 11, "unit": "PT"},
                "weightedFontFamily": {"fontFamily": "Arial"},
            },
            "fields": "fontSize,weightedFontFamily",
        }
    }


def _build_format_requests(
    insert_idx: int,
    line_info: list[dict],
    full_text_len: int,
    tab_id: str,
) -> list[dict]:
    """Build all formatting requests for inserted entry text.

    Applies (in order): bullets, indentation, paragraph style, text style,
    and inline formatting (bold/italic/underline).
    """
    reqs: list[dict] = []
    abs_end = insert_idx + full_text_len

    # 1. Native bullet list for the entire entry
    reqs.append(
        {
            "createParagraphBullets": {
                "range": {
                    "startIndex": insert_idx,
                    "endIndex": abs_end,
                    "tabId": tab_id,
                },
                "bulletPreset": "BULLET_DISC_CIRCLE_SQUARE",
            }
        }
    )

    # 2. Paragraph style (NORMAL_TEXT) + text style (Arial 11pt) for each line
    #    Apply these FIRST so subsequent overrides (indent, spacing) stick.
    for li in line_info:
        a = insert_idx + li["start"]
        b = insert_idx + li["end"]
        reqs.append(_normal_para_style(a, b, tab_id))
        reqs.append(_arial_11_style(a, b, tab_id))

    # 3. Indentation for nested bullets (applied AFTER NORMAL_TEXT so it sticks)
    #    Google Docs list nesting: each level adds 36pt.
    #    Level 0 default: indentStart=36, indentFirstLine=18
    #    Level 1: indentStart=72, indentFirstLine=54
    #    Level 2: indentStart=108, indentFirstLine=90
    for li in line_info:
        if li["level"] > 0:
            a = insert_idx + li["start"]
            b = insert_idx + li["end"]
            reqs.append(
                {
                    "updateParagraphStyle": {
                        "range": {
                            "startIndex": a,
                            "endIndex": b,
                            "tabId": tab_id,
                        },
                        "paragraphStyle": {
                            "indentStart": {
                                "magnitude": 36 * (li["level"] + 1),
                                "unit": "PT",
                            },
                            "indentFirstLine": {
                                "magnitude": 18 + 36 * li["level"],
                                "unit": "PT",
                            },
                        },
                        "fields": "indentStart,indentFirstLine",
                    }
                }
            )

    # 4. Space above the first line to visually separate entries
    first = line_info[0]
    reqs.append(
        {
            "updateParagraphStyle": {
                "range": {
                    "startIndex": insert_idx + first["start"],
                    "endIndex": insert_idx + first["end"],
                    "tabId": tab_id,
                },
                "paragraphStyle": {
                    "spaceAbove": {"magnitude": 10, "unit": "PT"},
                },
                "fields": "spaceAbove",
            }
        }
    )

    # 5. Inline formatting (bold, italic, underline)
    for li in line_info:
        for span in li["spans"]:
            a = insert_idx + span["start"]
            b = insert_idx + span["end"]
            style = {}
            fields = []
            for attr in ("bold", "italic", "underline"):
                if span.get(attr):
                    style[attr] = True
                    fields.append(attr)
            if fields:
                reqs.append(
                    {
                        "updateTextStyle": {
                            "range": {
                                "startIndex": a,
                                "endIndex": b,
                                "tabId": tab_id,
                            },
                            "textStyle": style,
                            "fields": ",".join(fields),
                        }
                    }
                )

    return reqs


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def get_full_text(doc_id: str, *, tab_name: str | None = None) -> str:
    """Get the full plain text content of a Google Doc (or a specific tab)."""
    service = build_service("docs", "v1")
    doc = service.documents().get(documentId=doc_id, includeTabsContent=True).execute()
    body, _ = _get_tab(doc, tab_name)

    parts = []
    for element in body.get("content", []):
        para = element.get("paragraph")
        if para:
            parts.append(_para_text(para))
    return "".join(parts)


def read_today_entries(
    doc_id: str, *, today: date | None = None, tab_name: str | None = None
) -> str:
    """Read all entries under today's date heading.

    Args:
        doc_id: Google Doc document ID.
        today: Override date (defaults to today).
        tab_name: Tab title to read from (default: first tab).

    Returns:
        Text of all entries under today's heading, or empty string if none.
    """
    today = today or date.today()
    heading = today.strftime("%Y%m%d")

    service = build_service("docs", "v1")
    doc = service.documents().get(documentId=doc_id, includeTabsContent=True).execute()
    body, _ = _get_tab(doc, tab_name)

    result = _find_heading_range(body, heading)
    if result is None:
        return ""

    heading_end, section_end = result
    content = body.get("content", [])

    parts = []
    for element in content:
        start = element.get("startIndex", 0)
        if start < heading_end:
            continue
        if start >= section_end:
            break

        para = element.get("paragraph")
        if para:
            parts.append(_para_text(para))

    return "".join(parts).strip()


def read_recent_entries(doc_id: str, *, n: int = 7, tab_name: str | None = None) -> str:
    """Read entries from the most recent *n* date headings.

    Useful for giving Claude context about recent work across multiple days.
    The document uses HEADING_1 dates in reverse chronological order, so this
    reads the first *n* headings from the top.

    Args:
        doc_id: Google Doc document ID.
        n: Number of date headings to include (default 7).
        tab_name: Tab title to read from (default: first tab).

    Returns:
        Text of recent entries with date headings preserved, or empty string.
    """
    service = build_service("docs", "v1")
    doc = service.documents().get(documentId=doc_id, includeTabsContent=True).execute()
    body, _ = _get_tab(doc, tab_name)
    content = body.get("content", [])

    # Walk through paragraphs, counting HEADING_1s
    headings_seen = 0
    parts: list[str] = []

    for element in content:
        para = element.get("paragraph")
        if not para:
            continue

        style = para.get("paragraphStyle", {}).get("namedStyleType", "")
        text = _para_text(para)

        if style == "HEADING_1":
            headings_seen += 1
            if headings_seen > n:
                break
            # Add a blank line before headings (except the first)
            if parts:
                parts.append("\n")
            parts.append(f"## {text.strip()}\n")
        elif headings_seen > 0:
            # Only include text that's under a heading
            parts.append(text)

    return "".join(parts).strip()


def append_to_today(
    doc_id: str,
    text: str,
    *,
    today: date | None = None,
    tab_name: str | None = None,
) -> None:
    """Append a formatted entry under today's date heading.

    Creates today's HEADING_1 at the top of the tab if it doesn't exist.
    Text supports simple markdown for rich formatting:

    - ``**bold**``, ``*italic*``, ``__underline__``
    - Indented lines (2 spaces per level) become nested bullets
    - Leading ``- `` or ``* `` on lines is stripped (native bullets replace them)

    Examples::

        # Simple entry
        append_to_today(DOC_ID, "Fixed the **segmentation bug**")

        # Nested bullets
        append_to_today(DOC_ID, \"\"\"Refactored auth module
          Moved token refresh to *background thread*
          Added __retry logic__ for expired creds\"\"\")

    Args:
        doc_id: Google Doc document ID.
        text: Entry text with optional markdown formatting.
        today: Override date (defaults to today).
        tab_name: Tab title to write to (default: first tab).
    """
    today = today or date.today()
    heading = today.strftime("%Y%m%d")

    service = build_service("docs", "v1")
    doc = service.documents().get(documentId=doc_id, includeTabsContent=True).execute()
    body, tab_id = _get_tab(doc, tab_name)

    result = _find_heading_range(body, heading)

    # --- Parse entry into structured lines --------------------------------
    lines = _parse_entry_lines(text)

    full_text = ""
    line_info: list[dict] = []

    for line in lines:
        plain, spans = _parse_inline(line["text"])
        line_start = len(full_text)
        full_text += plain + "\n"
        line_end = len(full_text)

        # Adjust span offsets to be relative to full_text
        adjusted = [
            {**s, "start": s["start"] + line_start, "end": s["end"] + line_start} for s in spans
        ]
        line_info.append(
            {"start": line_start, "end": line_end, "level": line["level"], "spans": adjusted}
        )

    ftl = len(full_text)

    # --- Build requests ---------------------------------------------------
    if result is not None:
        # Heading exists — insert right after heading (newest on top)
        insert_idx, _ = result
        insert_reqs: list[dict] = [
            {
                "insertText": {
                    "location": {"index": insert_idx, "tabId": tab_id},
                    "text": full_text,
                }
            },
        ]
        fmt_reqs = _build_format_requests(insert_idx, line_info, ftl, tab_id)
    else:
        # No heading — create one at the top (index 1, after section break)
        heading_line = f"{heading}\n"
        hl = len(heading_line)
        insert_idx = 1 + hl  # content goes right after heading

        insert_reqs = [
            {
                "insertText": {
                    "location": {"index": 1, "tabId": tab_id},
                    "text": heading_line,
                }
            },
            _heading_para_style(1, 1 + hl, tab_id),
            {
                "insertText": {
                    "location": {"index": insert_idx, "tabId": tab_id},
                    "text": full_text,
                }
            },
        ]
        fmt_reqs = _build_format_requests(insert_idx, line_info, ftl, tab_id)

    service.documents().batchUpdate(
        documentId=doc_id,
        body={"requests": insert_reqs + fmt_reqs},
    ).execute()
