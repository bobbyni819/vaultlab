"""vaultlab.context.google — Google Workspace integration for research-companion mode.

Lifted from bobby_google (in bobby-tools), adapted to use vaultlab config paths
(`~/.config/vaultlab/google/` instead of `~/.config/google/`).

For setup walkthrough see docs/setup-google.md.

Public surface (mirrors bobby_google):

    from vaultlab.context.google import (
        # Auth
        get_credentials, build_service,
        # Docs (lab work log)
        append_to_today, get_full_text, read_recent_entries, read_today_entries,
        # Sheets (sample manifests, panel info)
        read_range, write_range, append_rows, get_sheet_names,
        batch_read, batch_write, find_replace, set_formatting,
        clear_range, create_sheet, delete_sheet,
        # Drive (file scanning + ID resolution)
        DriveFile, scan_directory, get_google_id, open_file,
    )

Convention (per AGENTS.md): every prompt that includes Google content shows
the source citations in the trace log (`<kb>/.vaultlab/runs/<id>/trace.jsonl`).
"""

from __future__ import annotations

from vaultlab.context.google.auth import build_service, get_credentials
from vaultlab.context.google.docs import (
    append_to_today,
    get_full_text,
    read_recent_entries,
    read_today_entries,
)
from vaultlab.context.google.drive import (
    DriveFile,
    get_google_id,
    open_file,
    scan_directory,
)
from vaultlab.context.google.sheets import (
    append_rows,
    batch_read,
    batch_write,
    clear_range,
    create_sheet,
    delete_sheet,
    find_replace,
    get_sheet_names,
    read_range,
    set_formatting,
    write_range,
)

__all__ = [
    # auth
    "get_credentials", "build_service",
    # docs
    "append_to_today", "get_full_text", "read_recent_entries", "read_today_entries",
    # sheets
    "read_range", "write_range", "append_rows", "get_sheet_names",
    "batch_read", "batch_write", "find_replace", "set_formatting",
    "clear_range", "create_sheet", "delete_sheet",
    # drive
    "DriveFile", "scan_directory", "get_google_id", "open_file",
]
