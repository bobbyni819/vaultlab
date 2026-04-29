"""Extract citations from markdown documents."""

from __future__ import annotations

import re

from vaultlab.citations.models import Citation


def extract_citations(filepath: str) -> list[Citation]:
    """Extract all citations from a markdown file.

    Args:
        filepath: Path to a markdown file.

    Returns:
        List of Citation objects with claim context and line numbers.
    """
    with open(filepath, encoding="utf-8", errors="ignore") as f:
        text = f.read()
    return extract_citations_from_text(text, filepath)


def extract_citations_from_text(text: str, source_file: str) -> list[Citation]:
    """Extract citations from markdown text.

    Recognizes:
    - (Author et al., Year) / (Author, Year) / (Author and Author, Year)
    - Author et al. (Year)
    - (Author Year) --- no comma
    - (Author1 Year1; Author2 Year2) --- multiple
    - DOI: 10.xxxx/... or https://doi.org/10.xxxx/...
    - PMID: 12345

    Returns:
        List of Citation objects.
    """
    # Calculate frontmatter line offset before stripping
    frontmatter_lines = _count_frontmatter_lines(text)

    # Strip YAML frontmatter and code blocks
    text = _strip_frontmatter(text)
    text = _strip_code_blocks(text)

    lines = text.split("\n")
    citations: list[Citation] = []

    for line_idx, line in enumerate(lines):
        line_num = line_idx + 1 + frontmatter_lines

        # Find author-year citations
        citations.extend(_extract_author_year(line, source_file, line_num, lines, line_idx))

        # Find DOI references
        citations.extend(_extract_dois(line, source_file, line_num, lines, line_idx))

        # Find PMID references
        citations.extend(_extract_pmids(line, source_file, line_num, lines, line_idx))

    return citations


# Author name building block:
# - Standard: "Smith", "Garcia"
# - Lowercase prefix: "von Elm", "de Jong", "van der Berg"
# - Hyphenated: "Garcia-Lopez"
# Captures: optional known prefix(es) + capitalized surname + optional hyphenated part
# Only match known name prefixes (von, de, van, di, du, le, la, del, den, der, ten, ter)
# to avoid false matches like "shown by Smith" where "shown by" is not a name prefix.
_NAME_PREFIX = r"(?:(?:von|van|de|di|du|le|la|del|den|der|ten|ter)\s+(?:(?:von|van|de|di|du|le|la|del|den|der|ten|ter)\s+)?)?"
_AUTHOR_NAME = _NAME_PREFIX + r"[A-Z][a-z]+(?:-[A-Z][a-z]+)*"

# Pattern: (Author et al., Year) or (Author, Year) or (Author and Author, Year)
_PAREN_CITE = re.compile(
    r"\((" + _AUTHOR_NAME + r"(?:\s+(?:et\s+al\.|and\s+" + _AUTHOR_NAME + r"))?)"
    r"[,\s]+(\d{4})\)"
)

# Pattern: Author et al. (Year) or Author and Author (Year)
_INLINE_CITE = re.compile(
    r"(" + _AUTHOR_NAME + r"(?:\s+(?:et\s+al\.?|and\s+" + _AUTHOR_NAME + r")))\s+\((\d{4})\)"
)

# Pattern for multiple citations: (Author1 Year1; Author2 Year2)
_MULTI_CITE = re.compile(r"\(([^)]*\d{4}[^)]*;\s*[^)]*\d{4}[^)]*)\)")

# Single citation within multi-cite group
_SINGLE_IN_MULTI = re.compile(
    r"(" + _AUTHOR_NAME + r"(?:\s+(?:et\s+al\.?|and\s+" + _AUTHOR_NAME + r"))?)[,\s]+(\d{4})"
)

# DOI patterns
_DOI_INLINE = re.compile(r"(?:DOI|doi)[:\s]+\s*(10\.\d{4,}/[^\s,)]+)")
_DOI_URL = re.compile(r"https?://doi\.org/(10\.\d{4,}/[^\s,)>\"]+)")

# PMID pattern
_PMID = re.compile(r"PMID[:\s]*(\d{5,})")


def _extract_author_year(
    line: str,
    source_file: str,
    line_num: int,
    all_lines: list[str],
    line_idx: int,
) -> list[Citation]:
    """Extract author-year citations from a line."""
    citations = []
    claim = _get_claim_context(all_lines, line_idx)

    # Check for multi-citation first: (Smith 2020; Jones 2019)
    for m in _MULTI_CITE.finditer(line):
        group = m.group(1)
        for sub_m in _SINGLE_IN_MULTI.finditer(group):
            citations.append(
                Citation(
                    raw_text=sub_m.group(0).strip(),
                    authors=sub_m.group(1).strip(),
                    year=int(sub_m.group(2)),
                    claim=claim,
                    source_file=source_file,
                    line_number=line_num,
                )
            )

    if citations:
        return citations

    # Track matched spans to avoid double-counting overlapping matches
    matched_spans = set()

    # Single parenthetical: (Author et al., Year)
    for m in _PAREN_CITE.finditer(line):
        matched_spans.add((m.start(), m.end()))
        citations.append(
            Citation(
                raw_text=m.group(0),
                authors=m.group(1).strip(),
                year=int(m.group(2)),
                claim=claim,
                source_file=source_file,
                line_number=line_num,
            )
        )

    # Inline: Author et al. (Year)
    for m in _INLINE_CITE.finditer(line):
        # Avoid double-counting if this span overlaps with a parenthetical match
        overlaps = any(not (m.end() <= s[0] or m.start() >= s[1]) for s in matched_spans)
        if not overlaps:
            citations.append(
                Citation(
                    raw_text=m.group(0),
                    authors=m.group(1).strip(),
                    year=int(m.group(2)),
                    claim=claim,
                    source_file=source_file,
                    line_number=line_num,
                )
            )

    return citations


def _extract_dois(
    line: str,
    source_file: str,
    line_num: int,
    all_lines: list[str],
    line_idx: int,
) -> list[Citation]:
    """Extract DOI citations from a line."""
    citations = []
    claim = _get_claim_context(all_lines, line_idx)

    for pattern in (_DOI_INLINE, _DOI_URL):
        for m in pattern.finditer(line):
            doi = m.group(1).rstrip(".")
            citations.append(
                Citation(
                    raw_text=m.group(0),
                    authors="",
                    year=0,
                    claim=claim,
                    source_file=source_file,
                    line_number=line_num,
                    doi=doi,
                )
            )

    return citations


def _extract_pmids(
    line: str,
    source_file: str,
    line_num: int,
    all_lines: list[str],
    line_idx: int,
) -> list[Citation]:
    """Extract PMID citations from a line."""
    citations = []
    claim = _get_claim_context(all_lines, line_idx)

    for m in _PMID.finditer(line):
        citations.append(
            Citation(
                raw_text=m.group(0),
                authors="",
                year=0,
                claim=claim,
                source_file=source_file,
                line_number=line_num,
                pmid=m.group(1),
            )
        )

    return citations


def _get_claim_context(lines: list[str], line_idx: int) -> str:
    """Get the sentence containing the citation as claim context."""
    line = lines[line_idx].strip()
    # If the line is short, include surrounding lines
    if len(line) < 40 and line_idx > 0:
        line = lines[line_idx - 1].strip() + " " + line
    if len(line) < 40 and line_idx < len(lines) - 1:
        line = line + " " + lines[line_idx + 1].strip()
    # Trim to a reasonable length
    return line[:500]


def _count_frontmatter_lines(text: str) -> int:
    """Count the number of lines occupied by YAML frontmatter."""
    if text.startswith("---"):
        end = text.find("---", 3)
        if end != -1:
            # Count lines up to and including the closing ---
            frontmatter = text[: end + 3]
            # Also count any trailing newlines that get stripped
            rest = text[end + 3 :]
            stripped_rest = rest.lstrip("\n")
            blank_lines = len(rest) - len(stripped_rest)
            return frontmatter.count("\n") + blank_lines
    return 0


def _strip_frontmatter(text: str) -> str:
    """Remove YAML frontmatter from markdown text."""
    if text.startswith("---"):
        end = text.find("---", 3)
        if end != -1:
            return text[end + 3 :].lstrip("\n")
    return text


def _strip_code_blocks(text: str) -> str:
    """Remove fenced code blocks and inline code to avoid false citation matches."""
    # Remove fenced code blocks (``` ... ```)
    text = re.sub(r"```[^\n]*\n.*?```", _blank_lines, text, flags=re.DOTALL)
    # Remove inline code (` ... `)
    text = re.sub(r"`[^`\n]+`", "", text)
    return text


def _blank_lines(match: re.Match) -> str:
    """Replace a match with the same number of blank lines to preserve line numbers."""
    return "\n" * match.group(0).count("\n")
