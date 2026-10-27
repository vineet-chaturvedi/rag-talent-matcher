"""
The vector database: ChromaDB, running inside our Python process and saving to data/chroma/.

ChromaDB stores, for each chunk: an id, its vector, its text, and metadata (resume_id, employee_id, ...).
Given a query vector, it returns the nearest chunks using an HNSW index (see the notes in Step 6).

ChromaDB's Python API is synchronous; callers run it via asyncio.to_thread so the server never blocks.
SQLite (resume_chunks table) remains the source of truth - this store can always be rebuilt from it.
"""
import logging
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import chromadb

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


class VectorStore:
    def __init__(self, path: str, collection_name: str):
        Path(path).mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(
            path=path, settings=chromadb.Settings(anonymized_telemetry=False)  # no usage data sent anywhere
        )
        self._collection = self._client.get_or_create_collection(
            collection_name,
            embedding_function=None,                      # we bring our own vectors (Ollama), Chroma must not embed
            configuration={"hnsw": {"space": "cosine"}},  # compare vectors by angle, like Step 2's similarity
        )

    def count(self) -> int:
        return self._collection.count()

    def replace_resume(self, resume_id: int, ids: list[str], vectors: list[list[float]],
                       texts: list[str], metadatas: list[dict]) -> None:
        """Remove this resume's old chunks, then add the new ones. Safe to run twice (idempotent)."""
        self._collection.delete(where={"resume_id": resume_id})
        if ids:
            self._collection.add(ids=ids, embeddings=vectors, documents=texts, metadatas=metadatas)

    def delete_resume(self, resume_id: int) -> None:
        self._collection.delete(where={"resume_id": resume_id})

    def query(self, vector: list[float], n_results: int, where: dict | None = None) -> list[ChunkHit]:
        total = self.count()
        if total == 0:
            return []
        result = self._collection.query(
            query_embeddings=[vector],
            n_results=min(n_results, total),
            where=where,
            include=["documents", "metadatas", "distances"],
        )
        hits = []
        for chunk_id, text, meta, distance in zip(
            result["ids"][0], result["documents"][0], result["metadatas"][0], result["distances"][0]
        ):
            hits.append(ChunkHit(
                chunk_id=chunk_id, resume_id=int(meta["resume_id"]), employee_id=int(meta["employee_id"]),
                section=str(meta["section"]), text=text,
                similarity=round(1 - distance, 4),   # Chroma returns cosine DISTANCE = 1 - similarity
            ))
        return hits


@lru_cache
def get_vector_store() -> VectorStore:
    """One shared instance for the whole process (opening ChromaDB is not free)."""
    settings = get_settings()
    return VectorStore(settings.chroma_dir, settings.chroma_collection)
