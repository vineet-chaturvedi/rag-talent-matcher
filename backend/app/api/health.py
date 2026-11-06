"""
GET /api/health: "is everything this app needs actually working?"

Checks the database, Ollama, and every model in .env: Ollama models pulled, cloud models configured.
  ok       -> everything works                                          (HTTP 200)
  degraded -> reachable, but a model is missing or not configured      (HTTP 200)
  error    -> database unreachable, or Ollama unreachable while a model needs it  (HTTP 503)
"""
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_ollama
from app.config import Settings, get_settings
from app.llm.ollama_client import OllamaError, normalize_model_name
from app.llm.router import ModelRouter
from app.schemas.overview import HealthOut

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health", response_model=HealthOut,
            responses={503: {"model": HealthOut, "description": "Database or Ollama unreachable"}})
async def health(
    ollama: ModelRouter = Depends(get_ollama),
    settings: Settings = Depends(get_settings),
    db: AsyncSession = Depends(get_db),
):
    # ---- Database ----
    try:
        await db.execute(text("SELECT 1"))  # the simplest possible query: "are you there?"
        database = {"reachable": True}
    except SQLAlchemyError as exc:
        database = {"reachable": False, "error": str(exc)}

    # ---- Models (Ollama and any other provider, app/llm/router.py) ----
    # Ollama models must be pulled; cloud models must be configured (key set, ALLOW_CLOUD_MODELS). Cloud APIs
    # are not called here: a health check must be fast and free.
    installed: set[str] | None = None
    version, error = None, None
    try:
        version = await ollama.version()
        installed = {normalize_model_name(m) for m in await ollama.list_models()}
    except OllamaError as exc:
        error = str(exc)
    wanted = {"embed_model": settings.embed_model, "fast_llm_model": settings.fast_llm_model,
              "quality_llm_model": settings.quality_llm_model}
    # A task set to its own model (not fast/quality) needs that model too.
    for task in ("extraction_model", "role_parse_model", "judge_model", "agent_model"):
        name = getattr(settings, task)
        if name not in (settings.fast_llm_model, settings.quality_llm_model):
            wanted[task] = name
    models = {role: ollama.model_health(name, installed, "embed" if role == "embed_model" else "chat")
              for role, name in wanted.items()}
    models_ok = all(m["installed"] for m in models.values())
    ollama_needed = ollama.uses_ollama()
    ollama_info = {"reachable": installed is not None, "version": version, "models": models, "error": error}

    # ---- Overall verdict ----
    if not database["reachable"] or (ollama_needed and not ollama_info["reachable"]):
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