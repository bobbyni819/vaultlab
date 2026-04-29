"""RIS ingestor — one KbDocument per record.

RIS is line-oriented: ``XX  - value``. Each record terminated by ``ER  -``.
"""

from __future__ import annotations

from pathlib import Path

from vaultlab.kb.ingest.dispatcher import URL_PATTERN, register
from vaultlab.kb.ingest.models import KbDocument


def matches_ris(source: str) -> bool:
    if URL_PATTERN.match(source):
        return False
    p = Path(source)
    return p.suffix.lower() == ".ris" and p.is_file()


# Most useful RIS tags (full list is ~40+; covering what users actually paste)
_TAG_MAP = {
    "TI": "title",
    "T1": "title",
    "AU": "author",  # repeated
    "PY": "year",
    "Y1": "year",
    "DO": "doi",
    "UR": "url",
    "AB": "abstract",
    "JO": "journal",
    "JF": "journal",
    "T2": "journal",
    "ID": "ris_id",
    "TY": "ris_type",
}


@register(
    "ris",
    description="RIS citation files. Common Zotero / Mendeley / EndNote export. "
    "One KbDocument per record.",
    implemented=True,
)
def ingest_ris(source: str) -> list[KbDocument]:
    p = Path(source)
    text = p.read_text(encoding="utf-8")

    docs: list[KbDocument] = []
    record: dict[str, list[str]] = {}

    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        if len(line) < 6 or line[2:6] != "  - ":
            continue
        tag = line[:2]
        value = line[6:]
        if tag == "ER":
            if record:
                docs.append(_record_to_doc(record, source=p))
            record = {}
            continue
        mapped = _TAG_MAP.get(tag, tag.lower())
        record.setdefault(mapped, []).append(value)

    # Trailing record without ER (some malformed exports)
    if record:
        docs.append(_record_to_doc(record, source=p))

    return docs


def _record_to_doc(record: dict[str, list[str]], *, source: Path) -> KbDocument:
    title = (record.get("title") or [""])[0] or "(untitled RIS record)"
    authors = record.get("author", [])
    year = (record.get("year") or [""])[0]
    doi = (record.get("doi") or [""])[0]
    abstract = (record.get("abstract") or [""])[0]
    journal = (record.get("journal") or [""])[0]
    url = (record.get("url") or [""])[0]

    body_lines = [f"# {title}", ""]
    if authors:
        body_lines.append(f"**Authors:** {'; '.join(authors)}")
    if year:
        body_lines.append(f"**Year:** {year}")
    if journal:
        body_lines.append(f"**Journal:** {journal}")
    if doi:
        body_lines.append(f"**DOI:** {doi}")
    if url:
        body_lines.append(f"**URL:** {url}")
    body_lines.append("")
    if abstract:
        body_lines.append("## Abstract")
        body_lines.append("")
        body_lines.append(abstract)
        body_lines.append("")
    body_lines.append("## Notes")
    body_lines.append("")
    body_lines.append("<!-- Add reading notes here. -->")

    metadata: dict[str, object] = {"ingested_from": str(source.resolve())}
    if authors:
        metadata["authors"] = "; ".join(authors)
    if year:
        metadata["year"] = year
    if doi:
        metadata["doi"] = doi
    if journal:
        metadata["journal"] = journal
    if url:
        metadata["url"] = url

    return KbDocument(
        kind="citation",
        title=title,
        body="\n".join(body_lines),
        source=str(source.resolve()),
        metadata=metadata,
    )
