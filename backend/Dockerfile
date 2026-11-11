# The backend image (Step 15e, doc 21): ONE image for the API, the background worker and migrations.
#   docker build -t rag-backend ./backend
#   API        (default)  uvicorn on port 8010
#   worker     docker run rag-backend python -m app.worker
#   migrations docker run rag-backend alembic upgrade head
# Configuration comes only from environment variables (the orchestrator, a secret store, docker compose):
# no .env file is copied into the image, so no secret is ever baked in.

ARG PYTHON_IMAGE=python:3.13-slim

# ----------------------------------------------------------------------------- build: dependencies only
FROM ${PYTHON_IMAGE} AS build
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /build
COPY requirements.txt requirements-cloud.txt ./
# ChromaDB is only needed with SQLite (one machine); images use PostgreSQL + pgvector. WITH_CHROMA=true keeps it.
ARG WITH_CHROMA=false
RUN --mount=type=cache,target=/root/.cache/pip \
    python -m venv /opt/venv \
 && if [ "$WITH_CHROMA" = "true" ]; then cp requirements.txt deps.txt; else grep -v '^chromadb' requirements.txt > deps.txt; fi \
 && /opt/venv/bin/pip install -r deps.txt -r requirements-cloud.txt

# ----------------------------------------------------------------------------- runtime: small, non-root
FROM ${PYTHON_IMAGE} AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH=/opt/venv/bin:$PATH \
    ENVIRONMENT=production
RUN useradd --system --uid 10001 --no-create-home --home-dir /app --shell /usr/sbin/nologin app
WORKDIR /app
COPY --from=build /opt/venv /opt/venv
COPY alembic.ini ./
COPY migrations ./migrations
COPY app ./app
COPY scripts ./scripts
COPY evaluation ./evaluation
# The code belongs to root and is read-only for the app user (whatever the permissions on the build machine);
# data/ (local uploads, SQLite, ChromaDB, downloaded reranker models) is the only writable place. Its folders
# exist in the image owned by the app user, so a new Docker volume mounted on one of them gets that owner too.
RUN chmod -R a+rX,go-w /app \
 && mkdir -p /app/data/uploads /app/data/chroma /app/data/models \
 && chown -R app:app /app/data
USER app
EXPOSE 8010
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
  CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8010/api/health/live', timeout=4)"]
# --proxy-headers: behind a load balancer (ALB, Cloud Run, Front Door) trust X-Forwarded-For/Proto from it.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8010", "--proxy-headers", "--forwarded-allow-ips", "*", "--no-server-header"]
