"""Outlook email operations via the COM API.

Read, search, reply, forward, and send emails through the locally running
Outlook application.
"""

from __future__ import annotations

import logging
import os
import re
import time
from datetime import datetime

from vaultlab.context.outlook._connection import _with_retry, get_namespace, get_outlook_app
from vaultlab.context.outlook._constants import (
    FOLDER_NAME_MAP,
    OL_FLAG_COMPLETE,
    OL_FLAG_MARKED,
    OL_FLAG_NOT_FLAGGED,
    OL_FOLDER_DELETED,
    OL_FOLDER_DRAFTS,
    OL_FOLDER_INBOX,
    OL_FOLDER_SENT,
    OL_MAIL_ITEM,
)
from vaultlab.context.outlook._converters import (
    _com_date_to_datetime,
    _datetime_to_outlook_str,
    _extract_recipients,
    _get_sender_email,
    _importance_str,
)
from vaultlab.context.outlook.models import Email

logger = logging.getLogger(__name__)


def _get_folder(folder_name: str = "Inbox"):
    """Resolve a folder by name, returning the COM folder object."""
    ns = get_namespace()
    folder_id = FOLDER_NAME_MAP.get(folder_name.lower())
    if folder_id is not None:
        return ns.GetDefaultFolder(folder_id)
    # Try as a subfolder of Inbox
    inbox = ns.GetDefaultFolder(OL_FOLDER_INBOX)
    try:
        return inbox.Folders(folder_name)
    except Exception:
        pass
    # Try as a top-level folder
    for store in ns.Folders:
        try:
            return store.Folders(folder_name)
        except Exception:
            continue
    raise ValueError(f"Folder not found: {folder_name}")


@_with_retry
def list_folders(account: str | None = None) -> list[dict]:
    """List all mail folders with item counts.

    Args:
        account: Optional account email to list folders for.
            If None, lists folders for all accounts.

    Returns:
        List of dicts with 'name', 'account', 'item_count',
        and 'unread_count' keys.
    """
    ns = get_namespace()
    folders: list[dict] = []

    for i in range(ns.Folders.Count):
        store = ns.Folders.Item(i + 1)
        store_name = store.Name
        if account and account.lower() not in store_name.lower():
            continue
        for j in range(store.Folders.Count):
            try:
                sub = store.Folders.Item(j + 1)
                name = sub.Name
                if name.lower() in _SYSTEM_FOLDERS:
                    continue
                folders.append(
                    {
                        "name": name,
                        "account": store_name,
                        "item_count": sub.Items.Count,
                        "unread_count": sub.UnReadItemCount,
                    }
                )
            except Exception:
                continue
    return folders


def _item_to_email(item) -> Email:
    """Convert a COM MailItem to an Email dataclass."""
    recipients = _extract_recipients(item)
    to_list = [r["email"] or r["name"] for r in recipients["to"]]
    cc_list = [r["email"] or r["name"] for r in recipients["cc"]]

    received = None
    try:
        received = _com_date_to_datetime(item.ReceivedTime)
    except Exception:
        pass

    body = ""
    try:
        body = item.Body or ""
    except Exception:
        pass

    categories = []
    try:
        cat_str = item.Categories or ""
        if cat_str:
            categories = [c.strip() for c in cat_str.split(",") if c.strip()]
    except Exception:
        pass

    return Email(
        id=item.EntryID,
        subject=item.Subject or "",
        sender=item.SenderName or "",
        sender_email=_get_sender_email(item),
        to=to_list,
        cc=cc_list,
        received_time=received,
        body=body,
        body_preview=body[:200].strip(),
        is_read=not item.UnRead,
        has_attachments=item.Attachments.Count > 0,
        importance=_importance_str(item.Importance),
        conversation_id=item.ConversationID or "",
        categories=categories,
    )


@_with_retry
def read_inbox(
    limit: int = 50,
    unread_only: bool = False,
    since: datetime | None = None,
) -> list[Email]:
    """Read emails from the Inbox.

    Args:
        limit: Maximum number of emails to return.
        unread_only: If True, only return unread emails.
        since: If provided, only return emails received after this datetime.

    Returns:
        List of Email objects, newest first.
    """
    folder = _get_folder("Inbox")
    items = folder.Items
    items.Sort("[ReceivedTime]", Descending=True)

    filters = []
    if unread_only:
        filters.append("[UnRead] = True")
    if since:
        filters.append(f"[ReceivedTime] >= '{_datetime_to_outlook_str(since)}'")

    if filters:
        restriction = " AND ".join(filters)
        items = items.Restrict(restriction)

    emails = []
    for item in items:
        if len(emails) >= limit:
            break
        try:
            if item.Class == 43:  # olMail
                emails.append(_item_to_email(item))
        except Exception:
            logger.debug("Skipping item in inbox", exc_info=True)
    return emails


@_with_retry
def read_folder(
    folder_name: str,
    limit: int = 50,
    unread_only: bool = False,
    since: datetime | None = None,
) -> list[Email]:
    """Read emails from a named folder (Sent, Drafts, custom folders, etc.).

    Args:
        folder_name: Name of the folder (e.g., "Sent", "Drafts", "My Folder").
        limit: Maximum number of emails to return.
        unread_only: If True, only return unread emails.
        since: If provided, only return emails received after this datetime.

    Returns:
        List of Email objects, newest first.
    """
    folder = _get_folder(folder_name)
    items = folder.Items
    items.Sort("[ReceivedTime]", Descending=True)

    filters = []
    if unread_only:
        filters.append("[UnRead] = True")
    if since:
        filters.append(f"[ReceivedTime] >= '{_datetime_to_outlook_str(since)}'")
    if filters:
        items = items.Restrict(" AND ".join(filters))

    emails = []
    for item in items:
        if len(emails) >= limit:
            break
        try:
            if item.Class == 43:  # olMail
                emails.append(_item_to_email(item))
        except Exception:
            logger.debug("Skipping item in %s", folder_name, exc_info=True)
    return emails


_SYSTEM_FOLDERS = frozenset(
    (
        "inbox",
        "sent items",
        "outbox",
        "drafts",
        "deleted items",
        "junk email",
        "junk e-mail",
        "sync issues",
        "contacts",
        "calendar",
        "tasks",
        "notes",
        "journal",
        "rss feeds",
        "conversation history",
        "conversation action settings",
        "quick step settings",
        "social activity notifications",
        "yammer root",
        "externalcontacts",
        "files",
        "events",
        "dcp",
        "public folders",
        "favorites",
        "all public folders",
    )
)


def _search_single_folder(
    query: str,
    folder: str,
    limit: int,
    sender: str | None = None,
    since: datetime | None = None,
) -> list[Email]:
    """Search a single folder by subject or body content."""
    fld = _get_folder(folder)
    items = fld.Items
    items.Sort("[ReceivedTime]", Descending=True)

    # Apply date filter via Restrict if provided
    if since:
        try:
            date_str = _datetime_to_outlook_str(since)
            items = items.Restrict(f"[ReceivedTime] >= '{date_str}'")
        except Exception:
            logger.debug("Date restrict failed", exc_info=True)

    sender_lower = sender.lower() if sender else None

    # Try subject filter first via Restrict
    try:
        escaped = query.replace("'", "''")
        restriction = f"@SQL=\"urn:schemas:httpmail:subject\" LIKE '%{escaped}%'"
        restricted = items.Restrict(restriction)
        emails = []
        for item in restricted:
            if len(emails) >= limit:
                break
            try:
                if item.Class != 43:
                    continue
                if sender_lower:
                    item_sender = (item.SenderName or "").lower()
                    item_email = _get_sender_email(item).lower()
                    if sender_lower not in item_sender and sender_lower not in item_email:
                        continue
                emails.append(_item_to_email(item))
            except Exception:
                continue
        if emails:
            return emails
    except Exception:
        logger.debug("Restrict search failed, falling back to iteration", exc_info=True)

    # Fallback: iterate and match subject or body
    query_lower = query.lower()
    emails = []
    for item in items:
        if len(emails) >= limit:
            break
        try:
            if item.Class != 43:
                continue
            if sender_lower:
                item_sender = (item.SenderName or "").lower()
                item_email = _get_sender_email(item).lower()
                if sender_lower not in item_sender and sender_lower not in item_email:
                    continue
            subject = (item.Subject or "").lower()
            body = (item.Body or "").lower()
            if query_lower in subject or query_lower in body:
                emails.append(_item_to_email(item))
        except Exception:
            continue
    return emails


@_with_retry
def search_emails(
    query: str,
    folder: str = "Inbox",
    limit: int = 50,
    all_folders: bool = False,
    sender: str | None = None,
    since: datetime | None = None,
) -> list[Email]:
    """Search emails by subject or body content.

    Uses Outlook's Restrict filter on Subject, falling back to iteration
    for body search.

    Args:
        query: Search string to match against subject and body.
        folder: Folder to search in (default: Inbox). Ignored when
            all_folders is True.
        limit: Maximum number of results.
        all_folders: If True, search across Inbox, Sent Items, and all
            custom top-level folders under the default account.
        sender: If provided, only return emails where the sender name or
            email address contains this string (case-insensitive).
        since: If provided, only return emails received after this datetime.

    Returns:
        List of matching Email objects, newest first.
    """
    if not all_folders:
        return _search_single_folder(query, folder, limit, sender=sender, since=since)

    # Search across all mail folders
    ns = get_namespace()
    seen_ids: set[str] = set()
    all_emails: list[Email] = []

    # Standard folders first
    for std_folder in ("Inbox", "Sent"):
        for email in _search_single_folder(query, std_folder, limit, sender=sender, since=since):
            if email.id not in seen_ids:
                seen_ids.add(email.id)
                all_emails.append(email)

    # Custom top-level folders under each store
    for i in range(ns.Folders.Count):
        store = ns.Folders.Item(i + 1)
        for j in range(store.Folders.Count):
            try:
                sub = store.Folders.Item(j + 1)
                name = sub.Name
                if name.lower() in _SYSTEM_FOLDERS:
                    continue
                for email in _search_single_folder(query, name, limit, sender=sender, since=since):
                    if email.id not in seen_ids:
                        seen_ids.add(email.id)
                        all_emails.append(email)
            except Exception:
                continue

    # Sort newest first and apply limit
    all_emails.sort(key=lambda e: e.received_time or datetime.min, reverse=True)
    return all_emails[:limit]


@_with_retry
def get_email(entry_id: str) -> Email:
    """Get a single email by its EntryID.

    Args:
        entry_id: The Outlook EntryID of the email.

    Returns:
        Email object with full body content.
    """
    ns = get_namespace()
    item = ns.GetItemFromID(entry_id)
    return _item_to_email(item)


_BODY_FONT = "font-family:Aptos,Calibri,sans-serif;font-size:12pt"

# ---------------------------------------------------------------------------
# Signature helpers
# ---------------------------------------------------------------------------

_SIG_DIR = os.path.join(os.environ.get("APPDATA", ""), "Microsoft", "Signatures")


def _load_signature_html() -> str:
    """Load the default Outlook signature from the Signatures directory.

    Returns the HTML content of the first .htm signature file found,
    or an empty string if none exists.
    """
    if not os.path.isdir(_SIG_DIR):
        return ""
    for fname in sorted(os.listdir(_SIG_DIR)):
        if fname.endswith(".htm"):
            path = os.path.join(_SIG_DIR, fname)
            try:
                with open(path, encoding="utf-8") as f:
                    return f.read()
            except OSError:
                continue
    return ""


def _text_to_html(text: str) -> str:
    """Convert plain text body to styled HTML paragraphs."""
    lines = text.split("\n")
    parts = []
    for line in lines:
        if line.strip() == "":
            parts.append("<br>")
        else:
            parts.append(f'<p style="margin:0;{_BODY_FONT}">{line}</p>')
    return "".join(parts)


def _insert_body_html(body: str, existing_html: str, include_signature: bool = False) -> str:
    """Prepend styled body HTML before existing content (e.g., signature or quoted thread).

    Converts plain text to styled HTML paragraphs and inserts them after the
    <body> tag in the existing HTML, preserving signature and quoted content.

    Args:
        body: Plain text body to insert.
        existing_html: The existing HTML content (e.g., from Reply or new mail).
        include_signature: If True, append the Outlook signature after the body.
    """
    body_html = _text_to_html(body)
    if include_signature:
        sig = _load_signature_html()
        if sig:
            body_html += "<br>" + sig
    return re.sub(
        r"(<body[^>]*>)",
        r"\1" + body_html + "<br>",
        existing_html,
        count=1,
        flags=re.IGNORECASE,
    )


@_with_retry
def reply(
    entry_id: str,
    body: str,
    reply_all: bool = False,
    cc: str | list[str] | None = None,
    send: bool = True,
) -> str:
    """Reply to an email.

    Args:
        entry_id: The EntryID of the email to reply to.
        body: The reply body text.
        reply_all: If True, reply to all recipients.
        cc: Optional CC address(es) to add to the reply.
        send: If True, send immediately. If False, save as draft.

    Returns:
        EntryID of the saved draft (when send=False), or empty string (when sent).
    """
    ns = get_namespace()
    item = ns.GetItemFromID(entry_id)
    reply_item = item.ReplyAll() if reply_all else item.Reply()

    if cc:
        existing_cc = reply_item.CC or ""
        new_cc = "; ".join(cc) if isinstance(cc, list) else cc
        reply_item.CC = f"{existing_cc}; {new_cc}" if existing_cc else new_cc

    # Insert styled HTML body + signature before the quoted thread
    reply_item.HTMLBody = _insert_body_html(body, reply_item.HTMLBody, include_signature=True)

    if send:
        reply_item.Send()
        logger.info("Reply sent to %s", item.Subject)
        return ""
    else:
        reply_item.Save()
        logger.info("Reply draft saved for %s", item.Subject)
        return reply_item.EntryID


@_with_retry
def forward(
    entry_id: str,
    to: str | list[str],
    body: str | None = None,
    cc: str | list[str] | None = None,
    send: bool = True,
) -> str:
    """Forward an email.

    Args:
        entry_id: The EntryID of the email to forward.
        to: Recipient email address(es).
        body: Optional message to prepend to the forwarded email.
        cc: Optional CC address(es).
        send: If True, send immediately. If False, save as draft.

    Returns:
        EntryID of the saved draft (when send=False), or empty string (when sent).
    """
    ns = get_namespace()
    item = ns.GetItemFromID(entry_id)
    fwd = item.Forward()
    if isinstance(to, str):
        to = [to]
    fwd.To = "; ".join(to)
    if cc:
        fwd.CC = "; ".join(cc) if isinstance(cc, list) else cc
    if body:
        fwd.HTMLBody = _insert_body_html(body, fwd.HTMLBody, include_signature=True)
    if send:
        fwd.Send()
        logger.info("Forwarded '%s' to %s", item.Subject, to)
        return ""
    else:
        fwd.Save()
        logger.info("Forward draft saved for '%s'", item.Subject)
        return fwd.EntryID


@_with_retry
def send_email(
    to: str | list[str],
    subject: str,
    body: str,
    cc: str | list[str] | None = None,
    bcc: str | list[str] | None = None,
    attachments: list[str] | None = None,
    html: bool = False,
) -> None:
    """Compose and send an email.

    Args:
        to: Recipient email address(es).
        subject: Email subject line.
        body: Email body text.
        cc: Optional CC address(es).
        bcc: Optional BCC address(es).
        attachments: Optional list of file paths to attach.
        html: If True, set body as HTML content.
    """
    app = get_outlook_app()
    mail = app.CreateItem(OL_MAIL_ITEM)

    if isinstance(to, list):
        to = "; ".join(to)
    mail.To = to
    mail.Subject = subject

    if html:
        mail.HTMLBody = body
    else:
        mail.HTMLBody = _text_to_html(body)

    if cc:
        mail.CC = "; ".join(cc) if isinstance(cc, list) else cc
    if bcc:
        mail.BCC = "; ".join(bcc) if isinstance(bcc, list) else bcc
    if attachments:
        for path in attachments:
            mail.Attachments.Add(path)

    mail.Send()
    logger.info("Email sent to %s: %s", to, subject)


@_with_retry
def get_unread_count(folder: str = "Inbox") -> int:
    """Return the number of unread emails in a folder.

    Args:
        folder: Folder name (default: Inbox).

    Returns:
        Number of unread items.
    """
    fld = _get_folder(folder)
    return fld.UnReadItemCount


@_with_retry
def get_recent_from(
    sender: str,
    limit: int = 5,
    all_folders: bool = True,
) -> list[Email]:
    """Get recent emails from a specific sender.

    Convenience wrapper for quickly looking up recent messages from someone.

    Args:
        sender: Sender name or email substring (case-insensitive).
        limit: Maximum number of emails to return.
        all_folders: If True, search across all folders.

    Returns:
        List of Email objects from the sender, newest first.
    """
    return search_emails(
        query="",
        limit=limit,
        sender=sender,
        all_folders=all_folders,
    )


@_with_retry
def get_flagged_emails(limit: int = 50) -> list[Email]:
    """Return emails flagged for follow-up in the Inbox.

    Args:
        limit: Maximum number of flagged emails to return.

    Returns:
        List of flagged Email objects, newest first.
    """
    folder = _get_folder("Inbox")
    items = folder.Items
    items.Sort("[ReceivedTime]", Descending=True)

    restricted = items.Restrict(f"[FlagStatus] = {OL_FLAG_MARKED}")
    emails = []
    for item in restricted:
        if len(emails) >= limit:
            break
        try:
            if item.Class == 43:
                emails.append(_item_to_email(item))
        except Exception:
            logger.debug("Skipping flagged item", exc_info=True)
    return emails


@_with_retry
def count_by_sender(
    folder: str = "Inbox",
    limit: int = 200,
    since: datetime | None = None,
) -> list[tuple[str, str, int]]:
    """Count emails grouped by sender.

    Useful for seeing who emails you the most.

    Args:
        folder: Folder to analyze (default: Inbox).
        limit: Max emails to scan.
        since: If provided, only count emails received after this datetime.

    Returns:
        List of (sender_name, sender_email, count) tuples, sorted by
        count descending.
    """
    from collections import Counter

    fld = _get_folder(folder)
    items = fld.Items
    items.Sort("[ReceivedTime]", Descending=True)

    if since:
        date_str = _datetime_to_outlook_str(since)
        items = items.Restrict(f"[ReceivedTime] >= '{date_str}'")

    sender_counts: Counter[tuple[str, str]] = Counter()
    scanned = 0
    for item in items:
        if scanned >= limit:
            break
        try:
            if item.Class != 43:
                continue
            name = item.SenderName or ""
            email = _get_sender_email(item)
            sender_counts[(name, email)] += 1
            scanned += 1
        except Exception:
            continue

    return [(name, email, count) for (name, email), count in sender_counts.most_common()]


def send_personalized_emails(
    recipients: list[dict],
    subject: str,
    body_template: str,
    cc: str | None = None,
    delay: float = 1.5,
    dry_run: bool = False,
) -> tuple[int, list[dict]]:
    """Send individual personalized emails through Outlook.

    Args:
        recipients: List of dicts with at least 'email' and any keys used
                    in body_template (e.g., [{"first_name": "Alice", "email": "alice@example.com"}]).
        subject: Email subject line (same for all recipients).
        body_template: Email body with {placeholders} matching recipient dict keys.
        cc: Optional CC email address (applied to all emails).
        delay: Seconds to wait between sends (default 1.5).
        dry_run: If True, print emails without sending.

    Returns:
        Tuple of (sent_count, failed_list).
    """
    if not dry_run:
        app = get_outlook_app()

    sent = 0
    failed = []
    total = len(recipients)

    for r in recipients:
        body = body_template.format(**r)

        if dry_run:
            logger.info(
                "[DRY RUN %d/%d] Would send to %s (%s)",
                sent + 1,
                total,
                r.get("first_name", "?"),
                r["email"],
            )
            if sent == 0:
                logger.info(
                    "Preview — To: %s | Subject: %s | Body: %s...",
                    r["email"],
                    subject,
                    body[:300],
                )
            sent += 1
            continue

        try:
            mail = app.CreateItem(OL_MAIL_ITEM)
            mail.To = r["email"]
            if cc:
                mail.CC = cc
            mail.Subject = subject
            mail.HTMLBody = _text_to_html(body)
            mail.Send()
            sent += 1
            logger.info(
                "[%d/%d] Sent to %s (%s)",
                sent,
                total,
                r.get("first_name", "?"),
                r["email"],
            )
            if sent < total:
                time.sleep(delay)
        except Exception as e:
            failed.append(r)
            logger.error(
                "FAILED: %s (%s) - %s",
                r.get("first_name", "?"),
                r["email"],
                e,
            )

    logger.info("Done! Sent %d/%d emails.", sent, total)
    if failed:
        logger.warning("Failed: %d", len(failed))
        for f in failed:
            logger.warning("  - %s", f["email"])

    return sent, failed


def send_summary_email(
    to: str,
    subject: str,
    recipients: list[dict],
    original_subject: str,
    original_body_template: str,
    sender_name: str = "Bobby",
) -> None:
    """Send a summary/FYI email with the template and recipient list.

    Args:
        to: Recipient email (e.g., your PI).
        subject: Subject for the summary email.
        recipients: The same list used for send_personalized_emails.
        original_subject: The subject line that was sent to applicants.
        original_body_template: The body template (with {placeholders} intact).
        sender_name: Your name for the sign-off.
    """
    app = get_outlook_app()

    recipient_list = "\n".join(
        [
            f"  {i + 1}. {r.get('first_name', '?')} - {r['email']}"
            for i, r in enumerate(sorted(recipients, key=lambda x: x.get("first_name", "")))
        ]
    )

    body = f"""Hi,

Just a heads-up \u2014 I've sent the following email to {len(recipients)} applicants. The details are below.

---

Subject: {original_subject}

{original_body_template}

---

Full recipient list:
{recipient_list}

Let me know if you have any questions.

Best,
{sender_name}"""

    mail = app.CreateItem(OL_MAIL_ITEM)
    mail.To = to
    mail.Subject = subject
    mail.HTMLBody = _text_to_html(body)
    mail.Send()
    logger.info("Summary email sent to %s", to)


# ---------------------------------------------------------------------------
# Thread / conversation helpers
# ---------------------------------------------------------------------------


@_with_retry
def reply_to_thread(
    subject: str,
    body: str,
    reply_all: bool = True,
    folder: str = "Inbox",
    cc: str | list[str] | None = None,
    send: bool = True,
    all_folders: bool = False,
) -> None:
    """Find the most recent email by subject and reply in-thread.

    Args:
        subject: Subject line to search for (partial match).
        body: The reply body text.
        reply_all: If True, reply to all recipients.
        folder: Folder to search in (default: Inbox).
        cc: Optional CC address(es) to add to the reply.
        send: If True, send immediately. If False, save as draft.
        all_folders: If True, search across all folders to find the thread.
    """
    results = search_emails(subject, folder=folder, limit=1, all_folders=all_folders)
    if not results:
        raise ValueError(f"No email found with subject matching: {subject}")

    reply(
        entry_id=results[0].id,
        body=body,
        reply_all=reply_all,
        cc=cc,
        send=send,
    )
    action = "sent" if send else "drafted"
    logger.info("Reply %s in thread '%s'", action, results[0].subject)


@_with_retry
def send_with_signature(
    to: str | list[str],
    subject: str,
    body: str,
    cc: str | list[str] | None = None,
    bcc: str | list[str] | None = None,
    attachments: list[str] | None = None,
    html: bool = False,
) -> None:
    """Compose and send an email with Outlook's default signature.

    Reads the signature from the Signatures directory on disk and appends
    it after the body text.

    Args:
        to: Recipient email address(es).
        subject: Email subject line.
        body: Email body text (inserted above the signature).
        cc: Optional CC address(es).
        bcc: Optional BCC address(es).
        attachments: Optional list of file paths to attach.
        html: If True, set body as HTML content.
    """
    app = get_outlook_app()
    mail = app.CreateItem(OL_MAIL_ITEM)

    if isinstance(to, list):
        to = "; ".join(to)
    mail.To = to
    mail.Subject = subject

    if cc:
        mail.CC = "; ".join(cc) if isinstance(cc, list) else cc
    if bcc:
        mail.BCC = "; ".join(bcc) if isinstance(bcc, list) else bcc
    if attachments:
        for path in attachments:
            mail.Attachments.Add(path)

    # Build HTML body with signature from file
    sig = _load_signature_html()
    body_html = _text_to_html(body)
    if sig:
        body_html += "<br>" + sig
    mail.HTMLBody = f"<html><body>{body_html}</body></html>"

    mail.Send()
    logger.info("Email with signature sent to %s: %s", to, subject)


@_with_retry
def create_draft(
    to: str | list[str],
    subject: str,
    body: str,
    cc: str | list[str] | None = None,
    bcc: str | list[str] | None = None,
    attachments: list[str] | None = None,
) -> str:
    """Create a draft email with Outlook's default signature.

    Reads the signature from the Signatures directory on disk and appends
    it after the body text.

    Args:
        to: Recipient email address(es).
        subject: Email subject line.
        body: Email body text (inserted above the signature).
        cc: Optional CC address(es).
        bcc: Optional BCC address(es).
        attachments: Optional list of file paths to attach.

    Returns:
        The EntryID of the saved draft.
    """
    app = get_outlook_app()
    mail = app.CreateItem(OL_MAIL_ITEM)

    if isinstance(to, list):
        to = "; ".join(to)
    mail.To = to
    mail.Subject = subject

    if cc:
        mail.CC = "; ".join(cc) if isinstance(cc, list) else cc
    if bcc:
        mail.BCC = "; ".join(bcc) if isinstance(bcc, list) else bcc
    if attachments:
        for path in attachments:
            mail.Attachments.Add(path)

    # Build HTML body with signature from file
    sig = _load_signature_html()
    body_html = _text_to_html(body)
    if sig:
        body_html += "<br>" + sig
    mail.HTMLBody = f"<html><body>{body_html}</body></html>"

    mail.Save()
    draft_id = mail.EntryID
    logger.info("Draft created: %s (to: %s)", subject, to)
    return draft_id


@_with_retry
def get_drafts(limit: int = 50) -> list[Email]:
    """List draft emails.

    Args:
        limit: Maximum number of drafts to return.

    Returns:
        List of Email objects from the Drafts folder, newest first.
    """
    ns = get_namespace()
    folder = ns.GetDefaultFolder(OL_FOLDER_DRAFTS)
    items = folder.Items
    items.Sort("[CreationTime]", Descending=True)

    drafts = []
    for item in items:
        if len(drafts) >= limit:
            break
        try:
            if item.Class == 43:  # olMail
                drafts.append(_item_to_email(item))
        except Exception:
            logger.debug("Skipping draft item", exc_info=True)
    return drafts


@_with_retry
def send_draft(entry_id: str) -> None:
    """Send an existing draft email.

    Args:
        entry_id: The EntryID of the draft to send.

    Raises:
        ValueError: If the item is not found or is not a draft.
    """
    ns = get_namespace()
    item = ns.GetItemFromID(entry_id)
    subject = item.Subject
    item.Send()
    logger.info("Draft sent: %s", subject)


@_with_retry
def get_conversation(conversation_id: str, limit: int = 50) -> list[Email]:
    """Get the full email thread by ConversationID.

    Searches Inbox, Sent Items, and all custom folders, deduplicates,
    and returns messages in chronological order (oldest first).

    Args:
        conversation_id: The Outlook ConversationID string.
        limit: Maximum number of emails to return.

    Returns:
        List of Email objects, oldest first.
    """
    ns = get_namespace()
    escaped = conversation_id.replace("'", "''")
    restriction = f"[ConversationID] = '{escaped}'"

    seen_ids: set[str] = set()
    emails: list[Email] = []

    def _scan_folder(folder):
        items = folder.Items
        try:
            restricted = items.Restrict(restriction)
        except Exception:
            return
        for item in restricted:
            if len(emails) >= limit:
                break
            try:
                if item.Class != 43:
                    continue
                eid = item.EntryID
                if eid in seen_ids:
                    continue
                seen_ids.add(eid)
                emails.append(_item_to_email(item))
            except Exception:
                logger.debug("Skipping item in conversation", exc_info=True)

    # Standard folders
    for folder_id in (OL_FOLDER_INBOX, OL_FOLDER_SENT):
        _scan_folder(ns.GetDefaultFolder(folder_id))

    # Custom top-level folders
    for i in range(ns.Folders.Count):
        store = ns.Folders.Item(i + 1)
        for j in range(store.Folders.Count):
            try:
                sub = store.Folders.Item(j + 1)
                if sub.Name.lower() in _SYSTEM_FOLDERS:
                    continue
                _scan_folder(sub)
            except Exception:
                continue

    # Sort oldest-first for natural reading order
    emails.sort(key=lambda e: e.received_time or datetime.min)
    return emails


@_with_retry
def search_sent(query: str, limit: int = 50) -> list[Email]:
    """Search the Sent Items folder.

    Convenience wrapper around search_emails for the Sent folder.

    Args:
        query: Search string to match against subject and body.
        limit: Maximum number of results.

    Returns:
        List of matching Email objects, newest first.
    """
    return search_emails(query, folder="Sent", limit=limit)


# ---------------------------------------------------------------------------
# Attachment helpers
# ---------------------------------------------------------------------------


@_with_retry
def get_attachments_info(entry_id: str) -> list[dict[str, str]]:
    """List attachments on an email without downloading them.

    Args:
        entry_id: The Outlook EntryID of the email.

    Returns:
        List of dicts with 'filename', 'size', and 'index' keys.
    """
    ns = get_namespace()
    item = ns.GetItemFromID(entry_id)
    attachments = []
    for i in range(1, item.Attachments.Count + 1):
        att = item.Attachments.Item(i)
        attachments.append(
            {
                "filename": att.FileName,
                "size": att.Size,
                "index": i,
            }
        )
    return attachments


@_with_retry
def save_attachments(entry_id: str, dest_dir: str) -> list[str]:
    """Save all attachments from an email to a directory.

    Args:
        entry_id: The Outlook EntryID of the email.
        dest_dir: Directory path to save attachments into.

    Returns:
        List of saved file paths.

    Raises:
        FileNotFoundError: If dest_dir does not exist.
    """
    if not os.path.isdir(dest_dir):
        raise FileNotFoundError(f"Directory does not exist: {dest_dir}")

    ns = get_namespace()
    item = ns.GetItemFromID(entry_id)
    saved: list[str] = []

    for i in range(1, item.Attachments.Count + 1):
        att = item.Attachments.Item(i)
        filepath = os.path.join(dest_dir, att.FileName)
        att.SaveAsFile(filepath)
        saved.append(filepath)

    logger.info(
        "Saved %d attachment(s) from '%s' to %s",
        len(saved),
        item.Subject,
        dest_dir,
    )
    return saved


# ---------------------------------------------------------------------------
# Status / flag / folder management
# ---------------------------------------------------------------------------


@_with_retry
def mark_read(entry_id: str) -> None:
    """Mark an email as read.

    Args:
        entry_id: The Outlook EntryID of the email.
    """
    ns = get_namespace()
    item = ns.GetItemFromID(entry_id)
    item.UnRead = False
    item.Save()
    logger.info("Marked as read: %s", item.Subject)


@_with_retry
def mark_unread(entry_id: str) -> None:
    """Mark an email as unread.

    Args:
        entry_id: The Outlook EntryID of the email.
    """
    ns = get_namespace()
    item = ns.GetItemFromID(entry_id)
    item.UnRead = True
    item.Save()
    logger.info("Marked as unread: %s", item.Subject)


@_with_retry
def move_to_folder(entry_id: str, folder_name: str) -> None:
    """Move an email to a different folder.

    Args:
        entry_id: The Outlook EntryID of the email.
        folder_name: Destination folder name (e.g., "Archive", "Junk").
    """
    ns = get_namespace()
    item = ns.GetItemFromID(entry_id)
    subject = item.Subject  # capture before move invalidates COM ref
    dest = _get_folder(folder_name)
    item.Move(dest)
    logger.info("Moved '%s' to %s", subject, folder_name)


@_with_retry
def flag_email(entry_id: str, flag: bool = True) -> None:
    """Set or clear the follow-up flag on an email.

    Args:
        entry_id: The Outlook EntryID of the email.
        flag: If True, flag for follow-up. If False, clear the flag.
    """
    ns = get_namespace()
    item = ns.GetItemFromID(entry_id)
    item.FlagStatus = OL_FLAG_MARKED if flag else OL_FLAG_NOT_FLAGGED
    item.Save()
    action = "Flagged" if flag else "Unflagged"
    logger.info("%s: %s", action, item.Subject)


@_with_retry
def complete_flag(entry_id: str) -> None:
    """Mark a follow-up flag as complete (checkmark in Outlook).

    Different from unflagging — this marks the task as done rather than
    removing the flag entirely.

    Args:
        entry_id: The Outlook EntryID of the email.
    """
    ns = get_namespace()
    item = ns.GetItemFromID(entry_id)
    item.FlagStatus = OL_FLAG_COMPLETE
    item.Save()
    logger.info("Flag completed: %s", item.Subject)


@_with_retry
def mark_read_batch(entry_ids: list[str]) -> int:
    """Mark multiple emails as read in one call.

    Args:
        entry_ids: List of Outlook EntryIDs.

    Returns:
        Number of emails successfully marked as read.
    """
    ns = get_namespace()
    count = 0
    for eid in entry_ids:
        try:
            item = ns.GetItemFromID(eid)
            item.UnRead = False
            item.Save()
            count += 1
        except Exception:
            logger.debug("Failed to mark read: %s", eid, exc_info=True)
    logger.info("Marked %d/%d emails as read", count, len(entry_ids))
    return count


@_with_retry
def move_batch(entry_ids: list[str], folder_name: str) -> int:
    """Move multiple emails to a folder in one call.

    Args:
        entry_ids: List of Outlook EntryIDs.
        folder_name: Destination folder name.

    Returns:
        Number of emails successfully moved.
    """
    ns = get_namespace()
    dest = _get_folder(folder_name)
    count = 0
    for eid in entry_ids:
        try:
            item = ns.GetItemFromID(eid)
            item.Move(dest)
            count += 1
        except Exception:
            logger.debug("Failed to move: %s", eid, exc_info=True)
    logger.info("Moved %d/%d emails to %s", count, len(entry_ids), folder_name)
    return count


@_with_retry
def delete_email(entry_id: str, permanent: bool = False) -> None:
    """Delete an email.

    Args:
        entry_id: The Outlook EntryID of the email.
        permanent: If False (default), move to Deleted Items.
                   If True, permanently delete (moves to Deleted Items
                   first, then deletes from there).
    """
    ns = get_namespace()
    item = ns.GetItemFromID(entry_id)
    subject = item.Subject

    if permanent:
        deleted_folder = ns.GetDefaultFolder(OL_FOLDER_DELETED)
        moved = item.Move(deleted_folder)
        moved.Delete()
        logger.info("Permanently deleted: %s", subject)
    else:
        item.Delete()
        logger.info("Deleted (to trash): %s", subject)


@_with_retry
def set_categories(entry_id: str, categories: list[str]) -> None:
    """Set categories on an email, replacing any existing ones.

    Args:
        entry_id: The Outlook EntryID of the email.
        categories: List of category names to set.
    """
    ns = get_namespace()
    item = ns.GetItemFromID(entry_id)
    item.Categories = ", ".join(categories)
    item.Save()
    logger.info("Set categories on '%s': %s", item.Subject, categories)


@_with_retry
def add_category(entry_id: str, category: str) -> None:
    """Add a category to an email without removing existing ones.

    Args:
        entry_id: The Outlook EntryID of the email.
        category: Category name to add.
    """
    ns = get_namespace()
    item = ns.GetItemFromID(entry_id)
    existing = item.Categories or ""
    current = [c.strip() for c in existing.split(",") if c.strip()]
    if category not in current:
        current.append(category)
        item.Categories = ", ".join(current)
        item.Save()
        logger.info("Added category '%s' to '%s'", category, item.Subject)


@_with_retry
def remove_category(entry_id: str, category: str) -> None:
    """Remove a category from an email.

    Args:
        entry_id: The Outlook EntryID of the email.
        category: Category name to remove.
    """
    ns = get_namespace()
    item = ns.GetItemFromID(entry_id)
    existing = item.Categories or ""
    current = [c.strip() for c in existing.split(",") if c.strip()]
    if category in current:
        current.remove(category)
        item.Categories = ", ".join(current)
        item.Save()
        logger.info("Removed category '%s' from '%s'", category, item.Subject)


@_with_retry
def get_email_stats(
    folder: str = "Inbox",
    days: int = 7,
    limit: int = 500,
) -> dict:
    """Get email statistics for a folder over the last N days.

    Args:
        folder: Folder to analyze (default: Inbox).
        days: Number of days to look back.
        limit: Max emails to scan.

    Returns:
        Dict with keys: total, unread, days_covered, avg_per_day,
        top_senders (list of {name, email, count}),
        by_day (dict of date_str -> count).
    """
    from collections import Counter
    from datetime import timedelta

    since = datetime.now() - timedelta(days=days)
    fld = _get_folder(folder)
    items = fld.Items
    items.Sort("[ReceivedTime]", Descending=True)

    date_str = _datetime_to_outlook_str(since)
    items = items.Restrict(f"[ReceivedTime] >= '{date_str}'")

    total = 0
    unread = 0
    sender_counts: Counter[tuple[str, str]] = Counter()
    by_day: Counter[str] = Counter()

    for item in items:
        if total >= limit:
            break
        try:
            if item.Class != 43:
                continue
            total += 1
            if item.UnRead:
                unread += 1
            name = item.SenderName or ""
            email = _get_sender_email(item)
            sender_counts[(name, email)] += 1
            try:
                recv = _com_date_to_datetime(item.ReceivedTime)
                by_day[recv.strftime("%Y-%m-%d")] += 1
            except Exception:
                pass
        except Exception:
            continue

    top_senders = [
        {"name": name, "email": email, "count": count}
        for (name, email), count in sender_counts.most_common(10)
    ]

    avg_per_day = round(total / max(days, 1), 1)

    return {
        "total": total,
        "unread": unread,
        "days_covered": days,
        "avg_per_day": avg_per_day,
        "top_senders": top_senders,
        "by_day": dict(by_day),
    }
