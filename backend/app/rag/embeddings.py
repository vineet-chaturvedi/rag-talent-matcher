"""
Turning text into vectors with the embedding model (EMBED_MODEL in .env, via Ollama).

Retrieval embedding models are trained to see a fixed text in front of the QUERY and sometimes the
DOCUMENT, and expect it. nomic-embed-text, for example:
  - text being stored and searched   -> "search_document: ..."
  - the question / role description -> "search_query: ..."
Without it, search quality drops noticeably (test it with /api/dev/similarity). Which text each model wants
is in app/llm/models.py (KNOWN_EMBEDDINGS), or in .env (EMBED_QUERY_TEMPLATE / EMBED_DOCUMENT_TEMPLATE)
for a model that table doesn't know.
"""
from app.config import get_settings
from app.llm.models import EmbeddingProfile, apply, embedding_profile
from app.llm.ollama_client import OllamaClient


def profile_for(model: str) -> EmbeddingProfile:
    s = get_settings()
    # An empty line in .env means "not set" (use the known template); write {text} for "no prompt at all".
    return embedding_profile(model, s.embed_query_template or None, s.embed_document_template or None)


async def embed_documents(ollama: OllamaClient, texts: list[str], model: str, batch_size: int) -> list[list[float]]:
    """Embed many chunks, a batch at a time (one HTTP call per batch, not per chunk)."""
    template = profile_for(model).document_template
    vectors: list[list[float]] = []
    for i in range(0, len(texts), batch_size):
        batch = [apply(template, t) for t in texts[i:i + batch_size]]
        vectors.extend(await ollama.embed(batch, model=model, kind="document"))
    return vectors


async def embed_query(ollama: OllamaClient, text: str, model: str) -> list[float]:
    return (await ollama.embed([apply(profile_for(model).query_template, text)], model=model, kind="query"))[0]
