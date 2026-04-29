"""Paper dataclass for representing scientific literature metadata."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Paper:
    """A scientific paper with metadata from one or more APIs.

    Attributes:
        title: Paper title.
        authors: List of author names (e.g., ["Smith J", "Doe A"]).
        year: Publication year.
        journal: Journal or venue name.
        doi: Digital Object Identifier (e.g., "10.1038/s41586-024-07159-5").
        pmid: PubMed ID (e.g., "39358522").
        abstract: Paper abstract text.
        url: URL to the paper landing page.
        pdf_url: Direct URL to a PDF if available.
        citation_count: Number of citations (from Semantic Scholar or other source).
        source_api: Which API provided this record ("pubmed", "springer", "semantic").
    """

    title: str = ""
    authors: list[str] = field(default_factory=list)
    year: int = 0
    journal: str = ""
    doi: str = ""
    pmid: str = ""
    abstract: str = ""
    url: str = ""
    pdf_url: str = ""
    citation_count: int = 0
    source_api: str = ""

    def to_dict(self) -> dict:
        """Convert to a plain dict (for JSON serialization)."""
        return {
            "title": self.title,
            "authors": self.authors,
            "year": self.year,
            "journal": self.journal,
            "doi": self.doi,
            "pmid": self.pmid,
            "abstract": self.abstract,
            "url": self.url,
            "pdf_url": self.pdf_url,
            "citation_count": self.citation_count,
            "source_api": self.source_api,
        }

    @classmethod
    def from_dict(cls, d: dict) -> Paper:
        """Create a Paper from a dict."""
        return cls(
            title=d.get("title", ""),
            authors=d.get("authors", []),
            year=d.get("year", 0),
            journal=d.get("journal", ""),
            doi=d.get("doi", ""),
            pmid=d.get("pmid", ""),
            abstract=d.get("abstract", ""),
            url=d.get("url", ""),
            pdf_url=d.get("pdf_url", ""),
            citation_count=d.get("citation_count", 0),
            source_api=d.get("source_api", ""),
        )

    def __str__(self) -> str:
        parts = [self.title]
        if self.authors:
            first = self.authors[0]
            if len(self.authors) > 1:
                parts.append(f"  {first} et al.")
            else:
                parts.append(f"  {first}")
        if self.journal and self.year:
            parts.append(f"  {self.journal} ({self.year})")
        elif self.year:
            parts.append(f"  ({self.year})")
        if self.doi:
            parts.append(f"  DOI: {self.doi}")
        return "\n".join(parts)

    @property
    def doi_url(self) -> str:
        """Return the doi.org URL for this paper."""
        if self.doi:
            return f"https://doi.org/{self.doi}"
        return ""

    def merge(self, other: Paper) -> None:
        """Merge metadata from another Paper record (fills in blanks)."""
        if not self.title and other.title:
            self.title = other.title
        if not self.authors and other.authors:
            self.authors = other.authors
        if not self.year and other.year:
            self.year = other.year
        if not self.journal and other.journal:
            self.journal = other.journal
        if not self.doi and other.doi:
            self.doi = other.doi
        if not self.pmid and other.pmid:
            self.pmid = other.pmid
        if not self.abstract and other.abstract:
            self.abstract = other.abstract
        if not self.url and other.url:
            self.url = other.url
        if not self.pdf_url and other.pdf_url:
            self.pdf_url = other.pdf_url
        if not self.citation_count and other.citation_count:
            self.citation_count = other.citation_count
