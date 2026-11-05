"""
Turn a resume file (PDF, DOCX or legacy Word .doc) into clean plain text.

Synchronous on purpose: reading a file is CPU work, not waiting. The worker runs these
functions in a separate thread (asyncio.to_thread) so the web server never freezes.

Rule for this module (finding from the real resumes, doc 18): it may CLEAN text, but it must never
DELETE content. Version 1 removed every short line that repeated on most pages as a "page header",
and so deleted "Role: Lead Developer" under three projects and a whole "Tech: …" line. Now only lines at
the very top or bottom of a page can be treated as headers or footers.
"""
import re
import struct
import unicodedata
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import olefile
import pypdfium2 as pdfium
from docx import Document
from docx.table import Table
from docx.text.paragraph import Paragraph

from app.ingestion.storage import DOC_MIME, DOCX_MIME, PDF_MIME


class ExtractionError(Exception):
    """A permanent problem with the file itself. Retrying will not help."""


class ScannedDocumentError(ExtractionError):
    """The PDF has (almost) no text layer: it is a picture of a page and needs OCR."""


@dataclass
class ExtractedText:
    text: str
    page_count: int | None   # None for Word files: they have no fixed pages
    method: str              # which library produced the text


# --------------------------------------------------------------------------- public entry point
def extract_text(path: Path, mime_type: str, min_chars_per_page: int = 100) -> ExtractedText:
    if not path.exists():
        raise ExtractionError(f"File not found on disk: {path}")

    if mime_type == PDF_MIME:
        pages = _pdf_pages(path)
        text = clean_text("\n\n".join(remove_page_headers(pages)))
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

    if mime_type == DOC_MIME:
        text = clean_text(doc_text(path))
        if len(text) < 50:
            raise ExtractionError("The document contains almost no text.")
        return ExtractedText(text=text, page_count=None, method="olefile (Word 97-2003)")

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


_EDGE_LINES = 2                      # how many lines at the top and at the bottom of a page can be a header/footer
_LABEL_OR_BULLET = re.compile(r"^\W|:")   # "● …", "- …", "Role: …", "Tech: …" are content, never headers


def _visible(line: str) -> str:
    """The line without invisible characters, for comparing lines across pages."""
    return re.sub(r"[​‌‍﻿\s]+", " ", line).strip()


def remove_page_headers(pages: list[str]) -> list[str]:
    """
    Remove running headers and footers ("Ananya Iyer - Resume", "Confidential") from PDFs of 3+ pages.

    A line counts as a header or footer only if ALL of these are true:
      - it is one of the first or last 2 visible lines of a page,
      - the same text sits at the same edge (top or bottom) on at least 60% of the pages,
      - it is short (at most 80 characters) and is neither a bullet nor a "Label: value" line.
    Lines in the middle of a page are never removed, however often they repeat
    ("Role: Lead Developer" under every project is content).
    """
    if len(pages) < 3:
        return pages

    def edges(page: str) -> tuple[set[str], set[str]]:
        visible = [v for v in (_visible(line) for line in page.splitlines()) if v]
        return set(visible[:_EDGE_LINES]), set(visible[-_EDGE_LINES:])

    page_edges = [edges(page) for page in pages]
    threshold = len(pages) * 0.6
    tops = Counter(line for top, _ in page_edges for line in top)
    bottoms = Counter(line for _, bottom in page_edges for line in bottom)
    header = {line for line, n in tops.items() if n >= threshold and _is_header_like(line)}
    footer = {line for line, n in bottoms.items() if n >= threshold and _is_header_like(line)}

    cleaned = []
    for page, (top, bottom) in zip(pages, page_edges):
        lines = page.splitlines()
        visible_index = [i for i, line in enumerate(lines) if _visible(line)]
        drop = {i for i in visible_index[:_EDGE_LINES] if _visible(lines[i]) in header & top}
        drop |= {i for i in visible_index[-_EDGE_LINES:] if _visible(lines[i]) in footer & bottom}
        cleaned.append("\n".join(line for i, line in enumerate(lines) if i not in drop))
    return cleaned


def _is_header_like(line: str) -> bool:
    return 0 < len(line) <= 80 and not _LABEL_OR_BULLET.search(line)


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


# --------------------------------------------------------------------------- legacy Word .doc
def doc_text(path: Path) -> str:
    """
    The main text of a Word 97-2003 (.doc) file, read without Word or LibreOffice.

    A .doc file is an OLE "compound file" (a small file system inside one file). The text lives in the
    "WordDocument" stream as a list of PIECES; a table in the "0Table"/"1Table" stream (the "piece table",
    called CLX in Microsoft's [MS-DOC] specification) says where each piece starts and whether it is stored as
    1 byte per character (Windows-1252) or 2 (UTF-16). We read the pieces in order, keep the main document
    (not headers/footers/footnotes) and turn Word's control characters into plain text.
    """
    try:
        ole = olefile.OleFileIO(str(path))
    except OSError as exc:
        raise ExtractionError(f"Could not open the .doc file (corrupt, or not a Word 97-2003 file): {exc}") from exc
    try:
        if not ole.exists("WordDocument"):
            raise ExtractionError("This .doc file has no Word document inside (it may be another Office format).")
        word = ole.openstream("WordDocument").read()
        if struct.unpack_from("<H", word, 0)[0] != 0xA5EC:
            raise ExtractionError("This .doc file is not a Word 97-2003 document. Save it as .docx or PDF.")
        flags = struct.unpack_from("<H", word, 0x0A)[0]
        if flags & 0x0100:
            raise ExtractionError("The .doc file is password-protected.")
        table_name = "1Table" if flags & 0x0200 else "0Table"
        if not ole.exists(table_name):
            raise ExtractionError("The .doc file is incomplete (its text table is missing).")
        table = ole.openstream(table_name).read()

        main_chars = struct.unpack_from("<i", word, 0x4C)[0]          # ccpText: length of the main document
        fc_clx, lcb_clx = struct.unpack_from("<II", word, 0x01A2)     # where the piece table is
        clx = table[fc_clx: fc_clx + lcb_clx]
        pos = 0
        while pos < len(clx) and clx[pos] == 0x01:                    # skip formatting entries (Prc)
            pos += 3 + struct.unpack_from("<H", clx, pos + 1)[0]
        if pos >= len(clx) or clx[pos] != 0x02:
            raise ExtractionError("The .doc file's text table could not be read.")
        size = struct.unpack_from("<I", clx, pos + 1)[0]
        plc = clx[pos + 5: pos + 5 + size]
        count = (size - 4) // 12
        cps = struct.unpack_from(f"<{count + 1}I", plc, 0)
        pieces = []
        for k in range(count):
            _, fc, _ = struct.unpack_from("<HIH", plc, 4 * (count + 1) + 8 * k)
            length = cps[k + 1] - cps[k]
            if fc & 0x40000000:                                       # "compressed": 1 byte per character
                start = (fc & ~0x40000000) // 2
                pieces.append(word[start:start + length].decode("cp1252", errors="replace"))
            else:
                pieces.append(word[fc:fc + 2 * length].decode("utf-16-le", errors="replace"))
    except (struct.error, OSError) as exc:
        raise ExtractionError(f"The .doc file is damaged: {exc}") from exc
    finally:
        ole.close()

    text = "".join(pieces)
    if 0 < main_chars <= len(text):
        text = text[:main_chars]
    return _word_control_chars(text)


_FIELD = re.compile(r"\x13[^\x13\x14\x15]*\x14([^\x13\x15]*)\x15|\x13[^\x13\x14\x15]*\x15")


def _word_control_chars(text: str) -> str:
    """Word's special characters -> plain text. Fields keep their visible result ('HYPERLINK "…"' is dropped)."""
    for _ in range(3):                                   # fields can be nested; resolve inside-out
        text = _FIELD.sub(lambda m: m.group(1) or "", text)
    text = re.sub(r"[\x13\x14\x15]", "", text)
    text = text.replace("\r", "\n").replace("\x0b", "\n").replace("\x0c", "\n")
    text = text.replace("\x07", " | ")                   # end of a table cell
    text = text.replace("\x1e", "-").replace("\x1f", "")  # non-breaking hyphen, optional hyphen
    return re.sub(r"[\x00-\x08\x0e-\x1d]", "", text)     # pictures, drawn objects and other markers


# --------------------------------------------------------------------------- cleaning
_BULLETS = "•●▪■◦‣∙➢➤►▶✓✔❖◆◇○□"
_ZERO_WIDTH = "​‌‍﻿⁠"
_PRIVATE_USE = "-"                   # Wingdings/Symbol bullets from Word ("", "", "")
_PAGE_NUMBER = re.compile(r"^(page\s+\d+(\s*(of|/)\s*\d+)?|\d+\s*(of|/)\s*\d+)$", re.IGNORECASE)


def clean_text(text: str) -> str:
    """Normalise the many ways PDFs and Word encode the same text, so later steps see consistent input."""
    text = unicodedata.normalize("NFKC", text)                     # 'ﬁ' -> 'fi', full-width -> normal
    text = text.replace("\r\n", "\n").replace("\r", "\n")          # Windows/old-Mac line endings
    text = text.replace(" ", " ").replace("\t", " ")          # non-breaking space, tabs
    text = re.sub(f"[{_ZERO_WIDTH}]", "", text)                    # invisible characters
    text = re.sub(rf"(?m)^(\s*)[{_PRIVATE_USE}]", r"\1-", text)    # a symbol-font bullet at the line start
    text = re.sub(f"[{_PRIVATE_USE}]", "", text)                   # any other symbol-font character
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
