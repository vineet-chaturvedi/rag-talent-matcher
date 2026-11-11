"""
Database connection setup: the engine, the session factory, and bringing the schema up to date (migrations).

Two databases are supported with the same code (only DATABASE_URL changes):
  sqlite+aiosqlite:///./data/app.db                       one machine, no server: development and small setups
  postgresql+asyncpg://user:password@host:5432/dbname     production: RDS / Aurora, Cloud SQL, Azure Database
                                                          for PostgreSQL, or your own server (with pgvector)
"""
import logging
from pathlib import Path

from sqlalchemy import event, inspect, make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()
DIALECT = make_url(settings.database_url).get_backend_name()     # "sqlite" | "postgresql"
IS_SQLITE = DIALECT == "sqlite"
IS_POSTGRES = DIALECT == "postgresql"
BASELINE_REVISION = "0001"          # the schema of Steps 3-14 (migrations/versions/..._0001_baseline.py)


def _ensure_sqlite_folder(url: str) -> None:
    """SQLite creates the .db file automatically, but NOT its folder. Create data/ if missing."""
    if IS_SQLITE and ":///" in url:
        Path(url.split(":///", 1)[1]).parent.mkdir(parents=True, exist_ok=True)


def _engine_options() -> dict:
    if IS_POSTGRES:
        return {
            "pool_size": settings.db_pool_size,          # connections kept open per process
            "max_overflow": settings.db_max_overflow,    # extra connections under load, closed afterwards
            "pool_timeout": settings.db_pool_timeout_seconds,
            "pool_recycle": 1800,                        # renew connections before proxies / failovers drop them
            "pool_pre_ping": True,                       # a dead connection (DB restart, failover) is replaced
            "connect_args": {"server_settings": {
                # Times are stored as naive UTC everywhere. now() must be UTC too, whatever the server's zone.
                "timezone": "UTC",
                "application_name": settings.app_name[:63],   # visible in pg_stat_activity
                **({"statement_timeout": str(settings.db_statement_timeout_ms)}
                   if settings.db_statement_timeout_ms else {}),
            }},
        }
    return {}


_ensure_sqlite_folder(settings.database_url)

# The engine owns the connection pool. One per process.
engine = create_async_engine(settings.database_url, echo=settings.db_echo, **_engine_options())


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


# --------------------------------------------------------------------------- schema: Alembic migrations
# Columns added to tables BEFORE migrations existed (Steps 13b-14), with ALTER TABLE. A database created by
# an older version of the app gets them, then is stamped at the baseline revision (see _migrate).
LEGACY_ADDED_COLUMNS: list[tuple[str, str, str]] = [
    ("resume_skills", "uses", "INTEGER DEFAULT 0"),
    ("resume_skills", "source", "VARCHAR(20)"),
    ("resume_skills", "years_basis", "VARCHAR(20)"),
    ("resume_skills", "level", "VARCHAR(10)"),
    ("resume_chunks", "meta", "JSON"),
]


def alembic_config():
    from alembic.config import Config

    backend = Path(__file__).resolve().parents[2]
    config = Config(str(backend / "alembic.ini"))
    config.set_main_option("script_location", str(backend / "migrations"))
    return config


def _legacy_fixups(sync_conn) -> None:
    from sqlalchemy import text

    inspector = inspect(sync_conn)
    for table, column, ddl in LEGACY_ADDED_COLUMNS:
        if table in inspector.get_table_names() and column not in {c["name"] for c in inspector.get_columns(table)}:
            sync_conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}"))


def _migrate(sync_conn, revision: str = "head") -> None:
    from alembic import command

    config = alembic_config()
    config.attributes["connection"] = sync_conn
    tables = set(inspect(sync_conn).get_table_names())
    if "alembic_version" not in tables and "resumes" in tables:
        # Created by the app before Step 15 (tables made directly from the models): bring it to the baseline
        # and record that, instead of creating the tables again.
        logger.warning("Database from before migrations: adding Step 13b/14 columns and stamping revision %s",
                       BASELINE_REVISION)
        _legacy_fixups(sync_conn)
        command.stamp(config, BASELINE_REVISION)
    command.upgrade(config, revision)


async def migrate(target_engine, revision: str = "head", downgrade: bool = False) -> None:
    """
    Run the migrations on this engine (the app's at startup; another one for scripts and tests).

    SQLite: foreign keys are switched OFF while migrations run. Some schema changes make SQLite rebuild a table
    (copy, drop the old one, rename), and dropping a parent table with foreign keys ON deletes every child row
    through ON DELETE CASCADE: rebuilding `resumes` would wipe all chunks, skills and match results. Alembic
    requires this for SQLite; afterwards the integrity of every foreign key is checked, then they're back ON.
    (PRAGMA foreign_keys only works outside a transaction, so it is the first statement on the connection.)
    """
    from sqlalchemy import text

    sqlite = target_engine.dialect.name == "sqlite"
    async with target_engine.connect() as conn:
        if sqlite:
            await conn.execute(text("PRAGMA foreign_keys=OFF"))
        try:
            if downgrade:
                await conn.run_sync(_downgrade, revision)
            else:
                await conn.run_sync(_migrate, revision)
            await conn.commit()
            if sqlite:
                broken = (await conn.execute(text("PRAGMA foreign_key_check"))).all()
                if broken:
                    raise RuntimeError(f"A migration left {len(broken)} rows with broken foreign keys, e.g. {broken[:3]}")
        finally:
            if sqlite:
                await conn.execute(text("PRAGMA foreign_keys=ON"))


def _downgrade(sync_conn, revision: str) -> None:
    from alembic import command

    config = alembic_config()
    config.attributes["connection"] = sync_conn
    command.downgrade(config, revision)


def _pending(sync_conn) -> tuple[str | None, str]:
    from alembic.runtime.migration import MigrationContext
    from alembic.script import ScriptDirectory

    current = MigrationContext.configure(sync_conn).get_current_revision()
    head = ScriptDirectory.from_config(alembic_config()).get_current_head()
    return current, head


async def init_db() -> None:
    """
    Bring the schema up to date. DB_AUTO_MIGRATE=true (default): run the migrations now. In production with
    several replicas, prefer false and run `alembic upgrade head` once per release (CI/CD step or a one-off
    task); the app then only checks that the database is at the latest revision and refuses to start if not.
    """
    import app.db.models  # noqa: F401  (registers all models on Base.metadata)

    if settings.db_auto_migrate:
        await migrate(engine)
        return
    async with engine.connect() as conn:
        current, head = await conn.run_sync(_pending)
    if current != head:
        raise RuntimeError(f"The database is at migration {current or '(none)'}, the code needs {head}. "
                           "Run `alembic upgrade head` (from backend/) first, or set DB_AUTO_MIGRATE=true.")
