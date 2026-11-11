"""
The resume pipeline: the stages one resume goes through, and the work of each stage.

  Stage      waits in   works as     on success   (Step)
  parse      QUEUED     PARSING      PARSED       Step 4: file -> plain text
  extract    PARSED     EXTRACTING   EXTRACTED    Step 5: plain text -> structured profile (LLM)
  embed      EXTRACTED  EMBEDDING    READY        Step 6: chunks -> vectors -> vector store

The resume's status IS its place in the pipeline, stored in the database: it survives restarts, and any
worker can continue where another stopped. Who runs a stage, and when, is the job system's business
(app/jobs): this module only does the work of one claimed stage.
"""
import asyncio
import logging
from dataclasses import dataclass

from sqlalchemy import func

from app.config import Settings
from app.db.enums import ResumeStatus
from app.db.models import Resume
from app.db.session import SessionLocal
from app.extraction.extractor import extract_profile
from app.ingestion.text_extraction import ExtractionError, extract_text
from app.llm.ollama_client import OllamaClient
from app.services.indexing import index_resume
from app.services.profiles import save_profile
from app.storage import FileMissingError, get_storage

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Stage:
    name: str
    waiting: ResumeStatus     # resumes in this status are waiting for the stage...
    working: ResumeStatus     # ...and have this status while a worker runs it


PARSE = Stage("parse", ResumeStatus.QUEUED, ResumeStatus.PARSING)
EXTRACT = Stage("extract", ResumeStatus.PARSED, ResumeStatus.EXTRACTING)
EMBED = Stage("embed", ResumeStatus.EXTRACTED, ResumeStatus.EMBEDDING)
STAGES = [PARSE, EXTRACT, EMBED]
STAGE_FOR_WAITING = {s.waiting: s for s in STAGES}
WAITING = [s.waiting for s in STAGES]
WORKING = [s.working for s in STAGES]


@dataclass
class Claimed:
    """A snapshot of the claimed resume (plain values, so no database session stays open during LLM calls)."""
    id: int
    stage: Stage
    attempt: int
    path: str            # the storage key of the file (app/storage)
    mime_type: str
    raw_text: str | None


async def run_stage(job: Claimed, ollama: OllamaClient, settings: Settings) -> None:
    """Do the claimed stage and move the resume on. Raises ExtractionError (the file itself is the problem),
    LLMError (the model service), or anything unexpected; the caller decides what each means."""
    if job.stage is PARSE:
        await _parse(job, settings)
    elif job.stage is EXTRACT:
        await _extract(job, ollama, settings)
    else:
        await _embed(job, ollama, settings)


async def _parse(job: Claimed, settings: Settings) -> None:
    try:
        # local storage: the file itself; cloud storage: a private temporary copy, deleted afterwards
        async with get_storage().local_path(job.path) as path:
            result = await asyncio.to_thread(extract_text, path, job.mime_type, settings.min_chars_per_page)
    except FileMissingError as exc:
        raise ExtractionError(f"The uploaded file is missing from storage ({exc}).") from exc
    await update_resume(job.id, status=ResumeStatus.PARSED, attempts=0, raw_text=result.text,
                        page_count=result.page_count)
    logger.info("Resume %s parsed: %d characters via %s", job.id, len(result.text), result.method)


async def _extract(job: Claimed, ollama: OllamaClient, settings: Settings) -> None:
    if not job.raw_text:
        raise ExtractionError("No text to extract from (the parse stage produced nothing).")
    outcome = await extract_profile(
        ollama, job.raw_text,
        model=settings.extraction_model,
        num_ctx=settings.llm_num_ctx,
        max_output_tokens=settings.extraction_max_output_tokens,
        max_input_chars=settings.extraction_max_input_chars,
    )
    async with SessionLocal() as session:
        if not await save_profile(session, job.id, outcome):          # sets EXTRACTED, attempts 0
            logger.info("Resume %s was deleted during extraction; result discarded", job.id)


async def _embed(job: Claimed, ollama: OllamaClient, settings: Settings) -> None:
    if not await index_resume(job.id, ollama, settings):              # sets READY
        logger.info("Resume %s was deleted during embedding; nothing indexed", job.id)


async def update_resume(resume_id: int, **values) -> None:
    async with SessionLocal() as session:
        resume = await session.get(Resume, resume_id)
        if resume is None:
            logger.info("Resume %s was deleted while being processed; nothing to save", resume_id)
            return
        for key, value in values.items():
            setattr(resume, key, value)
        resume.lease_expires_at = None
        resume.processed_at = func.now()
        await session.commit()
