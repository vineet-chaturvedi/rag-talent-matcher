"""
The ONLY module that talks to Ollama's HTTP API.

Ollama endpoints we use:
  GET  /api/version  -> {"version": "0.x.y"}
  GET  /api/tags     -> list of installed models
  POST /api/embed    -> text(s) -> embedding vector(s)
  POST /api/chat     -> messages -> the model's reply (+ timing stats)
"""
import json
import logging
from collections.abc import AsyncIterator
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class OllamaError(Exception):
    """Raised when Ollama is unreachable or returns an error. Callers catch this one type."""


def normalize_model_name(name: str) -> str:
    """Ollama lists 'nomic-embed-text' as 'nomic-embed-text:latest'. Make names comparable."""
    return name if ":" in name else f"{name}:latest"


class OllamaClient:
    def __init__(self, base_url: str, timeout_seconds: float):
        # One AsyncClient reused for the whole app = connection reuse = faster.
        # connect=5s: fail fast if Ollama isn't running; overall timeout is long because
        # generation on CPU can take minutes.
        self._client = httpx.AsyncClient(
            base_url=base_url,
            timeout=httpx.Timeout(timeout_seconds, connect=5.0),
        )

    async def close(self) -> None:
        await self._client.aclose()

    # ---------- low-level helper ----------
    async def _request(self, method: str, path: str, payload: dict | None = None) -> dict[str, Any]:
        """Send one request and turn every kind of failure into an OllamaError."""
        try:
            response = await self._client.request(method, path, json=payload)
            response.raise_for_status()  # turns 4xx/5xx status codes into exceptions
            return response.json()
        except httpx.ConnectError as exc:
            raise OllamaError("Cannot connect to Ollama. Is it running? (check the tray icon)") from exc
        except httpx.TimeoutException as exc:
            raise OllamaError(f"Ollama did not answer within the timeout ({path}).") from exc
        except httpx.HTTPStatusError as exc:
            # e.g. 404 when the model isn't pulled: {"error": "model 'x' not found"}
            raise OllamaError(f"Ollama returned {exc.response.status_code}: {exc.response.text}") from exc

    # ---------- public methods ----------
    async def version(self) -> str:
        data = await self._request("GET", "/api/version")
        return data.get("version", "unknown")

    async def list_models(self) -> list[str]:
        data = await self._request("GET", "/api/tags")
        return [m["name"] for m in data.get("models", [])]

    async def embed(self, texts: list[str], model: str) -> list[list[float]]:
        """Embed many texts in ONE request (batching): far faster than one call per text."""
        data = await self._request("POST", "/api/embed", {"model": model, "input": texts})
        return data["embeddings"]

    async def chat(
        self,
        messages: list[dict[str, str]],
        model: str,
        temperature: float = 0.0,
        num_ctx: int | None = None,
        json_schema: dict | None = None,
        num_predict: int | None = None,
        tools: list[dict] | None = None,
    ) -> dict[str, Any]:
        """
        messages: [{"role": "system"|"user"|"assistant", "content": "..."}]
        json_schema: if given, Ollama FORCES the output to match it (structured outputs).
        num_predict: maximum number of tokens to generate (protects against endless output).
        tools: functions the model may ask to call (Step 10); its requests arrive in ["message"]["tool_calls"].
        Returns Ollama's full response: reply text in ["message"]["content"], plus timing stats.
        """
        options: dict[str, Any] = {"temperature": temperature}
        if num_ctx:
            options["num_ctx"] = num_ctx
        if num_predict:
            options["num_predict"] = num_predict

        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": False,   # wait for the full answer (chat_stream() streams it)
            "options": options,
        }
        if json_schema:
            payload["format"] = json_schema
        if tools:
            payload["tools"] = tools

        logger.info("chat -> model=%s messages=%d temp=%s", model, len(messages), temperature)
        data = await self._request("POST", "/api/chat", payload)
        logger.info(
            "chat <- model=%s prompt_tokens=%s output_tokens=%s",
            model, data.get("prompt_eval_count"), data.get("eval_count"),
        )
        return data

    async def chat_stream(
        self,
        messages: list[dict[str, Any]],
        model: str,
        tools: list[dict] | None = None,
        temperature: float = 0.0,
        num_ctx: int | None = None,
        num_predict: int | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """
        Streaming chat (Step 10): yields Ollama's chunks as they arrive, one JSON object per line:
          {"message": {"role": "assistant", "content": "Pri"}, "done": false}
          {"message": {"role": "assistant", "content": "", "tool_calls": [...]}, "done": false}
          {"message": {...}, "done": true, "done_reason": "stop", "eval_count": 120, ...}
        So the user sees the answer appear word by word instead of waiting for all of it.
        """
        options: dict[str, Any] = {"temperature": temperature}
        if num_ctx:
            options["num_ctx"] = num_ctx
        if num_predict:
            options["num_predict"] = num_predict
        payload: dict[str, Any] = {"model": model, "messages": messages, "stream": True, "options": options}
        if tools:
            payload["tools"] = tools
        logger.info("chat_stream -> model=%s messages=%d tools=%d", model, len(messages), len(tools or []))
        try:
            async with self._client.stream("POST", "/api/chat", json=payload) as response:
                if response.status_code >= 400:
                    body = (await response.aread()).decode(errors="replace")
                    raise OllamaError(f"Ollama returned {response.status_code}: {body}")
                async for line in response.aiter_lines():
                    if line.strip():
                        yield json.loads(line)
        except httpx.ConnectError as exc:
            raise OllamaError("Cannot connect to Ollama. Is it running? (check the tray icon)") from exc
        except httpx.TimeoutException as exc:
            raise OllamaError("Ollama did not answer within the timeout (/api/chat stream).") from exc
