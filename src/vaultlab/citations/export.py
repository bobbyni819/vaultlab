"""Citation reference-manager exporters (ENW / RIS / Zotero RDF).

Absorbed from the nature-citation skill (Yuan Yizhe, SJTU) at
nature-skills/skills/nature-citation/.

Lets vaultlab feed verified citations directly into the user's reference
manager. Pipes from the existing :class:`vaultlab.citations.models.Citation`
shape; does not fabricate metadata when fields are missing — empty fields
are emitted blank, never made up.

Public API
----------

- :func:`to_enw` — EndNote tagged ENW format
- :func:`to_ris` — RIS tagged format (Mendeley / Papers / Zotero accept)
- :func:`to_zotero_rdf` — Zotero-import-ready RDF/XML
- :func:`write_export` — write one of the three formats to disk

All three accept either ``Citation`` dataclasses or dicts shaped like
``Citation.to_dict()`` output.
"""

from __future__ import annotations

import html
from collections.abc import Iterable
from pathlib import Path
from typing import Any, Literal

ExportFormat = Literal["enw", "ris", "rdf"]


def _as_dict(cit: Any) -> dict[str, Any]:
    if hasattr(cit, "to_dict"):
        return cit.to_dict()
    return dict(cit)


def _author_list(cit: dict[str, Any]) -> list[str]:
    """Normalize the authors field into a list of strings.

    Citation.authors is a single string (from the markdown extraction);
    we split on common separators. If the upstream produces a list, use it.
    """
    val = cit.get("authors")
    if isinstance(val, list):
        return [str(a).strip() for a in val if str(a).strip()]
    if isinstance(val, str) and val.strip():
        # Split on common separators
        parts = []
        for chunk in val.replace(";", ",").split(","):
            chunk = chunk.strip()
            if chunk and chunk.lower() not in {"et al", "et al."}:
                parts.append(chunk)
        return parts
    return []


# ---------------------------------------------------------------------------
# ENW (EndNote tagged)


def _enw_record(cit: dict[str, Any]) -> str:
    """One ENW record. Standard tags:

    %0  Reference type (Journal Article default)
    %A  Author (repeat per author)
    %D  Year
    %T  Title
    %J  Journal
    %V  Volume
    %N  Issue
    %P  Pages
    %@  ISSN / ISBN
    %R  DOI
    %M  Accession (PMID)
    %U  URL
    %X  Abstract
    """
    lines: list[str] = ["%0 Journal Article"]
    for author in _author_list(cit):
        lines.append(f"%A {author}")
    year = cit.get("year")
    if year:
        lines.append(f"%D {year}")
    if cit.get("title"):
        lines.append(f"%T {cit['title']}")
    if cit.get("journal"):
        lines.append(f"%J {cit['journal']}")
    if cit.get("doi"):
        lines.append(f"%R {cit['doi']}")
    if cit.get("pmid"):
        lines.append(f"%M {cit['pmid']}")
    if cit.get("doi"):
        lines.append(f"%U https://doi.org/{cit['doi']}")
    if cit.get("claim"):
        # The claim is short — use it as a context note in the abstract slot.
        lines.append(f"%X {cit['claim']}")
    return "\n".join(lines)


def to_enw(citations: Iterable[Any]) -> str:
    """Serialize an iterable of Citation/dict to an EndNote ENW string.

    Records are separated by blank lines.
    """
    return "\n\n".join(_enw_record(_as_dict(c)) for c in citations) + "\n"


# ---------------------------------------------------------------------------
# RIS (Research Information Systems)


def _ris_record(cit: dict[str, Any]) -> str:
    """One RIS record. Standard tags:

    TY  -  Type of reference
    AU  -  Author (repeat)
    PY  -  Year
    TI  -  Title
    JO  -  Journal name
    DO  -  DOI
    AN  -  PMID
    UR  -  URL
    AB  -  Abstract
    ER  -  End of record
    """
    lines: list[str] = ["TY  - JOUR"]
    for author in _author_list(cit):
        lines.append(f"AU  - {author}")
    year = cit.get("year")
    if year:
        lines.append(f"PY  - {year}")
    if cit.get("title"):
        lines.append(f"TI  - {cit['title']}")
    if cit.get("journal"):
        lines.append(f"JO  - {cit['journal']}")
    if cit.get("doi"):
        lines.append(f"DO  - {cit['doi']}")
        lines.append(f"UR  - https://doi.org/{cit['doi']}")
    if cit.get("pmid"):
        lines.append(f"AN  - {cit['pmid']}")
    if cit.get("claim"):
        lines.append(f"AB  - {cit['claim']}")
    lines.append("ER  -")
    return "\n".join(lines)


def to_ris(citations: Iterable[Any]) -> str:
    """Serialize an iterable of Citation/dict to an RIS string."""
    return "\n\n".join(_ris_record(_as_dict(c)) for c in citations) + "\n"


# ---------------------------------------------------------------------------
# Zotero RDF


def _rdf_record(cit: dict[str, Any], rdf_id: str) -> str:
    """One Zotero-flavoured Dublin-Core RDF record."""
    title = html.escape(cit.get("title", ""))
    doi = html.escape(cit.get("doi", ""))
    year = cit.get("year") or ""
    journal = html.escape(cit.get("journal", ""))
    abstract = html.escape(cit.get("claim", ""))

    authors_xml = "\n".join(
        f"      <bib:authors><foaf:Person><foaf:surname>{html.escape(a)}</foaf:surname></foaf:Person></bib:authors>"
        for a in _author_list(cit)
    )
    title_xml = f"<dc:title>{title}</dc:title>" if title else ""
    date_xml = f"<dc:date>{year}</dc:date>" if year else ""
    doi_xml = f"<dc:identifier>DOI {doi}</dc:identifier>" if doi else ""
    journal_xml = (
        f"<dcterms:isPartOf><bib:Journal><dc:title>{journal}</dc:title></bib:Journal></dcterms:isPartOf>"
        if journal
        else ""
    )
    abstract_xml = f"<dcterms:abstract>{abstract}</dcterms:abstract>" if abstract else ""
    url_xml = f'<rdf:value rdf:resource="https://doi.org/{doi}"/>' if doi else ""

    return (
        f'  <bib:Article rdf:about="{rdf_id}">\n'
        f"    {title_xml}\n"
        f"    {date_xml}\n"
        f"    {doi_xml}\n"
        f"    {journal_xml}\n"
        f"    {abstract_xml}\n"
        f"    {url_xml}\n"
        f"{authors_xml}\n"
        "  </bib:Article>"
    )


def to_zotero_rdf(citations: Iterable[Any]) -> str:
    """Serialize an iterable of Citation/dict to a Zotero-import RDF/XML string."""
    records = []
    for i, c in enumerate(citations):
        cit = _as_dict(c)
        rdf_id = f"#item_{i + 1}"
        records.append(_rdf_record(cit, rdf_id))

    body = "\n".join(records)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"\n'
        '         xmlns:bib="http://purl.org/net/biblio#"\n'
        '         xmlns:dc="http://purl.org/dc/elements/1.1/"\n'
        '         xmlns:dcterms="http://purl.org/dc/terms/"\n'
        '         xmlns:foaf="http://xmlns.com/foaf/0.1/">\n'
        f"{body}\n"
        "</rdf:RDF>\n"
    )


# ---------------------------------------------------------------------------
# File writer


def write_export(
    out_path: Path | str,
    citations: Iterable[Any],
    *,
    fmt: ExportFormat | None = None,
) -> Path:
    """Write citations to ``out_path``. Format is inferred from extension
    (``.enw``, ``.ris``, ``.rdf`` / ``.xml``) unless ``fmt`` is given.
    """
    p = Path(out_path)
    if fmt is None:
        suf = p.suffix.lower().lstrip(".")
        if suf in {"enw"}:
            fmt = "enw"
        elif suf in {"ris"}:
            fmt = "ris"
        elif suf in {"rdf", "xml"}:
            fmt = "rdf"
        else:
            raise ValueError(
                f"Cannot infer format from extension {p.suffix!r}; pass fmt='enw'/'ris'/'rdf'."
            )

    if fmt == "enw":
        text = to_enw(citations)
    elif fmt == "ris":
        text = to_ris(citations)
    elif fmt == "rdf":
        text = to_zotero_rdf(citations)
    else:  # pragma: no cover
        raise ValueError(f"Unknown fmt: {fmt}")

    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p


__all__ = ["ExportFormat", "to_enw", "to_ris", "to_zotero_rdf", "write_export"]
