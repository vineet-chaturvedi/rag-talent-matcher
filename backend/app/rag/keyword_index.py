"""
Keyword search: SQLite FTS5 full-text index over resume chunks, ranked with BM25.

FTS5 is a search engine built into SQLite. We keep one row per chunk in a "virtual table":
    chunks_fts(chunk_id, resume_id, employee_id, text)
Only `text` is searchable; the ids are stored alongside (UNINDEXED) so a hit can be traced back.

Why keyword search next to vectors? Embeddings blur exact, rare terms ("CKA", "SAP FICO", "k8s").
BM25 rewards exactly those: a rare word that matches counts a lot.

Like ChromaDB, this index is derived from the resume_chunks table (the source of truth)
and can always be rebuilt from it.
"""
import logging
from dataclasses import dataclass

from sqlalchemy import bindparam, text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession

from app.db.session import IS_SQLITE, engine

logger = logging.getLogger(__name__)

TABLE = "chunks_fts"

_CREATE = f"""
CREATE VIRTUAL TABLE IF NOT EXISTS {TABLE} USING fts5(
    chunk_id UNINDEXED,
    resume_id UNINDEXED,
    employee_id UNINDEXED,
    text,
    tokenize = 'unicode61'
)
"""


@dataclass
class KeywordHit:
    chunk_id: str
    resume_id: int
    employee_id: int
    bm25: float          # SQLite's BM25: MORE NEGATIVE = BETTER match
    snippet: str         # the matching part of the chunk, with [matched] words in brackets


# --------------------------------------------------------------------------- setup
async def ensure_keyword_index() -> None:
    """Create the FTS table if needed, and rebuild it if it is out of sync with resume_chunks."""
    if not IS_SQLITE:
        logger.warning("Keyword index needs SQLite FTS5; skipped for this database")
        return
    async with engine.begin() as conn:
        await conn.execute(text(_CREATE))
        indexed = (await conn.execute(text(f"SELECT count(*) FROM {TABLE}"))).scalar_one()
        chunks = (await conn.execute(text("SELECT count(*) FROM resume_chunks"))).scalar_one()
        if indexed != chunks:
            await _rebuild(conn)
            logger.info("Keyword index rebuilt: %d chunks", chunks)
        else:
            logger.info("Keyword index ready: %d chunks", indexed)


async def _rebuild(conn: AsyncConnection) -> None:
    await conn.execute(text(f"DELETE FROM {TABLE}"))
    await conn.execute(text(f"""
        INSERT INTO {TABLE} (chunk_id, resume_id, employee_id, text)
        SELECT c.id, c.resume_id, r.employee_id, c.text
        FROM resume_chunks c JOIN resumes r ON r.id = c.resume_id
    """))


# --------------------------------------------------------------------------- write (inside the caller's transaction)
async def replace_resume_rows(session: AsyncSession, resume_id: int, employee_id: int,
                              rows: list[tuple[str, str]]) -> None:
    """rows = [(chunk_id, text), ...]. Called in the same transaction as the resume_chunks rows."""
    if not IS_SQLITE:
        return
    await delete_resume_rows(session, resume_id)
    if rows:
        await session.execute(
            text(f"INSERT INTO {TABLE} (chunk_id, resume_id, employee_id, text) VALUES (:c, :r, :e, :t)"),
            [{"c": cid, "r": resume_id, "e": employee_id, "t": body} for cid, body in rows],
        )


async def delete_resume_rows(session: AsyncSession, resume_id: int) -> None:
    if IS_SQLITE:
        await session.execute(text(f"DELETE FROM {TABLE} WHERE resume_id = :r"), {"r": resume_id})


# --------------------------------------------------------------------------- search
def build_match_query(terms: list[str]) -> str:
    """
    Turn search terms into an FTS5 query: every term becomes a quoted phrase, joined by OR.
        ["Kubernetes", "k8s", "Node.js"]  ->  "kubernetes" OR "k8s" OR "node.js"
    Quoting makes FTS treat each term literally (no special syntax) and match multi-word phrases.
    """
    phrases = []
    for term in terms:
        cleaned = term.strip().lower().replace('"', " ")
        if cleaned and f'"{cleaned}"' not in phrases:
            phrases.append(f'"{cleaned}"')
    return " OR ".join(phrases)


async def keyword_search(session: AsyncSession, terms: list[str], resume_ids: list[int],
                         limit: int = 200) -> list[KeywordHit]:
    """Best-matching chunks (BM25) among the given resumes."""
    if not IS_SQLITE or not terms or not resume_ids:
        return []
    query = build_match_query(terms)
    if not query:
        return []
    stmt = text(f"""
        SELECT chunk_id, resume_id, employee_id, bm25({TABLE}) AS score,
               snippet({TABLE}, 3, '[', ']', ' … ', 16) AS snip
        FROM {TABLE}
        WHERE {TABLE} MATCH :q AND resume_id IN :ids
        ORDER BY score
        LIMIT :limit
    """).bindparams(bindparam("ids", expanding=True))
    rows = (await session.execute(stmt, {"q": query, "ids": resume_ids, "limit": limit})).all()
    return [KeywordHit(r.chunk_id, int(r.resume_id), int(r.employee_id), float(r.score), r.snip) for r in rows]
