"""
Keyword search over resume chunks: the database's own full-text search.

  SQLite      FTS5, a search engine built into SQLite, ranked with BM25. One row per chunk in a "virtual table":
                  chunks_fts(chunk_id, resume_id, employee_id, text)
              Only `text` is searchable; the ids are stored alongside (UNINDEXED) so a hit can be traced back.
  PostgreSQL  a generated tsvector column on resume_chunks with a GIN index (migration 0001), ranked with
              BM25 computed in SQL (below). Postgres keeps the column in sync itself: nothing to write or rebuild.
              Both use the 'simple' word rules (no stemming), so they find the same chunks and rank them alike;
              retrieval uses only the ORDER (RRF), never the raw score.

Why keyword search next to vectors? Embeddings blur exact, rare terms ("CKA", "SAP FICO", "k8s").
BM25 rewards exactly those: a rare word that matches counts a lot.

Like ChromaDB, this index is derived from the resume_chunks table (the source of truth)
and can always be rebuilt from it.
"""
import logging
from dataclasses import dataclass

from sqlalchemy import bindparam, text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession

from app.db.session import IS_POSTGRES, IS_SQLITE, engine

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
    bm25: float          # BM25 as a NEGATIVE number: more negative = better match (both databases)
    snippet: str         # the matching part of the chunk, with [matched] words in brackets


# --------------------------------------------------------------------------- setup
async def ensure_keyword_index() -> None:
    """Create the FTS table if needed, and rebuild it if it is out of sync with resume_chunks."""
    if IS_POSTGRES:
        async with engine.connect() as conn:
            ok = (await conn.execute(text(
                "SELECT count(*) FROM information_schema.columns "
                "WHERE table_name = 'resume_chunks' AND column_name = 'search_vector'"))).scalar_one()
        if not ok:
            raise RuntimeError("resume_chunks.search_vector is missing: run the migrations (alembic upgrade head)")
        logger.info("Keyword index ready (PostgreSQL full-text search)")
        return
    if not IS_SQLITE:
        logger.warning("Keyword search supports SQLite and PostgreSQL; skipped for this database")
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
    """Best-matching chunks among the given resumes, best first."""
    if not terms or not resume_ids:
        return []
    if IS_POSTGRES:
        return await _postgres_search(session, terms, resume_ids, limit)
    if not IS_SQLITE:
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


def postgres_terms(terms: list[str]) -> list[str]:
    """Distinct, non-empty, lower-case terms (each becomes one phrase of the query)."""
    out: list[str] = []
    for term in terms:
        cleaned = " ".join(term.strip().lower().split())
        if cleaned and cleaned not in out:
            out.append(cleaned)
    return out


# PostgreSQL: text -> words exactly as the search_vector column does it (migration 0001)
WORDS_SQL = "regexp_replace({}, '[^[:alnum:]]+', ' ', 'g')"
# BM25's usual constants, as in SQLite FTS5: k1 = how fast repeated evidence saturates, b = length normalisation
BM25_K1, BM25_B = 1.2, 0.75


async def _postgres_search(session: AsyncSession, terms: list[str], resume_ids: list[int],
                           limit: int) -> list[KeywordHit]:
    """
    BM25 computed in SQL with SQLite FTS5's exact formula, so both databases rank alike:
        score(chunk) = sum over terms of  idf * tf * (k1 + 1) / (tf + k1 * (1 - b + b * len / avglen))
        idf          = ln((N - df + 0.5) / (df + 0.5)), at least 1e-6     N = all chunks, df = chunks with the term
        tf           = how often the term occurs in the chunk (a phrase: its least frequent word)
        len, avglen  = words in the chunk, and on average over all chunks
    so a rare term ("Terraform") counts more than a common one, repeated evidence counts with diminishing
    returns, and long chunks don't win by size. Each term is a phrase ("node.js", "machine learning"). The GIN
    index finds the matching chunks; ts_headline marks the matched words with [ ] like FTS5's snippet() and
    runs only for the rows that survive the LIMIT.
    """
    phrases = postgres_terms(terms)
    if not phrases:
        return []
    words = [WORDS_SQL.format(f":t{i}") for i in range(len(phrases))]
    values = ", ".join(f"({i}, phraseto_tsquery('simple', {w}), tsvector_to_array(to_tsvector('simple', {w})))"
                       for i, w in enumerate(words))
    any_term = " || ".join(f"phraseto_tsquery('simple', {w})" for w in words)
    length = "(SELECT coalesce(sum(cardinality(u.positions)), 0) FROM unnest({}.search_vector) u)"
    stmt = text(f"""
        WITH terms(i, q, words) AS (VALUES {values}),
        anyterm AS (SELECT ({any_term}) AS q),
        stats AS (SELECT count(*) AS n, coalesce(avg({length.format("c")}), 1) AS avglen FROM resume_chunks c),
        df AS (SELECT t.i, count(c.id) AS df
               FROM terms t LEFT JOIN resume_chunks c ON c.search_vector @@ t.q GROUP BY t.i),
        hits AS (SELECT c.id, c.resume_id, c.text, c.search_vector, {length.format("c")} AS len
                 FROM resume_chunks c CROSS JOIN anyterm
                 WHERE c.search_vector @@ anyterm.q AND c.resume_id IN :ids),
        matched AS (SELECT h.id, t.i,
                           (SELECT coalesce(min(cardinality(u.positions)), 1) FROM unnest(h.search_vector) u
                            WHERE u.lexeme = ANY(t.words)) AS tf
                    FROM hits h JOIN terms t ON h.search_vector @@ t.q),
        scored AS (
            SELECT h.id, h.resume_id, h.text,
                   sum(greatest(ln((s.n - df.df + 0.5) / (df.df + 0.5)), 1e-6)
                       * m.tf * {BM25_K1 + 1}
                       / (m.tf + {BM25_K1} * (1 - {BM25_B} + {BM25_B} * h.len / greatest(s.avglen, 1)))) AS score
            FROM hits h CROSS JOIN stats s JOIN matched m ON m.id = h.id JOIN df ON df.i = m.i
            GROUP BY h.id, h.resume_id, h.text
        )
        SELECT sc.id AS chunk_id, sc.resume_id, r.employee_id, -sc.score AS score,
               ts_headline('simple', sc.text, anyterm.q,
                           'StartSel=[, StopSel=], MaxWords=16, MinWords=6, MaxFragments=2, FragmentDelimiter=" … "')
                   AS snip
        FROM scored sc JOIN resumes r ON r.id = sc.resume_id CROSS JOIN anyterm
        ORDER BY sc.score DESC, sc.id
        LIMIT :limit
    """).bindparams(bindparam("ids", expanding=True))
    params = {f"t{i}": p for i, p in enumerate(phrases)} | {"ids": resume_ids, "limit": limit}
    rows = (await session.execute(stmt, params)).all()
    return [KeywordHit(r.chunk_id, int(r.resume_id), int(r.employee_id), float(r.score), r.snip) for r in rows]
