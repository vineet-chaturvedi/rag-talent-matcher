"""
Embedding-only providers with their own APIs (plain HTTP, no SDK needed):

  voyage/<model>    Voyage AI (Anthropic's recommended embeddings), e.g. voyage/voyage-3.5       VOYAGE_API_KEY
  cohere/<model>    Cohere, e.g. cohere/embed-v4.0, cohere/embed-multilingual-v3.0            COHERE_API_KEY
  gemini/<model>    Google, e.g. gemini/gemini-embedding-001 (native API, so the task type is sent) GEMINI_API_KEY

All three take the KIND of text as a parameter ("query" vs "document"), so no text prompts are added for them
(app/llm/models.py lists them as "no prompts"). OpenAI and Azure embeddings go through openai_compat.py.
Rate limits (429) and outages (5xx) are retried a few times with a growing pause before giving up.
"""
import asyncio
import logging

import httpx

from app.llm.errors import LLMError

logger = logging.getLogger(__name__)


class _HttpEmbedder:
    service = "embedding API"

    def __init__(self, timeout: float):
        self._client = httpx.AsyncClient(timeout=httpx.Timeout(timeout, connect=10.0))

    async def close(self) -> None:
        await self._client.aclose()

    async def _post(self, url: str, headers: dict, payload: dict) -> dict:
        for attempt in range(4):
            try:
                resp = await self._client.post(url, headers=headers, json=payload)
            except httpx.HTTPError as exc:
                if attempt == 3:
                    raise LLMError(f"Cannot reach {self.service}: {exc}") from exc
                await asyncio.sleep(2 ** attempt)
                continue
            if resp.status_code == 429 or resp.status_code >= 500:
                if attempt < 3:
                    await asyncio.sleep(2 ** attempt)
                    continue
            if resp.status_code >= 400:
                code = resp.status_code
                raise LLMError(f"{self.service} returned {code}: {resp.text[:300]}",
                               retryable=code in (401, 403, 404, 429) or code >= 500)
            return resp.json()
        raise LLMError(f"{self.service} did not answer")


class VoyageEmbedder(_HttpEmbedder):
    service = "Voyage AI"
    URL = "https://api.voyageai.com/v1/embeddings"

    def __init__(self, api_key: str | None, timeout: float, base_url: str | None = None):
        if not api_key:
            raise LLMError("VOYAGE_API_KEY is not set in backend/.env")
        super().__init__(timeout)
        self._key, self._url = api_key, base_url or self.URL

    async def embed(self, texts: list[str], model: str, kind: str = "document",
                    dimensions: int | None = None) -> list[list[float]]:
        payload = {"input": texts, "model": model, "input_type": "query" if kind == "query" else "document"}
        if dimensions:
            payload["output_dimension"] = dimensions
        data = await self._post(self._url, {"Authorization": f"Bearer {self._key}"}, payload)
        return [d["embedding"] for d in sorted(data["data"], key=lambda d: d.get("index", 0))]


class CohereEmbedder(_HttpEmbedder):
    service = "Cohere"
    URL = "https://api.cohere.com/v2/embed"

    def __init__(self, api_key: str | None, timeout: float, base_url: str | None = None):
        if not api_key:
            raise LLMError("COHERE_API_KEY is not set in backend/.env")
        super().__init__(timeout)
        self._key, self._url = api_key, base_url or self.URL

    async def embed(self, texts: list[str], model: str, kind: str = "document",
                    dimensions: int | None = None) -> list[list[float]]:
        payload = {"model": model, "texts": texts, "embedding_types": ["float"],
                   "input_type": "search_query" if kind == "query" else "search_document"}
        if dimensions:
            payload["output_dimension"] = dimensions
        data = await self._post(self._url, {"Authorization": f"Bearer {self._key}"}, payload)
        return data["embeddings"]["float"]


class GeminiEmbedder(_HttpEmbedder):
    service = "Gemini"
    BASE = "https://generativelanguage.googleapis.com/v1beta"

    def __init__(self, api_key: str | None, timeout: float, base_url: str | None = None):
        if not api_key:
            raise LLMError("GEMINI_API_KEY is not set in backend/.env")
        super().__init__(timeout)
        self._key, self._base = api_key, (base_url or self.BASE).rstrip("/")

    async def embed(self, texts: list[str], model: str, kind: str = "document",
                    dimensions: int | None = None) -> list[list[float]]:
        name = model if model.startswith("models/") else f"models/{model}"
        task = "RETRIEVAL_QUERY" if kind == "query" else "RETRIEVAL_DOCUMENT"
        requests = []
        for t in texts:
            r = {"model": name, "content": {"parts": [{"text": t}]}, "taskType": task}
            if dimensions:
                r["outputDimensionality"] = dimensions
            requests.append(r)
        data = await self._post(f"{self._base}/{name}:batchEmbedContents", {"x-goog-api-key": self._key},
                                {"requests": requests})
        return [e["values"] for e in data["embeddings"]]
