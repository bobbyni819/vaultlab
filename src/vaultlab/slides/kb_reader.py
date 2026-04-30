"""KB reader for vaultlab.slides.

Lifted from ``bobby_slides._content`` (bobby-tools, 2026-04). Port-not-rewrite:
pure file I/O over the standard KB layout (Sources/Wiki/Output) — no LLM, no
network. Used by the slide-deck composer to read concepts, summaries,
articles, and assets from a vaultlab knowledge base.

KB layout (per ``vaultlab.kb.paths`` conventions):

  <kb_root>/
    _Index.md, _Catalog.md, _Log.md
    Sources/Articles/  - paper summaries with YAML frontmatter
    Sources/Papers/    - full paper markdown
    Sources/Notes/     - analysis notes
    Sources/Assets/    - images, figures, screenshots
    Wiki/Concepts/     - synthesized concept pages
    Wiki/Methodology/  - pipeline docs
    Wiki/Summaries/    - cross-concept synthesis
    Output/Plans/, Drafts/, Reports/, Explorations/
"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Any

_FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n(.*)", re.DOTALL)
_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".svg", ".gif", ".webp"}


class KBNotFoundError(FileNotFoundError):
    """Raised when a KB root or expected subdirectory is missing."""


class KBReader:
    """Read structured content from a knowledge base.

    Args:
        kb_root: Path to the KB root (e.g. ``G:/My Drive/Knowledge/vaultlab``).

    Raises:
        KBNotFoundError: if ``kb_root`` does not exist or is not a directory.
    """

    def __init__(self, kb_root: Path | str):
        self.root = Path(kb_root)
        if not self.root.is_dir():
            raise KBNotFoundError(f"KB root not found or not a directory: {self.root}")

    # ------------------------------------------------------------------
    # Listing
    # ------------------------------------------------------------------

    def list_concepts(self) -> list[str]:
        """Return sorted list of concept page names (without ``.md`` extension)."""
        return self._list_md(self.root / "Wiki" / "Concepts")

    def list_methodology(self) -> list[str]:
        return self._list_md(self.root / "Wiki" / "Methodology")

    def list_summaries(self) -> list[str]:
        return self._list_md(self.root / "Wiki" / "Summaries")

    def list_articles(self) -> list[str]:
        return self._list_md(self.root / "Sources" / "Articles")

    def list_papers(self) -> list[str]:
        return self._list_md(self.root / "Sources" / "Papers")

    def list_notes(self) -> list[str]:
        return self._list_md(self.root / "Sources" / "Notes")

    @staticmethod
    def _list_md(directory: Path) -> list[str]:
        if not directory.is_dir():
            return []
        return sorted(p.stem for p in directory.glob("*.md") if p.is_file())

    # ------------------------------------------------------------------
    # Reading
    # ------------------------------------------------------------------

    def read_concept(self, name: str) -> dict[str, Any]:
        return self._read_md(self.root / "Wiki" / "Concepts" / f"{name}.md")

    def read_summary(self, name: str) -> dict[str, Any]:
        return self._read_md(self.root / "Wiki" / "Summaries" / f"{name}.md")

    def read_article(self, name: str) -> dict[str, Any]:
        return self._read_md(self.root / "Sources" / "Articles" / f"{name}.md")

    def read_paper(self, name: str) -> dict[str, Any]:
        return self._read_md(self.root / "Sources" / "Papers" / f"{name}.md")

    def read_note(self, name: str) -> dict[str, Any]:
        return self._read_md(self.root / "Sources" / "Notes" / f"{name}.md")

    def read_index(self) -> str:
        path = self.root / "_Index.md"
        if not path.is_file():
            return ""
        return path.read_text(encoding="utf-8")

    def read_catalog(self) -> str:
        path = self.root / "_Catalog.md"
        if not path.is_file():
            return ""
        return path.read_text(encoding="utf-8")

    @staticmethod
    def _read_md(path: Path) -> dict[str, Any]:
        if not path.is_file():
            raise FileNotFoundError(f"KB file not found: {path}")
        text = path.read_text(encoding="utf-8")
        frontmatter, body = _split_frontmatter(text)
        return {
            "path": str(path),
            "name": path.stem,
            "frontmatter": frontmatter,
            "body": body,
            "raw": text,
        }

    # ------------------------------------------------------------------
    # Figures / assets
    # ------------------------------------------------------------------

    def find_figures(self) -> list[Path]:
        """Return all image files under ``Sources/Assets/`` (recursive)."""
        assets = self.root / "Sources" / "Assets"
        if not assets.is_dir():
            return []
        return sorted(
            p for p in assets.rglob("*")
            if p.is_file() and p.suffix.lower() in _IMAGE_EXTS
        )

    # ------------------------------------------------------------------
    # Activity log
    # ------------------------------------------------------------------

    def append_log(
        self,
        action: str,
        title: str,
        body: str = "",
        pages: list[str] | None = None,
    ) -> None:
        """Append an entry to ``<kb>/_Log.md`` per the KB spec format.

        Format::

            ## [YYYY-MM-DD] action | Title

            Body text.
            - Pages updated: [[page1]], [[page2]]

        Args:
            action: one of ``"ingest"``, ``"query"``, ``"lint"``, ``"compile"``,
                ``"update"``, ``"reorganize"``.
            title: human-readable title for the entry.
            body: optional description paragraph.
            pages: optional list of wiki page names that were touched.
        """
        log_path = self.root / "_Log.md"
        date = datetime.now().strftime("%Y-%m-%d")
        lines = [f"## [{date}] {action} | {title}", ""]
        if body:
            lines.extend([body, ""])
        if pages:
            page_links = ", ".join(f"[[{p}]]" for p in pages)
            lines.append(f"- Pages updated: {page_links}")
            lines.append("")
        entry = "\n".join(lines) + "\n"

        existing = log_path.read_text(encoding="utf-8") if log_path.is_file() else ""
        log_path.write_text(existing + entry, encoding="utf-8")

    def write_report(self, filename: str, content: str) -> Path:
        """Write a generated report to ``<kb>/Output/Reports/<filename>``.

        Returns the path to the written file. Creates ``Output/Reports/`` if
        missing.
        """
        reports_dir = self.root / "Output" / "Reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        path = reports_dir / filename
        path.write_text(content, encoding="utf-8")
        return path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _split_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    """Split YAML frontmatter from markdown body.

    Returns ``(frontmatter_dict, body)``. If no frontmatter, returns
    ``({}, full_text)``.
    """
    match = _FRONTMATTER_RE.match(text)
    if not match:
        return {}, text
    try:
        import yaml  # type: ignore[import-not-found]
        fm = yaml.safe_load(match.group(1)) or {}
    except ImportError:
        # Fallback: simple key: value parser, no nested types
        fm = {}
        for line in match.group(1).splitlines():
            if ":" in line:
                k, _, v = line.partition(":")
                fm[k.strip()] = v.strip().strip("\"'")
    return fm, match.group(2)


__all__ = ["KBNotFoundError", "KBReader"]
