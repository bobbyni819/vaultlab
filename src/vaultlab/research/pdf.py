"""PDF text extraction — extract text from PDFs with graceful library fallback.

Tries pdfplumber first (best for tables + text), then pypdf as fallback.
If neither library is available, logs a warning and returns empty string.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)


def extract_text(pdf_path: str) -> str:
    """Extract text from a PDF file.

    Tries multiple methods in order:
    1. pdfplumber (best for tables + text)
    2. PyPDF2 / pypdf (fallback)
    3. Return empty string if no library available

    Args:
        pdf_path: Path to the PDF file.

    Returns:
        Extracted text as a single string, or empty string on failure.
    """
    pdf_path = os.path.abspath(pdf_path)
    if not os.path.isfile(pdf_path):
        logger.warning("PDF file not found: %s", pdf_path)
        return ""

    # Try pdfplumber first
    try:
        import pdfplumber

        pages = []
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    pages.append(text)
        if pages:
            return "\n\n".join(pages)
        logger.debug("pdfplumber returned no text for %s", pdf_path)
    except ImportError:
        logger.debug("pdfplumber not installed, trying pypdf")
    except Exception as e:
        logger.warning("pdfplumber failed on %s: %s", pdf_path, e)

    # Try pypdf (PyPDF2 successor)
    try:
        from pypdf import PdfReader

        reader = PdfReader(pdf_path)
        pages = []
        for page in reader.pages:
            text = page.extract_text()
            if text:
                pages.append(text)
        if pages:
            return "\n\n".join(pages)
        logger.debug("pypdf returned no text for %s", pdf_path)
    except ImportError:
        logger.debug("pypdf not installed")
    except Exception as e:
        logger.warning("pypdf failed on %s: %s", pdf_path, e)

    # Try legacy PyPDF2
    try:
        from PyPDF2 import PdfReader as LegacyReader

        reader = LegacyReader(pdf_path)
        pages = []
        for page in reader.pages:
            text = page.extract_text()
            if text:
                pages.append(text)
        if pages:
            return "\n\n".join(pages)
    except ImportError:
        pass
    except Exception as e:
        logger.warning("PyPDF2 failed on %s: %s", pdf_path, e)

    logger.warning("No PDF library available. Install pdfplumber or pypdf: pip install pdfplumber")
    return ""


def extract_and_save(pdf_path: str, output_dir: str | None = None) -> str:
    """Extract PDF text and save as markdown companion file.

    Creates a .md file with:
    - YAML frontmatter (title from first line, source path)
    - Full extracted text

    Args:
        pdf_path: Path to the PDF file.
        output_dir: Directory for the markdown file.
            Defaults to the same directory as the PDF.

    Returns:
        Path to the markdown file, or empty string on failure.
    """
    pdf_path = os.path.abspath(pdf_path)
    if not os.path.isfile(pdf_path):
        logger.warning("PDF file not found: %s", pdf_path)
        return ""

    text = extract_text(pdf_path)
    if not text:
        logger.warning("No text extracted from %s", pdf_path)
        return ""

    # Derive output path
    if output_dir is None:
        output_dir = os.path.dirname(pdf_path)
    os.makedirs(output_dir, exist_ok=True)

    stem = Path(pdf_path).stem
    md_path = os.path.join(output_dir, f"{stem}.md")

    # Extract title from first non-empty line
    first_line = ""
    for line in text.split("\n"):
        stripped = line.strip()
        if stripped:
            first_line = stripped
            break
    title = first_line[:120] if first_line else stem

    # Write markdown with YAML frontmatter
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("---\n")
        # Escape quotes in title for YAML
        safe_title = title.replace('"', '\\"')
        f.write(f'title: "{safe_title}"\n')
        f.write(f'source: "{pdf_path}"\n')
        f.write("type: pdf_extract\n")
        f.write("---\n\n")
        f.write(text)
        f.write("\n")

    logger.info("Saved extracted text to %s", md_path)
    return md_path


def batch_extract(pdf_dir: str, output_dir: str | None = None) -> list[str]:
    """Extract text from all PDFs in a directory.

    Skips PDFs that already have companion .md files (in the output dir).

    Args:
        pdf_dir: Directory containing PDF files.
        output_dir: Directory for markdown files.
            Defaults to the same directory as the PDFs.

    Returns:
        List of created markdown file paths.
    """
    pdf_dir = os.path.abspath(pdf_dir)
    if not os.path.isdir(pdf_dir):
        logger.warning("Directory not found: %s", pdf_dir)
        return []

    if output_dir is None:
        output_dir = pdf_dir
    output_dir = os.path.abspath(output_dir)

    created = []
    for filename in sorted(os.listdir(pdf_dir)):
        if not filename.lower().endswith(".pdf"):
            continue

        # Check if companion .md already exists
        stem = Path(filename).stem
        md_path = os.path.join(output_dir, f"{stem}.md")
        if os.path.exists(md_path):
            logger.debug("Skipping %s (companion .md exists)", filename)
            continue

        pdf_path = os.path.join(pdf_dir, filename)
        result = extract_and_save(pdf_path, output_dir)
        if result:
            created.append(result)

    logger.info(
        "Batch extract: %d/%d PDFs processed",
        len(created),
        len([f for f in os.listdir(pdf_dir) if f.lower().endswith(".pdf")]),
    )
    return created
