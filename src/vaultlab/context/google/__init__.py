"""Google ecosystem context — Docs, Sheets, Drive, Gmail, Calendar.

vaultlab integrates with the user's Google Workspace as a context input,
so research-companion mode has the user's lab work log, project
spreadsheets, and recent emails in scope without manual paste-in.

PLACEHOLDER — full implementation lifts code from `bobby_google` (in
bobby-tools) into this subpackage during the migration phase. The API
surface mirrors bobby_google with vaultlab-aware wrappers (auth caching
in ~/.config/vaultlab/, scope-aware RAG context assembly, KB ingest hooks).

Planned public surface (mirrors bobby_google):

    from vaultlab.context.google import (
        get_credentials, build_service,                    # auth
        append_to_today, read_recent_entries, get_full_text,  # docs
        read_range, write_range, append_rows,              # sheets
        scan_directory, get_google_id,                     # drive
        search_emails, read_recent,                        # gmail
        get_today_schedule, get_events,                    # calendar
    )

    # vaultlab-specific extensions:
    from vaultlab.context.google import (
        ingest_doc_to_kb,        # auto-ingest a Google Doc into <kb>/Sources/
        scope_for_project,       # narrow Google scope to current project's data
        as_context_passages,     # convert Google content → RAG passages
    )

Setup: `vaultlab setup --google` runs the OAuth flow and stores credentials
at `~/.config/vaultlab/google/`. See `docs/setup-google.md`.

License compatibility: vaultlab is MIT; Google API client libs are
Apache 2.0; OAuth scopes are user-controlled.
"""

from __future__ import annotations

# Placeholder. Real implementation lands in migration commit.
__all__: list[str] = []
