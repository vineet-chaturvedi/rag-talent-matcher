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


# Columns added to EXISTING tables after they were first created. create_all() only creates missing tables,
# so these are added with ALTER TABLE when absent. A stop-gap until real migrations (Alembic, Step 15).
ADDED_COLUMNS: list[tuple[str, str, str]] = [
    ("resume_skills", "uses", "INTEGER DEFAULT 0"),      # doc 18 extraction fix
    ("resume_skills", "source", "VARCHAR(20)"),
    ("resume_skills", "years_basis", "VARCHAR(20)"),    # evidence ladder (doc 09, 13.6)
    ("resume_skills", "level", "VARCHAR(10)"),
    ("resume_chunks", "meta", "JSON"),                  # chunk metadata: entry, role, technologies
]


def _add_missing_columns(sync_conn) -> None:
    from sqlalchemy import inspect, text

    inspector = inspect(sync_conn)
    for table, column, ddl in ADDED_COLUMNS:
        if table in inspector.get_table_names() and column not in {c["name"] for c in inspector.get_columns(table)}:
            sync_conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}"))


async def init_db() -> None:
    """Create any tables that don't exist yet, and add the few columns listed in ADDED_COLUMNS."""
    import app.db.models  # noqa: F401  (registers all models on Base.metadata)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_add_missing_columns)