"""Data models for Outlook items.

Plain dataclasses with to_dict() for easy serialization.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime


@dataclass
class Email:
    """Represents an Outlook email message."""

    id: str = ""
    subject: str = ""
    sender: str = ""
    sender_email: str = ""
    to: list[str] = field(default_factory=list)
    cc: list[str] = field(default_factory=list)
    received_time: datetime | None = None
    body: str = ""
    body_preview: str = ""
    is_read: bool = False
    has_attachments: bool = False
    importance: str = "normal"
    conversation_id: str = ""
    categories: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class CalendarEvent:
    """Represents an Outlook calendar event."""

    id: str = ""
    subject: str = ""
    start: datetime | None = None
    end: datetime | None = None
    organizer: str = ""
    attendees: list[dict[str, str]] = field(default_factory=list)
    location: str = ""
    body_preview: str = ""
    is_recurring: bool = False
    is_all_day: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Contact:
    """Represents an Outlook contact."""

    id: str = ""
    first_name: str = ""
    last_name: str = ""
    full_name: str = ""
    email: str = ""
    phone: str = ""
    company: str = ""
    job_title: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Task:
    """Represents an Outlook task."""

    id: str = ""
    subject: str = ""
    body: str = ""
    due_date: datetime | None = None
    start_date: datetime | None = None
    status: str = "not_started"
    percent_complete: int = 0
    priority: str = "normal"

    def to_dict(self) -> dict:
        return asdict(self)
