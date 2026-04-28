"""
Centralized Google OAuth authentication for vaultlab.context.google.

Credentials layout (per machine):
    ~/.config/vaultlab/google/client_secret.json   - OAuth client ID (copy once per machine)
    ~/.config/vaultlab/google/tokens/google_token.json - generated on first sign-in, auto-refreshes

Lifted from bobby_google.auth (in bobby-tools) — adapted to use the
vaultlab config directory. Same OAuth flow, same scope set, same auto-refresh.

For a fresh setup walk-through, see docs/setup-google.md.
"""

import os

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# Allow opt-in to legacy bobby_google config dir (for users migrating from bobby-tools)
# by setting VAULTLAB_GOOGLE_CONFIG_DIR. Defaults to vaultlab namespace.
_CONFIG_DIR = os.environ.get(
    "VAULTLAB_GOOGLE_CONFIG_DIR",
    os.path.expanduser(os.path.join("~", ".config", "vaultlab", "google")),
)
_CLIENT_SECRET = os.path.join(_CONFIG_DIR, "client_secret.json")
_TOKEN_DIR = os.path.join(_CONFIG_DIR, "tokens")
_TOKEN_FILE = os.path.join(_TOKEN_DIR, "google_token.json")

ALL_SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/forms.body",
    "https://www.googleapis.com/auth/documents",
    "https://mail.google.com/",
    "https://www.googleapis.com/auth/calendar",
]


def get_credentials(scopes=None):
    """Get Google OAuth credentials, handling token refresh and first-time auth.

    Args:
        scopes: List of OAuth scopes. Defaults to ALL_SCOPES.

    Returns:
        google.oauth2.credentials.Credentials
    """
    scopes = scopes or ALL_SCOPES
    os.makedirs(_TOKEN_DIR, exist_ok=True)

    creds = None
    if os.path.exists(_TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(_TOKEN_FILE, scopes)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(_CLIENT_SECRET):
                raise FileNotFoundError(
                    f"Client secret not found at {_CLIENT_SECRET}\n"
                    "Copy your client_secret.json from Google Cloud Console to this path."
                )
            flow = InstalledAppFlow.from_client_secrets_file(_CLIENT_SECRET, scopes)
            creds = flow.run_local_server(port=8090)

        with open(_TOKEN_FILE, "w") as f:
            f.write(creds.to_json())

    return creds


def build_service(api, version, scopes=None):
    """Build a Google API service client.

    Args:
        api: API name (e.g. "sheets", "drive", "gmail", "forms", "docs")
        version: API version (e.g. "v4", "v3", "v1")
        scopes: Optional scope override

    Returns:
        googleapiclient.discovery.Resource

    Example:
        sheets = build_service("sheets", "v4")
        drive = build_service("drive", "v3")
    """
    creds = get_credentials(scopes)
    return build(api, version, credentials=creds)
