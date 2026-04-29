"""Outlook calendar operations via the COM API.

Query events, create meetings and appointments, find free time slots,
and access shared calendars.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

from vaultlab.context.outlook._connection import _with_retry, get_namespace, get_outlook_app
from vaultlab.context.outlook._constants import OL_APPOINTMENT_ITEM, OL_FOLDER_CALENDAR, OL_MEETING
from vaultlab.context.outlook._converters import _com_date_to_datetime, _datetime_to_outlook_str
from vaultlab.context.outlook.models import CalendarEvent

logger = logging.getLogger(__name__)


def _item_to_event(item) -> CalendarEvent:
    """Convert a COM AppointmentItem to a CalendarEvent dataclass."""
    start = None
    end = None
    try:
        start = _com_date_to_datetime(item.Start)
    except Exception:
        pass
    try:
        end = _com_date_to_datetime(item.End)
    except Exception:
        pass

    attendees = []
    try:
        recipients = item.Recipients
        for i in range(1, recipients.Count + 1):
            recipient = recipients.Item(i)
            name = recipient.Name or ""
            email = ""
            try:
                addr_entry = recipient.AddressEntry
                if addr_entry.Type == "EX":
                    exchange_user = addr_entry.GetExchangeUser()
                    if exchange_user:
                        email = exchange_user.PrimarySmtpAddress or ""
                if not email:
                    email = addr_entry.Address or ""
            except Exception:
                email = recipient.Address or ""
            attendees.append({"name": name, "email": email})
    except Exception:
        logger.debug("Could not extract attendees", exc_info=True)

    body_preview = ""
    try:
        body_preview = (item.Body or "")[:500].strip()
    except Exception:
        pass

    return CalendarEvent(
        id=item.EntryID,
        subject=item.Subject or "",
        start=start,
        end=end,
        organizer=item.Organizer or "",
        attendees=attendees,
        location=item.Location or "",
        body_preview=body_preview,
        is_recurring=item.IsRecurring,
        is_all_day=item.AllDayEvent,
    )


@_with_retry
def get_events(
    start_date: datetime,
    end_date: datetime,
    include_recurring: bool = True,
) -> list[CalendarEvent]:
    """Get calendar events within a date range.

    Args:
        start_date: Start of the range (inclusive).
        end_date: End of the range (inclusive).
        include_recurring: If True, expand recurring events into individual occurrences.

    Returns:
        List of CalendarEvent objects sorted by start time.
    """
    ns = get_namespace()
    calendar = ns.GetDefaultFolder(OL_FOLDER_CALENDAR)
    items = calendar.Items

    if include_recurring:
        items.IncludeRecurrences = True
    items.Sort("[Start]")

    start_str = _datetime_to_outlook_str(start_date)
    end_str = _datetime_to_outlook_str(end_date)
    restriction = f"[Start] >= '{start_str}' AND [Start] <= '{end_str}'"
    restricted = items.Restrict(restriction)

    events = []
    for item in restricted:
        try:
            events.append(_item_to_event(item))
        except Exception:
            logger.debug("Skipping calendar item", exc_info=True)
    return events


@_with_retry
def get_today_schedule() -> list[CalendarEvent]:
    """Get all events for today.

    Returns:
        List of today's CalendarEvent objects sorted by start time.
    """
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    tomorrow = today + timedelta(days=1)
    return get_events(today, tomorrow)


@_with_retry
def get_tomorrow_schedule() -> list[CalendarEvent]:
    """Get all events for tomorrow.

    Returns:
        List of tomorrow's CalendarEvent objects sorted by start time.
    """
    tomorrow = (datetime.now() + timedelta(days=1)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    day_after = tomorrow + timedelta(days=1)
    return get_events(tomorrow, day_after)


@_with_retry
def get_week_events() -> list[CalendarEvent]:
    """Get all events for the next 7 days (including today).

    Returns:
        List of CalendarEvent objects for the coming week.
    """
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    week_end = today + timedelta(days=7)
    return get_events(today, week_end)


@_with_retry
def get_next_event() -> CalendarEvent | None:
    """Get the next upcoming event from now.

    Returns:
        The next CalendarEvent, or None if no events remain today/tomorrow.
    """
    now = datetime.now()
    tomorrow_end = (now + timedelta(days=1)).replace(hour=23, minute=59, second=59, microsecond=0)
    events = get_events(now, tomorrow_end)
    for event in events:
        if event.start and event.start >= now:
            return event
    return None


@_with_retry
def create_meeting(
    subject: str,
    start: datetime,
    end: datetime,
    attendees: list[str],
    location: str | None = None,
    body: str | None = None,
    send_invites: bool = True,
) -> CalendarEvent:
    """Create a meeting with attendees and optionally send invites.

    Args:
        subject: Meeting subject.
        start: Start datetime.
        end: End datetime.
        attendees: List of attendee email addresses.
        location: Optional meeting location.
        body: Optional meeting body/agenda.
        send_invites: If True, send meeting invitations immediately.

    Returns:
        The created CalendarEvent.
    """
    app = get_outlook_app()
    appt = app.CreateItem(OL_APPOINTMENT_ITEM)
    appt.Subject = subject
    appt.Start = start
    appt.End = end
    appt.MeetingStatus = OL_MEETING

    if location:
        appt.Location = location
    if body:
        appt.Body = body

    for email in attendees:
        appt.Recipients.Add(email)
    appt.Recipients.ResolveAll()

    if send_invites:
        appt.Send()
        logger.info("Meeting invitation sent: %s", subject)
    else:
        appt.Save()
        logger.info("Meeting saved (invites not sent): %s", subject)

    return CalendarEvent(
        id=appt.EntryID if not send_invites else "",
        subject=subject,
        start=start,
        end=end,
        attendees=[{"name": "", "email": e} for e in attendees],
        location=location or "",
        body_preview=(body or "")[:500],
    )


@_with_retry
def create_appointment(
    subject: str,
    start: datetime,
    end: datetime,
    location: str | None = None,
    body: str | None = None,
) -> CalendarEvent:
    """Create a personal appointment (no attendees).

    Args:
        subject: Appointment subject.
        start: Start datetime.
        end: End datetime.
        location: Optional location.
        body: Optional notes.

    Returns:
        The created CalendarEvent.
    """
    app = get_outlook_app()
    appt = app.CreateItem(OL_APPOINTMENT_ITEM)
    appt.Subject = subject
    appt.Start = start
    appt.End = end

    if location:
        appt.Location = location
    if body:
        appt.Body = body

    appt.Save()
    logger.info("Appointment created: %s", subject)

    return CalendarEvent(
        id=appt.EntryID,
        subject=subject,
        start=start,
        end=end,
        location=location or "",
        body_preview=(body or "")[:500],
    )


@_with_retry
def find_free_slots(
    date: datetime,
    duration_minutes: int = 30,
    work_start: int = 9,
    work_end: int = 17,
) -> list[tuple[datetime, datetime]]:
    """Find free time slots on a given date.

    Looks at the calendar for the given date and returns gaps between events
    within working hours.

    Args:
        date: The date to check.
        duration_minutes: Minimum slot duration in minutes.
        work_start: Start of working hours (hour, 24h format).
        work_end: End of working hours (hour, 24h format).

    Returns:
        List of (start, end) tuples representing free slots.
    """
    day_start = date.replace(hour=work_start, minute=0, second=0, microsecond=0)
    day_end = date.replace(hour=work_end, minute=0, second=0, microsecond=0)

    events = get_events(day_start, day_end)
    min_duration = timedelta(minutes=duration_minutes)

    # Build list of busy intervals, clamped to working hours
    busy = []
    for event in events:
        if event.start and event.end:
            start = max(event.start, day_start)
            end = min(event.end, day_end)
            if start < end:
                busy.append((start, end))

    # Sort and merge overlapping intervals
    busy.sort()
    merged = []
    for start, end in busy:
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))

    # Find gaps
    free = []
    cursor = day_start
    for start, end in merged:
        if start - cursor >= min_duration:
            free.append((cursor, start))
        cursor = max(cursor, end)
    if day_end - cursor >= min_duration:
        free.append((cursor, day_end))

    return free


@_with_retry
def get_shared_calendar(
    owner_name_or_email: str,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
) -> list[CalendarEvent]:
    """Access another user's shared calendar (best-effort).

    Uses GetSharedDefaultFolder to access a colleague's calendar. Requires
    that the other user has shared their calendar with you.

    Args:
        owner_name_or_email: The name or email of the calendar owner.
        start_date: Start of date range (defaults to today at midnight).
        end_date: End of date range (defaults to end of start_date's day).

    Returns:
        List of CalendarEvent objects from the shared calendar.

    Raises:
        RuntimeError: If the shared calendar cannot be accessed.
    """
    ns = get_namespace()

    try:
        recipient = ns.CreateRecipient(owner_name_or_email)
        recipient.Resolve()
        if not recipient.Resolved:
            raise RuntimeError(f"Could not resolve recipient: {owner_name_or_email}")

        shared_calendar = ns.GetSharedDefaultFolder(recipient, OL_FOLDER_CALENDAR)
    except Exception as exc:
        raise RuntimeError(
            f"Cannot access shared calendar for '{owner_name_or_email}'. "
            f"Ensure they have shared their calendar with you. Error: {exc}"
        ) from exc

    items = shared_calendar.Items
    items.IncludeRecurrences = True
    items.Sort("[Start]")

    if start_date is None:
        start_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    if end_date is None:
        end_date = start_date + timedelta(days=1)

    start_str = _datetime_to_outlook_str(start_date)
    end_str = _datetime_to_outlook_str(end_date)

    restriction = f"[Start] >= '{start_str}' AND [Start] <= '{end_str}'"
    restricted = items.Restrict(restriction)

    events = []
    for item in restricted:
        try:
            events.append(_item_to_event(item))
        except Exception:
            logger.debug("Skipping shared calendar item", exc_info=True)
    return events


@_with_retry
def delete_event(entry_id: str) -> None:
    """Delete a calendar event by its EntryID.

    Args:
        entry_id: The Outlook EntryID of the event.
    """
    ns = get_namespace()
    item = ns.GetItemFromID(entry_id)
    subject = item.Subject
    item.Delete()
    logger.info("Event deleted: %s", subject)


@_with_retry
def update_event(
    entry_id: str,
    subject: str | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
    location: str | None = None,
    body: str | None = None,
) -> CalendarEvent:
    """Update an existing calendar event's fields.

    Only provided fields are modified; others are left unchanged.

    Args:
        entry_id: The Outlook EntryID of the event.
        subject: New subject.
        start: New start time.
        end: New end time.
        location: New location.
        body: New body/notes.

    Returns:
        The updated CalendarEvent.
    """
    ns = get_namespace()
    item = ns.GetItemFromID(entry_id)

    if subject is not None:
        item.Subject = subject
    if start is not None:
        item.Start = start
    if end is not None:
        item.End = end
    if location is not None:
        item.Location = location
    if body is not None:
        item.Body = body

    item.Save()
    logger.info("Event updated: %s", item.Subject)
    return _item_to_event(item)
