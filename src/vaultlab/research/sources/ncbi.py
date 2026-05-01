"""NCBI PubMed E-utilities client using requests (no biopython dependency).

Endpoints:
    esearch — search PubMed by keywords, returns PMIDs
    efetch  — fetch metadata + abstract by PMID(s)

Rate limit: 10 requests/sec with API key, 3/sec without.
"""

from __future__ import annotations

import logging
import time
import xml.etree.ElementTree as ET

import requests

from vaultlab.research.paper import Paper

logger = logging.getLogger(__name__)

_BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
_TOOL = "bobby_research"
_EMAIL = "bobby@bobby-tools.local"

# PubMed E-utilities AND every word in a query — long natural-language
# queries with stopwords ("and", "across", "of", etc.) and unicode
# punctuation (em-dashes, en-dashes) become over-restrictive and return
# 0 hits. Empirical threshold: 7 keyword-words still works; adding 1-2
# stopwords kills the result count to 0. Strip these before sending.
_PUBMED_STOPWORDS: frozenset[str] = frozenset(
    {
        "a",
        "an",
        "the",
        "and",
        "or",
        "of",
        "in",
        "on",
        "at",
        "for",
        "to",
        "with",
        "by",
        "across",
        "through",
        "from",
        "into",
        "via",
    }
)


def _normalize_query_for_pubmed(query: str) -> str:
    """Strip em-dashes / en-dashes / common stopwords from a query.

    PubMed's E-utilities don't tolerate long natural-language queries
    well — they AND every word together, so "CODEX imaging — methods
    and applications across tissue types" requires every word
    (including "and", "across") to appear in the title/abstract.
    Result: 0 hits.

    This helper produces a keyword-only version that PubMed handles
    cleanly. Punctuation removed; stopwords dropped; whitespace
    collapsed.
    """
    if not query:
        return ""
    text = query
    # Replace unicode dashes + common punctuation with space
    for ch in ("—", "–", "−", "—", "–", ",", ";", ":"):
        text = text.replace(ch, " ")
    # Lowercase + split for stopword filtering
    words = [w for w in text.split() if w]
    keep = [w for w in words if w.lower() not in _PUBMED_STOPWORDS]
    if not keep:
        # All stopwords? Fall back to the original query — don't return empty.
        return query.strip()
    return " ".join(keep)


class NCBIClient:
    """Client for NCBI PubMed E-utilities."""

    def __init__(self, api_key: str = ""):
        self.api_key = api_key
        self._session = requests.Session()
        self._last_request_time = 0.0
        # With API key: 10 req/sec (0.1s), without: 3 req/sec (0.34s)
        self._min_interval = 0.1 if api_key else 0.34

    def _rate_limit(self) -> None:
        """Enforce rate limiting between requests."""
        elapsed = time.time() - self._last_request_time
        if elapsed < self._min_interval:
            time.sleep(self._min_interval - elapsed)
        self._last_request_time = time.time()

    def _base_params(self) -> dict:
        """Common parameters for all E-utility requests."""
        params = {"tool": _TOOL, "email": _EMAIL}
        if self.api_key:
            params["api_key"] = self.api_key
        return params

    def _get(self, endpoint: str, params: dict, retries: int = 3) -> requests.Response:
        """Make a GET request with rate limiting and retry."""
        url = _BASE_URL + endpoint
        for attempt in range(retries):
            self._rate_limit()
            try:
                resp = self._session.get(url, params=params, timeout=30)
                resp.raise_for_status()
                return resp
            except requests.RequestException as e:
                if attempt < retries - 1:
                    wait = 2**attempt
                    logger.warning(
                        "NCBI request failed (attempt %d/%d): %s. Retrying in %ds...",
                        attempt + 1,
                        retries,
                        e,
                        wait,
                    )
                    time.sleep(wait)
                else:
                    logger.error("NCBI request failed after %d attempts: %s", retries, e)
                    raise

    def search(self, query: str, max_results: int = 20) -> list[Paper]:
        """Search PubMed and return Paper objects with full metadata.

        Args:
            query: PubMed search query (supports MeSH terms, boolean operators, etc.).
            max_results: Maximum number of results to return.

        Returns:
            List of Paper objects with metadata from efetch.
        """
        # Step 1: esearch to get PMIDs.
        # Normalize query: PubMed AND's every word, so long natural-language
        # queries with stopwords return 0 hits. _normalize_query_for_pubmed
        # strips em-dashes + common English stopwords.
        normalized = _normalize_query_for_pubmed(query)
        if normalized != query:
            logger.debug(
                "NCBI: normalized query %r -> %r (PubMed-friendly)",
                query,
                normalized,
            )
        params = {
            **self._base_params(),
            "db": "pubmed",
            "term": normalized,
            "retmax": max_results,
            "retmode": "json",
            "sort": "relevance",
        }
        resp = self._get("esearch.fcgi", params)
        data = resp.json()

        id_list = data.get("esearchresult", {}).get("idlist", [])
        if not id_list:
            logger.info("No PubMed results for query: %s", query)
            return []

        logger.info("Found %d PubMed IDs for: %s", len(id_list), query)

        # Step 2: efetch to get full metadata
        return self._fetch_papers(id_list)

    def get_paper(self, pmid: str) -> Paper | None:
        """Fetch a single paper by PMID.

        Args:
            pmid: PubMed ID.

        Returns:
            Paper object or None if not found.
        """
        papers = self._fetch_papers([pmid])
        return papers[0] if papers else None

    def get_abstract(self, pmid: str) -> str:
        """Fetch just the abstract text for a PMID.

        Args:
            pmid: PubMed ID.

        Returns:
            Abstract text or empty string.
        """
        paper = self.get_paper(pmid)
        return paper.abstract if paper else ""

    def _fetch_papers(self, pmids: list[str]) -> list[Paper]:
        """Fetch full metadata for a list of PMIDs via efetch XML."""
        if not pmids:
            return []

        params = {
            **self._base_params(),
            "db": "pubmed",
            "id": ",".join(pmids),
            "rettype": "xml",
            "retmode": "xml",
        }
        resp = self._get("efetch.fcgi", params)

        try:
            root = ET.fromstring(resp.content)
        except ET.ParseError as e:
            logger.error("Failed to parse efetch XML: %s", e)
            return []

        papers = []
        for article in root.findall(".//PubmedArticle"):
            paper = self._parse_article(article)
            if paper:
                papers.append(paper)

        return papers

    def _parse_article(self, article: ET.Element) -> Paper | None:
        """Parse a PubmedArticle XML element into a Paper."""
        try:
            medline = article.find("MedlineCitation")
            if medline is None:
                return None

            # PMID
            pmid_el = medline.find("PMID")
            pmid = pmid_el.text if pmid_el is not None else ""

            # Article metadata
            art = medline.find("Article")
            if art is None:
                return None

            # Title
            title_el = art.find("ArticleTitle")
            title = self._get_text(title_el) if title_el is not None else ""

            # Abstract
            abstract_el = art.find("Abstract")
            abstract = ""
            if abstract_el is not None:
                parts = []
                for text_el in abstract_el.findall("AbstractText"):
                    label = text_el.get("Label", "")
                    text = self._get_text(text_el)
                    if label:
                        parts.append(f"{label}: {text}")
                    else:
                        parts.append(text)
                abstract = " ".join(parts)

            # Authors
            authors = []
            author_list = art.find("AuthorList")
            if author_list is not None:
                for author in author_list.findall("Author"):
                    last = author.findtext("LastName", "")
                    fore = author.findtext("ForeName", "")
                    initials = author.findtext("Initials", "")
                    if last:
                        name = f"{last} {initials}" if initials else last
                        if not initials and fore:
                            name = f"{last} {fore}"
                        authors.append(name)

            # Journal
            journal_el = art.find("Journal")
            journal = ""
            if journal_el is not None:
                title_el = journal_el.find("Title")
                if title_el is not None and title_el.text:
                    journal = title_el.text
                else:
                    iso = journal_el.find("ISOAbbreviation")
                    if iso is not None and iso.text:
                        journal = iso.text

            # Year
            year = 0
            pub_date = art.find(".//PubDate")
            if pub_date is not None:
                year_el = pub_date.find("Year")
                if year_el is not None and year_el.text:
                    try:
                        year = int(year_el.text)
                    except ValueError:
                        pass
                # Try MedlineDate if Year not present
                if not year:
                    med_date = pub_date.find("MedlineDate")
                    if med_date is not None and med_date.text:
                        try:
                            year = int(med_date.text[:4])
                        except (ValueError, IndexError):
                            pass

            # DOI
            doi = ""
            article_ids = art.findall("ELocationID")
            for eid in article_ids:
                if eid.get("EIdType") == "doi" and eid.text:
                    doi = eid.text
                    break
            # Also check PubmedData/ArticleIdList
            if not doi:
                pub_data = article.find("PubmedData")
                if pub_data is not None:
                    for aid in pub_data.findall(".//ArticleId"):
                        if aid.get("IdType") == "doi" and aid.text:
                            doi = aid.text
                            break

            # URL
            url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else ""

            # PDF URL (try PMC)
            pdf_url = ""
            pmc_id = ""
            pub_data = article.find("PubmedData")
            if pub_data is not None:
                for aid in pub_data.findall(".//ArticleId"):
                    if aid.get("IdType") == "pmc" and aid.text:
                        pmc_id = aid.text
                        break
            if pmc_id:
                pdf_url = f"https://www.ncbi.nlm.nih.gov/pmc/articles/{pmc_id}/pdf/"

            return Paper(
                title=title,
                authors=authors,
                year=year,
                journal=journal,
                doi=doi,
                pmid=pmid,
                abstract=abstract,
                url=url,
                pdf_url=pdf_url,
                source_api="pubmed",
            )

        except Exception as e:
            logger.error("Error parsing PubMed article: %s", e)
            return None

    @staticmethod
    def _get_text(element: ET.Element) -> str:
        """Extract all text content from an XML element, including mixed content."""
        parts = []
        if element.text:
            parts.append(element.text)
        for child in element:
            if child.text:
                parts.append(child.text)
            if child.tail:
                parts.append(child.tail)
        return "".join(parts).strip()
