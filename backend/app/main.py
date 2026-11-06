"""
Entry point. Run with:   uvicorn app.main:app --reload --port 8010
"""
import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import (agent, auth, dev, employees, feedback, health, matching, overview, projects, resumes, search,
                     users)
from app.auth.dependencies import get_current_user, require_admin
from app.config import get_settings
from app.db.session import engine, init_db
from app.services.users import count_users
from app.ingestion.worker import IngestionWorker
from app.llm.router import make_model_client
from app.matching.runner import recover_interrupted_runs
from app.rag.keyword_index import ensure_keyword_index
from app.rag.vector_store import get_vector_store
from app.services.indexing import requeue_for_embedding

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
    # One client for every model of every provider (app/llm/router.py). Named "ollama" for history's sake.
    app.state.ollama = make_model_client(settings)
    if cloud := app.state.ollama.cloud_models_in_use():
        state = "ALLOWED" if settings.allow_cloud_models else "BLOCKED until ALLOW_CLOUD_MODELS=true"
        logger.warning("Cloud models configured (%s): %s. They receive resume text and role descriptions.",
                       state, ", ".join(cloud))
    store = get_vector_store()   # opens (or creates) data/chroma, the collection of the current EMBED_MODEL
    logger.info("Vector store ready (%s, collection %s): %d chunks", settings.chroma_dir,
                settings.vector_collection, store.count())
    logger.info("Models: %s", ", ".join(f"{k}={v}" for k, v in settings.models_in_use.items()))
    if settings.auto_reembed_on_model_change and (
            stale := await requeue_for_embedding(settings.embedding_signature)):
        logger.warning("Embeddings are now made with %s: %d resume(s) were embedded with another model or size "
                       "and are queued for re-embedding (the worker does it in the background).",
                       settings.embedding_signature, stale)
    await ensure_keyword_index()  # SQLite FTS5 table for keyword (BM25) search, rebuilt if out of sync
    if interrupted := await recover_interrupted_runs():
        logger.warning("%d match run(s) were interrupted by the last shutdown and marked failed", interrupted)
    app.state.match_tasks = set()   # background LLM-judge tasks (Step 8)
    if not settings.jwt_secret:
        logger.warning("JWT_SECRET is not set: using a random development secret, so logins end when the "
                       "server restarts. Add JWT_SECRET to .env (see .env.example).")
    settings.jwt_secret_value       # fails fast in production if the secret is missing
    if await count_users() == 0:
        logger.warning("No portal users yet. Create the first admin:  python -m scripts.create_user --role admin")

    app.state.worker = None
    if settings.worker_enabled:
        app.state.worker = IngestionWorker(settings, app.state.ollama)
        app.state.worker.start()

    logger.info("Started %s (%s) | Ollama at %s", settings.app_name, settings.environment, settings.ollama_base_url)
    yield
    # ---- shutdown ----
    for task in list(app.state.match_tasks):   # stop judging; those runs are marked failed
        task.cancel()
    await asyncio.gather(*app.state.match_tasks, return_exceptions=True)
    if app.state.worker is not None:
        await app.state.worker.stop()
    await app.state.ollama.close()
    await engine.dispose()
    logger.info("Shutdown complete")


app = FastAPI(
    title=settings.app_name,
    version="0.10.0",
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

# Public: health check and login. Everything else needs a logged-in user (Step 9);
# admin-only actions (uploads, imports, re-processing, users, dev tools) are checked per endpoint.
signed_in = [Depends(get_current_user)]
app.include_router(health.router)
app.include_router(auth.router)
app.include_router(users.router)                                   # admin only (checked in the router)
app.include_router(overview.router, dependencies=signed_in)
app.include_router(employees.router, dependencies=signed_in)
app.include_router(resumes.router, dependencies=signed_in)
app.include_router(search.router, dependencies=signed_in)
app.include_router(projects.router, dependencies=signed_in)
app.include_router(matching.router, dependencies=signed_in)
app.include_router(agent.router, dependencies=signed_in)
app.include_router(feedback.router, dependencies=signed_in)   # the admin list checks the role itself
if settings.is_development:
    app.include_router(dev.router, dependencies=[Depends(require_admin)])


@app.get("/", tags=["root"])
async def root():
    return {"message": f"{settings.app_name} API is running", "docs": "/docs", "health": "/api/health"}
