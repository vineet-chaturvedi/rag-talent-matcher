"""
Provider: the OpenAI chat-completions API, and every service that speaks it.

Used for (prefix in .env -> service):
  openai/<model>   OpenAI                     OPENAI_API_KEY (OPENAI_BASE_URL optional)
  azure/<deploy>   Azure OpenAI               AZURE_OPENAI_API_KEY, AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_API_VERSION
  gemini/<model>   Google Gemini (its OpenAI-compatible endpoint)          GEMINI_API_KEY
  compat/<model>   any other OpenAI-compatible server: vLLM, LM Studio, OpenRouter, Groq, Mistral, DeepSeek,
                   Together, a company LLM gateway ...                    COMPAT_BASE_URL, COMPAT_API_KEY
  vertex/<model>   Google Vertex AI's OpenAI-compatible endpoint: Gemini, and partner/open models (Llama ...)
                   VERTEX_PROJECT, VERTEX_LOCATION; Google credentials (app/llm/google_auth.py), no key in .env

It speaks the app's common (Ollama-shaped) format to the rest of the code and translates:
  messages      tool calls get ids here (Ollama's format has none; OpenAI links each tool result to its call by id)
  json_schema   -> response_format {"type": "json_schema"}; if a service refuses it -> {"type": "json_object"}
                   with the schema written into the instructions (the app checks the JSON with Pydantic anyway)
  num_predict   -> max_tokens (or max_completion_tokens for newer OpenAI models that refuse max_tokens)
  answers       -> {"message": {"content", "tool_calls"}, "done_reason", "prompt_eval_count", "eval_count"}
Parameters a model refuses (temperature on reasoning models, ...) are dropped once and remembered per model.
"""
import json
import logging
from collections.abc import AsyncIterator
from typing import Any

from app.llm.errors import LLMError
from app.llm.models import inline_refs, strip_thinking

logger = logging.getLogger(__name__)

GEMINI_OPENAI_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"


def _sdk():
    try:
        import openai
    except ImportError as exc:  # optional dependency: only needed for cloud models
        raise LLMError("This model needs the OpenAI SDK: pip install openai") from exc
    return openai


def to_error(exc: Exception, service: str) -> LLMError:
    """SDK exception -> LLMError, with retryable = 'not this request's fault'."""
    openai = _sdk()
    if isinstance(exc, LLMError):
        return exc
    if isinstance(exc, (openai.APIConnectionError, openai.APITimeoutError)):
        return LLMError(f"Cannot reach {service}: {exc}")
    if isinstance(exc, openai.APIStatusError):
        code = exc.status_code
        retryable = code in (401, 403, 404, 408, 409, 429) or code >= 500   # setup, limits, outages
        return LLMError(f"{service} returned {code}: {exc.message}", retryable=retryable)
    return LLMError(f"{service}: {type(exc).__name__}: {exc}")


def to_openai_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Common format -> OpenAI messages. Tool results are matched to the calls in order."""
    out: list[dict[str, Any]] = []
    pending: list[str] = []
    counter = 0
    for m in messages:
        role = m["role"]
        if role == "assistant" and m.get("tool_calls"):
            calls = []
            for c in m["tool_calls"]:
                counter += 1
                call_id = f"call_{counter}"
                pending.append(call_id)
                fn = c.get("function", c)
                args = fn.get("arguments") or {}
                calls.append({"id": call_id, "type": "function",
                              "function": {"name": fn["name"],
                                           "arguments": args if isinstance(args, str) else json.dumps(args)}})
            out.append({"role": "assistant", "content": m.get("content") or None, "tool_calls": calls})
        elif role == "tool":
            if pending:
                call_id = pending.pop(0)
            else:
                counter += 1
                call_id = f"call_{counter}"
            out.append({"role": "tool", "tool_call_id": call_id, "content": m.get("content") or ""})
        else:
            out.append({"role": role, "content": m.get("content") or ""})
    return out


def _parse_args(raw: str | None) -> dict:
    try:
        value = json.loads(raw or "{}")
        return value if isinstance(value, dict) else {}
    except ValueError:
        return {}


_FINISH = {"length": "length", "stop": "stop", "tool_calls": "stop", "content_filter": "content_filter"}


class OpenAICompatProvider:
    def __init__(self, service: str, client, token=None, model_prefix: str = ""):
        self.service = service            # e.g. "OpenAI", "Gemini": used in messages
        self._client = client
        self._token = token               # GoogleToken for Vertex: a fresh OAuth token before each request
        self._model_prefix = model_prefix  # Vertex names models "<publisher>/<model>": "google/" by default
        self._quirks: dict[str, set[str]] = {}   # model -> parameters it refused

    # ----------------------------------------------------------------- construction
    @classmethod
    def openai(cls, api_key: str | None, base_url: str | None, timeout: float) -> "OpenAICompatProvider":
        if not api_key:
            raise LLMError("OPENAI_API_KEY is not set in backend/.env")
        return cls("OpenAI", _sdk().AsyncOpenAI(api_key=api_key, base_url=base_url or None, timeout=timeout))

    @classmethod
    def azure(cls, api_key: str | None, endpoint: str | None, api_version: str, timeout: float):
        if not api_key or not endpoint:
            raise LLMError("AZURE_OPENAI_API_KEY and AZURE_OPENAI_ENDPOINT must be set in backend/.env")
        return cls("Azure OpenAI", _sdk().AsyncAzureOpenAI(api_key=api_key, azure_endpoint=endpoint,
                                                           api_version=api_version, timeout=timeout))

    @classmethod
    def gemini(cls, api_key: str | None, base_url: str | None, timeout: float) -> "OpenAICompatProvider":
        if not api_key:
            raise LLMError("GEMINI_API_KEY is not set in backend/.env")
        return cls("Gemini", _sdk().AsyncOpenAI(api_key=api_key, base_url=base_url or GEMINI_OPENAI_URL,
                                                timeout=timeout))

    @classmethod
    def compat(cls, api_key: str | None, base_url: str | None, timeout: float) -> "OpenAICompatProvider":
        if not base_url:
            raise LLMError("COMPAT_BASE_URL is not set in backend/.env (e.g. http://localhost:8000/v1)")
        # Many self-hosted servers need no key, but the SDK insists on one.
        return cls(f"OpenAI-compatible server {base_url}",
                   _sdk().AsyncOpenAI(api_key=api_key or "not-needed", base_url=base_url, timeout=timeout))

    @classmethod
    def vertex(cls, base_url: str, timeout: float, token) -> "OpenAICompatProvider":
        """base_url: https://<location>-aiplatform.googleapis.com/v1/projects/<p>/locations/<location>/endpoints/openapi"""
        return cls("Vertex AI", _sdk().AsyncOpenAI(api_key="set-per-request", base_url=base_url, timeout=timeout),
                   token=token, model_prefix="google/")

    async def close(self) -> None:
        await self._client.close()

    async def _authorize(self) -> None:
        if self._token is not None:
            self._client.api_key = await self._token.get()     # the SDK reads api_key on every request

    def _model(self, model: str) -> str:
        return model if not self._model_prefix or "/" in model else self._model_prefix + model

    # ----------------------------------------------------------------- request building
    def _params(self, model: str, messages, temperature, json_schema, num_predict, tools, stream) -> dict:
        quirks = self._quirks.get(model, set())
        msgs = to_openai_messages(messages)
        params: dict[str, Any] = {"model": model, "messages": msgs}
        if "temperature" not in quirks:
            params["temperature"] = temperature
        if num_predict:
            params["max_completion_tokens" if "max_tokens" in quirks else "max_tokens"] = num_predict
        if tools:
            params["tools"] = tools          # our tool specs are already in OpenAI's function format
        if json_schema:
            if "json_schema" in quirks:
                params["response_format"] = {"type": "json_object"}
                note = ("Answer with ONE JSON object that follows this JSON schema exactly, and nothing else:\n"
                        + json.dumps(json_schema))
                params["messages"] = [{"role": "system", "content": note}] + msgs
            else:
                params["response_format"] = {"type": "json_schema",
                                             "json_schema": {"name": "answer", "schema": inline_refs(json_schema),
                                                             "strict": False}}
        if stream:
            params["stream"] = True
            if "stream_options" not in quirks:
                params["stream_options"] = {"include_usage": True}
        return params

    def _learn(self, model: str, exc: Exception) -> bool:
        """A 400 about one parameter: remember to leave it out (or change it) for this model. True = try again."""
        openai = _sdk()
        if not isinstance(exc, openai.BadRequestError):
            return False
        text = str(exc).lower()
        quirks = self._quirks.setdefault(model, set())
        for key, words in (("temperature", ["temperature"]), ("max_tokens", ["max_tokens"]),
                           ("json_schema", ["response_format", "json_schema"]),
                           ("stream_options", ["stream_options"])):
            if key not in quirks and any(w in text for w in words):
                quirks.add(key)
                logger.info("%s model %s refused %s; asking again without it.", self.service, model, key)
                return True
        return False

    # ----------------------------------------------------------------- chat
    async def chat(self, messages, model, temperature=0.0, num_ctx=None, json_schema=None, num_predict=None,
                   tools=None) -> dict[str, Any]:
        await self._authorize()
        model = self._model(model)
        for _ in range(5):
            params = self._params(model, messages, temperature, json_schema, num_predict, tools, stream=False)
            try:
                resp = await self._client.chat.completions.create(**params)
                break
            except Exception as exc:
                if self._learn(model, exc):
                    continue
                raise to_error(exc, self.service) from exc
        else:
            raise LLMError(f"{self.service} kept refusing the request for {model}", retryable=False)
        choice = resp.choices[0]
        msg = choice.message
        calls = [{"function": {"name": c.function.name, "arguments": _parse_args(c.function.arguments)}}
                 for c in (msg.tool_calls or []) if getattr(c, "function", None)]
        usage = resp.usage
        logger.info("chat <- %s model=%s prompt_tokens=%s output_tokens=%s", self.service, model,
                    getattr(usage, "prompt_tokens", None), getattr(usage, "completion_tokens", None))
        return {
            "model": model,
            "message": {"role": "assistant", "content": strip_thinking(msg.content or ""),
                        **({"tool_calls": calls} if calls else {})},
            "done": True,
            "done_reason": _FINISH.get(choice.finish_reason or "stop", choice.finish_reason),
            "prompt_eval_count": getattr(usage, "prompt_tokens", None),
            "eval_count": getattr(usage, "completion_tokens", None),
        }

    async def chat_stream(self, messages, model, tools=None, temperature=0.0, num_ctx=None,
                          num_predict=None) -> AsyncIterator[dict[str, Any]]:
        await self._authorize()
        model = self._model(model)
        for _ in range(5):
            params = self._params(model, messages, temperature, None, num_predict, tools, stream=True)
            try:
                stream = await self._client.chat.completions.create(**params)
                break
            except Exception as exc:
                if self._learn(model, exc):
                    continue
                raise to_error(exc, self.service) from exc
        else:
            raise LLMError(f"{self.service} kept refusing the request for {model}", retryable=False)

        calls: dict[int, dict[str, Any]] = {}     # tool calls arrive in pieces, keyed by index
        finish, usage = None, None
        try:
            async for chunk in stream:
                if getattr(chunk, "usage", None):
                    usage = chunk.usage
                for choice in chunk.choices or []:
                    delta = choice.delta
                    if delta is not None and delta.content:
                        yield {"message": {"role": "assistant", "content": delta.content}, "done": False}
                    for tc in (getattr(delta, "tool_calls", None) or []):
                        slot = calls.setdefault(tc.index if tc.index is not None else len(calls),
                                                {"name": "", "arguments": ""})
                        if tc.function is not None:
                            slot["name"] += tc.function.name or ""
                            slot["arguments"] += tc.function.arguments or ""
                    if choice.finish_reason:
                        finish = choice.finish_reason
        except Exception as exc:
            raise to_error(exc, self.service) from exc
        if calls:
            yield {"message": {"role": "assistant", "content": "", "tool_calls": [
                {"function": {"name": c["name"], "arguments": _parse_args(c["arguments"])}}
                for _, c in sorted(calls.items()) if c["name"]]}, "done": False}
        yield {"message": {"role": "assistant", "content": ""}, "done": True,
               "done_reason": _FINISH.get(finish or "stop", finish),
               "prompt_eval_count": getattr(usage, "prompt_tokens", None),
               "eval_count": getattr(usage, "completion_tokens", None)}

    # ----------------------------------------------------------------- embeddings
    async def embed(self, texts: list[str], model: str, kind: str = "document",
                    dimensions: int | None = None) -> list[list[float]]:
        await self._authorize()
        params: dict[str, Any] = {"model": self._model(model), "input": texts}
        if dimensions:
            params["dimensions"] = dimensions   # text-embedding-3-*: shorter vectors, cheaper storage
        try:
            resp = await self._client.embeddings.create(**params)
        except Exception as exc:
            raise to_error(exc, self.service) from exc
        return [d.embedding for d in sorted(resp.data, key=lambda d: d.index)]
