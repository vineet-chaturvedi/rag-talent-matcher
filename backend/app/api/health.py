"""
GET /api/health: "is everything this app needs actually working?"

Checks the database and Ollama (reachable + every model in .env installed).
  ok       -> everything works                                (HTTP 200)
  degraded -> reachable, but a model is missing               (HTTP 200)
  error    -> database or Ollama unreachable                  (HTTP 503)
"""
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_ollama
from app.config import Settings, get_settings
from app.llm.ollama_client import OllamaClient, OllamaError, normalize_model_name

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health")
async def health(
    ollama: OllamaClient = Depends(get_ollama),
    settings: Settings = Depends(get_settings),
    db: AsyncSession = Depends(get_db),
):
    # ---- Database ----
    try:
        await db.execute(text("SELECT 1"))  # the simplest possible query: "are you there?"
        database = {"reachable": True}
    except SQLAlchemyError as exc:
        database = {"reachable": False, "error": str(exc)}

    # ---- Ollama ----
    models_ok = False
    try:
        version = await ollama.version()
        installed = {normalize_model_name(m) for m in await ollama.list_models()}
        required = {
            "embed_model": settings.embed_model,
            "fast_llm_model": settings.fast_llm_model,
            "quality_llm_model": settings.quality_llm_model,
        }
        models = {
            role: {"name": name, "installed": normalize_model_name(name) in installed}
            for role, name in required.items()
        }
        models_ok = all(m["installed"] for m in models.values())
        ollama_info = {"reachable": True, "version": version, "models": models}
    except OllamaError as exc:
        ollama_info = {"reachable": False, "error": str(exc)}

    # ---- Overall verdict ----
    if not database["reachable"] or not ollama_info["reachable"]:
        status, code = "error", 503
    elif not models_ok:
        status, code = "degraded", 200
    else:
        status, code = "ok", 200

    return JSONResponse(
        status_code=code,
        content={
            "app": settings.app_name,
            "environment": settings.environment,
            "status": status,
            "database": database,
            "ollama": ollama_info,
        },
    )