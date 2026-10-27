"""
Indexing one resume: build chunks -> embed them -> store vectors in ChromaDB -> store chunk rows in SQLite.
Called by the worker's "embed" stage (status EXTRACTED -> EMBEDDING -> READY).
"""
import asyncio
import logging
import uuid
from datetime import date

from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import selectinload

from app.config import Settings
from app.db.enums import ResumeStatus
from app.db.models import Resume, ResumeChunk, ResumeSkill
from app.db.session import SessionLocal
from app.llm.ollama_client import OllamaClient
from app.rag.chunking import JobInfo, build_chunks
from app.rag.embeddings import embed_documents
from app.rag.vector_store import get_vector_store

logger = logging.getLogger(__name__)


async def index_resume(resume_id: int, ollama: OllamaClient, settings: Settings) -> bool:
    """Returns False if the resume no longer exists."""
    # 1. Read everything we need (short read-only session).
    async with SessionLocal() as session:
        resume = await session.get(
            Resume, resume_id,
            options=[
                selectinload(Resume.employee),
                selectinload(Resume.profile),
                selectinload(Resume.experiences),
                selectinload(Resume.skills).selectinload(ResumeSkill.skill),
            ],
        )
        if resume is None:
            return False
        profile = resume.profile
        skills = sorted(((l.skill.name, l.years) for l in resume.skills), key=lambda s: -(s[1] or 0))
        jobs = [
            JobInfo(e.title, e.company, e.start_date, e.end_date, e.is_current, e.description)
            for e in sorted(resume.experiences, key=lambda e: e.start_date or date.min, reverse=True)
        ]
        employee_id, employee_code, full_name = resume.employee.id, resume.employee.employee_code, resume.employee.full_name
        raw_text = resume.raw_text or ""

    # 2. Chunk (pure Python, milliseconds).
    drafts = build_chunks(
        employee_code=employee_code, full_name=full_name, raw_text=raw_text,
        headline=profile.headline if profile else None,
        total_years=profile.total_experience_years if profile else None,
        summary=profile.summary if profile else None,
        skills=skills, jobs=jobs,
        max_chars=settings.chunk_max_chars, overlap=settings.chunk_overlap_chars,
        anonymize_text=settings.anonymize_chunks,
    )

    # 3. Embed (Ollama, about a second per resume on CPU).
    vectors = await embed_documents(ollama, [d.text for d in drafts], settings.embed_model, settings.embed_batch_size)

    # 4. Vectors -> ChromaDB (first: if this fails, the database still says EMBEDDING and the stage is retried).
    ids = [str(uuid.uuid4()) for _ in drafts]
    metadatas = [
        {"resume_id": resume_id, "employee_id": employee_id, "employee_code": employee_code,
         "section": d.section.value, "chunk_index": i, "embedding_model": settings.embed_model}
        for i, d in enumerate(drafts)
    ]
    await asyncio.to_thread(
        get_vector_store().replace_resume, resume_id, ids, vectors, [d.text for d in drafts], metadatas
    )

    # 5. Chunk rows -> SQLite (the source of truth) and mark the resume READY, in one transaction.
    async with SessionLocal() as session:
        resume = await session.get(Resume, resume_id)
        if resume is None:                                   # deleted meanwhile: undo the vectors
            await asyncio.to_thread(get_vector_store().delete_resume, resume_id)
            return False
        await session.execute(delete(ResumeChunk).where(ResumeChunk.resume_id == resume_id))
        session.add_all(
            ResumeChunk(id=cid, resume_id=resume_id, section=d.section, chunk_index=i, text=d.text,
                        token_count=d.token_estimate, embedding_model=settings.embed_model)
            for i, (cid, d) in enumerate(zip(ids, drafts))
        )
        resume.status = ResumeStatus.READY
        resume.attempts = 0
        resume.error_message = None
        resume.processed_at = func.now()
        await session.commit()
    logger.info("Resume %s indexed: %d chunks", resume_id, len(drafts))
    return True


async def requeue_for_embedding() -> int:
    """Send every READY current resume back to the embed stage (e.g. after changing the embedding model)."""
    async with SessionLocal() as session:
        result = await session.execute(
            update(Resume)
            .where(Resume.is_current.is_(True), Resume.status == ResumeStatus.READY)
            .values(status=ResumeStatus.EXTRACTED, attempts=0)
        )
        await session.commit()
        return result.rowcount


async def chunks_of(resume_id: int) -> list[ResumeChunk]:
    async with SessionLocal() as session:
        return list((await session.scalars(
            select(ResumeChunk).where(ResumeChunk.resume_id == resume_id).order_by(ResumeChunk.chunk_index)
        )).all())
