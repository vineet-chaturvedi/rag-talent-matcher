"""
Database connection setup: the engine, the session factory, SQLite tuning, and table creation.
"""
from pathlib import Path

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings
from app.db.base import Base

settings = get_settings()
IS_SQLITE = settings.database_url.startswith("sqlite")


def _ensure_sqlite_folder(url: str) -> None:
    """SQLite creates the .db file automatically, but NOT its folder. Create data/ if missing."""
    if IS_SQLITE and ":///" in url:
        Path(url.split(":///", 1)[1]).parent.mkdir(parents=True, exist_ok=True)


_ensure_sqlite_folder(settings.database_url)

# The engine owns the connection pool. One per application.
engine = create_async_engine(settings.database_url, echo=settings.db_echo)


@event.listens_for(engine.sync_engine, "connect")
def _apply_sqlite_pragmas(dbapi_connection, _connection_record) -> None:
    """Runs on EVERY new connection. PRAGMAs are SQLite's per-connection settings."""
    if not IS_SQLITE:
        return
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")    # off by default in SQLite! Without it CASCADE does nothing
    cursor.execute("PRAGMA journal_mode=WAL")   # readers don't block the writer and vice versa
    cursor.execute("PRAGMA busy_timeout=5000")  # wait up to 5s for a lock instead of failing instantly
    cursor.close()


# A factory that creates sessions. expire_on_commit=False: objects stay readable after commit
# (otherwise accessing employee.name after commit would trigger a new query, which fails in async).
SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def init_db() -> None:
    """Create any tables that don't exist yet. Does NOT alter existing tables (see migrations, Step 15)."""
    import app.db.models  # noqa: F401  (registers all models on Base.metadata)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)