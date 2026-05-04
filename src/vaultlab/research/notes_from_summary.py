"""Parse Tier-A summary markdown → three-tier speaker_notes dict.

A Tier-A summary file at ``Wiki/Summaries/<doi-slug>.md`` carries the
information a speaker needs for a slide:

- Frontmatter:  doi, title, authors, journal, year, role_in_set
- ``## TL;DR``        — concise paper-level synthesis (~200-400 words)
- ``## Why it matters in this lineage`` — context narrative
- ``## Methods (extracted summary)``    — bulleted methods list
- ``## Key findings (with [page] provenance)`` — bulleted findings list

This module parses the file into a structured ``SummaryRecord`` and
provides ``speaker_notes_from_summary`` which composes the three-tier
``mental_map + script + extended_walkthrough`` notes dict that Bobby's
hard-rules memory mandates. Every field is overridable via keyword
arguments to the composer so deck authors can tune per-slide voice.

Reference design context: feedback_slide_hard_rules.md +
feedback_slide_dynamic_practices.md (2026-05-03).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class SummaryRecord:
    """A parsed Tier-A summary file."""

    doi: str
    title: str
    authors: list[str] = field(default_factory=list)
    journal: str = ""
    year: int | None = None
    role_in_set: str = ""
    tier: str = "A"
    tldr: str = ""
    why_matters: str = ""
    methods: list[str] = field(default_factory=list)
    key_findings: list[str] = field(default_factory=list)
    raw_path: str = ""

    def authors_short(self) -> str:
        """'Hickey et al. 2024' style citation."""
        if not self.authors:
            return f"({self.year})" if self.year else "(undated)"
        last_first = self.authors[0].split()[-1]
        if len(self.authors) == 1:
            return f"{last_first} {self.year}".strip()
        return f"{last_first} et al. {self.year}".strip()

    def journal_short(self) -> str:
        """Compact journal name for citation footer."""
        if not self.journal:
            return ""
        # Common abbreviations
        substitutions = [
            ("Cell Systems", "Cell Sys"),
            ("Frontiers in Immunology", "Front Immunol"),
            ("Frontiers Immunology", "Front Immunol"),
            ("Frontiers in Microbiology", "Front Microbiol"),
            ("Frontiers Microbiology", "Front Microbiol"),
            ("Nature Methods", "Nat Methods"),
            ("Nature Biotechnology", "Nat Biotechnol"),
            ("New England Journal of Medicine", "NEJM"),
            ("Proceedings of the National Academy of Sciences", "PNAS"),
            ("Journal of Theoretical Biology", "J Theor Biol"),
            ("PLoS One", "PLoS One"),
        ]
        result = self.journal
        for full, short in substitutions:
            if full.lower() in result.lower():
                return short
        return result

    def citation_footer(self) -> str:
        """Compose 'Authors, Journal Year' for slide footer."""
        bits = [self.authors_short()]
        j = self.journal_short()
        if j:
            bits.append(j)
        return " | ".join([b for b in bits if b])


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------


_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
_HEADING_RE = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)


def parse_summary_file(path: Path | str) -> SummaryRecord:
    """Parse a Tier-A summary markdown file into a :class:`SummaryRecord`."""
    path = Path(path)
    text = path.read_text(encoding="utf-8")

    # Frontmatter
    fm_match = _FRONTMATTER_RE.match(text)
    fm: dict[str, Any] = {}
    if fm_match:
        try:
            fm = yaml.safe_load(fm_match.group(1)) or {}
        except yaml.YAMLError:
            fm = {}
        body = text[fm_match.end():]
    else:
        body = text

    # Section split — find every "## Header" and slice
    sections: dict[str, str] = {}
    matches = list(_HEADING_RE.finditer(body))
    for i, m in enumerate(matches):
        heading = m.group(1).strip().lower()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        sections[heading] = body[start:end].strip()

    def _get_section(*keys: str) -> str:
        """Find first matching section by partial header match."""
        for k in keys:
            for header, content in sections.items():
                if k.lower() in header:
                    return content
        return ""

    tldr_text = _get_section("tl;dr", "tldr", "summary")
    why_text = _get_section("why it matters", "why this matters")
    methods_text = _get_section("methods (extracted", "methods")
    findings_text = _get_section("key findings", "main findings")

    # Year coercion (frontmatter may give str/int)
    year_raw = fm.get("year")
    year: int | None = None
    if isinstance(year_raw, int):
        year = year_raw
    elif isinstance(year_raw, str):
        m = re.search(r"\d{4}", year_raw)
        year = int(m.group(0)) if m else None

    authors_raw = fm.get("authors") or []
    if isinstance(authors_raw, str):
        # comma-separated string
        authors = [a.strip() for a in re.split(r"[,;]\s*", authors_raw) if a.strip()]
    elif isinstance(authors_raw, list):
        authors = [str(a).strip() for a in authors_raw if str(a).strip()]
    else:
        authors = []

    return SummaryRecord(
        doi=str(fm.get("doi", "")).strip(),
        title=str(fm.get("title", "")).strip(),
        authors=authors,
        journal=str(fm.get("journal", "")).strip(),
        year=year,
        role_in_set=str(fm.get("role_in_set", "")).strip(),
        tier=str(fm.get("tier", "A")).strip(),
        tldr=tldr_text,
        why_matters=why_text,
        methods=_extract_bullets(methods_text),
        key_findings=_extract_bullets(findings_text),
        raw_path=str(path),
    )


def _extract_bullets(section_text: str) -> list[str]:
    """Pull bullet entries out of a markdown section.

    Handles ``- foo`` and ``* foo`` styles. Multi-line bullets (continuation
    on the next line indented with 2+ spaces) are joined.
    """
    if not section_text:
        return []
    bullets: list[str] = []
    current: list[str] = []
    for line in section_text.splitlines():
        if re.match(r"^[\-*]\s+", line):
            if current:
                bullets.append(" ".join(current).strip())
                current = []
            current.append(re.sub(r"^[\-*]\s+", "", line).rstrip())
        elif line.startswith("  ") and current:
            current.append(line.strip())
        else:
            if current:
                bullets.append(" ".join(current).strip())
                current = []
    if current:
        bullets.append(" ".join(current).strip())
    return bullets


# ---------------------------------------------------------------------------
# Composer — three-tier speaker_notes dict
# ---------------------------------------------------------------------------


_KEY_TERM_PATTERNS = [
    re.compile(r"\b([A-Z]{2,}(?:-?\d+)?)\b"),  # acronyms (CODEX, IMC, CN21)
    re.compile(r"\b([A-Z][a-z]+(?:[A-Z][a-z]*)+)\b"),  # CamelCase tokens
    re.compile(r"\b(R²[\s≈=]\s*\d\.\d{1,3})"),  # R² values
]


def _extract_key_terms(record: SummaryRecord, max_terms: int = 7) -> list[str]:
    """Heuristic: pull jargon from TL;DR + key_findings."""
    text = " ".join([record.tldr] + record.key_findings)
    seen: set[str] = set()
    terms: list[str] = []
    for pat in _KEY_TERM_PATTERNS:
        for m in pat.finditer(text):
            term = m.group(1)
            if len(term) < 2 or term in seen:
                continue
            # Filter junk: pure numbers, common words
            if term.lower() in {"the", "and", "this", "that", "with", "from", "for"}:
                continue
            if term.isdigit():
                continue
            seen.add(term)
            terms.append(term)
            if len(terms) >= max_terms:
                return terms
    return terms


_FALSE_TERMINATORS = re.compile(
    r"(?:et\s+al|e\.g|i\.e|cf|vs|Mr|Dr|Mrs|Ms|Prof|Inc|Ltd|Sr|Jr|"
    r"Fig|Eq|No|St|Co|US|UK|EU|approx)\.\s*$",
    re.IGNORECASE,
)


def _first_sentence(text: str) -> str:
    """Pull the first complete sentence from a paragraph.

    Handles abbreviations that contain periods (et al., e.g., i.e., Fig.,
    Eq., Dr., Mrs.) so the sentence doesn't get clipped at "et al."
    """
    text = text.strip()
    if not text:
        return ""
    # Strip leading bold/italic markers
    text = re.sub(r"^[*_#]+\s*", "", text).strip()
    # Skip leading numbered-list markers ("1.", "(1)", "1)") — they're not the sentence
    text = re.sub(r"^\(?(\d{1,2})[.)\]]\s+", "", text).strip()

    # Walk through candidate sentence ends; reject those preceded by abbreviations
    pos = 0
    while pos < len(text):
        m = re.search(r"[.!?](?:\s|$)", text[pos:])
        if not m:
            break
        end = pos + m.start() + 1  # include the punctuation
        candidate = text[:end]
        # Reject if candidate ends with a known abbreviation
        if _FALSE_TERMINATORS.search(candidate):
            pos = end
            continue
        return candidate.strip()
    return text[:300].strip()


def _strip_md(text: str) -> str:
    """Remove markdown bold/italic/links/wikilinks so the prose flows."""
    text = re.sub(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]", r"\2 \1", text)  # [[doi|label]] -> "label doi"
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)  # bold
    text = re.sub(r"\*([^*]+)\*", r"\1", text)      # italic
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)  # markdown link
    text = re.sub(r"\[([^\]]+)\]", r"\1", text)     # bare brackets
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _derive_hook(record: SummaryRecord) -> str:
    """One-line opener — synthesize from why_matters first sentence or TL;DR."""
    src = record.why_matters or record.tldr
    sent = _first_sentence(_strip_md(src))
    return sent[:200]


def _derive_key_claim(record: SummaryRecord) -> str:
    """The slide's load-bearing claim — TL;DR first sentence."""
    return _first_sentence(_strip_md(record.tldr))[:300]


def _derive_evidence(record: SummaryRecord) -> str:
    """Compact pointer to data/methods backing the claim."""
    if record.methods:
        # First method bullet, stripped
        first = _strip_md(record.methods[0])
        return first[:240]
    if record.key_findings:
        return _strip_md(record.key_findings[0])[:240]
    return ""


def _compose_script(
    record: SummaryRecord,
    *,
    target_words: int = 280,
) -> str:
    """Compose a ~200-400 word script default from TL;DR + Why it matters.

    Strategy: take the TL;DR (already a polished synthesis paragraph)
    plus the first paragraph of Why-it-matters if present. Strip
    markdown decoration, normalize whitespace, trim to target.
    """
    parts: list[str] = []
    if record.tldr:
        parts.append(_strip_md(record.tldr))
    if record.why_matters:
        why = _strip_md(record.why_matters)
        # Take first paragraph only (split on blank line)
        first_para = why.split("\n\n", 1)[0].strip()
        if first_para and first_para not in parts[0]:
            parts.append(first_para)
    text = " ".join(parts).strip()
    return _trim_to_word_target(text, target_words)


def _compose_extended_walkthrough(
    record: SummaryRecord,
    *,
    audience_familiar: bool = False,
    target_words: int = 750,
) -> str:
    """Compose a 600-900 word concept walkthrough.

    Structure:
        BACKGROUND — TL;DR
        WHY IT MATTERS — Why-it-matters narrative
        METHODS — bulleted methods reflowed into prose
        KEY FINDINGS — bulleted findings reflowed into prose
    """
    sections: list[str] = []

    if record.tldr:
        sections.append(f"BACKGROUND — {_strip_md(record.tldr)}")

    if record.why_matters and not audience_familiar:
        sections.append(f"\n\nWHY IT MATTERS — {_strip_md(record.why_matters)}")

    if record.methods:
        method_lines = [_strip_md(m) for m in record.methods[:8]]
        sections.append("\n\nMETHODS — " + " ".join(method_lines))

    if record.key_findings:
        finding_lines = [_strip_md(k) for k in record.key_findings[:8]]
        sections.append("\n\nKEY FINDINGS — " + " ".join(finding_lines))

    text = " ".join(sections).strip()
    text = re.sub(r"\s+", " ", text)  # squash whitespace
    return _trim_to_word_target(text, target_words)


def _trim_to_word_target(text: str, target_words: int) -> str:
    """Trim text to approximately target word count at sentence boundary."""
    words = text.split()
    if len(words) <= target_words:
        return text
    # Take first N words then trim to last sentence boundary
    trimmed = " ".join(words[:target_words])
    last_punct = max(trimmed.rfind("."), trimmed.rfind("!"), trimmed.rfind("?"))
    if last_punct > target_words * 4:  # >chars of ~80% target words
        trimmed = trimmed[: last_punct + 1]
    return trimmed.strip()


def speaker_notes_from_summary(
    record: SummaryRecord,
    *,
    hook: str = "",
    key_claim: str = "",
    evidence: str = "",
    key_terms: list[str] | None = None,
    click: str = "",
    transition: str = "",
    script: str = "",
    extended_walkthrough: str = "",
    audience_familiar: bool = False,
    script_target_words: int = 280,
    walkthrough_target_words: int = 750,
) -> dict[str, Any]:
    """Build a 3-tier ``speaker_notes`` dict from a SummaryRecord.

    All fields can be overridden by passing the corresponding keyword
    argument; otherwise they're auto-derived from the summary record.

    Returns a dict ready to drop into a slide-spec's ``speaker_notes``
    field — same shape as ``feedback_slide_hard_rules.md`` mandates:
    mental-map keys + ``script`` + ``extended_walkthrough``.
    """
    return {
        "hook": hook or _derive_hook(record),
        "key_claim": key_claim or _derive_key_claim(record),
        "evidence": evidence or _derive_evidence(record),
        "key_terms": key_terms if key_terms is not None else _extract_key_terms(record),
        "click": click,
        "transition": transition,
        "script": script or _compose_script(record, target_words=script_target_words),
        "extended_walkthrough": extended_walkthrough or _compose_extended_walkthrough(
            record,
            audience_familiar=audience_familiar,
            target_words=walkthrough_target_words,
        ),
    }


# ---------------------------------------------------------------------------
# High-level convenience: load by DOI slug
# ---------------------------------------------------------------------------


def load_summary(
    doi_slug: str,
    *,
    summaries_dir: Path | str = "G:/My Drive/Knowledge/vaultlab/Wiki/Summaries",
) -> SummaryRecord | None:
    """Load a summary by DOI slug (e.g., ``10.1038_s41586-022-05672-3``).

    Returns ``None`` if the file doesn't exist.
    """
    summaries_dir = Path(summaries_dir)
    candidates = [
        summaries_dir / f"{doi_slug}.md",
        summaries_dir / f"{doi_slug.replace('.', '-')}.md",
    ]
    for c in candidates:
        if c.exists():
            return parse_summary_file(c)
    return None


__all__ = [
    "SummaryRecord",
    "parse_summary_file",
    "load_summary",
    "speaker_notes_from_summary",
]
