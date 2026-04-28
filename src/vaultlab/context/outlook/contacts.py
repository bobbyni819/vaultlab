"""Outlook contacts operations via the COM API.

Read, search, and create contacts in the default Contacts folder.
"""

from __future__ import annotations

import logging

from vaultlab.context.outlook._connection import get_namespace, get_outlook_app, _with_retry
from vaultlab.context.outlook._constants import OL_CONTACT_ITEM, OL_FOLDER_CONTACTS
from vaultlab.context.outlook.models import Contact

logger = logging.getLogger(__name__)


def _item_to_contact(item) -> Contact:
    """Convert a COM ContactItem to a Contact dataclass."""
    email = ""
    try:
        email = item.Email1Address or ""
    except Exception:
        pass

    phone = ""
    try:
        phone = item.BusinessTelephoneNumber or item.MobileTelephoneNumber or ""
    except Exception:
        pass

    return Contact(
        id=item.EntryID,
        first_name=item.FirstName or "",
        last_name=item.LastName or "",
        full_name=item.FullName or "",
        email=email,
        phone=phone,
        company=item.CompanyName or "",
        job_title=item.JobTitle or "",
    )


@_with_retry
def read_contacts(limit: int = 200) -> list[Contact]:
    """Read contacts from the default Contacts folder.

    Args:
        limit: Maximum number of contacts to return.

    Returns:
        List of Contact objects sorted by full name.
    """
    ns = get_namespace()
    folder = ns.GetDefaultFolder(OL_FOLDER_CONTACTS)
    items = folder.Items
    items.Sort("[FullName]")

    contacts = []
    for item in items:
        if len(contacts) >= limit:
            break
        try:
            if item.Class == 40:  # olContact
                contacts.append(_item_to_contact(item))
        except Exception:
            logger.debug("Skipping contact item", exc_info=True)
    return contacts


@_with_retry
def search_contacts(query: str) -> list[Contact]:
    """Search contacts by name or email substring.

    Args:
        query: Search string to match against name and email.

    Returns:
        List of matching Contact objects.
    """
    ns = get_namespace()
    folder = ns.GetDefaultFolder(OL_FOLDER_CONTACTS)
    items = folder.Items
    items.Sort("[FullName]")

    query_lower = query.lower()
    matches = []
    for item in items:
        try:
            if item.Class != 40:
                continue
            full_name = (item.FullName or "").lower()
            email = ""
            try:
                email = (item.Email1Address or "").lower()
            except Exception:
                pass
            if query_lower in full_name or query_lower in email:
                matches.append(_item_to_contact(item))
        except Exception:
            continue
    return matches


@_with_retry
def create_contact(
    first_name: str,
    last_name: str,
    email: str,
    phone: str | None = None,
    company: str | None = None,
    job_title: str | None = None,
) -> Contact:
    """Create a new contact in the default Contacts folder.

    Args:
        first_name: Contact's first name.
        last_name: Contact's last name.
        email: Contact's email address.
        phone: Optional phone number.
        company: Optional company name.
        job_title: Optional job title.

    Returns:
        The created Contact object.
    """
    app = get_outlook_app()
    item = app.CreateItem(OL_CONTACT_ITEM)
    item.FirstName = first_name
    item.LastName = last_name
    item.Email1Address = email

    if phone:
        item.BusinessTelephoneNumber = phone
    if company:
        item.CompanyName = company
    if job_title:
        item.JobTitle = job_title

    item.Save()
    logger.info("Contact created: %s %s (%s)", first_name, last_name, email)

    return Contact(
        id=item.EntryID,
        first_name=first_name,
        last_name=last_name,
        full_name=f"{first_name} {last_name}",
        email=email,
        phone=phone or "",
        company=company or "",
        job_title=job_title or "",
    )
