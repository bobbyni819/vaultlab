"""Outlook COM API enum constants.

These mirror the OlDefaultFolders, OlItemType, and related enums from the
Outlook Object Model so we don't need to pull them at runtime.
"""

# --- Default folder IDs (OlDefaultFolders) ---
OL_FOLDER_INBOX = 6
OL_FOLDER_SENT = 5
OL_FOLDER_DRAFTS = 16
OL_FOLDER_CALENDAR = 9
OL_FOLDER_CONTACTS = 10
OL_FOLDER_TASKS = 13
OL_FOLDER_DELETED = 3
OL_FOLDER_OUTBOX = 4
OL_FOLDER_JUNK = 23

# --- Item types (OlItemType) ---
OL_MAIL_ITEM = 0
OL_APPOINTMENT_ITEM = 1
OL_CONTACT_ITEM = 2
OL_TASK_ITEM = 3

# --- Meeting status (OlMeetingStatus) ---
OL_MEETING = 1
OL_NON_MEETING = 0

# --- Importance (OlImportance) ---
OL_IMPORTANCE_LOW = 0
OL_IMPORTANCE_NORMAL = 1
OL_IMPORTANCE_HIGH = 2

IMPORTANCE_MAP = {
    OL_IMPORTANCE_LOW: "low",
    OL_IMPORTANCE_NORMAL: "normal",
    OL_IMPORTANCE_HIGH: "high",
}

# --- Task status (OlTaskStatus) ---
OL_TASK_NOT_STARTED = 0
OL_TASK_IN_PROGRESS = 1
OL_TASK_COMPLETE = 2
OL_TASK_WAITING = 3
OL_TASK_DEFERRED = 4

TASK_STATUS_MAP = {
    OL_TASK_NOT_STARTED: "not_started",
    OL_TASK_IN_PROGRESS: "in_progress",
    OL_TASK_COMPLETE: "complete",
    OL_TASK_WAITING: "waiting",
    OL_TASK_DEFERRED: "deferred",
}

# --- Busy status (OlBusyStatus) ---
OL_FREE = 0
OL_TENTATIVE = 1
OL_BUSY = 2
OL_OUT_OF_OFFICE = 3

# --- Recipient type (OlMailRecipientType) ---
OL_TO = 1
OL_CC = 2
OL_BCC = 3

# --- Folder name to default ID mapping ---
# --- Flag status (OlFlagStatus) ---
OL_FLAG_NOT_FLAGGED = 0
OL_FLAG_COMPLETE = 1
OL_FLAG_MARKED = 2

FOLDER_NAME_MAP = {
    "inbox": OL_FOLDER_INBOX,
    "sent": OL_FOLDER_SENT,
    "sent items": OL_FOLDER_SENT,
    "drafts": OL_FOLDER_DRAFTS,
    "calendar": OL_FOLDER_CALENDAR,
    "contacts": OL_FOLDER_CONTACTS,
    "tasks": OL_FOLDER_TASKS,
    "deleted": OL_FOLDER_DELETED,
    "deleted items": OL_FOLDER_DELETED,
    "outbox": OL_FOLDER_OUTBOX,
    "junk": OL_FOLDER_JUNK,
    "junk email": OL_FOLDER_JUNK,
}
