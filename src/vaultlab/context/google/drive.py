"""Google Drive directory scanner for mixed local/cloud file access.

Scans a local Google Drive for Desktop directory and classifies each file:
- **Google-native** files (.gdoc, .gsheet, .gslides, etc.) are resolved to
  Google file IDs via the Drive API so they can be accessed with the
  appropriate Google API (Sheets, Docs, etc.).
- **Regular files** (.docx, .xlsx, .pdf, etc.) get their local path for
  direct filesystem access.

Google Drive for Desktop syncs native files as ~175-byte binary stubs that
can't be read directly.  This module bridges that gap.

Usage:
    from vaultlab.context.google.drive import scan_directory, get_google_id

    # Scan a local Drive folder
    files = scan_directory("G:/My Drive/HickeyLabProjects/")
    for f in files:
        print(f"{f.name:30s} {f.file_type:15s} {f.google_id or f.local_path}")

    # Resolve a single .gsheet to a spreadsheet ID
    sid = get_google_id("G:/My Drive/some_spreadsheet.gsheet")
"""

from __future__ import annotations

import mimetypes
import os
from dataclasses import dataclass

from vaultlab.context.google.auth import build_service


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class DriveFile:
    """Represents a file found in a local Google Drive directory.

    Attributes:
        name: Display name (without extension for Google-native files).
        file_type: Classification string — "google_doc", "google_sheet",
            "google_slides", "google_form", "google_drawing", "google_map",
            or "file" for regular files.
        local_path: Full local filesystem path (set for regular files,
            None for Google-native files).
        google_id: Google file ID (set for Google-native files,
            None for regular files).
        mime_type: MIME type of the file.
        extension: Original file extension (lowercase, with dot).
    """
    name: str
    file_type: str
    local_path: str | None
    google_id: str | None
    mime_type: str
    extension: str


# ---------------------------------------------------------------------------
# File type mapping
# ---------------------------------------------------------------------------

# Extension → (file_type, Google MIME type)
_GOOGLE_NATIVE_TYPES: dict[str, tuple[str, str]] = {
    ".gdoc":    ("google_doc",     "application/vnd.google-apps.document"),
    ".gsheet":  ("google_sheet",   "application/vnd.google-apps.spreadsheet"),
    ".gslides": ("google_slides",  "application/vnd.google-apps.presentation"),
    ".gform":   ("google_form",    "application/vnd.google-apps.form"),
    ".gdraw":   ("google_drawing", "application/vnd.google-apps.drawing"),
    ".gmap":    ("google_map",     "application/vnd.google-apps.map"),
}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _get_drive_service():
    """Build a Drive v3 API client."""
    return build_service("drive", "v3")


def _is_google_native(extension: str) -> bool:
    """Check if a file extension corresponds to a Google-native type."""
    return extension.lower() in _GOOGLE_NATIVE_TYPES


def _classify_file(filename: str) -> tuple[str, str, str]:
    """Classify a file by its extension.

    Args:
        filename: The filename (with extension).

    Returns:
        Tuple of (file_type, mime_type, extension).
    """
    _, ext = os.path.splitext(filename)
    ext = ext.lower()

    if ext in _GOOGLE_NATIVE_TYPES:
        file_type, mime_type = _GOOGLE_NATIVE_TYPES[ext]
        return file_type, mime_type, ext

    # Regular file — infer MIME type from extension
    mime_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    return "file", mime_type, ext


def _resolve_folder_id(local_path: str) -> str:
    """Map a local Google Drive path to a Drive folder ID.

    Traverses the path hierarchy via the Drive API, starting from "My Drive"
    root and walking down each subfolder.

    Args:
        local_path: Local path under Google Drive (e.g.
            "G:/My Drive/Projects/Lab").

    Returns:
        The Drive folder ID for the target directory.

    Raises:
        ValueError: If a folder in the path cannot be found via the API.
    """
    # Normalize and find the "My Drive" segment
    normalized = os.path.normpath(local_path).replace("\\", "/")

    # Find "My Drive" in the path to determine the relative portion
    my_drive_idx = normalized.lower().find("my drive")
    if my_drive_idx == -1:
        raise ValueError(
            f"Cannot determine Drive root from path: {local_path!r}. "
            "Expected a path containing 'My Drive'."
        )
    # Everything after "My Drive" is the relative path
    relative = normalized[my_drive_idx + len("My Drive"):]
    parts = [p for p in relative.split("/") if p]

    if not parts:
        # Requesting the root "My Drive" folder
        return "root"

    service = _get_drive_service()
    parent_id = "root"

    for folder_name in parts:
        query = (
            f"'{parent_id}' in parents "
            f"and name = '{folder_name}' "
            f"and mimeType = 'application/vnd.google-apps.folder' "
            f"and trashed = false"
        )
        resp = service.files().list(
            q=query,
            fields="files(id, name)",
            pageSize=1,
        ).execute()

        files = resp.get("files", [])
        if not files:
            raise ValueError(
                f"Folder '{folder_name}' not found under parent '{parent_id}' "
                f"while resolving path: {local_path!r}"
            )
        parent_id = files[0]["id"]

    return parent_id


def _list_folder_files(folder_id: str) -> dict[str, str]:
    """List all files in a Drive folder, returning a name→ID mapping.

    Args:
        folder_id: The Drive folder ID.

    Returns:
        Dict mapping file names (without extension) to Google file IDs.
        Only includes Google-native file types.
    """
    service = _get_drive_service()
    name_to_id: dict[str, str] = {}
    page_token = None

    while True:
        resp = service.files().list(
            q=f"'{folder_id}' in parents and trashed = false",
            fields="nextPageToken, files(id, name, mimeType)",
            pageSize=1000,
            pageToken=page_token,
        ).execute()

        for f in resp.get("files", []):
            name_to_id[f["name"]] = f["id"]

        page_token = resp.get("nextPageToken")
        if not page_token:
            break

    return name_to_id


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def scan_directory(
    local_path: str,
    *,
    recursive: bool = False,
) -> list[DriveFile]:
    """Scan a local Google Drive directory and classify each file.

    Google-native files are resolved to file IDs via the Drive API.
    Regular files get their local paths for direct filesystem access.

    Args:
        local_path: Path to a local Google Drive directory
            (e.g. "G:/My Drive/Projects/").
        recursive: If True, scan subdirectories recursively.

    Returns:
        List of DriveFile objects for all files found.
    """
    local_path = os.path.normpath(local_path)

    if not os.path.isdir(local_path):
        raise FileNotFoundError(f"Directory not found: {local_path!r}")

    # Cache: folder_path → {name: google_id}
    folder_cache: dict[str, dict[str, str]] = {}

    def _get_folder_files(dir_path: str) -> dict[str, str]:
        """Get Drive API file listing for a local directory (cached)."""
        if dir_path not in folder_cache:
            folder_id = _resolve_folder_id(dir_path)
            folder_cache[dir_path] = _list_folder_files(folder_id)
        return folder_cache[dir_path]

    results: list[DriveFile] = []

    def _scan(dir_path: str) -> None:
        # Check for Google-native files to decide if we need API lookup
        entries = list(os.scandir(dir_path))
        has_native = any(
            e.is_file() and _is_google_native(os.path.splitext(e.name)[1].lower())
            for e in entries
        )

        # Only call Drive API if there are Google-native files in this folder
        cloud_files = _get_folder_files(dir_path) if has_native else {}

        for entry in entries:
            if entry.is_dir():
                if recursive:
                    _scan(entry.path)
                continue

            if not entry.is_file():
                continue

            file_type, mime_type, ext = _classify_file(entry.name)

            if _is_google_native(ext):
                # Google-native file — resolve ID by matching stem name
                stem = os.path.splitext(entry.name)[0]
                google_id = cloud_files.get(stem)
                results.append(DriveFile(
                    name=stem,
                    file_type=file_type,
                    local_path=None,
                    google_id=google_id,
                    mime_type=mime_type,
                    extension=ext,
                ))
            else:
                # Regular file
                results.append(DriveFile(
                    name=entry.name,
                    file_type=file_type,
                    local_path=entry.path,
                    google_id=None,
                    mime_type=mime_type,
                    extension=ext,
                ))

    _scan(local_path)
    return results


def get_google_id(local_path: str) -> str:
    """Resolve a local Google-native file to its Google file ID.

    Given a path to a .gdoc, .gsheet, .gslides, etc. file, uses the Drive
    API to find the corresponding Google file ID by matching the filename
    in the parent folder.

    Args:
        local_path: Path to a Google-native file
            (e.g. "G:/My Drive/report.gsheet").

    Returns:
        The Google file ID string.

    Raises:
        ValueError: If the file is not a Google-native type or can't be found.
    """
    local_path = os.path.normpath(local_path)
    filename = os.path.basename(local_path)
    stem, ext = os.path.splitext(filename)
    ext = ext.lower()

    if not _is_google_native(ext):
        raise ValueError(
            f"Not a Google-native file type: {ext!r}. "
            f"Expected one of: {', '.join(_GOOGLE_NATIVE_TYPES)}"
        )

    # Resolve parent folder and find file by name
    parent_dir = os.path.dirname(local_path)
    folder_id = _resolve_folder_id(parent_dir)
    cloud_files = _list_folder_files(folder_id)

    if stem not in cloud_files:
        raise ValueError(
            f"Could not find '{stem}' in Drive folder. "
            f"Available files: {list(cloud_files.keys())[:20]}"
        )

    return cloud_files[stem]


def open_file(drive_file: DriveFile) -> str:
    """Extract the appropriate identifier from a DriveFile for API access.

    Routes based on file type:
    - google_sheet → returns the spreadsheet_id (for sheets.read_range)
    - google_doc → returns the doc_id (for docs.get_full_text)
    - Other Google types → returns the google_id
    - Regular files → returns the local_path

    Args:
        drive_file: A DriveFile instance from scan_directory.

    Returns:
        A Google file ID (for Google-native files) or local path string
        (for regular files).

    Raises:
        ValueError: If the DriveFile has neither google_id nor local_path.
    """
    if drive_file.google_id is not None:
        return drive_file.google_id
    if drive_file.local_path is not None:
        return drive_file.local_path
    raise ValueError(
        f"DriveFile '{drive_file.name}' has neither google_id nor local_path"
    )
