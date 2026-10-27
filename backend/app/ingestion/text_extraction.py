"""
Turn a resume file (PDF or DOCX) into clean plain text.

Synchronous on purpose: reading a PDF is CPU work, not waiting. The worker runs these
functions in a separate thread (asyncio.to_thread) so the web server never freezes.
"""
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import pypdfium2 as pdfium
from docx import Document
from docx.table import Table
from docx.text.paragraph import Paragraph

from app.ingestion.storage import DOCX_MIME, PDF_MIME


class ExtractionError(Exception):
    """A permanent problem with the file itself. Retrying will not help."""


class ScannedDocumentError(ExtractionError):
    """The PDF has (almost) no text layer: it is a picture of a page and needs OCR."""


@dataclass
class ExtractedText:
    text: str
    page_count: int | None   # None for DOCX: Word files have no fixed pages
    method: str              # which library produced the text


# --------------------------------------------------------------------------- public entry point
def extract_text(path: Path, mime_type: str, min_chars_per_page: int = 100) -> ExtractedText:
    if not path.exists():
        raise ExtractionError(f"File not found on disk: {path}")

    if mime_type == PDF_MIME:
        pages = _pdf_pages(path)
        text = clean_text("\n\n".join(_remove_repeated_lines(pages)))
        if len(text) < min_chars_per_page * len(pages):
            raise ScannedDocumentError(
                f"Only {len(text)} characters of text in {len(pages)} page(s). "
                "This looks like a scanned image; it needs OCR before it can be processed."
            )
        return ExtractedText(text=text, page_count=len(pages), method="pypdfium2")

    if mime_type == DOCX_MIME:
        text = clean_text(_docx_text(path))
        if len(text) < 50:
            raise ExtractionError("The document contains almost no text.")
        return ExtractedText(text=text, page_count=None, method="python-docx")

    raise ExtractionError(f"Unsupported file type: {mime_type}")


# --------------------------------------------------------------------------- PDF
def _pdf_pages(path: Path) -> list[str]:
    """Text of each page, in the order the PDF stores it (usually reading order, column by column)."""
    try:
        pdf = pdfium.PdfDocument(str(path))
    except pdfium.PdfiumError as exc:
        # Raised for corrupt files and for password-protected PDFs.
        raise ExtractionError(f"Could not open the PDF (corrupt or password-protected): {exc}") from exc
    try:
        pages = []
        for page in pdf:
            textpage = page.get_textpage()
            pages.append(textpage.get_text_range())
            textpage.close()
            page.close()
        return pages
    finally:
        pdf.close()


def _remove_repeated_lines(pages: list[str]) -> list[str]:
    """
    Headers/footers ("Ananya Iyer - Resume", "Confidential") repeat on every page and would pollute
    chunks. A short line that appears on most pages of a 3+ page document is treated as one.
    """
    if len(pages) < 3:
        return pages
    counts = Counter(
        line.strip()
        for page in pages
        for line in set(page.splitlines())
        if 0 < len(line.strip()) <= 80
    )
    threshold = len(pages) * 0.6
    repeated = {line for line, n in counts.items() if n >= threshold}
    return ["\n".join(l for l in page.splitlines() if l.strip() not in repeated) for page in pages]


# --------------------------------------------------------------------------- DOCX
def _docx_text(path: Path) -> str:
    """Paragraphs AND tables, in document order. Many resumes put skills inside tables."""
    try:
        document = Document(str(path))
    except Exception as exc:  # python-docx raises several types for broken files
        raise ExtractionError(f"Could not open the DOCX file: {exc}") from exc

    parts: list[str] = []
    for block in document.iter_inner_content():   # yields Paragraph and Table objects in order
        if isinstance(block, Paragraph):
            text = block.text.strip()
            if not text:
                continue
            style = (block.style.name or "") if block.style is not None else ""
            if style.startswith(("Heading", "Title")):
                parts.append("")                    # blank line before a heading: keeps sections apart
            parts.append(text)
        elif isinstance(block, Table):
            parts.extend(_table_lines(block))
    return "\n".join(parts)


def _table_lines(table: Table) -> list[str]:
    """One line per table row, cells joined with ' | '. Merged cells repeat their text, so skip repeats."""
    lines = []
    for row in table.rows:
        cells: list[str] = []
        for cell in row.cells:
            text = cell.text.strip()
            if text and (not cells or cells[-1] != text):
                cells.append(text)
        if cells:
            lines.append(" | ".join(cells))
    return lines


# --------------------------------------------------------------------------- cleaning
_BULLETS = "•●▪■◦‣∙"
_ZERO_WIDTH = "​‌‍﻿"
_PAGE_NUMBER = re.compile(r"^(page\s+\d+(\s*(of|/)\s*\d+)?|\d+\s*(of|/)\s*\d+)$", re.IGNORECASE)


def clean_text(text: str) -> str:
    """Normalise the many ways PDFs and Word encode the same text, so later steps see consistent input."""
    text = unicodedata.normalize("NFKC", text)                     # 'ﬁ' -> 'fi', full-width -> normal
    text = text.replace("\r\n", "\n").replace("\r", "\n")          # Windows/old-Mac line endings
    text = text.replace(" ", " ").replace("\t", " ")          # non-breaking space, tabs
    text = re.sub(f"[{_ZERO_WIDTH}]", "", text)                    # invisible characters
    text = re.sub(f"[{_BULLETS}]", "-", text)                      # one bullet style
    text = re.sub(r"([a-z])-\n([a-z])", r"\1\2", text)             # "develop-\nment" -> "development"

    lines: list[str] = []
    for raw in text.split("\n"):
        line = re.sub(r" {2,}", " ", raw).strip()
        if _PAGE_NUMBER.match(line):                               # "Page 2 of 3", "2/3"
            continue
        if lines and lines[-1] == "-" and line:                    # a bullet alone on its line:
            lines[-1] = f"- {line}"                                #   glue it to the next line
            continue
        lines.append(line)

    text = "\n".join(lines)
    text = re.sub(r"\n{3,}", "\n\n", text)                         # at most one blank line in a row
    return text.strip()
