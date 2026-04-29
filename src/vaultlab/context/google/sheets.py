"""Google Sheets helpers for reading, writing, and formatting spreadsheet data.

Wraps the Sheets v4 API with ergonomic functions for common operations.
All functions accept a ``spreadsheet_id`` (the long ID from the URL) and
A1-notation ranges.  An optional ``sheet_name`` parameter prepends the sheet
tab name automatically and handles quoting.

Usage:
    from vaultlab.context.google.sheets import read_range, write_range, get_sheet_names

    sid = "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgVE2upms"
    names = get_sheet_names(sid)
    data = read_range(sid, "A1:C5", sheet_name="Sheet1")
    data_dicts = read_range(sid, "A1:C5", sheet_name="Sheet1", as_dicts=True)
"""

from __future__ import annotations

import re

from vaultlab.context.google.auth import build_service

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _get_service():
    """Build a Sheets v4 API client."""
    return build_service("sheets", "v4")


def _qualify_range(range_: str, sheet_name: str | None) -> str:
    """Prepend sheet name to an A1 range if not already qualified.

    Handles quoting for sheet names containing spaces or special characters.

    Args:
        range_: A1 notation range (e.g. "A1:C5" or "Sheet1!A1:C5").
        sheet_name: Sheet tab name to prepend, or None to leave as-is.

    Returns:
        Fully qualified A1 range string.
    """
    if sheet_name is None or "!" in range_:
        return range_
    # Quote sheet name if it contains spaces or special chars
    if re.search(r"[ '!]", sheet_name):
        quoted = "'" + sheet_name.replace("'", "''") + "'"
    else:
        quoted = sheet_name
    return f"{quoted}!{range_}"


def _rows_to_dicts(rows: list[list]) -> list[dict]:
    """Convert header + data rows to a list of dicts.

    The first row is treated as headers. Subsequent rows become dicts
    keyed by those headers. Short rows are padded with empty strings
    so every dict has the same keys.

    Args:
        rows: 2D list where rows[0] is the header row.

    Returns:
        List of dicts, one per data row.

    Raises:
        ValueError: If rows is empty (no header row).
    """
    # TODO: This is a good place for you to implement!
    # See the contribution request below the file.
    if not rows:
        raise ValueError("Cannot convert empty rows to dicts — no header row")
    headers = rows[0]
    width = len(headers)
    return [dict(zip(headers, row + [""] * (width - len(row)), strict=False)) for row in rows[1:]]


def _get_sheet_id(spreadsheet_id: str, title: str) -> int:
    """Resolve a sheet tab name to its numeric sheetId.

    Args:
        spreadsheet_id: The spreadsheet ID.
        title: Sheet tab name to find.

    Returns:
        The numeric sheetId.

    Raises:
        ValueError: If the sheet name is not found (lists available names).
    """
    service = _get_service()
    meta = (
        service.spreadsheets()
        .get(spreadsheetId=spreadsheet_id, fields="sheets.properties")
        .execute()
    )

    for sheet in meta.get("sheets", []):
        props = sheet["properties"]
        if props["title"].lower() == title.lower():
            return props["sheetId"]

    available = [s["properties"]["title"] for s in meta.get("sheets", [])]
    raise ValueError(f"Sheet '{title}' not found. Available: {available}")


def _col_to_index(col: str) -> int:
    """Convert a column letter to a 0-based index (A=0, Z=25, AA=26)."""
    result = 0
    for ch in col.upper():
        result = result * 26 + (ord(ch) - ord("A") + 1)
    return result - 1


def _a1_to_grid_range(range_: str, sheet_id: int) -> dict:
    """Parse A1 notation into a GridRange dict for batchUpdate requests.

    Supports formats like "A1:C5", "A:C", "A1", "Sheet1!A1:C5".
    The sheet name prefix (if present) is stripped — sheet_id is used instead.

    Args:
        range_: A1 notation range (sheet prefix is ignored).
        sheet_id: Numeric sheet ID to use in the GridRange.

    Returns:
        GridRange dict with sheetId, startRowIndex, endRowIndex,
        startColumnIndex, endColumnIndex.
    """
    # Strip sheet name prefix if present
    if "!" in range_:
        range_ = range_.split("!", 1)[1]

    grid: dict = {"sheetId": sheet_id}

    # Match cell references like A1, AA100, A, etc.
    pattern = r"([A-Za-z]+)(\d*)"
    parts = range_.split(":")

    m = re.match(pattern, parts[0])
    if m:
        grid["startColumnIndex"] = _col_to_index(m.group(1))
        if m.group(2):
            grid["startRowIndex"] = int(m.group(2)) - 1

    if len(parts) == 2:
        m = re.match(pattern, parts[1])
        if m:
            grid["endColumnIndex"] = _col_to_index(m.group(1)) + 1
            if m.group(2):
                grid["endRowIndex"] = int(m.group(2))
    else:
        # Single cell — end = start + 1
        grid["endColumnIndex"] = grid["startColumnIndex"] + 1
        if "startRowIndex" in grid:
            grid["endRowIndex"] = grid["startRowIndex"] + 1

    return grid


# ---------------------------------------------------------------------------
# Public API — Core CRUD
# ---------------------------------------------------------------------------


def read_range(
    spreadsheet_id: str,
    range_: str,
    *,
    sheet_name: str | None = None,
    as_dicts: bool = False,
    value_render: str = "FORMATTED_VALUE",
) -> list[list] | list[dict]:
    """Read values from a spreadsheet range.

    Args:
        spreadsheet_id: The spreadsheet ID.
        range_: A1 notation range (e.g. "A1:C5").
        sheet_name: Sheet tab name (prepended if range lacks one).
        as_dicts: If True, treat row 0 as headers and return list of dicts.
        value_render: How values should be rendered. One of
            "FORMATTED_VALUE", "UNFORMATTED_VALUE", "FORMULA".

    Returns:
        2D list of cell values, or list of dicts if as_dicts=True.
    """
    service = _get_service()
    qualified = _qualify_range(range_, sheet_name)
    result = (
        service.spreadsheets()
        .values()
        .get(
            spreadsheetId=spreadsheet_id,
            range=qualified,
            valueRenderOption=value_render,
        )
        .execute()
    )

    rows = result.get("values", [])
    if as_dicts:
        return _rows_to_dicts(rows)
    return rows


def write_range(
    spreadsheet_id: str,
    range_: str,
    values: list[list],
    *,
    sheet_name: str | None = None,
    value_input: str = "USER_ENTERED",
) -> dict:
    """Write values to a spreadsheet range.

    Args:
        spreadsheet_id: The spreadsheet ID.
        range_: A1 notation range (e.g. "A1:C5").
        values: 2D list of values to write.
        sheet_name: Sheet tab name (prepended if range lacks one).
        value_input: How input should be interpreted. One of
            "USER_ENTERED" (parses formulas/numbers) or "RAW".

    Returns:
        API response dict with updatedCells, updatedRows, etc.
    """
    service = _get_service()
    qualified = _qualify_range(range_, sheet_name)
    return (
        service.spreadsheets()
        .values()
        .update(
            spreadsheetId=spreadsheet_id,
            range=qualified,
            valueInputOption=value_input,
            body={"values": values},
        )
        .execute()
    )


def append_rows(
    spreadsheet_id: str,
    range_: str,
    values: list[list],
    *,
    sheet_name: str | None = None,
    value_input: str = "USER_ENTERED",
) -> dict:
    """Append rows after the last row with data in a range.

    Args:
        spreadsheet_id: The spreadsheet ID.
        range_: A1 notation range that defines the table to append to.
        values: 2D list of row values to append.
        sheet_name: Sheet tab name (prepended if range lacks one).
        value_input: How input should be interpreted.

    Returns:
        API response dict.
    """
    service = _get_service()
    qualified = _qualify_range(range_, sheet_name)
    return (
        service.spreadsheets()
        .values()
        .append(
            spreadsheetId=spreadsheet_id,
            range=qualified,
            valueInputOption=value_input,
            insertDataOption="INSERT_ROWS",
            body={"values": values},
        )
        .execute()
    )


def clear_range(
    spreadsheet_id: str,
    range_: str,
    *,
    sheet_name: str | None = None,
) -> dict:
    """Clear all values in a spreadsheet range (formatting is preserved).

    Args:
        spreadsheet_id: The spreadsheet ID.
        range_: A1 notation range to clear.
        sheet_name: Sheet tab name (prepended if range lacks one).

    Returns:
        API response dict.
    """
    service = _get_service()
    qualified = _qualify_range(range_, sheet_name)
    return (
        service.spreadsheets()
        .values()
        .clear(
            spreadsheetId=spreadsheet_id,
            range=qualified,
            body={},
        )
        .execute()
    )


# ---------------------------------------------------------------------------
# Public API — Metadata
# ---------------------------------------------------------------------------


def get_sheet_names(spreadsheet_id: str) -> list[str]:
    """Get the names of all sheet tabs in a spreadsheet.

    Args:
        spreadsheet_id: The spreadsheet ID.

    Returns:
        List of sheet tab names in order.
    """
    service = _get_service()
    meta = (
        service.spreadsheets()
        .get(spreadsheetId=spreadsheet_id, fields="sheets.properties")
        .execute()
    )
    return [s["properties"]["title"] for s in meta.get("sheets", [])]


def create_sheet(
    spreadsheet_id: str,
    title: str,
    *,
    rows: int | None = None,
    cols: int | None = None,
) -> int:
    """Create a new sheet tab in a spreadsheet.

    Args:
        spreadsheet_id: The spreadsheet ID.
        title: Name for the new sheet tab.
        rows: Optional row count (default determined by Sheets).
        cols: Optional column count (default determined by Sheets).

    Returns:
        The numeric sheetId of the new tab.
    """
    service = _get_service()
    props: dict = {"title": title}
    grid_props: dict = {}
    if rows is not None:
        grid_props["rowCount"] = rows
    if cols is not None:
        grid_props["columnCount"] = cols
    if grid_props:
        props["gridProperties"] = grid_props

    resp = (
        service.spreadsheets()
        .batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={"requests": [{"addSheet": {"properties": props}}]},
        )
        .execute()
    )

    return resp["replies"][0]["addSheet"]["properties"]["sheetId"]


def delete_sheet(spreadsheet_id: str, title: str) -> None:
    """Delete a sheet tab by name.

    Args:
        spreadsheet_id: The spreadsheet ID.
        title: Name of the sheet tab to delete.

    Raises:
        ValueError: If the sheet name is not found.
    """
    sheet_id = _get_sheet_id(spreadsheet_id, title)
    service = _get_service()
    service.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={"requests": [{"deleteSheet": {"sheetId": sheet_id}}]},
    ).execute()


# ---------------------------------------------------------------------------
# Public API — Batch operations
# ---------------------------------------------------------------------------


def batch_read(
    spreadsheet_id: str,
    ranges: list[str],
    *,
    as_dicts: bool = False,
    value_render: str = "FORMATTED_VALUE",
) -> dict[str, list]:
    """Read multiple ranges in a single API call.

    Args:
        spreadsheet_id: The spreadsheet ID.
        ranges: List of A1 notation ranges.
        as_dicts: If True, convert each range's rows to dicts.
        value_render: How values should be rendered.

    Returns:
        Dict mapping each range string to its rows (list[list] or list[dict]).
    """
    service = _get_service()
    result = (
        service.spreadsheets()
        .values()
        .batchGet(
            spreadsheetId=spreadsheet_id,
            ranges=ranges,
            valueRenderOption=value_render,
        )
        .execute()
    )

    out: dict[str, list] = {}
    for vr in result.get("valueRanges", []):
        key = vr["range"]
        rows = vr.get("values", [])
        out[key] = _rows_to_dicts(rows) if as_dicts else rows
    return out


def batch_write(
    spreadsheet_id: str,
    data: dict[str, list[list]],
    *,
    value_input: str = "USER_ENTERED",
) -> dict:
    """Write to multiple ranges in a single API call.

    Args:
        spreadsheet_id: The spreadsheet ID.
        data: Dict mapping A1 ranges to 2D value lists.
        value_input: How input should be interpreted.

    Returns:
        API response dict.
    """
    service = _get_service()
    body = {
        "valueInputOption": value_input,
        "data": [{"range": r, "values": v} for r, v in data.items()],
    }
    return (
        service.spreadsheets()
        .values()
        .batchUpdate(
            spreadsheetId=spreadsheet_id,
            body=body,
        )
        .execute()
    )


# ---------------------------------------------------------------------------
# Public API — Advanced
# ---------------------------------------------------------------------------


def find_replace(
    spreadsheet_id: str,
    find: str,
    replacement: str,
    *,
    sheet_name: str | None = None,
    match_case: bool = False,
    match_entire_cell: bool = False,
) -> int:
    """Find and replace text across a spreadsheet or specific sheet.

    Args:
        spreadsheet_id: The spreadsheet ID.
        find: Text to search for.
        replacement: Text to replace matches with.
        sheet_name: Limit search to this sheet tab (default: all sheets).
        match_case: Whether the search is case-sensitive.
        match_entire_cell: Whether to match the entire cell contents.

    Returns:
        Number of occurrences replaced.
    """
    service = _get_service()
    req: dict = {
        "find": find,
        "replacement": replacement,
        "matchCase": match_case,
        "matchEntireCell": match_entire_cell,
        "allSheets": sheet_name is None,
    }
    if sheet_name is not None:
        req["sheetId"] = _get_sheet_id(spreadsheet_id, sheet_name)

    resp = (
        service.spreadsheets()
        .batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={"requests": [{"findReplace": req}]},
        )
        .execute()
    )

    return resp["replies"][0]["findReplace"].get("occurrencesChanged", 0)


def _parse_color(color: str) -> dict:
    """Parse a hex color string (#RRGGBB) to a Sheets color dict."""
    color = color.lstrip("#")
    return {
        "red": int(color[0:2], 16) / 255,
        "green": int(color[2:4], 16) / 255,
        "blue": int(color[4:6], 16) / 255,
    }


def set_formatting(
    spreadsheet_id: str,
    range_: str,
    *,
    sheet_name: str | None = None,
    bold: bool | None = None,
    italic: bool | None = None,
    font_size: int | None = None,
    font_family: str | None = None,
    bg_color: str | None = None,
    text_color: str | None = None,
    number_format: str | None = None,
    h_align: str | None = None,
) -> None:
    """Apply formatting to a range of cells.

    Args:
        spreadsheet_id: The spreadsheet ID.
        range_: A1 notation range.
        sheet_name: Sheet tab name (used to resolve sheetId for GridRange).
        bold: Set text bold.
        italic: Set text italic.
        font_size: Font size in points.
        font_family: Font family name (e.g. "Arial").
        bg_color: Background color as hex string (e.g. "#FF0000").
        text_color: Text color as hex string.
        number_format: Number format pattern (e.g. "#,##0.00", "0%").
        h_align: Horizontal alignment ("LEFT", "CENTER", "RIGHT").
    """
    # Resolve sheet name for GridRange
    qualified = _qualify_range(range_, sheet_name)
    if "!" in qualified:
        sn = qualified.split("!")[0].strip("'")
    else:
        sn = None

    if sn:
        sheet_id = _get_sheet_id(spreadsheet_id, sn)
    else:
        # Default to first sheet
        service = _get_service()
        meta = (
            service.spreadsheets()
            .get(spreadsheetId=spreadsheet_id, fields="sheets.properties")
            .execute()
        )
        sheet_id = meta["sheets"][0]["properties"]["sheetId"]

    grid_range = _a1_to_grid_range(range_, sheet_id)

    # Build cell format and field mask
    cell_format: dict = {}
    fields: list[str] = []

    text_fmt: dict = {}
    if bold is not None:
        text_fmt["bold"] = bold
        fields.append("userEnteredFormat.textFormat.bold")
    if italic is not None:
        text_fmt["italic"] = italic
        fields.append("userEnteredFormat.textFormat.italic")
    if font_size is not None:
        text_fmt["fontSize"] = font_size
        fields.append("userEnteredFormat.textFormat.fontSize")
    if font_family is not None:
        text_fmt["fontFamily"] = font_family
        fields.append("userEnteredFormat.textFormat.fontFamily")
    if text_color is not None:
        text_fmt["foregroundColor"] = _parse_color(text_color)
        fields.append("userEnteredFormat.textFormat.foregroundColor")
    if text_fmt:
        cell_format["textFormat"] = text_fmt

    if bg_color is not None:
        cell_format["backgroundColor"] = _parse_color(bg_color)
        fields.append("userEnteredFormat.backgroundColor")

    if number_format is not None:
        cell_format["numberFormat"] = {"type": "NUMBER", "pattern": number_format}
        fields.append("userEnteredFormat.numberFormat")

    if h_align is not None:
        cell_format["horizontalAlignment"] = h_align
        fields.append("userEnteredFormat.horizontalAlignment")

    if not fields:
        return

    service = _get_service()
    service.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={
            "requests": [
                {
                    "repeatCell": {
                        "range": grid_range,
                        "cell": {"userEnteredFormat": cell_format},
                        "fields": ",".join(fields),
                    }
                }
            ]
        },
    ).execute()
