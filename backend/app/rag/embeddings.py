"""
Turning text into vectors with the embedding model (nomic-embed-text via Ollama).

nomic-embed-text was trained with TASK PREFIXES, and expects them:
  - text being stored and searched   -> "search_document: ..."
  - the question / role description -> "search_query: ..."
Without them, search quality drops noticeably (you can test this with /api/dev/similarity).
"""
from app.llm.ollama_client import OllamaClient

DOCUMENT_PREFIX = "search_document: "
QUERY_PREFIX = "search_query: "


async def embed_documents(ollama: OllamaClient, texts: list[str], model: str, batch_size: int) -> list[list[float]]:
    """Embed many chunks, a batch at a time (one HTTP call per batch, not per chunk)."""
    vectors: list[list[float]] = []
    for i in range(0, len(texts), batch_size):
        batch = [DOCUMENT_PREFIX + t for t in texts[i:i + batch_size]]
        vectors.extend(await ollama.embed(batch, model=model))
    return vectors


async def embed_query(ollama: OllamaClient, text: str, model: str) -> list[float]:
    return (await ollama.embed([QUERY_PREFIX + text], model=model))[0]
