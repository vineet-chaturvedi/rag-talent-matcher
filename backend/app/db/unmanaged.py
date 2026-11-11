"""
Database objects that exist on purpose WITHOUT an ORM model, so Alembic's autogenerate must neither create
nor drop them (used by migrations/env.py and the schema drift test).

  chunks_fts*                     SQLite FTS5 keyword index and its shadow tables (app/rag/keyword_index.py)
  emb_*, vector_collections       pgvector collections and their registry (app/rag/vector_store.py)
  resume_chunks.search_vector     PostgreSQL generated full-text column + its GIN index (migration 0001)
"""
_TABLE_PREFIXES = ("chunks_fts", "emb_")
_TABLES = {"vector_collections"}
_COLUMNS = {("resume_chunks", "search_vector")}
_INDEX_PREFIXES = ("ix_resume_chunks_search_vector",)


def include_object(obj, name, type_, reflected, compare_to) -> bool:
    if type_ == "table":
        return not (name in _TABLES or name.startswith(_TABLE_PREFIXES))
    if type_ == "column":
        return (obj.table.name, name) not in _COLUMNS
    if type_ == "index":
        return not (name or "").startswith(_INDEX_PREFIXES)
    return True
