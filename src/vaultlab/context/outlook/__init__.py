"""vaultlab.context.outlook — Outlook Classic integration (Windows-only).

Lifted from bobby_outlook (in bobby-tools). Uses Outlook COM automation
via pywin32 — Windows only, requires Outlook Classic open and signed in.

Cross-platform users: see vaultlab.context.google for Gmail / Calendar.

For setup walkthrough see docs/setup-outlook-windows.md.

Public surface (mirrors bobby_outlook):

    from vaultlab.context.outlook import (
        # Email
        read_inbox, search_emails, send_email, reply, forward,
        get_unread_count, get_recent_from, get_flagged_emails,
        create_draft, get_drafts, send_draft, get_conversation,
        # Calendar
        get_today_schedule, get_events, find_free_slots, create_meeting,
        # Tasks
        read_tasks, create_task, complete_task,
        # Contacts
        read_contacts, search_contacts, create_contact,
        # Models
        Email, CalendarEvent, Task, Contact,
    )
"""

from __future__ import annotations

import platform


def _check_platform() -> None:
    """Raise if running on non-Windows; vaultlab.context.outlook requires Windows."""
    if platform.system() != "Windows":
        raise RuntimeError(
            "vaultlab.context.outlook requires Windows with Outlook Classic. "
            f"Detected platform: {platform.system()}. "
            "On macOS/Linux, use vaultlab.context.google for Gmail/Calendar instead. "
            "See docs/setup-outlook-windows.md for details."
        )


# Lazy import — only attempt the COM-dependent imports on Windows. On other
# platforms, importing vaultlab.context.outlook still succeeds; the actual
# function calls raise the platform error via _check_platform().
if platform.system() == "Windows":
    from vaultlab.context.outlook.calendar import (
        create_meeting,
        find_free_slots,
        get_events,
        get_today_schedule,
    )
    from vaultlab.context.outlook.contacts import (
        create_contact,
        read_contacts,
        search_contacts,
    )
    from vaultlab.context.outlook.email import (
        count_by_sender,
        create_draft,
        forward,
        get_attachments_info,
        get_conversation,
        get_drafts,
        get_email,
        get_flagged_emails,
        get_recent_from,
        get_unread_count,
        list_folders,
        mark_read,
        mark_read_batch,
        mark_unread,
        move_to_folder,
        read_folder,
        read_inbox,
        reply,
        reply_to_thread,
        save_attachments,
        search_emails,
        search_sent,
        send_draft,
        send_email,
        send_personalized_emails,
        send_summary_email,
        send_with_signature,
    )
    from vaultlab.context.outlook.models import (
        CalendarEvent,
        Contact,
        Email,
        Task,
    )
    from vaultlab.context.outlook.tasks import (
        complete_task,
        create_task,
        read_tasks,
    )

    __all__ = [
        "CalendarEvent",
        "Contact",
        # models
        "Email",
        "Task",
        "complete_task",
        "count_by_sender",
        "create_contact",
        "create_draft",
        "create_meeting",
        "create_task",
        "find_free_slots",
        "forward",
        "get_attachments_info",
        "get_conversation",
        "get_drafts",
        "get_email",
        "get_events",
        "get_flagged_emails",
        "get_recent_from",
        # calendar
        "get_today_schedule",
        "get_unread_count",
        "list_folders",
        "mark_read",
        "mark_read_batch",
        "mark_unread",
        "move_to_folder",
        # contacts
        "read_contacts",
        "read_folder",
        # email
        "read_inbox",
        # tasks
        "read_tasks",
        "reply",
        "reply_to_thread",
        "save_attachments",
        "search_contacts",
        "search_emails",
        "search_sent",
        "send_draft",
        "send_email",
        "send_personalized_emails",
        "send_summary_email",
        "send_with_signature",
    ]
else:
    # On non-Windows: provide platform-error stubs for any attribute access.
    __all__ = []
