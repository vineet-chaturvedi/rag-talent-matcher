"""
Move everything from SQLite + ChromaDB to PostgreSQL + pgvector (doc 21), without re-running any model.

    python -m scripts.migrate_to_postgres --target postgresql+asyncpg://user:password@host:5432/rag
    python -m scripts.migrate_to_postgres --target ... --source sqlite+aiosqlite:///./data/app.db --chroma ./data/chroma

What it does, in order:
  1. brings the target to the latest migration (an EMPTY database; it refuses one that already has data)
  2. copies every table in foreign-key order, keeping the ids, in batches, then moves each id sequence past
     the highest id (so new rows don't collide)
  3. copies the vectors of every ChromaDB collection into pgvector (same vectors, same chunk ids)
  4. compares the row counts of every table, and the vector counts

Then set DATABASE_URL to the target in backend/.env (VECTOR_STORE=auto picks pgvector) and restart. Resume
files are not touched (they stay where UPLOAD_DIR / the storage backend keeps them). The source is only read.
"""
import argparse
import asyncio
import logging
import sys
from collections import defaultdict

from sqlalchemy import func, inspect, select, text
from sqlalchemy.ext.asyncio import create_async_engine

logger = logging.getLogger("migrate_to_postgres")
BATCH = 500


async def _migrate_target(engine) -> None:
    from app.db.session import migrate

    await migrate(engine)


async def copy_tables(source, target, batch: int = BATCH) -> dict[str, int]:
    import app.db.models  # noqa: F401
    from app.db.base import Base

    copied: dict[str, int] = {}
    async with source.connect() as src, target.begin() as dst:
        source_tables = set(await src.run_sync(lambda c: inspect(c).get_table_names()))
        for table in Base.metadata.sorted_tables:             # parents before children (foreign keys)
            if table.name not in source_tables:
                copied[table.name] = 0
                continue
            source_columns = set(await src.run_sync(lambda c, n=table.name: {col["name"] for col in
                                                                             inspect(c).get_columns(n)}))
            columns = [c for c in table.columns if c.name in source_columns]
            total = 0
            result = await src.stream(select(*columns))
            async for rows in result.partitions(batch):
                await dst.execute(table.insert(), [dict(r._mapping) for r in rows])
                total += len(rows)
            copied[table.name] = total
            logger.info("%-22s %6d rows", table.name, total)
        for table in Base.metadata.sorted_tables:
            pk = list(table.primary_key.columns)
            if len(pk) == 1 and pk[0].autoincrement is not False and pk[0].type.python_type is int:
                await dst.execute(text(
                    f"SELECT setval(pg_get_serial_sequence('{table.name}', '{pk[0].name}'), "
                    f"coalesce(max({pk[0].name}), 1), max({pk[0].name}) IS NOT NULL) FROM {table.name}"))
    return copied


async def copy_vectors(chroma_dir: str, target, page: int = 1000) -> dict[str, int]:
    import chromadb

    from app.rag.vector_store import PgVectorStore

    client = chromadb.PersistentClient(path=chroma_dir, settings=chromadb.Settings(anonymized_telemetry=False))
    async with target.connect() as conn:
        resumes = {r for (r,) in await conn.execute(text("SELECT id FROM resumes"))}
    copied: dict[str, int] = {}
    for collection in client.list_collections():
        col = client.get_collection(collection.name if hasattr(collection, "name") else collection)
        by_resume: dict[int, list] = defaultdict(list)
        offset = 0
        while True:
            got = await asyncio.to_thread(col.get, include=["embeddings", "documents", "metadatas"],
                                          limit=page, offset=offset)
            if not got["ids"]:
                break
            for cid, vec, doc, meta in zip(got["ids"], got["embeddings"], got["documents"], got["metadatas"]):
                if int(meta["resume_id"]) in resumes:                  # skip vectors of deleted resumes
                    by_resume[int(meta["resume_id"])].append((cid, [float(x) for x in vec], doc, meta))
            offset += len(got["ids"])
        store = PgVectorStore(col.name, target)
        for resume_id, items in by_resume.items():
            await store.replace_resume(resume_id, [i[0] for i in items], [i[1] for i in items],
                                       [i[2] for i in items], [i[3] for i in items])
        copied[col.name] = sum(len(v) for v in by_resume.values())
        logger.info("vectors %-40s %6d (collection %s)", col.name, copied[col.name], store.table)
    return copied


async def verify(source, target, copied_vectors: dict[str, int]) -> bool:
    import app.db.models  # noqa: F401
    from app.db.base import Base
    from app.rag.vector_store import PgVectorStore

    ok = True
    async with source.connect() as src, target.connect() as dst:
        source_tables = set(await src.run_sync(lambda c: inspect(c).get_table_names()))
        for table in Base.metadata.sorted_tables:
            if table.name not in source_tables:
                continue
            a = (await src.execute(select(func.count()).select_from(table))).scalar_one()
            b = (await dst.execute(select(func.count()).select_from(table))).scalar_one()
            if a != b:
                ok = False
                logger.error("%s: %d rows in the source, %d in the target", table.name, a, b)
    for name, n in copied_vectors.items():
        if (got := await PgVectorStore(name, target).count()) != n:
            ok = False
            logger.error("vectors %s: %d copied, %d found", name, n, got)
    return ok


async def main(argv: list[str] | None = None) -> int:
    from app.config import get_settings

    settings = get_settings()
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--target", required=True, help="postgresql+asyncpg://user:password@host:5432/db")
    parser.add_argument("--source", default=settings.database_url, help="default: DATABASE_URL in .env")
    parser.add_argument("--chroma", default=settings.chroma_dir, help="default: CHROMA_DIR in .env")
    parser.add_argument("--skip-vectors", action="store_true", help="copy only the tables (re-embed later)")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    logging.getLogger("alembic").setLevel(logging.WARNING)

    if not args.target.startswith("postgresql"):
        parser.error("--target must be a postgresql+asyncpg:// URL")
    source = create_async_engine(args.source)
    target = create_async_engine(args.target, connect_args={"server_settings": {"timezone": "UTC"}})
    try:
        await _migrate_target(target)
        async with target.connect() as conn:
            if (await conn.execute(text("SELECT count(*) FROM employees"))).scalar_one():
                logger.error("The target already has data: use an empty database (nothing was copied).")
                return 2
        copied = await copy_tables(source, target)
        vectors = {} if args.skip_vectors else await copy_vectors(args.chroma, target)
        if not await verify(source, target, vectors):
            logger.error("Counts differ: see above. The target is incomplete; empty it and run again.")
            return 1
        logger.info("Done: %d rows in %d tables, %d vectors. Now set DATABASE_URL=%s in backend/.env.",
                    sum(copied.values()), sum(1 for n in copied.values() if n), sum(vectors.values()),
                    target.url.render_as_string(hide_password=True))
        return 0
    finally:
        await source.dispose()
        await target.dispose()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
