"""
Entry point. Run with:   uvicorn app.main:app --reload --port 8010
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import dev, employees, health, resumes
from app.config import get_settings
from app.db.session import engine, init_db
from app.ingestion.worker import IngestionWorker
from app.llm.ollama_client import OllamaClient

settings = get_settings()

logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)s %(levelname)-7s [%(name)s] %(message)s",
)
logger = logging.getLogger("app")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ---- startup ----
    await init_db()
    logger.info("Database ready (%s)", settings.database_url)
    app.state.ollama = OllamaClient(settings.ollama_base_url, settings.ollama_timeout_seconds)

    app.state.worker = None
    if settings.worker_enabled:
        app.state.worker = IngestionWorker(settings)
        app.state.worker.start()

    logger.info("Started %s (%s) | Ollama at %s", settings.app_name, settings.environment, settings.ollama_base_url)
    yield
    # ---- shutdown ----
    if app.state.worker is not None:
        await app.state.worker.stop()
    await app.state.ollama.close()
    await engine.dispose()
    logger.info("Shutdown complete")


app = FastAPI(
    title=settings.app_name,
    version="0.3.0",
    description="RAG system that matches employees to internal project roles using local LLMs (Ollama).",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(employees.router)
app.include_router(resumes.router)
if settings.is_development:
    app.include_router(dev.router)


@app.get("/", tags=["root"])
async def root():
    return {"message": f"{settings.app_name} API is running", "docs": "/docs", "health": "/api/health"}