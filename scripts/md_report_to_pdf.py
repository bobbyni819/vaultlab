"""Render a markdown report to a paginated PDF via reportlab.

General-purpose enough for the validation/stress-test reports: handles
ATX headings (#/##/###), GitHub pipe tables (with wrapped cells so columns
never overflow), bullet lists, blockquotes, `inline code`, **bold**, and
paragraphs. No LaTeX engine required.

Usage:
    /opt/anaconda3/bin/python scripts/md_report_to_pdf.py <in.md> <out.pdf>
"""

from __future__ import annotations

import html
import re
import sys
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    HRFlowable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

styles = getSampleStyleSheet()
H1 = ParagraphStyle("h1", parent=styles["Heading1"], fontSize=15, leading=18, spaceBefore=6, spaceAfter=6, textColor=colors.HexColor("#2b2218"))
H2 = ParagraphStyle("h2", parent=styles["Heading2"], fontSize=12, leading=15, spaceBefore=10, spaceAfter=4, textColor=colors.HexColor("#3a2f20"))
H3 = ParagraphStyle("h3", parent=styles["Heading3"], fontSize=10, leading=13, spaceBefore=7, spaceAfter=3, textColor=colors.HexColor("#4a3d29"))
BODY = ParagraphStyle("body", parent=styles["Normal"], fontSize=9, leading=12.5, alignment=TA_LEFT, spaceAfter=5)
BULLET = ParagraphStyle("bullet", parent=BODY, leftIndent=14, bulletIndent=4, spaceAfter=2)
CELL = ParagraphStyle("cell", parent=styles["Normal"], fontSize=7.8, leading=10)
CELLH = ParagraphStyle("cellh", parent=CELL, fontName="Helvetica-Bold", textColor=colors.white)
QUOTE = ParagraphStyle("quote", parent=BODY, leftIndent=10, textColor=colors.HexColor("#555"), borderColor=colors.HexColor("#c2b89f"))


def inline(text: str) -> str:
    """Convert a subset of inline markdown to reportlab mini-HTML."""
    text = html.escape(text, quote=False)
    text = re.sub(r"`([^`]+)`", r'<font face="Courier" size="8" color="#7a3b14">\1</font>', text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"(?<!\*)\*(?!\*)([^*]+)\*(?!\*)", r"<i>\1</i>", text)
    return text


def split_row(line: str) -> list[str]:
    line = line.strip()
    if line.startswith("|"):
        line = line[1:]
    if line.endswith("|"):
        line = line[:-1]
    return [c.strip() for c in line.split("|")]


def build(md_path: Path, pdf_path: Path) -> None:
    lines = md_path.read_text(encoding="utf-8").splitlines()
    page_w = LETTER[0] - 1.1 * inch  # usable width given margins below
    flow = []
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        stripped = line.strip()

        if not stripped:
            i += 1
            continue

        # horizontal rule
        if re.fullmatch(r"-{3,}", stripped):
            flow.append(Spacer(1, 3))
            flow.append(HRFlowable(width="100%", thickness=0.6, color=colors.HexColor("#c2b89f")))
            flow.append(Spacer(1, 3))
            i += 1
            continue

        # headings
        m = re.match(r"^(#{1,3})\s+(.*)", stripped)
        if m:
            level = len(m.group(1))
            style = {1: H1, 2: H2, 3: H3}[level]
            flow.append(Paragraph(inline(m.group(2)), style))
            i += 1
            continue

        # table: a header row followed by a |---| separator
        if stripped.startswith("|") and i + 1 < n and re.match(r"^\s*\|?[\s:|-]+\|?\s*$", lines[i + 1]) and "-" in lines[i + 1]:
            header = split_row(stripped)
            i += 2  # skip separator
            rows = []
            while i < n and lines[i].strip().startswith("|"):
                rows.append(split_row(lines[i].strip()))
                i += 1
            ncols = len(header)
            data = [[Paragraph(inline(c), CELLH) for c in header]]
            for r in rows:
                r = (r + [""] * ncols)[:ncols]
                data.append([Paragraph(inline(c), CELL) for c in r])
            col_w = page_w / ncols
            t = Table(data, colWidths=[col_w] * ncols, repeatRows=1)
            t.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#6b5b40")),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#b7ab90")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f4f0e6")]),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]))
            flow.append(t)
            flow.append(Spacer(1, 6))
            continue

        # blockquote
        if stripped.startswith(">"):
            flow.append(Paragraph(inline(stripped.lstrip("> ").strip()), QUOTE))
            i += 1
            continue

        # bullet / numbered list
        bm = re.match(r"^(\s*)([-*]|\d+\.)\s+(.*)", line)
        if bm:
            indent = len(bm.group(1))
            sty = ParagraphStyle("b", parent=BULLET, leftIndent=14 + indent * 6)
            bchar = "•" if bm.group(2) in ("-", "*") else bm.group(2)
            flow.append(Paragraph(inline(bm.group(3)), sty, bulletText=bchar))
            i += 1
            continue

        # paragraph (gather consecutive non-special lines)
        para = [stripped]
        i += 1
        while i < n and lines[i].strip() and not re.match(r"^(#{1,3}\s|>|\||\s*([-*]|\d+\.)\s|-{3,}$)", lines[i].strip()):
            para.append(lines[i].strip())
            i += 1
        flow.append(Paragraph(inline(" ".join(para)), BODY))

    doc = SimpleDocTemplate(
        str(pdf_path), pagesize=LETTER,
        leftMargin=0.55 * inch, rightMargin=0.55 * inch,
        topMargin=0.5 * inch, bottomMargin=0.5 * inch,
        title=md_path.stem,
    )
    doc.build(flow)
    print(f"wrote {pdf_path}")


if __name__ == "__main__":
    build(Path(sys.argv[1]), Path(sys.argv[2]))
