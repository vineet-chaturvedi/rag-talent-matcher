"""The storage interface every backend implements, and what all of them share."""
import contextlib
import os
import re
import tempfile
from collections.abc import AsyncIterator
from pathlib import Path, PurePosixPath
from typing import Protocol

_KEY_PART = re.compile(r"^[A-Za-z0-9._-]+$")


class StorageError(Exception):
    """The storage service failed or is misconfigured (the message is safe to log)."""


class FileMissingError(StorageError):
    """No file under this key."""


def check_key(key: str) -> str:
    """Keys are relative, '/'-separated, and made of safe characters only: no '..', no absolute paths."""
    parts = key.split("/")      # not PurePosixPath: it would quietly turn "a//b" into "a/b"
    if not key or any(p in ("", ".", "..") or not _KEY_PART.match(p) for p in parts):
        raise StorageError(f"Invalid storage key: {key!r}")
    return key


def join_prefix(prefix: str, key: str) -> str:
    """'resumes/' + 'EMP-1/x.pdf' -> 'resumes/EMP-1/x.pdf' (an empty prefix is allowed)."""
    prefix = (prefix or "").strip("/")
    return f"{prefix}/{check_key(key)}" if prefix else check_key(key)


class FileStorage(Protocol):
    name: str

    def describe(self) -> str:
        """Where files go, for logs and the health check, e.g. "s3://bucket/resumes/"."""

    async def put(self, key: str, data: bytes, content_type: str) -> None:
        """Store (or replace) the file. Atomic: readers never see a half-written file."""

    async def get(self, key: str) -> bytes:
        """The file's bytes. Raises FileMissingError if there is none."""

    async def delete(self, key: str) -> None:
        """Remove the file; no error if it is already gone."""

    async def exists(self, key: str) -> bool: ...

    def local_path(self, key: str) -> contextlib.AbstractAsyncContextManager[Path]:
        """The file as a path on this machine, for libraries that read files (PDF/Word text extraction).
        Cloud backends download it to a private temporary file that is deleted afterwards."""

    async def close(self) -> None: ...


class DownloadingStorage:
    """local_path() for cloud backends: download to a temporary file readable by this user only."""

    async def get(self, key: str) -> bytes:  # implemented by the backend
        raise NotImplementedError

    @contextlib.asynccontextmanager
    async def local_path(self, key: str) -> AsyncIterator[Path]:
        data = await self.get(key)
        suffix = PurePosixPath(key).suffix
        fd, name = tempfile.mkstemp(prefix="resume-", suffix=suffix)   # created with mode 0600
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(data)
            yield Path(name)
        finally:
            Path(name).unlink(missing_ok=True)
