"""
Entry point. Run with:   uvicorn app.main:app --reload --port 8000
   app.main -> the file app/main.py      :app -> the FastAPI object named `app` inside it
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import dev, health
from app.config import get_settings
from app.llm.ollama_client import OllamaClient

settings = get_settings()

logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)s %(levelname)-7s [%(name)s] %(message)s",
)
logger = logging.getLogger("app")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ---- runs ONCE at startup ----
    app.state.ollama = OllamaClient(settings.ollama_base_url, settings.ollama_timeout_seconds)
    logger.info("Started %s (%s) | Ollama at %s", settings.app_name, settings.environment, settings.ollama_base_url)
    yield  # <- the app serves requests while paused here
    # ---- runs ONCE at shutdown ----
    await app.state.ollama.close()
    logger.info("Shutdown complete")


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="RAG system that matches candidates to jobs using local LLMs (Ollama).",
    lifespan=lifespan,
)

# Allow the Next.js dev server (localhost:3000) to call this API from the browser.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers group related endpoints; each file in app/api/ contributes one.
app.include_router(health.router)
if settings.is_development:
    app.include_router(dev.router)


@app.get("/", tags=["root"])
async def root():
    return {"message": f"{settings.app_name} API is running", "docs": "/docs", "health": "/api/health"}