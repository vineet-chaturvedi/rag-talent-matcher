"""
Provider: Anthropic's Messages API (Claude).            .env: anthropic/<model>, ANTHROPIC_API_KEY

Translation between the app's common (Ollama-shaped) format and Claude's:
  system messages   -> the separate `system` parameter
  tool calls        -> "tool_use" content blocks with ids; tool results -> "tool_result" blocks in a user message
  roles             -> Claude needs user / assistant turns alternating: neighbours with the same role are merged
  json_schema       -> a forced tool call: Claude must call a tool whose input schema IS our schema, and the
                       tool's input is the JSON answer. Works on every Claude model and with any JSON schema.
  num_predict       -> max_tokens (required by Claude; ANTHROPIC_MAX_TOKENS when the caller sets none)
  answers           -> {"message": {"content", "tool_calls"}, "done_reason", "prompt_eval_count", "eval_count"}
"""
import json
import logging
from collections.abc import AsyncIterator
from typing import Any

from app.llm.errors import LLMError
from app.llm.models import inline_refs

logger = logging.getLogger(__name__)

ANSWER_TOOL = "structured_answer"
_STOP = {"end_turn": "stop", "stop_sequence": "stop", "tool_use": "stop", "max_tokens": "length"}


def _sdk():
    try:
        import anthropic
    except ImportError as exc:
        raise LLMError("This model needs the Anthropic SDK: pip install anthropic") from exc
    return anthropic


def to_error(exc: Exception) -> LLMError:
    anthropic = _sdk()
    if isinstance(exc, LLMError):
        return exc
    if isinstance(exc, (anthropic.APIConnectionError, anthropic.APITimeoutError)):
        return LLMError(f"Cannot reach Anthropic: {exc}")
    if isinstance(exc, anthropic.APIStatusError):
        code = exc.status_code
        retryable = code in (401, 403, 404, 408, 409, 429) or code >= 500   # setup, limits, 529 overloaded
        return LLMError(f"Anthropic returned {code}: {exc.message}", retryable=retryable)
    return LLMError(f"Anthropic: {type(exc).__name__}: {exc}")


def to_anthropic(messages: list[dict[str, Any]]) -> tuple[str, list[dict[str, Any]]]:
    """Common format -> (system text, Claude messages)."""
    system: list[str] = []
    out: list[dict[str, Any]] = []
    pending: list[str] = []
    counter = 0

    def push(role: str, blocks: list[dict[str, Any]]) -> None:
        blocks = [b for b in blocks if not (b["type"] == "text" and not b["text"].strip())]
        if not blocks:
            return
        if out and out[-1]["role"] == role:
            out[-1]["content"].extend(blocks)          # Claude wants alternating roles: merge neighbours
        else:
            out.append({"role": role, "content": blocks})

    for m in messages:
        role, content = m["role"], m.get("content") or ""
        if role == "system":
            system.append(content)
        elif role == "assistant":
            blocks = [{"type": "text", "text": content}]
            for c in m.get("tool_calls") or []:
                counter += 1
                call_id = f"toolu_{counter:04d}"
                pending.append(call_id)
                fn = c.get("function", c)
                args = fn.get("arguments") or {}
                blocks.append({"type": "tool_use", "id": call_id, "name": fn["name"],
                               "input": json.loads(args) if isinstance(args, str) else args})
            push("assistant", blocks)
        elif role == "tool":
            call_id = pending.pop(0) if pending else f"toolu_{counter + 1:04d}"
            push("user", [{"type": "tool_result", "tool_use_id": call_id, "content": content}])
        else:
            push("user", [{"type": "text", "text": content}])
    if out and out[0]["role"] != "user":               # Claude's first turn must be the user's
        out.insert(0, {"role": "user", "content": [{"type": "text", "text": "(continue)"}]})
    return "\n\n".join(s for s in system if s.strip()), out


def to_anthropic_tools(tools: list[dict] | None) -> list[dict]:
    """OpenAI/Ollama function specs -> Claude tool specs."""
    out = []
    for t in tools or []:
        fn = t.get("function", t)
        out.append({"name": fn["name"], "description": fn.get("description", ""),
                    "input_schema": inline_refs(fn.get("parameters") or {"type": "object", "properties": {}})})
    return out


class AnthropicProvider:
    service = "Anthropic"

    def __init__(self, api_key: str | None, base_url: str | None, timeout: float, default_max_tokens: int):
        if not api_key:
            raise LLMError("ANTHROPIC_API_KEY is not set in backend/.env")
        self._client = _sdk().AsyncAnthropic(api_key=api_key, base_url=base_url or None, timeout=timeout)
        self._max_tokens = default_max_tokens
        self._no_temperature: set[str] = set()

    async def close(self) -> None:
        await self._client.close()

    def _params(self, model, messages, temperature, json_schema, num_predict, tools) -> dict[str, Any]:
        system, msgs = to_anthropic(messages)
        params: dict[str, Any] = {"model": model, "messages": msgs, "max_tokens": num_predict or self._max_tokens}
        if model not in self._no_temperature:
            # Sent as raw JSON (extra_body): recent SDK versions no longer list `temperature`, while many Claude
            # models still accept it. A model that refuses it gets the request again without it.
            params["extra_body"] = {"temperature": temperature}
        if system:
            params["system"] = system
        if json_schema:
            params["tools"] = [{"name": ANSWER_TOOL, "description": "Give the answer in exactly this structure.",
                                "input_schema": inline_refs(json_schema)}]
            params["tool_choice"] = {"type": "tool", "name": ANSWER_TOOL}
        elif tools:
            params["tools"] = to_anthropic_tools(tools)
        return params

    @staticmethod
    def _convert(resp, model: str, structured: bool) -> dict[str, Any]:
        text, calls = "", []
        for block in resp.content:
            if block.type == "text":
                text += block.text
            elif block.type == "tool_use":
                if structured and block.name == ANSWER_TOOL:
                    text = json.dumps(block.input)
                else:
                    calls.append({"function": {"name": block.name, "arguments": dict(block.input or {})}})
        usage = resp.usage
        return {
            "model": model,
            "message": {"role": "assistant", "content": text, **({"tool_calls": calls} if calls else {})},
            "done": True,
            "done_reason": _STOP.get(resp.stop_reason or "end_turn", resp.stop_reason),
            "prompt_eval_count": getattr(usage, "input_tokens", None),
            "eval_count": getattr(usage, "output_tokens", None),
        }

    def _retry_without_temperature(self, model: str, exc: Exception, params: dict) -> bool:
        """Some models refuse `temperature`: leave it out from now on for that model."""
        if isinstance(exc, _sdk().BadRequestError) and "temperature" in str(exc).lower() and "extra_body" in params:
            self._no_temperature.add(model)
            params.pop("extra_body")
            logger.info("Anthropic model %s refused temperature; asking again without it.", model)
            return True
        return False

    async def chat(self, messages, model, temperature=0.0, num_ctx=None, json_schema=None, num_predict=None,
                   tools=None) -> dict[str, Any]:
        params = self._params(model, messages, temperature, json_schema, num_predict, tools)
        try:
            try:
                resp = await self._client.messages.create(**params)
            except Exception as exc:
                if not self._retry_without_temperature(model, exc, params):
                    raise
                resp = await self._client.messages.create(**params)
        except Exception as exc:
            raise to_error(exc) from exc
        out = self._convert(resp, model, structured=bool(json_schema))
        logger.info("chat <- Anthropic model=%s prompt_tokens=%s output_tokens=%s", model,
                    out["prompt_eval_count"], out["eval_count"])
        return out

    async def chat_stream(self, messages, model, tools=None, temperature=0.0, num_ctx=None,
                          num_predict=None) -> AsyncIterator[dict[str, Any]]:
        params = self._params(model, messages, temperature, None, num_predict, tools)
        for attempt in (1, 2):
            try:
                async with self._client.messages.stream(**params) as stream:
                    async for text in stream.text_stream:
                        if text:
                            yield {"message": {"role": "assistant", "content": text}, "done": False}
                    final = await stream.get_final_message()
                break
            except Exception as exc:
                if attempt == 1 and self._retry_without_temperature(model, exc, params):
                    continue
                raise to_error(exc) from exc
        out = self._convert(final, model, structured=False)
        if out["message"].get("tool_calls"):
            yield {"message": {"role": "assistant", "content": "", "tool_calls": out["message"]["tool_calls"]},
                   "done": False}
        yield {"message": {"role": "assistant", "content": ""}, "done": True, "done_reason": out["done_reason"],
               "prompt_eval_count": out["prompt_eval_count"], "eval_count": out["eval_count"]}
