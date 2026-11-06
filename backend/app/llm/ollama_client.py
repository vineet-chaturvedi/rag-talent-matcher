"""
The ONLY module that talks to Ollama's HTTP API. (Cloud providers have their own modules; app/llm/router.py
sends each request to the right one, so the rest of the app doesn't know or care which provider answers.)

Its request and answer shapes are the app's common format: the other providers translate to and from it.

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

from app.llm.errors import LLMError
from app.llm.models import strip_thinking

logger = logging.getLogger(__name__)


# The historical name of the app's model error, kept because many modules catch it. It IS LLMError, so it
# also catches errors from the cloud providers (app/llm/errors.py).
OllamaError = LLMError


def normalize_model_name(name: str) -> str:
    """Ollama lists 'nomic-embed-text' as 'nomic-embed-text:latest'. Make names comparable."""
    return name if ":" in name else f"{name}:latest"


class OllamaClient:
    def __init__(self, base_url: str, timeout_seconds: float, think: str = "off"):
        # One AsyncClient reused for the whole app = connection reuse = faster.
        # connect=5s: fail fast if Ollama isn't running; overall timeout is long because
        # generation on CPU can take minutes.
        self._client = httpx.AsyncClient(
            base_url=base_url,
            timeout=httpx.Timeout(timeout_seconds, connect=5.0),
        )
        # LLM_THINK (see app/llm/models.py): "off" sends think=false, "on" think=true, "default" nothing.
        self._think = think
        self._no_think_flag: set[str] = set()   # models that rejected the flag: never send it to them again

    def _think_field(self, payload: dict[str, Any]) -> None:
        if self._think != "default" and payload["model"] not in self._no_think_flag:
            payload["think"] = self._think == "on"

    @staticmethod
    def _rejects_think(status: int, body: str) -> bool:
        return status == 400 and "think" in body.lower()

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
            # e.g. 404 when the model isn't pulled: {"error": "model 'x' not found"} (fixable: retry later);
            # 400 = this request itself is invalid (retrying the same request won't help).
            code = exc.response.status_code
            raise OllamaError(f"Ollama returned {code}: {exc.response.text}", retryable=code != 400) from exc

    # ---------- public methods ----------
    async def version(self) -> str:
        data = await self._request("GET", "/api/version")
        return data.get("version", "unknown")

    async def list_models(self) -> list[str]:
        data = await self._request("GET", "/api/tags")
        return [m["name"] for m in data.get("models", [])]

    async def embed(self, texts: list[str], model: str, kind: str = "document") -> list[list[float]]:
        # kind ("document" / "query") matters for APIs that take it as a parameter; Ollama models get it
        # through the text prompts instead (app/rag/embeddings.py)
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
        self._think_field(payload)

        logger.info("chat -> model=%s messages=%d temp=%s", model, len(messages), temperature)
        try:
            data = await self._request("POST", "/api/chat", payload)
        except OllamaError as exc:
            if "think" not in payload or "think" not in str(exc).lower():
                raise
            logger.info("Model %s doesn't take the think flag; asking again without it.", model)
            self._no_think_flag.add(model)
            payload.pop("think")
            data = await self._request("POST", "/api/chat", payload)
        message = data.get("message") or {}
        if message.get("content"):
            message["content"] = strip_thinking(message["content"])   # keep only the answer
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
        self._think_field(payload)
        logger.info("chat_stream -> model=%s messages=%d tools=%d", model, len(messages), len(tools or []))
        try:
            for attempt in (1, 2):
                async with self._client.stream("POST", "/api/chat", json=payload) as response:
                    if response.status_code >= 400:
                        body = (await response.aread()).decode(errors="replace")
                        if attempt == 1 and "think" in payload and self._rejects_think(response.status_code, body):
                            logger.info("Model %s doesn't take the think flag; asking again without it.", model)
                            self._no_think_flag.add(model)
                            payload.pop("think")
                            continue
                        raise OllamaError(f"Ollama returned {response.status_code}: {body}",
                                          retryable=response.status_code != 400)
                    async for line in response.aiter_lines():
                        if line.strip():
                            yield json.loads(line)
                    return
        except httpx.ConnectError as exc:
            raise OllamaError("Cannot connect to Ollama. Is it running? (check the tray icon)") from exc
        except httpx.TimeoutException as exc:
            raise OllamaError("Ollama did not answer within the timeout (/api/chat stream).") from exc
