"""
Business logic for resumes: adding an uploaded file, deleting, retrying.
"""
import asyncio
import re
from pathlib import Path

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.db.enums import ResumeStatus
from app.db.models import Employee, Resume
from app.ingestion.storage import build_storage_path, delete_file, save_file, validate_resume_file
from app.rag.keyword_index import delete_resume_rows
from app.rag.vector_store import get_vector_store


class DuplicateResumeError(Exception):
    def __init__(self, existing: Resume):
        self.existing = existing
        super().__init__(f"This exact file was already uploaded (resume id {existing.id}).")


async def add_resume(
    session: AsyncSession, settings: Settings, employee: Employee, filename: str, data: bytes
) -> Resume:
    """
    Validate, store and queue one resume for an employee. It becomes the employee's current resume.
    Raises InvalidFileError or DuplicateResumeError.
    """
    file = validate_resume_file(filename, data, settings.max_upload_bytes)

    existing = await session.scalar(select(Resume).where(Resume.file_hash == file.sha256))
    if existing is not None:
        raise DuplicateResumeError(existing)

    previous_ids = list((await session.scalars(
        select(Resume.id).where(Resume.employee_id == employee.id, Resume.is_current.is_(True))
    )).all())

    path = build_storage_path(Path(settings.upload_dir), employee.employee_code, file)
    save_file(path, data)
    try:
        # Older versions stay as history but are no longer searched.
        await session.execute(
            update(Resume)
            .where(Resume.employee_id == employee.id, Resume.is_current.is_(True))
            .values(is_current=False)
        )
        resume = Resume(
            employee_id=employee.id,
            original_filename=Path(filename).name[:255],
            stored_path=path.as_posix(),
            file_hash=file.sha256,
            mime_type=file.mime_type,
            file_size_bytes=file.size_bytes,
            is_current=True,
            status=ResumeStatus.QUEUED,
        )
        session.add(resume)
        await session.commit()
    except Exception:
        # The database didn't accept it: don't leave an orphan file behind.
        await session.rollback()
        delete_file(path)
        raise
    await session.refresh(resume)  # load the values the database filled in (created_at, ...)

    # The old version is no longer current: remove it from both search indexes.
    for old_id in previous_ids:
        await asyncio.to_thread(get_vector_store().delete_resume, old_id)
        await delete_resume_rows(session, old_id)
    if previous_ids:
        await session.commit()
    return resume


_CODE_PREFIX = re.compile(r"^([^_\s.]+)")


def employee_code_from_filename(filename: str) -> str | None:
    """'EMP-1001_ananya_iyer.pdf' -> 'EMP-1001'  (everything before the first '_', space or '.')."""
    match = _CODE_PREFIX.match(Path(filename).name)
    return match.group(1).upper() if match else None


async def delete_resume(session: AsyncSession, resume: Resume) -> None:
    """Delete one resume version: database rows (cascade) + the file. Promote the newest remaining version."""
    resume_id, employee_id, was_current, path = resume.id, resume.employee_id, resume.is_current, resume.stored_path
    await delete_resume_rows(session, resume_id)   # keyword index (not covered by CASCADE)
    await session.delete(resume)   # cascades to profile, skills, chunks... (Steps 5-6)
    await session.flush()
    if was_current:
        newest = await session.scalar(
            select(Resume).where(Resume.employee_id == employee_id).order_by(Resume.created_at.desc(), Resume.id.desc()).limit(1)
        )
        if newest is not None:
            newest.is_current = True
            if newest.status == ResumeStatus.READY:
                newest.status = ResumeStatus.EXTRACTED   # its vectors were removed earlier: re-index it
    await session.commit()
    delete_file(path)
    await asyncio.to_thread(get_vector_store().delete_resume, resume_id)


async def retry_resume(session: AsyncSession, resume: Resume) -> Resume:
    """
    Put a FAILED resume back in the queue with a fresh attempt counter.
    If its text was already extracted, skip parsing and go straight back to LLM extraction.
    """
    resume.status = ResumeStatus.PARSED if resume.raw_text else ResumeStatus.QUEUED
    resume.attempts = 0
    resume.error_message = None
    await session.commit()
    return resume


async def requeue_for_extraction(session: AsyncSession) -> int:
    """
    Send every current resume that already has text back to the extraction stage.
    Use after changing the extraction model or prompt. Old profiles are replaced when re-extracted.
    """
    result = await session.execute(
        update(Resume)
        .where(
            Resume.is_current.is_(True),
            Resume.raw_text.is_not(None),
            Resume.status.in_([ResumeStatus.EXTRACTED, ResumeStatus.READY, ResumeStatus.FAILED]),
        )
        .values(status=ResumeStatus.PARSED, attempts=0, error_message=None)
    )
    await session.commit()
    return result.rowcount
