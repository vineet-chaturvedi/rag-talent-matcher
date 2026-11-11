"""
The vector database: where chunk vectors live and how the nearest ones are found.

Two interchangeable backends behind one async interface (VECTOR_STORE in .env, "auto" by default):
  chroma     ChromaDB inside our Python process, saved to data/chroma/      (with SQLite: one machine)
  pgvector   PostgreSQL's pgvector extension: vectors in the same database as everything else, so one backup,
             one access policy and transactions with the data       (with PostgreSQL: production, any cloud)

Either way the relational table resume_chunks stays the source of truth: the vectors can always be rebuilt
from it (re-embedding), and a different embedding model or size gets its own collection, never mixed.
"""
import asyncio
import hashlib
import json
import logging
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Protocol

from app.config import get_settings

logger = logging.getLogger(__name__)


@dataclass
class ChunkHit:
    chunk_id: str
    resume_id: int
    employee_id: int
    section: str
    text: str
    similarity: float     # cosine similarity: 1 = same meaning, 0 = unrelated


class VectorStore(Protocol):
    name: str

    async def count(self) -> int: ...

    async def replace_resume(self, resume_id: int, ids: list[str], vectors: list[list[float]],
                             texts: list[str], metadatas: list[dict]) -> None:
        """Remove this resume's old chunks, then add the new ones. Safe to run twice (idempotent)."""

    async def delete_resume(self, resume_id: int) -> None: ...

    async def query(self, vector: list[float], n_results: int,
                    employee_ids: list[int] | None = None) -> list[ChunkHit]:
        """The n nearest chunks, optionally only from these employees."""


# =========================================================================== ChromaDB
class ChromaVectorStore:
    """ChromaDB's API is synchronous: every call runs in a worker thread so the server never blocks."""
    name = "chroma"

    def __init__(self, path: str, collection_name: str):
        import chromadb

        Path(path).mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(
            path=path, settings=chromadb.Settings(anonymized_telemetry=False)  # no usage data sent anywhere
        )
        self._collection = self._client.get_or_create_collection(
            collection_name,
            embedding_function=None,                      # we bring our own vectors, Chroma must not embed
            configuration={"hnsw": {"space": "cosine"}},  # compare vectors by angle
        )

    async def count(self) -> int:
        return await asyncio.to_thread(self._collection.count)

    async def replace_resume(self, resume_id, ids, vectors, texts, metadatas) -> None:
        def run():
            self._collection.delete(where={"resume_id": resume_id})
            if ids:
                self._collection.add(ids=ids, embeddings=vectors, documents=texts, metadatas=metadatas)
        await asyncio.to_thread(run)

    async def delete_resume(self, resume_id: int) -> None:
        await asyncio.to_thread(self._collection.delete, where={"resume_id": resume_id})

    async def query(self, vector, n_results, employee_ids=None) -> list[ChunkHit]:
        where = None
        if employee_ids:
            where = {"employee_id": {"$in": employee_ids}} if len(employee_ids) > 1 else {"employee_id": employee_ids[0]}

        def run():
            total = self._collection.count()
            if total == 0:
                return None
            return self._collection.query(query_embeddings=[vector], n_results=min(n_results, total), where=where,
                                          include=["documents", "metadatas", "distances"])
        result = await asyncio.to_thread(run)
        if result is None:
            return []
        return [
            ChunkHit(chunk_id=cid, resume_id=int(meta["resume_id"]), employee_id=int(meta["employee_id"]),
                     section=str(meta["section"]), text=text,
                     similarity=round(1 - distance, 4))   # Chroma returns cosine DISTANCE = 1 - similarity
            for cid, text, meta, distance in zip(result["ids"][0], result["documents"][0], result["metadatas"][0],
                                                 result["distances"][0])
        ]


# =========================================================================== pgvector
# pgvector's HNSW index handles up to 2,000 dimensions for `vector` and 4,000 for `halfvec` (16-bit floats,
# half the storage; enough precision for search). Bigger vectors (rare) are searched exactly, without an index.
HNSW_MAX_VECTOR, HNSW_MAX_HALFVEC = 2000, 4000


def table_for(collection: str) -> str:
    """A safe, stable table name for a collection (PostgreSQL names: at most 63 characters)."""
    return "emb_" + hashlib.sha1(collection.encode()).hexdigest()[:16]


def _literal(vector: list[float]) -> str:
    return "[" + ",".join(repr(float(x)) for x in vector) + "]"


class PgVectorStore:
    """
    One table per collection (embedding model + size), created on first use with the right vector size:
        emb_<hash>(chunk_id PK, resume_id FK -> resumes ON DELETE CASCADE, employee_id, section, text,
                   metadata jsonb, embedding vector(N) | halfvec(N))
    with an HNSW index (cosine) for fast nearest-neighbour search and b-tree indexes for the filters.
    vector_collections (migration 0001) records which table holds which collection and its size.
    """
    name = "pgvector"

    def __init__(self, collection: str, engine):
        self.collection = collection
        self.table = table_for(collection)
        self._engine = engine
        self._column_type: str | None = None      # "vector" | "halfvec", known once the table exists
        self._lock = asyncio.Lock()

    async def _existing(self, conn) -> tuple[int, str] | None:
        from sqlalchemy import text

        row = (await conn.execute(text("SELECT dimensions, column_type FROM vector_collections WHERE name = :n"),
                                  {"n": self.collection})).first()
        return (int(row.dimensions), row.column_type) if row else None

    async def _ensure_table(self, dimensions: int) -> str:
        """Create the collection's table on first write (concurrency-safe across processes). -> column type."""
        from sqlalchemy import text

        if self._column_type:
            return self._column_type
        async with self._lock, self._engine.begin() as conn:
            await conn.execute(text("SELECT pg_advisory_xact_lock(hashtext(:t))"), {"t": self.table})
            existing = await self._existing(conn)
            if existing:
                if existing[0] != dimensions:
                    raise RuntimeError(f"Collection {self.collection} holds {existing[0]}-dimension vectors, "
                                       f"got {dimensions}: a different model or EMBED_DIMENSIONS needs its own "
                                       "collection (it gets one automatically through the embedding signature).")
                self._column_type = existing[1]
                return self._column_type
            version = (await conn.execute(text(
                "SELECT extversion FROM pg_extension WHERE extname = 'vector'"))).scalar_one_or_none()
            if version is None:
                raise RuntimeError("The pgvector extension is not installed: run the migrations (alembic upgrade head)")
            has_halfvec = tuple(int(p) for p in version.split(".")[:2]) >= (0, 7)
            column = "halfvec" if dimensions > HNSW_MAX_VECTOR and has_halfvec else "vector"
            t = self.table
            await conn.execute(text(f"""
                CREATE TABLE IF NOT EXISTS {t} (
                    chunk_id    varchar(36) PRIMARY KEY,
                    resume_id   integer NOT NULL REFERENCES resumes(id) ON DELETE CASCADE,
                    employee_id integer NOT NULL,
                    section     varchar(30) NOT NULL,
                    text        text NOT NULL,
                    metadata    jsonb NOT NULL DEFAULT '{{}}',
                    embedding   {column}({dimensions}) NOT NULL
                )"""))
            await conn.execute(text(f"CREATE INDEX IF NOT EXISTS {t}_resume_id ON {t} (resume_id)"))
            await conn.execute(text(f"CREATE INDEX IF NOT EXISTS {t}_employee_id ON {t} (employee_id)"))
            if dimensions <= (HNSW_MAX_HALFVEC if column == "halfvec" else HNSW_MAX_VECTOR):
                await conn.execute(text(f"CREATE INDEX IF NOT EXISTS {t}_embedding ON {t} "
                                        f"USING hnsw (embedding {column}_cosine_ops)"))
            else:
                logger.warning("%d-dimension vectors are too large for an HNSW index here: searches will be exact "
                               "(fine for thousands of resumes; set EMBED_DIMENSIONS to shorten them)", dimensions)
            await conn.execute(text(
                "INSERT INTO vector_collections (name, table_name, dimensions, column_type) VALUES (:n, :t, :d, :c)"),
                {"n": self.collection, "t": t, "d": dimensions, "c": column})
            logger.info("pgvector collection %s created as %s (%s(%d))", self.collection, t, column, dimensions)
            self._column_type = column
            return column

    async def _known_type(self) -> str | None:
        if self._column_type:
            return self._column_type
        async with self._engine.connect() as conn:
            existing = await self._existing(conn)
        if existing:
            self._column_type = existing[1]
        return self._column_type

    async def count(self) -> int:
        from sqlalchemy import text

        if not await self._known_type():
            return 0
        async with self._engine.connect() as conn:
            return int((await conn.execute(text(f"SELECT count(*) FROM {self.table}"))).scalar_one())

    async def replace_resume(self, resume_id, ids, vectors, texts, metadatas) -> None:
        from sqlalchemy import text

        if not ids:
            await self.delete_resume(resume_id)
            return
        column = await self._ensure_table(len(vectors[0]))
        rows = [{"id": cid, "r": resume_id, "e": int(meta["employee_id"]), "s": str(meta["section"]), "x": body,
                 "m": json.dumps(meta), "v": _literal(vec)}
                for cid, vec, body, meta in zip(ids, vectors, texts, metadatas)]
        async with self._engine.begin() as conn:      # delete + insert in one transaction: never half-indexed
            await conn.execute(text(f"DELETE FROM {self.table} WHERE resume_id = :r"), {"r": resume_id})
            await conn.execute(text(
                f"INSERT INTO {self.table} (chunk_id, resume_id, employee_id, section, text, metadata, embedding) "
                f"VALUES (:id, :r, :e, :s, :x, CAST(:m AS jsonb), CAST(:v AS {column}))"), rows)

    async def delete_resume(self, resume_id: int) -> None:
        from sqlalchemy import text

        if not await self._known_type():
            return
        async with self._engine.begin() as conn:
            await conn.execute(text(f"DELETE FROM {self.table} WHERE resume_id = :r"), {"r": resume_id})

    async def query(self, vector, n_results, employee_ids=None) -> list[ChunkHit]:
        from sqlalchemy import bindparam, text

        column = await self._known_type()
        if not column or n_results <= 0:
            return []
        select = f"""SELECT chunk_id, resume_id, employee_id, section, text,
                    1 - (embedding <=> CAST(:v AS {column})) AS similarity"""
        order = f"ORDER BY embedding <=> CAST(:v AS {column}), chunk_id LIMIT :n"
        params: dict = {"v": _literal(vector), "n": n_results}
        if employee_ids:
            # Filtered: take these employees' chunks first (b-tree), then sort them exactly. An approximate
            # (HNSW) search with a filter can return fewer than n rows, because it filters AFTER finding neighbours.
            stmt = text(f"""WITH subset AS MATERIALIZED (
                                SELECT * FROM {self.table} WHERE employee_id IN :emps)
                            {select} FROM subset {order}""").bindparams(bindparam("emps", expanding=True))
            params["emps"] = list(employee_ids)
        else:
            stmt = text(f"{select} FROM {self.table} {order}")
        async with self._engine.begin() as conn:
            # Candidate list of the HNSW search: at least twice the results wanted (pgvector's default is 40).
            await conn.execute(text(f"SET LOCAL hnsw.ef_search = {max(40, min(int(n_results) * 2, 1000))}"))
            rows = (await conn.execute(stmt, params)).all()
        return [ChunkHit(chunk_id=r.chunk_id, resume_id=int(r.resume_id), employee_id=int(r.employee_id),
                         section=r.section, text=r.text, similarity=round(float(r.similarity), 4)) for r in rows]


# =========================================================================== which one
def store_kind(settings=None) -> str:
    settings = settings or get_settings()
    if settings.vector_store != "auto":
        return settings.vector_store
    from app.db.session import IS_POSTGRES
    return "pgvector" if IS_POSTGRES else "chroma"


@lru_cache
def get_vector_store() -> VectorStore:
    """
    One shared instance per process. Its collection belongs to the current embedding model and size
    (app/llm/models.py: collection_name), because vectors of different models must never be mixed.
    """
    settings = get_settings()
    if store_kind(settings) == "pgvector":
        from app.db.session import IS_POSTGRES, engine
        if not IS_POSTGRES:
            raise RuntimeError("VECTOR_STORE=pgvector needs a PostgreSQL DATABASE_URL")
        return PgVectorStore(settings.vector_collection, engine)
    return ChromaVectorStore(settings.chroma_dir, settings.vector_collection)
