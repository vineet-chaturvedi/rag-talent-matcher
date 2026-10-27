"""
The background worker: takes resumes from the queue (status = QUEUED) and processes them one at a time.

The "queue" is simply the resumes table: every resume has a status, so the queue survives
server restarts and crashes. Step 4: QUEUED -> PARSING -> PARSED (or FAILED).
Steps 5-6 add: PARSED -> EXTRACTING -> EMBEDDING -> READY.
"""
import asyncio
import logging
from pathlib import Path

from sqlalchemy import func, select, update

from app.config import Settings
from app.db.enums import ResumeStatus
from app.db.models import Resume
from app.db.session import SessionLocal
from app.ingestion.text_extraction import ExtractionError, extract_text

logger = logging.getLogger(__name__)


class IngestionWorker:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._wake = asyncio.Event()          # set() = "there may be new work, look now"
        self._stopping = False
        self._task: asyncio.Task | None = None

    # ------------------------------------------------------------------ lifecycle
    def start(self) -> None:
        self._task = asyncio.create_task(self._run(), name="ingestion-worker")

    async def stop(self) -> None:
        self._stopping = True
        self._wake.set()
        if self._task:
            try:
                # Let the current resume finish (up to 30 s), then give up waiting.
                await asyncio.wait_for(self._task, timeout=30)
            except TimeoutError:
                self._task.cancel()

    def notify(self) -> None:
        """Called by the upload endpoints so new files are processed immediately, not after the poll delay."""
        self._wake.set()

    @property
    def running(self) -> bool:
        return self._task is not None and not self._task.done()

    # ------------------------------------------------------------------ main loop
    async def _run(self) -> None:
        logger.info("Ingestion worker started")
        await self._recover_interrupted()
        while not self._stopping:
            try:
                did_work = await self._process_next()
            except Exception:
                # A bug must not kill the worker forever: log it, pause, keep going.
                logger.exception("Unexpected error in ingestion worker")
                did_work = False
            if did_work:
                continue                        # more may be waiting: go again straight away
            self._wake.clear()
            try:
                await asyncio.wait_for(self._wake.wait(), timeout=self.settings.worker_poll_seconds)
            except TimeoutError:
                pass                            # nothing woke us: just poll again
        logger.info("Ingestion worker stopped")

    async def _recover_interrupted(self) -> None:
        """A resume left in PARSING means the server stopped mid-way. Put it back in the queue."""
        async with SessionLocal() as session:
            result = await session.execute(
                update(Resume).where(Resume.status == ResumeStatus.PARSING).values(status=ResumeStatus.QUEUED)
            )
            await session.commit()
            if result.rowcount:
                logger.warning("Re-queued %d resume(s) interrupted by a restart", result.rowcount)

    # ------------------------------------------------------------------ one resume
    async def _process_next(self) -> bool:
        """Process the oldest queued resume. Returns False when the queue is empty."""
        # 1. Claim it: mark PARSING in its own short transaction, so the admin page shows progress.
        async with SessionLocal() as session:
            resume = await session.scalar(
                select(Resume)
                .where(Resume.status == ResumeStatus.QUEUED)
                .order_by(Resume.created_at, Resume.id)
                .limit(1)
            )
            if resume is None:
                return False
            resume.status = ResumeStatus.PARSING
            resume.attempts += 1
            resume.error_message = None
            await session.commit()
            resume_id, path, mime_type, attempt = resume.id, resume.stored_path, resume.mime_type, resume.attempts

        logger.info("Parsing resume %s (attempt %d): %s", resume_id, attempt, path)

        # 2. Do the slow work OUTSIDE any database transaction, in a thread.
        try:
            result = await asyncio.to_thread(
                extract_text, Path(path), mime_type, self.settings.min_chars_per_page
            )
        except ExtractionError as exc:
            # The file itself is the problem (scanned, corrupt, empty): retrying is pointless.
            logger.warning("Resume %s failed permanently: %s", resume_id, exc)
            await self._save(resume_id, status=ResumeStatus.FAILED, error_message=str(exc))
            return True
        except Exception as exc:
            # Unexpected (a bug, disk hiccup...): retry a few times before giving up.
            logger.exception("Resume %s: unexpected error", resume_id)
            give_up = attempt >= self.settings.worker_max_attempts
            note = f"gave up after {attempt} attempts" if give_up else "will retry"
            await self._save(
                resume_id,
                status=ResumeStatus.FAILED if give_up else ResumeStatus.QUEUED,
                error_message=f"{type(exc).__name__}: {exc} ({note})",
            )
            return True

        # 3. Save the result.
        await self._save(
            resume_id,
            status=ResumeStatus.PARSED,
            raw_text=result.text,
            page_count=result.page_count,
        )
        logger.info("Resume %s parsed: %d characters via %s", resume_id, len(result.text), result.method)
        return True

    async def _save(self, resume_id: int, **values) -> None:
        async with SessionLocal() as session:
            resume = await session.get(Resume, resume_id)
            if resume is None:
                logger.info("Resume %s was deleted while being processed; nothing to save", resume_id)
                return
            for key, value in values.items():
                setattr(resume, key, value)
            resume.processed_at = func.now()
            await session.commit()
