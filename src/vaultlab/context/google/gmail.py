"""Gmail API helpers — send emails with attachments via Google API."""

import base64
import mimetypes
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from vaultlab.context.google.auth import build_service


def _get_service():
    return build_service("gmail", "v1")


def send_email(to, subject, body, attachments=None):
    """Send an email via Gmail API.

    Args:
        to: Recipient email address.
        subject: Email subject line.
        body: Plain text body.
        attachments: Optional list of file paths to attach.
    """
    service = _get_service()
    profile = service.users().getProfile(userId="me").execute()
    sender = profile["emailAddress"]

    if attachments:
        msg = MIMEMultipart()
        msg.attach(MIMEText(body, "plain"))
        for filepath in attachments:
            path = Path(filepath)
            if not path.exists():
                continue
            ctype, _ = mimetypes.guess_type(str(path))
            if ctype is None:
                ctype = "application/octet-stream"
            maintype, subtype = ctype.split("/", 1)
            with open(path, "rb") as f:
                part = MIMEBase(maintype, subtype)
                part.set_payload(f.read())
            from email import encoders
            encoders.encode_base64(part)
            part.add_header("Content-Disposition", "attachment", filename=path.name)
            msg.attach(part)
    else:
        msg = MIMEText(body, "plain")

    msg["to"] = to
    msg["from"] = sender
    msg["subject"] = subject

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    service.users().messages().send(
        userId="me", body={"raw": raw}
    ).execute()
