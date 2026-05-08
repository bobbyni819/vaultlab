"""Auto-discovery of computational tools from literature (SPEC-O extension).

Closes the SPEC-O gap on top of the existing curated registry: when
batched-reader processes a paper that introduces a tool, this module
detects the tool-paper signature, extracts metadata (name, language,
GitHub URL, install command, input data format), and writes a new
entry to ``packages/discovered/<name>.md``.

The curated `packages/` directory is hand-maintained; the
``packages/discovered/`` subdirectory is auto-populated. Both are
loaded by :func:`vaultlab.kb.tools_index.load_index`. Discovered
entries can be promoted to curated by moving the file.

Public API
----------
- :func:`detect_tool_signature` — heuristic pattern match on paper text
- :func:`extract_tool_metadata` — pull tool fields from paper / abstract
- :func:`save_discovered_tool` — write to discovered/ as a Markdown stub
- :func:`is_already_known` — check curated + discovered + external_repos
- :func:`promote_to_curated` — move discovered/ entry to curated packages/

Lineage
-------
- conceptual-deep-dive-knowledge-recall-2026-05-08.md §3
  (Tier-B abstract persistence concept)
- spec-roadmap-2026-05-07.md SPEC-O (computational tool discovery)
- audit-report-2026-05-08.md §3 (hidden tools_index asset)
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from vaultlab.kb.tools_index.loader import (
    load_external_repos,
    load_index,
    packages_dir,
)

logger = logging.getLogger(__name__)

__all__ = [
    "DiscoveredTool",
    "detect_tool_signature",
    "discovered_dir",
    "extract_tool_metadata",
    "is_already_known",
    "promote_to_curated",
    "save_discovered_tool",
]


# ---------------------------------------------------------------------------
# Heuristics for detecting tool-introducing papers
# ---------------------------------------------------------------------------


# Tool-introducing-paper signal phrases. If a paper's abstract / intro
# contains these patterns, it likely introduces a software tool.
_TOOL_INTRODUCTION_PHRASES = [
    r"\bwe present\b",
    r"\bwe introduce\b",
    r"\bwe developed?\b",
    r"\bwe report\b.{0,80}\b(software|tool|package|library|framework|pipeline)\b",
    r"\bopen[\- ]?source\b",
    r"\bavailable at\s+(github|gitlab|bitbucket)",
    r"\bimplemented in\s+(python|r|julia|c\+\+|rust|go)\b",
    r"\bavailable as a\s+(python|r|julia)\s+package\b",
    r"\bpip install\b",
    r"\bcran\b",
    r"\bbioconductor\b",
    r"\bcran package\b",
]


# Tool-name extraction from the introducing pattern. Handles common
# conventions: "we present X", "we introduce X (description)", "X is a
# new package for...", etc.
_TOOL_NAME_PATTERNS = [
    r"\b(?:we present|we introduce|we report|introducing)\s+(\w[\w\-\.]+)",
    r"\b(\w[\w\-\.]+) is a (?:new |novel |open[\-\s]?source )?(?:python|r|julia)\s+(?:tool|package|library|framework)",
    r"\b(\w[\w\-\.]+):\s+a\s+(?:python|r|julia)\s+(?:tool|package|library)",
]


# Language detection
_LANGUAGE_PATTERNS = {
    "python": [r"\bpython\s+(?:tool|package|library)\b", r"\bpip install\b", r"\.py\b"],
    "r": [r"\br\s+(?:tool|package|library)\b", r"\bcran\b", r"\bbioconductor\b"],
    "julia": [r"\bjulia\s+(?:tool|package|library)\b"],
    "cli": [r"\bcommand[\- ]line\b", r"\bcli tool\b"],
}


# Install command extraction
_INSTALL_PATTERNS = [
    r"`?(pip install\s+\S+)`?",
    r"`?(conda install\s+(?:-c\s+\S+\s+)?\S+)`?",
    r"`?(mamba install\s+(?:-c\s+\S+\s+)?\S+)`?",
    r"`?(install\.packages\([\"'][^\"']+[\"']\))`?",
    r"`?(BiocManager::install\([\"'][^\"']+[\"']\))`?",
]


# GitHub / hosting URL extraction
_REPO_URL_PATTERNS = [
    r"https?://github\.com/[\w\-\.]+/[\w\-\.]+/?",
    r"https?://gitlab\.com/[\w\-\.]+/[\w\-\.]+/?",
    r"https?://bitbucket\.org/[\w\-\.]+/[\w\-\.]+/?",
    r"https?://codeberg\.org/[\w\-\.]+/[\w\-\.]+/?",
]


# Input data format hints
_DATA_FORMAT_HINTS = {
    "anndata": [r"\banndata\b", r"\.h5ad\b"],
    "h5ad": [r"\.h5ad\b"],
    "csv": [r"\bcsv\b"],
    "fastq": [r"\bfastq\b"],
    "bam": [r"\bbam\b"],
    "imzML": [r"\bimzml\b"],
    "tiff": [r"\btiff?\b"],
    "ome-tiff": [r"\bome[\-\s]?tiff\b"],
    "spatial-data": [r"\bspatialdata\b"],
    "seurat": [r"\bseurat\b"],
    "loom": [r"\.loom\b"],
}


@dataclass
class DiscoveredTool:
    """Metadata for an auto-discovered computational tool.

    Attributes
    ----------
    name
        Tool name (e.g., ``"scvi-tools"``, ``"squidpy"``).
    language
        Implementation language (``"python"``, ``"r"``, etc., or empty).
    install
        Install command (e.g., ``"pip install scvi-tools"``), or empty.
    repo_url
        Hosting URL (GitHub / GitLab), or empty.
    description
        One-sentence description from the paper's abstract.
    domains
        Domain tags inferred from text (e.g., ``["spatial", "single-cell"]``).
    input_data
        Detected input data formats (e.g., ``["anndata", "h5ad"]``).
    discovered_via
        How this tool was discovered (e.g., ``"lit-arc on 2026-05-08 (DOI X)"``).
    discovered_date
        ISO date.
    paper_doi
        DOI of the paper that introduces the tool, when available.
    raw_signal_phrases
        The pattern matches that triggered detection (for audit).
    """

    name: str
    language: str = ""
    install: str = ""
    repo_url: str = ""
    description: str = ""
    domains: list[str] = field(default_factory=list)
    input_data: list[str] = field(default_factory=list)
    discovered_via: str = ""
    discovered_date: str = ""
    paper_doi: str = ""
    raw_signal_phrases: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def discovered_dir() -> Path:
    """Return the directory for auto-discovered tools."""
    return packages_dir() / "discovered"


def detect_tool_signature(text: str) -> tuple[bool, list[str]]:
    """Heuristic check whether a paper introduces a software tool.

    Returns ``(introduces_tool, matched_signal_phrases)``. The phrases
    are useful for audit / explainability.

    Threshold: ≥1 strong introduction phrase + ≥1 install/repo/language
    indicator. This keeps the signal/noise ratio reasonable on real
    abstracts (many papers reference tools without introducing them).
    """
    text_lower = text.lower()
    introduction_hits = []
    indicator_hits = []

    for pat in _TOOL_INTRODUCTION_PHRASES:
        m = re.search(pat, text_lower, re.IGNORECASE)
        if m:
            introduction_hits.append(m.group(0))

    # Indicators: install, repo, language are all signals
    for lang_patterns in _LANGUAGE_PATTERNS.values():
        for pat in lang_patterns:
            m = re.search(pat, text_lower)
            if m:
                indicator_hits.append(m.group(0))
                break

    for pat in _INSTALL_PATTERNS:
        m = re.search(pat, text_lower, re.IGNORECASE)
        if m:
            indicator_hits.append(m.group(0))
            break

    for pat in _REPO_URL_PATTERNS:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            indicator_hits.append(m.group(0))
            break

    is_tool_intro = len(introduction_hits) >= 1 and len(indicator_hits) >= 1
    matched = introduction_hits + indicator_hits
    return is_tool_intro, matched


def extract_tool_metadata(
    text: str,
    *,
    paper_doi: str = "",
    discovered_via: str = "",
) -> DiscoveredTool | None:
    """Extract a :class:`DiscoveredTool` from paper text.

    Returns None if the text doesn't look like a tool-introducing paper
    (per :func:`detect_tool_signature`).
    """
    is_intro, signals = detect_tool_signature(text)
    if not is_intro:
        return None

    # Tool name
    name = _extract_tool_name(text)
    if not name:
        # Couldn't parse a name — bail
        logger.debug("tool-paper signal hit but no name extracted")
        return None

    # Language
    language = _detect_language(text)

    # Install command
    install = _extract_install_command(text)

    # Repo URL
    repo_url = _extract_repo_url(text)

    # Description from first sentence after the introduction phrase
    description = _extract_description(text, name)

    # Domains — infer from common topic keywords in the text
    domains = _infer_domains(text)

    # Input data formats
    input_data = _detect_input_data(text)

    return DiscoveredTool(
        name=name,
        language=language,
        install=install,
        repo_url=repo_url,
        description=description,
        domains=domains,
        input_data=input_data,
        discovered_via=discovered_via or f"abstract-scan {date.today().isoformat()}",
        discovered_date=date.today().isoformat(),
        paper_doi=paper_doi,
        raw_signal_phrases=signals[:10],  # cap for storage
    )


def is_already_known(tool_name: str) -> bool:
    """Check whether a tool is already in curated, discovered, or external repos."""
    name_lower = tool_name.lower().strip()
    if not name_lower:
        return False

    # Curated packages (top-level packages/*.md)
    curated_index = load_index()
    for known_name in curated_index:
        if known_name.lower() == name_lower:
            return True

    # Discovered (sub-directory)
    disc_dir = discovered_dir()
    if disc_dir.exists():
        for f in disc_dir.glob("*.md"):
            if f.stem.lower() == name_lower:
                return True

    # External repos
    repos = load_external_repos()
    for repo in repos:
        if isinstance(repo, dict):
            slug = str(repo.get("slug", "")).lower()
            if slug == name_lower:
                return True

    return False


def save_discovered_tool(
    tool: DiscoveredTool,
    *,
    overwrite: bool = False,
) -> Path:
    """Write a discovered-tool entry to ``packages/discovered/<name>.md``.

    Returns the path. If a curated entry already exists with the same
    name, doesn't write (returns the curated path).

    Parameters
    ----------
    tool
        The :class:`DiscoveredTool` to persist.
    overwrite
        If False (default), raises if discovered/<name>.md already
        exists. If True, overwrites.
    """
    if is_already_known(tool.name) and not overwrite:
        # Don't shadow curated; if discovered/ already has it, also skip
        logger.info("tool %s already known; skipping discovered/ write", tool.name)
        return _existing_tool_path(tool.name)

    disc_dir = discovered_dir()
    disc_dir.mkdir(parents=True, exist_ok=True)

    target = disc_dir / f"{tool.name}.md"
    target.write_text(_render_tool_md(tool), encoding="utf-8")
    logger.info("Saved discovered tool to %s", target)
    return target


def promote_to_curated(name: str) -> Path:
    """Move a discovered/ entry to curated packages/.

    Returns the new path. Raises FileNotFoundError if the discovered
    entry doesn't exist; raises FileExistsError if a curated entry of
    the same name already exists.
    """
    disc = discovered_dir() / f"{name}.md"
    if not disc.exists():
        raise FileNotFoundError(f"No discovered entry at {disc}")

    target = packages_dir() / f"{name}.md"
    if target.exists():
        raise FileExistsError(f"Curated entry already at {target}")

    disc.rename(target)
    logger.info("Promoted %s from discovered/ to curated", name)
    return target


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def _extract_tool_name(text: str) -> str:
    """Try several patterns to pull the tool name out of paper text."""
    for pat in _TOOL_NAME_PATTERNS:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            candidate = m.group(1).strip(",.;:()[]{}\"'")
            # Exclude generic words that often follow "we present"
            if candidate.lower() in {"a", "an", "the", "two", "three", "this", "an open", "a novel"}:
                continue
            if 2 <= len(candidate) <= 50:
                return candidate
    return ""


def _detect_language(text: str) -> str:
    """Return the most-supported language; falls back to empty string."""
    text_lower = text.lower()
    counts: dict[str, int] = {}
    for lang, patterns in _LANGUAGE_PATTERNS.items():
        for pat in patterns:
            if re.search(pat, text_lower):
                counts[lang] = counts.get(lang, 0) + 1
    if not counts:
        return ""
    # Pick the most-supported, biased toward python (more common)
    return max(counts.items(), key=lambda kv: (kv[1], kv[0] == "python"))[0]


def _extract_install_command(text: str) -> str:
    """Return the first install command found, or empty string."""
    for pat in _INSTALL_PATTERNS:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            return m.group(1).strip()
    return ""


def _extract_repo_url(text: str) -> str:
    """Return the first GitHub/GitLab/etc. URL found."""
    for pat in _REPO_URL_PATTERNS:
        m = re.search(pat, text)
        if m:
            return m.group(0).rstrip("/")
    return ""


def _extract_description(text: str, name: str) -> str:
    """Pull a one-sentence description for the tool.

    Strategy: find the sentence that mentions the tool name + grab the
    first 200 chars around it. Good-enough for a v1 abstract scan.
    """
    sentences = re.split(r"(?<=[.!?])\s+", text)
    for sentence in sentences:
        if name.lower() in sentence.lower():
            cleaned = " ".join(sentence.split())
            if 30 <= len(cleaned) <= 300:
                return cleaned.rstrip(".")
            if len(cleaned) > 300:
                return cleaned[:297].rstrip() + "..."
    return ""


def _infer_domains(text: str) -> list[str]:
    """Detect common bio-info domain tags in the text."""
    domain_keywords = {
        "single-cell": [r"\bsingle[\-\s]?cell\b", r"\bsc(?:rna|atac|dna)[\-\s]?seq\b"],
        "spatial": [r"\bspatial\s+(?:transcriptomic|omics|expression|proteomic)"],
        "spatial-omics": [r"\bspatial\s+(?:transcriptomic|omics)"],
        "imaging": [r"\b(?:multiplex |multi-)?(?:if|ihc|imaging mass)"],
        "metabolomics": [r"\bmetabolom"],
        "lipidomics": [r"\blipidom"],
        "proteomics": [r"\bproteom"],
        "scrnaseq": [r"\bscrna[\-\s]?seq\b"],
        "deep-learning": [r"\b(?:deep learning|neural network|transformer)\b"],
        "batch-correction": [r"\bbatch[\-\s]?correction\b", r"\bbatch[\-\s]?effect\b"],
        "trajectory": [r"\btrajectory\b", r"\bpseudotime\b"],
        "cell-cell-interaction": [r"\bcell[\-\s]?cell\s+interaction"],
        "segmentation": [r"\bsegmentation\b"],
        "statistics": [r"\bstatistical\s+(?:test|analysis|inference)"],
    }
    text_lower = text.lower()
    hits = []
    for domain, patterns in domain_keywords.items():
        for pat in patterns:
            if re.search(pat, text_lower):
                hits.append(domain)
                break
    return hits


def _detect_input_data(text: str) -> list[str]:
    """Detect input data format hints."""
    text_lower = text.lower()
    hits = []
    for fmt, patterns in _DATA_FORMAT_HINTS.items():
        for pat in patterns:
            if re.search(pat, text_lower):
                hits.append(fmt)
                break
    return hits


def _existing_tool_path(name: str) -> Path:
    """Return the path of an existing tool entry (curated or discovered)."""
    name_lower = name.lower()
    for f in packages_dir().glob("*.md"):
        if f.stem.lower() == name_lower:
            return f
    disc_dir = discovered_dir()
    if disc_dir.exists():
        for f in disc_dir.glob("*.md"):
            if f.stem.lower() == name_lower:
                return f
    return packages_dir() / f"{name}.md"  # would-be curated path


def _render_tool_md(tool: DiscoveredTool) -> str:
    """Render a DiscoveredTool as the canonical .md format."""
    domains_str = ", ".join(tool.domains) if tool.domains else ""
    input_str = ", ".join(tool.input_data) if tool.input_data else ""

    body_parts = [
        "---",
        f"name: {tool.name}",
        f"description: {tool.description or '(auto-discovered; no description extracted)'}",
        f"domains: [{domains_str}]",
        f"install: {tool.install}",
        f"docs_url: {tool.repo_url}",
        f"language: {tool.language}",
        f"input_data: [{input_str}]",
        "status: discovered",
        f"discovered_via: {tool.discovered_via}",
        f"discovered_date: {tool.discovered_date}",
        f"paper_doi: {tool.paper_doi}",
        "---",
        "",
        f"# {tool.name}",
        "",
        "## Summary",
        "",
        tool.description or "_Auto-discovered from literature; description not extracted._",
        "",
        "## Discovery context",
        "",
        f"This tool was auto-discovered via lit-arc on {tool.discovered_date}.",
        f"Source paper: `{tool.paper_doi or 'unknown'}`.",
        "",
        "## When to use",
        "",
        f"_Inferred domains: {domains_str or 'none extracted'}._",
        f"_Inferred input formats: {input_str or 'none extracted'}._",
        "",
        "Refine this section by hand after evaluating the tool, then promote",
        "to curated via `vaultlab.kb.tools_index.discovery.promote_to_curated()`.",
        "",
        "## Install",
        "",
        f"```\n{tool.install or '# Install command not extracted from paper'}\n```",
        "",
        "## Repository",
        "",
        f"{tool.repo_url or '_Not extracted from paper._'}",
        "",
        "## Audit trail",
        "",
        "Signal phrases that triggered detection:",
    ]
    for phrase in tool.raw_signal_phrases:
        body_parts.append(f"- `{phrase}`")
    body_parts.append("")
    return "\n".join(body_parts)
