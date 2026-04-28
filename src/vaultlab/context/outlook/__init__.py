"""Outlook context (Windows-only) — email, calendar, contacts, tasks.

vaultlab integrates with Outlook Classic via COM automation on Windows
so research-companion mode has the user's email, calendar, and tasks
in scope. Cross-platform users on macOS/Linux should use
`vaultlab.context.google` (Gmail + Google Calendar) instead.

PLACEHOLDER — full implementation lifts code from `bobby_outlook` (in
bobby-tools) into this subpackage during the migration phase.

Planned public surface (mirrors bobby_outlook):

    from vaultlab.context.outlook import (
        # Email
        read_inbox, search_emails, send_email, reply, forward,
        get_unread_count, get_recent_from, get_flagged_emails,

        # Calendar
        get_today_schedule, get_events, find_free_slots, create_meeting,

        # Tasks
        read_tasks, create_task, complete_task,

        # Contacts
        read_contacts, search_contacts,
    )

    # vaultlab-specific extensions:
    from vaultlab.context.outlook import (
        scope_to_research_threads,   # narrow to research-related emails
        as_context_passages,         # convert email content → RAG passages
        ingest_thread_to_kb,         # auto-ingest a research thread into KB
    )

Platform requirement: **Windows only**, with Outlook Classic open and
signed in. macOS / Linux users get a clear error message and a pointer
to vaultlab.context.google for Gmail.

Setup: `vaultlab setup --outlook` (Windows only).
See `docs/setup-outlook-windows.md`.
"""

from __future__ import annotations

import platform

# Placeholder. Real implementation lands in migration commit.
__all__: list[str] = []


def _check_platform() -> None:
    """Raise if running on non-Windows; vaultlab.context.outlook requires Windows."""
    if platform.system() != "Windows":
        raise RuntimeError(
            "vaultlab.context.outlook requires Windows with Outlook Classic. "
            f"Detected platform: {platform.system()}. "
            "On macOS/Linux, use vaultlab.context.google for Gmail/Calendar instead. "
            "See docs/setup-outlook-windows.md for details."
        )
