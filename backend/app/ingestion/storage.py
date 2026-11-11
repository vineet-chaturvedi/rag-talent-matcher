"""
Checking uploaded resume files, and naming them for storage (where they are kept: app/storage).

Pure functions: no database, no web framework. That keeps them easy to read and to test.
"""
import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

PDF_MIME = "application/pdf"
DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
DOC_MIME = "application/msword"

# extension -> (MIME type we store, the "magic bytes" every real file of that type starts with)
ALLOWED_TYPES: dict[str, tuple[str, bytes]] = {
    ".pdf": (PDF_MIME, b"%PDF-"),
    ".docx": (DOCX_MIME, b"PK\x03\x04"),  # a .docx is a ZIP archive; ZIPs start with "PK"
    ".doc": (DOC_MIME, b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"),  # Word 97-2003: an OLE compound file
}


class InvalidFileError(ValueError):
    """The upload is not an acceptable resume. The message is safe to show to the user."""


@dataclass(frozen=True)
class ValidatedFile:
    extension: str   # ".pdf", ".docx" or ".doc"
    mime_type: str
    sha256: str      # 64 hex characters: the file's fingerprint
    size_bytes: int


def validate_resume_file(filename: str, data: bytes, max_bytes: int) -> ValidatedFile:
    """Raise InvalidFileError if the file is not a usable resume; otherwise describe it."""
    extension = Path(filename or "").suffix.lower()

    if extension not in ALLOWED_TYPES:
        raise InvalidFileError(f"Unsupported file type '{extension or '(none)'}'. Upload a PDF, DOCX or DOC file.")
    if not data:
        raise InvalidFileError("The file is empty.")
    if len(data) > max_bytes:
        raise InvalidFileError(
            f"The file is larger than the {max_bytes // (1024 * 1024)} MB limit."
        )

    mime_type, magic = ALLOWED_TYPES[extension]
    if not data.startswith(magic):
        # The name says .pdf but the bytes say otherwise: renamed, corrupted, or malicious.
        raise InvalidFileError(f"The file is named {extension} but its contents are not a real {extension[1:].upper()} file.")

    return ValidatedFile(
        extension=extension,
        mime_type=mime_type,
        sha256=hashlib.sha256(data).hexdigest(),
        size_bytes=len(data),
    )


def safe_folder_name(value: str) -> str:
    """Keep only letters, digits, '-' and '_' so a value can never escape the uploads folder."""
    cleaned = re.sub(r"[^A-Za-z0-9_-]", "_", value).strip("_")
    return cleaned or "unknown"


def storage_key(employee_code: str, file: ValidatedFile) -> str:
    """<EMPLOYEE_CODE>/<first 16 chars of sha256>.<ext>, the same on every storage backend.
    The user's file name is never used (it is kept in the database, for downloads)."""
    return f"{safe_folder_name(employee_code)}/{file.sha256[:16]}{file.extension}"
