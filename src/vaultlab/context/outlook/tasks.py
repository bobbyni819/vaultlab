"""Outlook tasks operations via the COM API.

Read, create, and complete tasks in the default Tasks folder.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from vaultlab.context.outlook._connection import get_namespace, get_outlook_app, _with_retry
from vaultlab.context.outlook._constants import (
    OL_FOLDER_TASKS,
    OL_IMPORTANCE_HIGH,
    OL_IMPORTANCE_LOW,
    OL_IMPORTANCE_NORMAL,
    OL_TASK_COMPLETE,
    OL_TASK_ITEM,
    TASK_STATUS_MAP,
)
from vaultlab.context.outlook._converters import _com_date_to_datetime, _importance_str
from vaultlab.context.outlook.models import Task

logger = logging.getLogger(__name__)

_PRIORITY_MAP = {
    "low": OL_IMPORTANCE_LOW,
    "normal": OL_IMPORTANCE_NORMAL,
    "high": OL_IMPORTANCE_HIGH,
}


def _item_to_task(item) -> Task:
    """Convert a COM TaskItem to a Task dataclass."""
    due_date = None
    try:
        due_date = _com_date_to_datetime(item.DueDate)
        # Outlook uses 1/1/4501 as "no date" sentinel
        if due_date.year > 4000:
            due_date = None
    except Exception:
        pass

    start_date = None
    try:
        start_date = _com_date_to_datetime(item.StartDate)
        if start_date.year > 4000:
            start_date = None
    except Exception:
        pass

    return Task(
        id=item.EntryID,
        subject=item.Subject or "",
        body=item.Body or "",
        due_date=due_date,
        start_date=start_date,
        status=TASK_STATUS_MAP.get(item.Status, "not_started"),
        percent_complete=item.PercentComplete,
        priority=_importance_str(item.Importance),
    )


@_with_retry
def read_tasks(include_completed: bool = False, limit: int = 100) -> list[Task]:
    """Read tasks from the default Tasks folder.

    Args:
        include_completed: If True, include completed tasks.
        limit: Maximum number of tasks to return.

    Returns:
        List of Task objects.
    """
    ns = get_namespace()
    folder = ns.GetDefaultFolder(OL_FOLDER_TASKS)
    items = folder.Items
    items.Sort("[DueDate]")

    if not include_completed:
        items = items.Restrict("[Complete] = False")

    tasks = []
    for item in items:
        if len(tasks) >= limit:
            break
        try:
            if item.Class == 48:  # olTask
                tasks.append(_item_to_task(item))
        except Exception:
            logger.debug("Skipping task item", exc_info=True)
    return tasks


@_with_retry
def create_task(
    subject: str,
    due_date: Optional[datetime] = None,
    body: Optional[str] = None,
    priority: Optional[str] = None,
) -> Task:
    """Create a new task in the default Tasks folder.

    Args:
        subject: Task subject/title.
        due_date: Optional due date.
        body: Optional task body/notes.
        priority: Optional priority ("low", "normal", "high").

    Returns:
        The created Task object.
    """
    app = get_outlook_app()
    item = app.CreateItem(OL_TASK_ITEM)
    item.Subject = subject

    if due_date:
        item.DueDate = due_date
    if body:
        item.Body = body
    if priority:
        item.Importance = _PRIORITY_MAP.get(priority.lower(), OL_IMPORTANCE_NORMAL)

    item.Save()
    logger.info("Task created: %s", subject)

    return Task(
        id=item.EntryID,
        subject=subject,
        body=body or "",
        due_date=due_date,
        priority=priority or "normal",
    )


@_with_retry
def update_task(
    entry_id: str,
    subject: Optional[str] = None,
    due_date: Optional[datetime] = None,
    body: Optional[str] = None,
    priority: Optional[str] = None,
) -> Task:
    """Update an existing task's fields.

    Only provided fields are modified; others are left unchanged.

    Args:
        entry_id: The Outlook EntryID of the task.
        subject: New subject/title.
        due_date: New due date.
        body: New body/notes.
        priority: New priority ("low", "normal", "high").

    Returns:
        The updated Task object.
    """
    ns = get_namespace()
    item = ns.GetItemFromID(entry_id)

    if subject is not None:
        item.Subject = subject
    if due_date is not None:
        item.DueDate = due_date
    if body is not None:
        item.Body = body
    if priority is not None:
        item.Importance = _PRIORITY_MAP.get(priority.lower(), OL_IMPORTANCE_NORMAL)

    item.Save()
    logger.info("Task updated: %s", item.Subject)
    return _item_to_task(item)


@_with_retry
def complete_task(entry_id: str) -> None:
    """Mark a task as 100% complete.

    Args:
        entry_id: The Outlook EntryID of the task.
    """
    ns = get_namespace()
    item = ns.GetItemFromID(entry_id)
    item.Status = OL_TASK_COMPLETE
    item.PercentComplete = 100
    item.Save()
    logger.info("Task completed: %s", item.Subject)


@_with_retry
def delete_task(entry_id: str) -> None:
    """Delete a task by its EntryID.

    Args:
        entry_id: The Outlook EntryID of the task.
    """
    ns = get_namespace()
    item = ns.GetItemFromID(entry_id)
    subject = item.Subject
    item.Delete()
    logger.info("Task deleted: %s", subject)


@_with_retry
def search_tasks(
    query: str,
    include_completed: bool = False,
    limit: int = 50,
    due_before: Optional[datetime] = None,
) -> list[Task]:
    """Search tasks by subject or body substring.

    Args:
        query: Search string to match against subject and body (case-insensitive).
        include_completed: If True, include completed tasks.
        limit: Maximum number of results.
        due_before: If set, only return tasks due before this date.

    Returns:
        List of matching Task objects.
    """
    ns = get_namespace()
    folder = ns.GetDefaultFolder(OL_FOLDER_TASKS)
    items = folder.Items
    items.Sort("[DueDate]")

    if not include_completed:
        items = items.Restrict("[Complete] = False")

    query_lower = query.lower()
    matches = []
    for item in items:
        if len(matches) >= limit:
            break
        try:
            if item.Class != 48:  # olTask
                continue
            subject = (item.Subject or "").lower()
            body = (item.Body or "").lower()
            if query_lower not in subject and query_lower not in body:
                continue
            if due_before is not None:
                task = _item_to_task(item)
                if task.due_date is None or task.due_date >= due_before:
                    continue
                matches.append(task)
            else:
                matches.append(_item_to_task(item))
        except Exception:
            logger.debug("Skipping task item", exc_info=True)
    return matches


@_with_retry
def get_overdue_tasks(limit: int = 50) -> list[Task]:
    """Return incomplete tasks that are past their due date.

    Args:
        limit: Maximum number of results.

    Returns:
        List of overdue Task objects, sorted by due date.
    """
    ns = get_namespace()
    folder = ns.GetDefaultFolder(OL_FOLDER_TASKS)
    items = folder.Items
    items.Sort("[DueDate]")
    items = items.Restrict("[Complete] = False")

    now = datetime.now()
    overdue = []
    for item in items:
        if len(overdue) >= limit:
            break
        try:
            if item.Class != 48:
                continue
            task = _item_to_task(item)
            if task.due_date is not None and task.due_date < now:
                overdue.append(task)
        except Exception:
            logger.debug("Skipping task item", exc_info=True)
    return overdue
