"""End-to-end smoke test: run the html_report_gallery example and verify all
expected outputs are written + are parseable HTML.
"""

from __future__ import annotations

import html.parser
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
EXAMPLE_SCRIPT = REPO_ROOT / "examples" / "html_report_gallery" / "run_gallery.py"


class _Validator(html.parser.HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.errors: list[str] = []

    def error(self, message: str) -> None:  # pragma: no cover
        self.errors.append(message)


def _parses(text: str) -> bool:
    v = _Validator()
    try:
        v.feed(text)
    except Exception as exc:  # pragma: no cover - very rare
        v.errors.append(str(exc))
    return not v.errors


def test_gallery_script_runs_end_to_end(tmp_path: Path):
    """Execute run_gallery.py as a module; verify all expected files appear."""
    if not EXAMPLE_SCRIPT.exists():
        pytest.skip("example script not present (clean repo only?)")

    # Add src/ to sys.path so we can import vaultlab without reinstall
    sys.path.insert(0, str(REPO_ROOT / "src"))

    # Import as a module instead of subprocess — faster, avoids env pollution
    spec_path = EXAMPLE_SCRIPT
    import importlib.util

    spec = importlib.util.spec_from_file_location("run_gallery", spec_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    rc = module.main(["--out", str(tmp_path)])
    assert rc == 0

    expected = [
        "index.html",
        "deck-audit.html",
        "litarc.html",
        "reasoning.html",
        "citation-audit.html",
        "dossier.html",
        "deck-preview.html",
        "slide-reorder.html",
        "citation-triage.html",
        "deckplan-tuner.html",
    ]
    for name in expected:
        path = tmp_path / name
        assert path.exists(), f"missing: {name}"
        text = path.read_text(encoding="utf-8")
        assert text.startswith("<!doctype html>"), f"{name}: not HTML"
        assert _parses(text), f"{name}: invalid HTML"


def test_index_links_to_every_consumer(tmp_path: Path):
    if not EXAMPLE_SCRIPT.exists():
        pytest.skip("example script not present")

    sys.path.insert(0, str(REPO_ROOT / "src"))
    import importlib.util

    spec = importlib.util.spec_from_file_location("run_gallery", EXAMPLE_SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.main(["--out", str(tmp_path)])

    index_text = (tmp_path / "index.html").read_text(encoding="utf-8")
    # The index should reference each consumer by filename in the copy-path actions
    for name in (
        "deck-audit.html",
        "litarc.html",
        "reasoning.html",
        "citation-audit.html",
        "dossier.html",
        "deck-preview.html",
        "slide-reorder.html",
        "citation-triage.html",
        "deckplan-tuner.html",
    ):
        assert name in index_text


def test_index_contains_card_grid(tmp_path: Path):
    if not EXAMPLE_SCRIPT.exists():
        pytest.skip("example script not present")

    sys.path.insert(0, str(REPO_ROOT / "src"))
    import importlib.util

    spec = importlib.util.spec_from_file_location("run_gallery", EXAMPLE_SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.main(["--out", str(tmp_path)])

    index_text = (tmp_path / "index.html").read_text(encoding="utf-8")
    assert "vl-cards" in index_text
    assert "10 HTML outputs generated" in index_text or "9 HTML outputs generated" in index_text
