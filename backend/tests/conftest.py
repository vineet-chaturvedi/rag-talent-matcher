"""
Shared test fixtures.

The tests never read backend/.env: every Settings object is built here with explicit values, so a developer's
own .env (keys, models, database) can't change a result or leak into a test.
"""
import json
import os
import socket
import tempfile
import threading
from pathlib import Path

import pytest

# The app's database, vector store and files: a throwaway place for this test run, set BEFORE any app module
# is imported (they create the engine on import). The same tests run on both databases:
#   python -m pytest                                                        SQLite + ChromaDB (temporary files)
#   TEST_DATABASE_URL=postgresql+asyncpg://u:p@localhost/rag_test python -m pytest     PostgreSQL + pgvector
# The PostgreSQL database is EMPTIED at the start (its public schema is dropped): never point it at real data.
_TMP = Path(tempfile.mkdtemp(prefix="rag-tests-"))
TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL") or f"sqlite+aiosqlite:///{(_TMP / 'test.db').as_posix()}"
os.environ.update(DATABASE_URL=TEST_DATABASE_URL, CHROMA_DIR=str(_TMP / "chroma"), UPLOAD_DIR=str(_TMP / "uploads"),
                  ENVIRONMENT="development", DB_AUTO_MIGRATE="true", VECTOR_STORE="auto", WORKER_ENABLED="false",
                  EMBED_DIMENSIONS="", EMBED_MODEL="nomic-embed-text", STORAGE_BACKEND="local", QUEUE_BACKEND="local")

from app.config import Settings  # noqa: E402

# Never read backend/.env in tests: the developer's own settings (a cloud queue, a reranker, other models)
# must not change a result. Only the defaults, the variables above, and each test's own values count.
Settings.model_config["env_file"] = None


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def make_settings(**values) -> Settings:
    """Settings from defaults + values only (never from .env or the environment's model settings)."""
    return Settings(_env_file=None, **values)


@pytest.fixture(scope="session")
def cloud_url() -> str:
    """The Bedrock / Vertex AI stand-in (tests/fakes/cloud_models.py), on real HTTP, for the whole session."""
    import uvicorn

    from tests.fakes.cloud_models import make_app, wait_until_up

    port = free_port()
    server = uvicorn.Server(uvicorn.Config(make_app(), host="127.0.0.1", port=port, log_level="warning"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    wait_until_up(port)
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    thread.join(timeout=5)


@pytest.fixture
def aws_env(monkeypatch):
    """Fake AWS credentials, so boto3 signs requests (the stand-in checks the signature header exists)."""
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "AKIATESTTESTTEST")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "test-secret")
    monkeypatch.delenv("AWS_PROFILE", raising=False)
    monkeypatch.delenv("AWS_BEARER_TOKEN_BEDROCK", raising=False)


@pytest.fixture
def google_env(monkeypatch, tmp_path, cloud_url):
    """A real service-account key file whose token endpoint is the stand-in: google-auth signs a JWT and
    exchanges it for an access token exactly as it does against Google."""
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                            serialization.NoEncryption()).decode()
    path = tmp_path / "service-account.json"
    path.write_text(json.dumps({
        "type": "service_account", "project_id": "adc-project", "private_key_id": "k1", "private_key": pem,
        "client_email": "rag-matcher@adc-project.iam.gserviceaccount.com", "client_id": "1",
        "token_uri": f"{cloud_url}/token"}))
    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", str(path))
    monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)
    return path


@pytest.fixture(scope="session")
async def database():
    """The test database, empty and migrated to the latest revision, once per run."""
    from sqlalchemy import text

    from app.db.session import IS_POSTGRES, engine, init_db
    if IS_POSTGRES:
        async with engine.begin() as conn:
            await conn.execute(text("DROP SCHEMA public CASCADE"))
            await conn.execute(text("CREATE SCHEMA public"))
    await init_db()
    from app.rag.keyword_index import ensure_keyword_index
    await ensure_keyword_index()          # as at app startup
    yield engine
    await engine.dispose()
