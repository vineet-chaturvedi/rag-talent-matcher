"""
GET /api/health: "is everything this app needs actually working?"

Checks that Ollama is reachable AND that every model named in .env is installed.
The frontend admin page will show this, and it's the first thing to check when something breaks.
"""
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from app.api.deps import get_ollama
from app.config import Settings, get_settings
from app.llm.ollama_client import OllamaClient, OllamaError, normalize_model_name

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health")
async def health(
    ollama: OllamaClient = Depends(get_ollama),
    settings: Settings = Depends(get_settings),
):
    base = {"app": settings.app_name, "environment": settings.environment}

    try:
        version = await ollama.version()
        installed = {normalize_model_name(m) for m in await ollama.list_models()}
    except OllamaError as exc:
        # 503 Service Unavailable: our app is up, but a dependency isn't.
        return JSONResponse(
            status_code=503,
            content={**base, "status": "error", "ollama": {"reachable": False, "error": str(exc)}},
        )

    required = {
        "embed_model": settings.embed_model,
        "fast_llm_model": settings.fast_llm_model,
        "quality_llm_model": settings.quality_llm_model,
    }
    models = {
        role: {"name": name, "installed": normalize_model_name(name) in installed}
        for role, name in required.items()
    }
    all_ok = all(m["installed"] for m in models.values())

    return {
        **base,
        "status": "ok" if all_ok else "degraded",  # degraded = reachable, but a model is missing
        "ollama": {"reachable": True, "version": version, "models": models},
    }