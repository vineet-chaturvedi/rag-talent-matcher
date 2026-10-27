"""
Search endpoints:
  POST /api/search/semantic        find employees by MEANING (Step 6)
  GET  /api/resumes/{id}/chunks    see exactly how a resume was chunked
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_ollama
from app.config import Settings, get_settings
from app.db.models import Resume
from app.llm.ollama_client import OllamaClient, OllamaError
from app.rag.search import semantic_search
from app.rag.vector_store import get_vector_store
from app.schemas.search import EmployeeResult, MatchedChunk, SemanticSearchRequest, SemanticSearchResponse
from app.services.indexing import chunks_of

router = APIRouter(tags=["search"])


@router.post("/api/search/semantic", response_model=SemanticSearchResponse)
async def search_semantic(
    req: SemanticSearchRequest,
    db: AsyncSession = Depends(get_db),
    ollama: OllamaClient = Depends(get_ollama),
    settings: Settings = Depends(get_settings),
):
    try:
        matches, timings = await semantic_search(
            db, ollama, get_vector_store(), settings.embed_model, req.query, top_k=req.top_k,
        )
    except OllamaError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    return SemanticSearchResponse(
        query=req.query,
        timings=timings,
        results=[
            EmployeeResult(
                rank=i + 1,
                employee_id=m.employee.id, employee_code=m.employee.employee_code,
                full_name=m.employee.full_name, designation=m.employee.designation,
                location=m.employee.location, availability_status=m.employee.availability_status,
                allocation_percent=m.employee.allocation_percent, score=m.score,
                matched_chunks=[MatchedChunk(section=c.section, similarity=c.similarity, text=c.text)
                                for c in m.chunks],
            )
            for i, m in enumerate(matches)
        ],
    )


@router.get("/api/resumes/{resume_id}/chunks")
async def resume_chunks(resume_id: int, db: AsyncSession = Depends(get_db)):
    if await db.get(Resume, resume_id) is None:
        raise HTTPException(status_code=404, detail="Resume not found")
    return [
        {"chunk_index": c.chunk_index, "section": c.section, "token_estimate": c.token_count,
         "embedding_model": c.embedding_model, "text": c.text}
        for c in await chunks_of(resume_id)
    ]
