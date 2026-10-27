"""
Learning-only endpoints (disabled when ENVIRONMENT=production).

POST /api/dev/chat        -> talk to the fast or quality model, see real speed stats
POST /api/dev/similarity  -> compare two texts by embedding similarity
"""
import math
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.deps import get_ollama
from app.config import Settings, get_settings
from app.llm.ollama_client import OllamaClient, OllamaError

router = APIRouter(prefix="/api/dev", tags=["dev (learning only)"])

NS_PER_SECOND = 1_000_000_000  # Ollama reports durations in nanoseconds


# ---------------------------------------------------------------- chat
class ChatRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=8000,
                        examples=["In one sentence, what does a DevOps engineer do?"])
    model: Literal["fast", "quality"] = "fast"   # only these two values are accepted
    temperature: float = Field(0.0, ge=0.0, le=2.0)
    system: str | None = Field(None, examples=["You are a concise technical recruiter."])


class ChatResponse(BaseModel):
    model: str
    answer: str
    prompt_tokens: int
    output_tokens: int
    load_seconds: float
    prompt_tokens_per_second: float
    output_tokens_per_second: float


def _rate(tokens: int, duration_ns: int) -> float:
    return round(tokens / (duration_ns / NS_PER_SECOND), 2) if duration_ns else 0.0


@router.post("/chat", response_model=ChatResponse)
async def dev_chat(
    req: ChatRequest,
    ollama: OllamaClient = Depends(get_ollama),
    settings: Settings = Depends(get_settings),
):
    model = settings.fast_llm_model if req.model == "fast" else settings.quality_llm_model

    messages = []
    if req.system:
        messages.append({"role": "system", "content": req.system})
    messages.append({"role": "user", "content": req.prompt})

    try:
        data = await ollama.chat(messages, model=model, temperature=req.temperature,
                                 num_ctx=settings.llm_num_ctx)
    except OllamaError as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    return ChatResponse(
        model=model,
        answer=data["message"]["content"],
        prompt_tokens=data.get("prompt_eval_count", 0),
        output_tokens=data.get("eval_count", 0),
        load_seconds=round(data.get("load_duration", 0) / NS_PER_SECOND, 2),
        prompt_tokens_per_second=_rate(data.get("prompt_eval_count", 0), data.get("prompt_eval_duration", 0)),
        output_tokens_per_second=_rate(data.get("eval_count", 0), data.get("eval_duration", 0)),
    )


# ---------------------------------------------------------------- similarity
class SimilarityRequest(BaseModel):
    text_a: str = Field(..., min_length=1, examples=["Looking for a backend developer with Django experience"])
    text_b: str = Field(..., min_length=1, examples=["Built REST APIs in Python for 4 years"])
    use_prefixes: bool = Field(True, description="Add nomic's search_query:/search_document: prefixes")


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """
    cos(angle between two vectors) = (a . b) / (|a| * |b|)
     1.0 -> same direction (same meaning), 0 -> unrelated, negative -> opposite.
    """
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    return dot / (norm_a * norm_b) if norm_a and norm_b else 0.0


@router.post("/similarity")
async def dev_similarity(
    req: SimilarityRequest,
    ollama: OllamaClient = Depends(get_ollama),
    settings: Settings = Depends(get_settings),
):
    # text_a plays the "job/query" role, text_b the "resume/document" role.
    a = f"search_query: {req.text_a}" if req.use_prefixes else req.text_a
    b = f"search_document: {req.text_b}" if req.use_prefixes else req.text_b

    try:
        vec_a, vec_b = await ollama.embed([a, b], model=settings.embed_model)  # one batched call
    except OllamaError as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    return {
        "cosine_similarity": round(cosine_similarity(vec_a, vec_b), 4),
        "dimensions": len(vec_a),
        "used_prefixes": req.use_prefixes,
    }