"""STORAGE_BACKEND=local: files in a folder (UPLOAD_DIR, default backend/data/uploads, git-ignored)."""
import asyncio
import contextlib
from collections.abc import AsyncIterator
from pathlib import Path

from app.storage.base import FileMissingError, StorageError, check_key


class LocalStorage:
    name = "local"

    def __init__(self, root: str):
        self.root = Path(root)
        self._root_resolved = self.root.resolve()

    def describe(self) -> str:
        return f"folder {self._root_resolved}"

    def path_of(self, key: str) -> Path:
        """
        The file of a key, never outside the upload folder. Before Step 15, rows stored the path itself
        ("data/uploads/EMP-1001/ab12.pdf", relative to backend/, or absolute): those still resolve.
        """
        given = Path(key)
        if given.is_absolute():
            candidate = given
        else:
            inside = self.root / key
            # legacy: a path relative to backend/ that exists, while root/key doesn't
            candidate = given if not inside.exists() and given.exists() else inside
        resolved = candidate.resolve()
        if not resolved.is_relative_to(self._root_resolved):
            raise StorageError(f"{key!r} points outside the upload folder")
        return resolved

    async def put(self, key: str, data: bytes, content_type: str) -> None:
        path = self.root / check_key(key)

        def write() -> None:
            # A temporary file, then a rename: a crash never leaves a half-written resume.
            path.parent.mkdir(parents=True, exist_ok=True)
            temp = path.with_name(path.name + ".part")
            temp.write_bytes(data)
            temp.replace(path)
        try:
            await asyncio.to_thread(write)
        except OSError as exc:      # no permission, disk full, read-only volume ...
            raise StorageError(f"Cannot write to the upload folder {self._root_resolved}: {exc.strerror}") from exc

    async def get(self, key: str) -> bytes:
        path = self.path_of(key)
        try:
            return await asyncio.to_thread(path.read_bytes)
        except FileNotFoundError as exc:
            raise FileMissingError(f"No file {key!r} in {self.root}") from exc

    async def delete(self, key: str) -> None:
        await asyncio.to_thread(self.path_of(key).unlink, missing_ok=True)

    async def exists(self, key: str) -> bool:
        try:
            return await asyncio.to_thread(self.path_of(key).is_file)
        except StorageError:
            return False

    @contextlib.asynccontextmanager
    async def local_path(self, key: str) -> AsyncIterator[Path]:
        path = self.path_of(key)
        if not path.is_file():
            raise FileMissingError(f"No file {key!r} in {self.root}")
        yield path

    async def close(self) -> None:
        pass
