"""
Semantic search: a question in plain words -> the employees whose resume chunks are closest in meaning.

  1. embed the query                     ("search_query: container orchestration")
  2. ask ChromaDB for the nearest chunks  (a pool, e.g. 60 chunks)
  3. keep only chunks of CURRENT, READY resumes (drops anything stale)
  4. group chunks by employee            (one employee can match through several chunks)
  5. rank employees by their best chunk  (Step 7 improves this with keywords, filters and fusion)
"""
import asyncio
import time
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.enums import ResumeStatus
from app.db.models import Employee, Resume
from app.llm.ollama_client import OllamaClient
from app.rag.embeddings import embed_query
from app.rag.vector_store import ChunkHit, VectorStore


@dataclass
class EmployeeMatch:
    employee: Employee
    score: float                       # similarity of the best matching chunk
    chunks: list[ChunkHit] = field(default_factory=list)


async def semantic_search(
    session: AsyncSession, ollama: OllamaClient, store: VectorStore, embed_model: str,
    query: str, top_k: int = 10, chunk_pool: int = 60, chunks_per_employee: int = 3,
) -> tuple[list[EmployeeMatch], dict]:
    started = time.perf_counter()
    vector = await embed_query(ollama, query, embed_model)
    embedded = time.perf_counter()
    hits = await asyncio.to_thread(store.query, vector, chunk_pool)
    searched = time.perf_counter()

    # Only chunks from resumes that are still current and fully processed count.
    resume_ids = {h.resume_id for h in hits}
    valid = {
        r.id: r for r in (await session.scalars(
            select(Resume).where(Resume.id.in_(resume_ids), Resume.is_current.is_(True),
                                 Resume.status == ResumeStatus.READY)
        )).all()
    } if resume_ids else {}
    employees = {
        e.id: e for e in (await session.scalars(
            select(Employee).where(Employee.id.in_({r.employee_id for r in valid.values()}))
        )).all()
    } if valid else {}

    by_employee: dict[int, EmployeeMatch] = {}
    for hit in hits:                                   # hits arrive best-first
        if hit.resume_id not in valid or hit.employee_id not in employees:
            continue
        match = by_employee.setdefault(hit.employee_id, EmployeeMatch(employees[hit.employee_id], hit.similarity))
        if len(match.chunks) < chunks_per_employee:
            match.chunks.append(hit)

    ranked = sorted(by_employee.values(), key=lambda m: m.score, reverse=True)[:top_k]
    timings = {
        "embed_ms": round((embedded - started) * 1000),
        "vector_search_ms": round((searched - embedded) * 1000),
        "total_ms": round((time.perf_counter() - started) * 1000),
        "chunks_considered": len(hits),
    }
    return ranked, timings
