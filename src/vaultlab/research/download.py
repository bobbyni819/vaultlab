"""PDF download and Obsidian-compatible knowledge base export."""

from __future__ import annotations

import logging
import os
import re

import requests

from vaultlab.research.paper import Paper

logger = logging.getLogger(__name__)

_UNPAYWALL_BASE = "https://api.unpaywall.org/v2/"
_UNPAYWALL_EMAIL = "bobby@bobby-tools.local"


def _elsevier_pdf_url_and_headers(doi: str) -> tuple[str, dict] | None:
    """Return (url, headers) for an Elsevier PDF request, or None if
    no key is configured.  Lazy-loads config to keep module import cheap."""
    try:
        from vaultlab.research.config import get_key

        key = get_key("elsevier_key")
    except Exception:
        return None
    if not key:
        return None
    url = f"https://api.elsevier.com/content/article/doi/{doi}"
    headers = {"X-ELS-APIKey": key, "Accept": "application/pdf"}
    return url, headers


def _springer_oa_pdf_url(doi: str) -> str:
    """Query Springer OA API for a fullTextUrl PDF link, or empty string."""
    try:
        from vaultlab.research.config import get_key

        key = get_key("springer_open_access_api_key")
    except Exception:
        return ""
    if not key:
        return ""
    try:
        url = "http://api.springernature.com/openaccess/json"
        r = requests.get(url, params={"q": f'doi:"{doi}"', "api_key": key}, timeout=20)
        if r.status_code != 200:
            return ""
        data = r.json()
        for rec in data.get("records", []):
            # openAccess records commonly contain a list in 'url' with 'format'=='pdf'
            for u in rec.get("url", []) or []:
                if isinstance(u, dict) and u.get("format", "").lower() == "pdf":
                    return u.get("value", "")
    except Exception as e:
        logger.debug("Springer OA lookup failed for %s: %s", doi, e)
    return ""


def download_pdf(
    paper: Paper,
    output_dir: str,
    session: requests.Session | None = None,
) -> str:
    """Download PDF for a paper, trying multiple sources.

    Resolution order:
    1. PMC full text PDF (if paper has pdf_url from PubMed)
    2. Springer OA PDF (if DOI is from Springer)
    3. Unpaywall (free OA resolver)

    Args:
        paper: Paper object with metadata.
        output_dir: Directory to save the PDF.
        session: Optional requests session for connection reuse.

    Returns:
        Path to the downloaded PDF, or empty string if unavailable.
    """
    if session is None:
        session = requests.Session()

    os.makedirs(output_dir, exist_ok=True)
    filename = _make_filename(paper) + ".pdf"
    filepath = os.path.join(output_dir, filename)

    # Skip if already downloaded
    if os.path.exists(filepath) and os.path.getsize(filepath) > 1000:
        logger.info("PDF already exists: %s", filepath)
        return filepath

    # Try each source.  Each entry is (source_name, url, extra_headers_or_None).
    urls_to_try: list[tuple[str, str, dict | None]] = []

    # 1. Existing pdf_url (e.g., from PMC)
    if paper.pdf_url:
        urls_to_try.append(("PMC/existing", paper.pdf_url, None))

    # 2. Springer direct-DOI (works for any Springer DOI if the content is OA)
    if paper.doi and "springer" in paper.doi.lower():
        urls_to_try.append(
            ("Springer DOI-PDF", f"https://link.springer.com/content/pdf/{paper.doi}.pdf", None)
        )

    # 2b. Springer OA API (works for any DOI with Springer OA record, even non-Springer-prefix DOIs
    #     referenced by Springer)
    if paper.doi:
        spr_oa = _springer_oa_pdf_url(paper.doi)
        if spr_oa:
            urls_to_try.append(("Springer OA", spr_oa, None))

    # 3. Elsevier Article Retrieval API (requires institutional license + api key)
    if paper.doi:
        elsevier = _elsevier_pdf_url_and_headers(paper.doi)
        if elsevier:
            el_url, el_headers = elsevier
            urls_to_try.append(("Elsevier API", el_url, el_headers))

    # 4. Unpaywall
    if paper.doi:
        unpaywall_url = _get_unpaywall_pdf_url(paper.doi, session)
        if unpaywall_url:
            urls_to_try.append(("Unpaywall", unpaywall_url, None))

    for source_name, url, extra_headers in urls_to_try:
        try:
            logger.info("Trying PDF download from %s: %s", source_name, url)
            kwargs = {"timeout": 90, "allow_redirects": True}
            if extra_headers:
                kwargs["headers"] = extra_headers
            resp = session.get(url, **kwargs)
            if resp.status_code == 200 and len(resp.content) > 1000:
                content_type = resp.headers.get("Content-Type", "")
                if "pdf" in content_type or resp.content[:5] == b"%PDF-":
                    with open(filepath, "wb") as f:
                        f.write(resp.content)
                    logger.info("Downloaded PDF (%s): %s", source_name, filepath)
                    return filepath
                else:
                    logger.debug(
                        "%s returned non-PDF content type: %s",
                        source_name,
                        content_type,
                    )
            else:
                logger.debug(
                    "%s returned status %d (size %d)",
                    source_name,
                    resp.status_code,
                    len(resp.content),
                )
        except requests.RequestException as e:
            logger.debug("Failed to download from %s: %s", source_name, e)

    logger.info("No PDF available for: %s", paper.title)
    return ""


def save_to_kb(paper: Paper, kb_dir: str, update_index: bool = True) -> str:
    """Save paper metadata as Obsidian-compatible markdown with YAML frontmatter.

    Creates a markdown file in kb_dir/Sources/Articles/ with the paper's
    metadata in YAML frontmatter and abstract in the body.

    Args:
        paper: Paper object with metadata.
        kb_dir: Path to the knowledge base root directory.
        update_index: If True, rebuild the KB index after saving (default True).

    Returns:
        Path to the saved markdown file.
    """
    articles_dir = os.path.join(kb_dir, "Sources", "Articles")
    os.makedirs(articles_dir, exist_ok=True)

    filename = _make_filename(paper) + ".md"
    filepath = os.path.join(articles_dir, filename)

    # Build YAML frontmatter
    lines = ["---"]
    lines.append(f'title: "{_escape_yaml(paper.title)}"')

    if paper.authors:
        lines.append("authors:")
        for author in paper.authors:
            lines.append(f'  - "{_escape_yaml(author)}"')

    if paper.year:
        lines.append(f"year: {paper.year}")
    if paper.journal:
        lines.append(f'journal: "{_escape_yaml(paper.journal)}"')
    if paper.doi:
        lines.append(f'doi: "{paper.doi}"')
    if paper.pmid:
        lines.append(f'pmid: "{paper.pmid}"')
    if paper.url:
        lines.append(f'url: "{paper.url}"')
    if paper.pdf_url:
        lines.append(f'pdf_url: "{paper.pdf_url}"')
    if paper.citation_count:
        lines.append(f"citation_count: {paper.citation_count}")
    lines.append(f'source: "{paper.source_api}"')
    from datetime import date

    lines.append(f"created: {date.today().isoformat()}")
    lines.append("status: ACTIVE")
    lines.append("tags: [article, literature]")
    lines.append("---")
    lines.append("")

    # Title as heading
    lines.append(f"# {paper.title}")
    lines.append("")

    # Authors and journal
    if paper.authors:
        author_str = ", ".join(paper.authors)
        lines.append(f"**Authors:** {author_str}")
        lines.append("")
    if paper.journal and paper.year:
        lines.append(f"**Published in:** {paper.journal} ({paper.year})")
        lines.append("")
    if paper.doi:
        lines.append(f"**DOI:** [{paper.doi}](https://doi.org/{paper.doi})")
        lines.append("")

    # Abstract
    if paper.abstract:
        lines.append("## Abstract")
        lines.append("")
        lines.append(paper.abstract)
        lines.append("")

    # Links
    lines.append("## Links")
    lines.append("")
    if paper.url:
        lines.append(f"- [Source]({paper.url})")
    if paper.doi:
        lines.append(f"- [DOI](https://doi.org/{paper.doi})")
    if paper.pmid:
        lines.append(f"- [PubMed](https://pubmed.ncbi.nlm.nih.gov/{paper.pmid}/)")
    lines.append("")

    content = "\n".join(lines)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)

    logger.info("Saved paper to KB: %s", filepath)

    # Optionally update the KB index so the new paper appears in _Catalog.md
    if update_index:
        try:
            from bobby_kb import rebuild_index

            rebuild_index(kb_dir)
            logger.info("KB index rebuilt after save")
        except ImportError:
            logger.debug("bobby_kb not available, skipping index rebuild")
        except Exception as e:
            logger.warning("Index rebuild failed: %s", e)

    return filepath


def _make_filename(paper: Paper) -> str:
    """Generate a clean filename from paper metadata."""
    # Use DOI slug if available
    if paper.doi:
        slug = paper.doi.replace("/", "_").replace(".", "-")
        return slug[:100]

    # Fall back to sanitized title
    title = paper.title or "untitled"
    # Remove non-alphanumeric characters
    slug = re.sub(r"[^\w\s-]", "", title)
    slug = re.sub(r"\s+", "_", slug).strip("_")
    return slug[:100]


def _escape_yaml(text: str) -> str:
    """Escape special characters for YAML string values."""
    return text.replace('"', '\\"').replace("\n", " ")


def _get_unpaywall_pdf_url(doi: str, session: requests.Session) -> str:
    """Query Unpaywall for a free PDF URL."""
    try:
        url = f"{_UNPAYWALL_BASE}{doi}"
        resp = session.get(
            url,
            params={"email": _UNPAYWALL_EMAIL},
            timeout=15,
        )
        if resp.status_code != 200:
            return ""
        data = resp.json()

        # Try best OA location
        best_oa = data.get("best_oa_location")
        if best_oa:
            pdf = best_oa.get("url_for_pdf", "")
            if pdf:
                return pdf

        # Try all OA locations
        for loc in data.get("oa_locations", []):
            pdf = loc.get("url_for_pdf", "")
            if pdf:
                return pdf

    except Exception as e:
        logger.debug("Unpaywall lookup failed for %s: %s", doi, e)

    return ""
