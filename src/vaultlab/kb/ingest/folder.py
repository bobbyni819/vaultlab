"""Folder ingestor — recurses a directory; dispatches each file."""

from __future__ import annotations

from pathlib import Path

from vaultlab.kb.ingest.dispatcher import URL_PATTERN, register
from vaultlab.kb.ingest.models import KbDocument


def matches_folder(source: str) -> bool:
    if URL_PATTERN.match(source):
        return False
    return Path(source).is_dir()


_DEFAULT_SKIP = {".git", ".obsidian", "__pycache__", ".pytest_cache", "node_modules", ".venv"}


@register(
    "folder",
    description="Recurse a directory and ingest every supported file inside. "
    "Skips .git/.obsidian/__pycache__/etc. by default.",
    implemented=True,
)
def ingest_folder(source: str) -> list[KbDocument]:
    # Lazy-import dispatcher.ingest so we get the bootstrap-protected version
    from vaultlab.kb.ingest.dispatcher import IngestError, ingest

    root = Path(source)
    docs: list[KbDocument] = []

    for path in sorted(root.rglob("*")):
        if any(part in _DEFAULT_SKIP for part in path.parts):
            continue
        if not path.is_file():
            continue
        try:
            result = ingest(str(path))
        except (IngestError, NotImplementedError):
            # Unsupported file type in folder — silent skip; the dispatcher's
            # error message is already informative if the caller tries the
            # specific file directly.
            continue
        if isinstance(result, list):
            docs.extend(result)
        else:
            docs.append(result)

    return docs
