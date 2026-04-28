"""COM-to-Python conversion helpers for Outlook items."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from vaultlab.context.outlook._constants import IMPORTANCE_MAP, OL_IMPORTANCE_NORMAL, OL_TO, OL_CC, OL_BCC

logger = logging.getLogger(__name__)


def _com_date_to_datetime(com_date: Any) -> datetime:
    """Convert a COM date object to a Python datetime.

    Handles pywintypes.TimeType and generic datetime-like objects.
    """
    try:
        import pywintypes

        if isinstance(com_date, pywintypes.TimeType):
            return datetime(
                com_date.year,
                com_date.month,
                com_date.day,
                com_date.hour,
                com_date.minute,
                com_date.second,
            )
    except (ImportError, AttributeError):
        pass

    if isinstance(com_date, datetime):
        return com_date

    # Fallback: treat as datetime-like object
    return datetime(
        com_date.year,
        com_date.month,
        com_date.day,
        com_date.hour,
        com_date.minute,
        com_date.second,
    )


def _datetime_to_outlook_str(dt: datetime) -> str:
    """Format a datetime for Outlook Restrict() filter queries.

    Outlook expects: MM/DD/YYYY HH:MM AM/PM
    """
    return dt.strftime("%m/%d/%Y %I:%M %p")


def _extract_recipients(item: Any) -> dict[str, list[dict[str, str]]]:
    """Extract To/CC/BCC recipients from an Outlook item.

    Returns:
        Dict with keys 'to', 'cc', 'bcc', each containing a list of
        {'name': ..., 'email': ...} dicts.
    """
    result: dict[str, list[dict[str, str]]] = {"to": [], "cc": [], "bcc": []}
    type_key = {OL_TO: "to", OL_CC: "cc", OL_BCC: "bcc"}

    try:
        recipients = item.Recipients
        for i in range(1, recipients.Count + 1):
            recipient = recipients.Item(i)
            name = recipient.Name or ""
            email = ""
            try:
                # Try to resolve the SMTP address
                addr_entry = recipient.AddressEntry
                if addr_entry.Type == "EX":
                    exchange_user = addr_entry.GetExchangeUser()
                    if exchange_user:
                        email = exchange_user.PrimarySmtpAddress or ""
                if not email:
                    email = addr_entry.Address or ""
            except Exception:
                email = recipient.Address or ""

            key = type_key.get(recipient.Type, "to")
            result[key].append({"name": name, "email": email})
    except Exception:
        logger.debug("Could not extract recipients", exc_info=True)

    return result


def _get_sender_email(item: Any) -> str:
    """Extract the sender's SMTP email address from a mail item."""
    try:
        if item.SenderEmailType == "EX":
            sender = item.Sender
            if sender:
                exchange_user = sender.GetExchangeUser()
                if exchange_user:
                    return exchange_user.PrimarySmtpAddress or ""
        return item.SenderEmailAddress or ""
    except Exception:
        return ""


def _importance_str(importance_value: int) -> str:
    """Convert an Outlook importance enum to a human-readable string."""
    return IMPORTANCE_MAP.get(importance_value, "normal")
