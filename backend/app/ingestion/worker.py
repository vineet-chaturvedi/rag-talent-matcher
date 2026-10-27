"""
The background worker: moves resumes through the pipeline, one resume and one stage at a time.

The "queue" is the resumes table itself: each resume's status says which stage it is waiting for,
so the queue survives restarts and crashes.

  Stage      waits in   works as     on success   (Step)
  parse      QUEUED     PARSING      PARSED       Step 4: file -> plain text
  extract    PARSED     EXTRACTING   EXTRACTED    Step 5: plain text -> structured profile (LLM)
  embed      EXTRACTED  EMBEDDING    READY        Step 6: chunks -> vectors -> ChromaDB
"""
import asyncio
import logging
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import func, select, update

from app.config import Settings
from app.db.enums import ResumeStatus
from app.db.models import Resume
from app.db.session import SessionLocal
from app.extraction.extractor import extract_profile
from app.ingestion.text_extraction import ExtractionError, extract_text
from app.llm.ollama_client import OllamaClient, OllamaError
from app.services.indexing import index_resume
from app.services.profiles import save_profile

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Stage:
    name: str
    waiting: ResumeStatus     # pick resumes in this status...
    working: ResumeStatus     # ...mark them with this while processing


# Earlier stages first: cheap parsing of new uploads never waits behind slow LLM work.
STAGES = [
    Stage("parse", ResumeStatus.QUEUED, ResumeStatus.PARSING),
    Stage("extract", ResumeStatus.PARSED, ResumeStatus.EXTRACTING),
    Stage("embed", ResumeStatus.EXTRACTED, ResumeStatus.EMBEDDING),
]


@dataclass
class Claimed:
    """A snapshot of the resume we are working on (plain values, so no database session stays open)."""
    id: int
    stage: Stage
    attempt: int
    path: str
    mime_type: str
    raw_text: str | None


class IngestionWorker:
    def __init__(self, settings: Settings, ollama: OllamaClient):
        self.settings = settings
        self.ollama = ollama
        self._wake = asyncio.Event()      # set() = "there may be new work, look now"
        self._stop = asyncio.Event()      # set() = "shut down"
        self._task: asyncio.Task | None = None

    # ------------------------------------------------------------------ lifecycle
    def start(self) -> None:
        self._task = asyncio.create_task(self._run(), name="ingestion-worker")

    async def stop(self) -> None:
        self._stop.set()
        self._wake.set()
        if self._task:
            try:
                await asyncio.wait_for(self._task, timeout=30)
            except TimeoutError:
                # An LLM call can take minutes: cancel it. The resume stays in a "working" status
                # and is put back in the queue by _recover_interrupted() on the next start.
                self._task.cancel()

    def notify(self) -> None:
        self._wake.set()

    @property
    def running(self) -> bool:
        return self._task is not None and not self._task.done()

    async def _sleep(self, seconds: float) -> None:
        """Sleep, but wake up immediately if the server is shutting down."""
        try:
            await asyncio.wait_for(self._stop.wait(), timeout=seconds)
        except TimeoutError:
            pass

    # ------------------------------------------------------------------ main loop
    async def _run(self) -> None:
        logger.info("Ingestion worker started (extraction model: %s)", self.settings.extraction_model)
        await self._recover_interrupted()
        while not self._stop.is_set():
            try:
                did_work = await self._process_next()
            except Exception:
                logger.exception("Unexpected error in ingestion worker")
                did_work = False
            if did_work:
                continue
            self._wake.clear()
            try:
                await asyncio.wait_for(self._wake.wait(), timeout=self.settings.worker_poll_seconds)
            except TimeoutError:
                pass
        logger.info("Ingestion worker stopped")

    async def _recover_interrupted(self) -> None:
        """Anything left in a 'working' status was interrupted: put it back where it was waiting."""
        async with SessionLocal() as session:
            for stage in STAGES:
                result = await session.execute(
                    update(Resume).where(Resume.status == stage.working).values(status=stage.waiting)
                )
                if result.rowcount:
                    logger.warning("Re-queued %d resume(s) interrupted during '%s'", result.rowcount, stage.name)
            await session.commit()

    # ------------------------------------------------------------------ one unit of work
    async def _claim(self) -> Claimed | None:
        """Find the next resume for the earliest stage that has work, and mark it as being worked on."""
        async with SessionLocal() as session:
            for stage in STAGES:
                resume = await session.scalar(
                    select(Resume)
                    .where(Resume.status == stage.waiting, Resume.is_current.is_(True))
                    .order_by(Resume.created_at, Resume.id)
                    .limit(1)
                )
                if resume is None:
                    continue
                resume.status = stage.working
                resume.attempts += 1
                resume.error_message = None
                await session.commit()
                return Claimed(resume.id, stage, resume.attempts, resume.stored_path,
                               resume.mime_type, resume.raw_text)
        return None

    async def _process_next(self) -> bool:
        job = await self._claim()
        if job is None:
            return False
        logger.info("Resume %s: %s (attempt %d)", job.id, job.stage.name, job.attempt)
        try:
            if job.stage.name == "parse":
                await self._parse(job)
            elif job.stage.name == "extract":
                await self._extract(job)
            elif job.stage.name == "embed":
                await self._embed(job)
        except ExtractionError as exc:
            # The file itself is the problem (scanned, corrupt...): retrying won't help.
            logger.warning("Resume %s failed permanently: %s", job.id, exc)
            await self._update(job.id, status=ResumeStatus.FAILED, error_message=str(exc))
        except OllamaError as exc:
            # Ollama is down or busy: not the resume's fault. Undo the attempt and pause.
            logger.warning("Ollama unavailable (%s). Pausing %.0fs.", exc, self.settings.ollama_retry_seconds)
            await self._update(job.id, status=job.stage.waiting, attempts=job.attempt - 1,
                               error_message=f"Waiting for Ollama: {exc}")
            await self._sleep(self.settings.ollama_retry_seconds)
        except Exception as exc:
            logger.exception("Resume %s: unexpected error during %s", job.id, job.stage.name)
            give_up = job.attempt >= self.settings.worker_max_attempts
            note = f"gave up after {job.attempt} attempts" if give_up else "will retry"
            await self._update(
                job.id,
                status=ResumeStatus.FAILED if give_up else job.stage.waiting,
                error_message=f"{job.stage.name}: {type(exc).__name__}: {exc} ({note})",
            )
        return True

    # ------------------------------------------------------------------ stages
    async def _parse(self, job: Claimed) -> None:
        result = await asyncio.to_thread(
            extract_text, Path(job.path), job.mime_type, self.settings.min_chars_per_page
        )
        await self._update(job.id, status=ResumeStatus.PARSED, attempts=0,
                           raw_text=result.text, page_count=result.page_count)
        logger.info("Resume %s parsed: %d characters via %s", job.id, len(result.text), result.method)

    async def _extract(self, job: Claimed) -> None:
        if not job.raw_text:
            raise ExtractionError("No text to extract from (the parse stage produced nothing).")
        outcome = await extract_profile(
            self.ollama, job.raw_text,
            model=self.settings.extraction_model,
            num_ctx=self.settings.llm_num_ctx,
            max_output_tokens=self.settings.extraction_max_output_tokens,
            max_input_chars=self.settings.extraction_max_input_chars,
        )
        async with SessionLocal() as session:
            if not await save_profile(session, job.id, outcome):
                logger.info("Resume %s was deleted during extraction; result discarded", job.id)

    async def _embed(self, job: Claimed) -> None:
        if not await index_resume(job.id, self.ollama, self.settings):
            logger.info("Resume %s was deleted during embedding; nothing indexed", job.id)

    async def _update(self, resume_id: int, **values) -> None:
        async with SessionLocal() as session:
            resume = await session.get(Resume, resume_id)
            if resume is None:
                logger.info("Resume %s was deleted while being processed; nothing to save", resume_id)
                return
            for key, value in values.items():
                setattr(resume, key, value)
            resume.processed_at = func.now()
            await session.commit()
