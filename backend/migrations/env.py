"""
Alembic's entry point: how migrations reach the database.

Two ways in:
  1. The command line (`alembic upgrade head`): opens its own connection from DATABASE_URL (backend/.env).
  2. The app at startup (app/db/session.py: init_db, when DB_AUTO_MIGRATE=true): passes its open connection in
     config.attributes["connection"], so the same engine and settings are used.

On PostgreSQL every migration run first takes a transaction-scoped advisory lock: when several app replicas
start at once, one migrates and the others wait, then find nothing left to do.
"""
import asyncio

from alembic import context
from sqlalchemy import Connection, pool, text
from sqlalchemy.ext.asyncio import async_engine_from_config

import app.db.models  # noqa: F401  (registers every table on Base.metadata)
from app.config import get_settings
from app.db.base import Base
from app.db.unmanaged import include_object

config = context.config
target_metadata = Base.metadata
MIGRATION_LOCK_ID = 726_091_405          # any constant; shared by every replica of this app


def _configure(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        include_object=include_object,
        compare_type=True,
        render_as_batch=connection.dialect.name == "sqlite",   # SQLite can't ALTER most things: copy-and-move
    )


def do_run_migrations(connection: Connection) -> None:
    _configure(connection)
    with context.begin_transaction():
        if connection.dialect.name == "postgresql":
            connection.execute(text("SELECT pg_advisory_xact_lock(:id)"), {"id": MIGRATION_LOCK_ID})
        context.run_migrations()


async def run_async_migrations() -> None:
    section = config.get_section(config.config_ini_section, {})
    section["sqlalchemy.url"] = get_settings().database_url
    engine = async_engine_from_config(section, prefix="sqlalchemy.", poolclass=pool.NullPool)
    async with engine.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await engine.dispose()


def run_migrations_offline() -> None:
    """`alembic upgrade head --sql`: print the SQL instead of running it (for a DBA to review)."""
    context.configure(url=get_settings().database_url, target_metadata=target_metadata,
                      include_object=include_object, literal_binds=True, dialect_opts={"paramstyle": "named"})
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
elif (connection := config.attributes.get("connection")) is not None:
    do_run_migrations(connection)
else:
    if config.config_file_name:          # the command line: show "Running upgrade ..." lines
        from logging.config import fileConfig
        fileConfig(config.config_file_name, disable_existing_loggers=False)
    asyncio.run(run_async_migrations())
