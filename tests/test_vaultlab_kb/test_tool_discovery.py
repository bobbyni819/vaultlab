"""Tests for vaultlab.kb.tools_index.discovery (SPEC-O extension).

Auto-discovery of computational tools from paper abstracts. Verifies
detection heuristics + metadata extraction + write-to-discovered/.
"""

from __future__ import annotations

from pathlib import Path
from unittest import mock

import pytest

from vaultlab.kb.tools_index.discovery import (
    DiscoveredTool,
    detect_tool_signature,
    discovered_dir,
    extract_tool_metadata,
    is_already_known,
    save_discovered_tool,
)


# Sample abstracts — real-shaped text patterns
ABSTRACT_INTRODUCES_TOOL = """
We present scvi-tools, a Python package for probabilistic analysis of
single-cell omics data. The package provides scVI, scANVI, totalVI,
and other generative models for batch correction and integration.
scvi-tools is open-source and available at https://github.com/scverse/scvi-tools.
Installation: pip install scvi-tools.
"""

ABSTRACT_REFERENCES_TOOL_BUT_DOES_NOT_INTRODUCE = """
We applied existing methods including scanpy and squidpy to analyze
spatial transcriptomics data from a cohort of 50 patients. The
analysis revealed that long-chain sphingomyelins accumulate in the
muscularis layer.
"""

ABSTRACT_INTRODUCES_R_PACKAGE = """
We introduce CellChat, an R package for inference and analysis of
intercellular communication networks from single-cell RNA-seq data.
CellChat is implemented in R and available via CRAN and at
https://github.com/sqjin/CellChat.
"""


def test_detects_tool_introducing_paper() -> None:
    """An abstract that introduces a tool returns is_tool_intro=True."""
    is_intro, signals = detect_tool_signature(ABSTRACT_INTRODUCES_TOOL)
    assert is_intro is True
    assert len(signals) >= 2  # at least 1 intro + 1 indicator


def test_does_not_flag_tool_using_paper() -> None:
    """An abstract that USES tools without introducing returns False."""
    is_intro, _ = detect_tool_signature(ABSTRACT_REFERENCES_TOOL_BUT_DOES_NOT_INTRODUCE)
    assert is_intro is False


def test_detects_r_package_introducing_paper() -> None:
    """R-language tool introduction also gets detected."""
    is_intro, _ = detect_tool_signature(ABSTRACT_INTRODUCES_R_PACKAGE)
    assert is_intro is True


def test_extract_metadata_python_package() -> None:
    """Extract returns a populated DiscoveredTool for a Python package."""
    tool = extract_tool_metadata(
        ABSTRACT_INTRODUCES_TOOL,
        paper_doi="10.1234/scvi-tools",
        discovered_via="test",
    )
    assert tool is not None
    assert tool.name.lower() == "scvi-tools"
    assert tool.language == "python"
    assert "pip install" in tool.install
    assert "github.com" in tool.repo_url
    assert "single-cell" in tool.domains or "scrnaseq" in tool.domains
    assert tool.paper_doi == "10.1234/scvi-tools"


def test_extract_metadata_r_package() -> None:
    """R package detection works."""
    tool = extract_tool_metadata(
        ABSTRACT_INTRODUCES_R_PACKAGE,
        paper_doi="10.1234/cellchat",
    )
    assert tool is not None
    assert tool.name.lower() == "cellchat"
    assert tool.language == "r"
    assert "github.com" in tool.repo_url


def test_extract_metadata_returns_none_for_non_tool_paper() -> None:
    """Non-tool-paper text returns None."""
    tool = extract_tool_metadata(ABSTRACT_REFERENCES_TOOL_BUT_DOES_NOT_INTRODUCE)
    assert tool is None


def test_extract_metadata_detects_input_format() -> None:
    """Input data formats are inferred from text."""
    text = (
        "We present squidpy, a Python package for spatial omics data analysis. "
        "It works on AnnData objects (.h5ad files) and supports OME-TIFF imaging. "
        "Available at https://github.com/scverse/squidpy. Install: pip install squidpy."
    )
    tool = extract_tool_metadata(text)
    assert tool is not None
    assert "anndata" in tool.input_data
    # h5ad is normalized to anndata; both may or may not appear depending on regex order
    assert any(fmt in tool.input_data for fmt in ["anndata", "h5ad"])


def test_is_already_known_detects_curated_packages() -> None:
    """Curated packages (e.g., scvi-tools, scanpy) are detected as known."""
    # These are curated in the bundled tools_index
    assert is_already_known("scvi-tools") is True
    assert is_already_known("scanpy") is True
    assert is_already_known("squidpy") is True


def test_is_already_known_returns_false_for_novel(tmp_path: Path) -> None:
    """Random unknown tool name returns False."""
    assert is_already_known("definitely_not_a_real_tool_xyz") is False


def test_save_discovered_tool_creates_md(tmp_path: Path, monkeypatch) -> None:
    """save_discovered_tool writes the .md to discovered/."""
    # Redirect packages_dir to a tmp location for the test
    fake_pkgs = tmp_path / "packages"
    fake_pkgs.mkdir()

    with mock.patch(
        "vaultlab.kb.tools_index.discovery.packages_dir",
        return_value=fake_pkgs,
    ), mock.patch(
        "vaultlab.kb.tools_index.discovery.load_index",
        return_value={},  # no curated entries in the fake setup
    ), mock.patch(
        "vaultlab.kb.tools_index.discovery.load_external_repos",
        return_value=[],
    ):
        tool = DiscoveredTool(
            name="testtool-xyz",
            description="A test tool for discovery validation.",
            language="python",
            install="pip install testtool-xyz",
            repo_url="https://github.com/example/testtool-xyz",
            domains=["test"],
            input_data=["csv"],
            discovered_via="unit-test",
            discovered_date="2026-05-08",
        )
        path = save_discovered_tool(tool)

    assert path.exists()
    text = path.read_text(encoding="utf-8")
    assert "name: testtool-xyz" in text
    assert "status: discovered" in text
    assert "pip install testtool-xyz" in text
    assert "## Summary" in text
    assert "## Audit trail" in text


def test_save_discovered_tool_skips_when_already_curated(tmp_path: Path) -> None:
    """Trying to save a tool whose name matches a curated package skips."""
    # scvi-tools is in the real curated list
    tool = DiscoveredTool(
        name="scvi-tools",
        description="Test description",
    )
    path = save_discovered_tool(tool, overwrite=False)
    # Returns the curated path (not the discovered one)
    assert path.suffix == ".md"
    # Curated path is the bundled one; should NOT be in discovered/
    assert "discovered" not in str(path)


def test_render_md_includes_status_discovered() -> None:
    """Rendered markdown declares status: discovered."""
    from vaultlab.kb.tools_index.discovery import _render_tool_md
    tool = DiscoveredTool(
        name="foo",
        description="Foo is a tool.",
        language="python",
        domains=["bar"],
        discovered_via="test",
        discovered_date="2026-05-08",
        paper_doi="10.1234/foo",
    )
    rendered = _render_tool_md(tool)
    assert "status: discovered" in rendered
    assert "name: foo" in rendered
    assert "10.1234/foo" in rendered


def test_extract_metadata_handles_no_doi() -> None:
    """Missing paper_doi works (defaults to empty string)."""
    tool = extract_tool_metadata(ABSTRACT_INTRODUCES_TOOL)
    assert tool is not None
    assert tool.paper_doi == ""
