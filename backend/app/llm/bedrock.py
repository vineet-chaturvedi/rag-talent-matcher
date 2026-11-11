"""
Provider: Amazon Bedrock.                 .env: bedrock/<model id>, AWS_REGION (+ the usual AWS credentials)

  chat        the Converse API: ONE request format for every Bedrock chat model (Claude, Llama, Mistral,
              Amazon Nova, DeepSeek, ...), tool calls included. Streaming with ConverseStream.
  embeddings  InvokeModel with the model family's own body: Amazon Titan Text Embeddings (v1, v2) and
              Cohere Embed (v3, v4).

Model ids are Bedrock's own, or an inference profile for cross-region routing, e.g.
  bedrock/anthropic.claude-sonnet-4-5-20250929-v1:0     bedrock/apac.anthropic.claude-sonnet-4-5-20250929-v1:0
  bedrock/meta.llama3-3-70b-instruct-v1:0               bedrock/amazon.titan-embed-text-v2:0

Credentials: boto3's standard chain, nothing secret in .env when running on AWS:
  an IAM role (ECS task role, EC2 instance profile, Lambda), AWS_PROFILE / SSO on a laptop, or the
  AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY variables; a Bedrock API key via AWS_BEARER_TOKEN_BEDROCK also works.
  The IAM policy needs bedrock:InvokeModel and bedrock:InvokeModelWithResponseStream on the models used.

Structured output (json_schema), tried in this order and remembered per model:
  1. native   Converse's outputConfig json_schema (models that support structured output)
  2. tool     a forced call to a tool whose input schema IS the schema (works on Claude, Mistral Large, Nova ...)
  3. prompt   the schema in the instructions, the JSON taken from the answer (any model; Pydantic checks it)

boto3 is synchronous: every call runs in a worker thread (asyncio.to_thread) so the server never blocks, and
a stream is read in a thread and handed to the event loop chunk by chunk.
"""
import asyncio
import json
import logging
import re
import threading
from collections.abc import AsyncIterator
from typing import Any

from app.llm.errors import LLMError
from app.llm.models import inline_refs, strip_thinking

logger = logging.getLogger(__name__)

SERVICE = "Amazon Bedrock"
ANSWER_TOOL = "structured_answer"
STRUCTURED_MODES = ("native", "tool", "prompt")
_STOP = {"end_turn": "stop", "stop_sequence": "stop", "tool_use": "stop", "max_tokens": "length",
         "model_context_window_exceeded": "length", "guardrail_intervened": "content_filter",
         "content_filtered": "content_filter"}
# Error codes that are not the request's fault: setup (access, model not enabled), limits and outages.
_RETRYABLE = {"ThrottlingException", "ServiceUnavailableException", "InternalServerException",
              "ModelNotReadyException", "ModelTimeoutException", "AccessDeniedException",
              "ResourceNotFoundException", "UnrecognizedClientException", "ExpiredTokenException",
              "ServiceQuotaExceededException", "RequestTimeout", "InvalidSignatureException"}
EMBED_CONCURRENCY = 8          # parallel InvokeModel calls for one-text-per-request models (Titan)
COHERE_BATCH = 96              # Cohere Embed's limit of texts per request


def _sdk():
    try:
        import boto3
        import botocore
    except ImportError as exc:  # optional dependency
        raise LLMError("bedrock/ models need boto3: pip install -r requirements-cloud.txt") from exc
    return boto3, botocore


def to_error(exc: Exception) -> LLMError:
    """botocore exception -> LLMError (retryable = 'not this request's fault')."""
    if isinstance(exc, LLMError):
        return exc
    _, botocore = _sdk()
    if isinstance(exc, botocore.exceptions.ClientError):
        err = exc.response.get("Error", {})
        code, message = err.get("Code", "Error"), err.get("Message", str(exc))
        return LLMError(f"{SERVICE} {code}: {message}", retryable=code in _RETRYABLE)
    if isinstance(exc, (botocore.exceptions.EndpointConnectionError, botocore.exceptions.ConnectTimeoutError,
                        botocore.exceptions.ReadTimeoutError, botocore.exceptions.ConnectionClosedError)):
        return LLMError(f"Cannot reach {SERVICE}: {exc}")
    if isinstance(exc, botocore.exceptions.NoCredentialsError):
        return LLMError(f"{SERVICE}: no AWS credentials found (IAM role, AWS_PROFILE or access keys)")
    if isinstance(exc, botocore.exceptions.NoRegionError):
        return LLMError(f"{SERVICE}: no AWS region set (AWS_REGION in backend/.env)")
    if isinstance(exc, botocore.exceptions.BotoCoreError):
        return LLMError(f"{SERVICE}: {exc}")
    return LLMError(f"{SERVICE}: {type(exc).__name__}: {exc}", retryable=False)


def _is_validation(exc: Exception) -> bool:
    """The request was refused as invalid: by Bedrock, or already by an older botocore that doesn't know a
    parameter (e.g. outputConfig): both mean "try the next structured-output mode"."""
    if type(exc).__name__ == "ParamValidationError":
        return True
    try:
        return exc.response["Error"]["Code"] == "ValidationException"   # type: ignore[attr-defined]
    except (AttributeError, KeyError, TypeError):
        return False


# --------------------------------------------------------------------------- request translation
def _tool_specs(tools: list[dict] | None) -> list[dict]:
    """OpenAI/Ollama function specs -> Converse toolSpecs."""
    out = []
    for t in tools or []:
        fn = t.get("function", t)
        out.append({"toolSpec": {"name": fn["name"], "description": fn.get("description") or fn["name"],
                                 "inputSchema": {"json": inline_refs(fn.get("parameters")
                                                                     or {"type": "object", "properties": {}})}}})
    return out


def to_converse(messages: list[dict[str, Any]], with_tools: bool) -> tuple[list[dict], list[dict]]:
    """
    Common (Ollama-shaped) messages -> (system blocks, Converse messages).
    Converse rules: user/assistant turns alternate and start with the user; no empty text blocks; tool calls are
    toolUse blocks with ids, and their results toolResult blocks in the next user turn. A request without tools
    may not contain tool blocks, so then earlier tool steps are written out as text.
    """
    system: list[dict] = []
    out: list[dict] = []
    pending: list[str] = []
    counter = 0

    def push(role: str, blocks: list[dict]) -> None:
        blocks = [b for b in blocks if not ("text" in b and not b["text"].strip())]
        if not blocks:
            return
        if out and out[-1]["role"] == role:
            out[-1]["content"].extend(blocks)
        else:
            out.append({"role": role, "content": blocks})

    for m in messages:
        role, content = m["role"], m.get("content") or ""
        if role == "system":
            if content.strip():
                system.append({"text": content})
        elif role == "assistant":
            blocks: list[dict] = [{"text": content}]
            for c in m.get("tool_calls") or []:
                fn = c.get("function", c)
                args = fn.get("arguments") or {}
                args = json.loads(args) if isinstance(args, str) else args
                if with_tools:
                    counter += 1
                    call_id = f"tooluse_{counter:04d}"
                    pending.append(call_id)
                    blocks.append({"toolUse": {"toolUseId": call_id, "name": fn["name"], "input": args}})
                else:
                    blocks.append({"text": f"(called {fn['name']} with {json.dumps(args)})"})
            push("assistant", blocks)
        elif role == "tool":
            if with_tools and pending:
                push("user", [{"toolResult": {"toolUseId": pending.pop(0), "content": [{"text": content or "(empty)"}]}}])
            else:
                push("user", [{"text": f"Tool result: {content}"}])
        else:
            push("user", [{"text": content}])
    if not out or out[0]["role"] != "user":
        out.insert(0, {"role": "user", "content": [{"text": "(continue)"}]})
    return system, out


def _json_from_text(text: str) -> str:
    """The JSON object in a model's answer (it may be wrapped in ``` fences or prose)."""
    text = strip_thinking(text or "").strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.DOTALL)
    if fenced:
        return fenced.group(1)
    start, end = text.find("{"), text.rfind("}")
    return text[start:end + 1] if start != -1 and end > start else text


# --------------------------------------------------------------------------- the provider
class BedrockProvider:
    service = SERVICE

    def __init__(self, region: str | None, profile: str | None, endpoint_url: str | None, timeout: float,
                 max_tokens: int | None = None, client=None):
        boto3, botocore = _sdk()
        if client is None:
            session = boto3.Session(profile_name=profile or None, region_name=region or None)
            if not session.region_name:
                raise LLMError(f"{SERVICE}: no AWS region set (AWS_REGION in backend/.env)")
            config = botocore.config.Config(
                read_timeout=timeout, connect_timeout=10, max_pool_connections=32,
                retries={"mode": "adaptive", "max_attempts": 4},     # throttling handled with backoff
                user_agent_extra="rag-talent-matcher")
            client = session.client("bedrock-runtime", endpoint_url=endpoint_url or None, config=config)
        self._client = client
        self._max_tokens = max_tokens
        self._structured: dict[str, str] = {}          # model -> structured-output mode that worked
        self._no_temperature: set[str] = set()         # models that refuse a temperature

    async def close(self) -> None:
        await asyncio.to_thread(self._client.close)

    # ------------------------------------------------------------------ helpers
    def _params(self, model: str, messages, temperature, num_predict, tools, mode: str | None,
                json_schema: dict | None) -> dict[str, Any]:
        with_tools = bool(tools) or mode == "tool"
        msgs = messages
        if mode == "prompt":
            note = ("Answer with ONE JSON object that follows this JSON schema exactly, and nothing else "
                    "(no explanations, no code fences):\n" + json.dumps(inline_refs(json_schema or {})))
            msgs = [{"role": "system", "content": note}] + list(messages)
        system, converse = to_converse(msgs, with_tools)
        params: dict[str, Any] = {"modelId": model, "messages": converse}
        if system:
            params["system"] = system
        inference: dict[str, Any] = {}
        if model not in self._no_temperature:
            inference["temperature"] = temperature
        if num_predict or self._max_tokens:
            inference["maxTokens"] = num_predict or self._max_tokens
        if inference:
            params["inferenceConfig"] = inference
        if mode == "native":
            params["outputConfig"] = {"textFormat": {"type": "json_schema", "structure": {"jsonSchema": {
                "schema": json.dumps(inline_refs(json_schema or {})), "name": "answer"}}}}
        if mode == "tool":
            params["toolConfig"] = {
                "tools": [{"toolSpec": {"name": ANSWER_TOOL, "description": "Give the answer in exactly this structure.",
                                        "inputSchema": {"json": inline_refs(json_schema or {})}}}],
                "toolChoice": {"tool": {"name": ANSWER_TOOL}}}
        elif tools:
            params["toolConfig"] = {"tools": _tool_specs(tools)}
        return params

    def _learn_temperature(self, model: str, exc: Exception) -> bool:
        if _is_validation(exc) and "temperature" in str(exc).lower() and model not in self._no_temperature:
            self._no_temperature.add(model)
            logger.info("%s model %s refused temperature; asking again without it.", SERVICE, model)
            return True
        return False

    @staticmethod
    def _convert(resp: dict, model: str, mode: str | None) -> dict[str, Any]:
        text, calls = "", []
        for block in resp.get("output", {}).get("message", {}).get("content", []):
            if "text" in block:
                text += block["text"]
            elif "toolUse" in block:
                use = block["toolUse"]
                if mode == "tool" and use.get("name") == ANSWER_TOOL:
                    text = json.dumps(use.get("input") or {})
                else:
                    calls.append({"function": {"name": use["name"], "arguments": dict(use.get("input") or {})}})
        if mode in ("native", "prompt"):
            text = _json_from_text(text)
        usage = resp.get("usage") or {}
        return {
            "model": model,
            "message": {"role": "assistant", "content": strip_thinking(text), **({"tool_calls": calls} if calls else {})},
            "done": True,
            "done_reason": _STOP.get(resp.get("stopReason") or "end_turn", resp.get("stopReason")),
            "prompt_eval_count": usage.get("inputTokens"),
            "eval_count": usage.get("outputTokens"),
        }

    # ------------------------------------------------------------------ chat
    async def chat(self, messages, model, temperature=0.0, num_ctx=None, json_schema=None, num_predict=None,
                   tools=None) -> dict[str, Any]:
        if not json_schema:
            modes: tuple[str | None, ...] = (None,)
        elif model in self._structured:
            modes = (self._structured[model],)
        else:
            modes = STRUCTURED_MODES
        last: Exception | None = None
        for mode in modes:
            for _ in range(2):           # second try only after learning "no temperature"
                params = self._params(model, messages, temperature, num_predict, tools, mode, json_schema)
                try:
                    resp = await asyncio.to_thread(self._client.converse, **params)
                except Exception as exc:
                    if self._learn_temperature(model, exc):
                        continue
                    last = exc
                    break
                if mode:
                    if self._structured.get(model) != mode:
                        logger.info("%s model %s: structured output via %s", SERVICE, model, mode)
                    self._structured[model] = mode
                out = self._convert(resp, model, mode)
                logger.info("chat <- %s model=%s prompt_tokens=%s output_tokens=%s", SERVICE, model,
                            out["prompt_eval_count"], out["eval_count"])
                return out
            if last is not None and not (json_schema and _is_validation(last)):
                break                     # only a refused structured-output mode moves on to the next mode
        raise to_error(last) from last

    async def chat_stream(self, messages, model, tools=None, temperature=0.0, num_ctx=None,
                          num_predict=None) -> AsyncIterator[dict[str, Any]]:
        for attempt in (1, 2):
            params = self._params(model, messages, temperature, num_predict, tools, None, None)
            try:
                resp = await asyncio.to_thread(self._client.converse_stream, **params)
                break
            except Exception as exc:
                if attempt == 1 and self._learn_temperature(model, exc):
                    continue
                raise to_error(exc) from exc

        calls: dict[int, dict[str, Any]] = {}      # tool calls arrive in pieces, keyed by content block index
        stop, usage = None, {}
        async for event in _drain_in_thread(resp["stream"]):
            if "contentBlockStart" in event:
                start = event["contentBlockStart"]
                use = (start.get("start") or {}).get("toolUse")
                if use:
                    calls[start.get("contentBlockIndex", len(calls))] = {"name": use.get("name", ""), "input": ""}
            elif "contentBlockDelta" in event:
                delta = event["contentBlockDelta"]
                d = delta.get("delta") or {}
                if d.get("text"):
                    yield {"message": {"role": "assistant", "content": d["text"]}, "done": False}
                elif "toolUse" in d:
                    slot = calls.setdefault(delta.get("contentBlockIndex", len(calls)), {"name": "", "input": ""})
                    slot["input"] += d["toolUse"].get("input") or ""
            elif "messageStop" in event:
                stop = event["messageStop"].get("stopReason")
            elif "metadata" in event:
                usage = event["metadata"].get("usage") or {}
        if calls:
            yield {"message": {"role": "assistant", "content": "", "tool_calls": [
                {"function": {"name": c["name"], "arguments": _parse_json_object(c["input"])}}
                for _, c in sorted(calls.items()) if c["name"]]}, "done": False}
        yield {"message": {"role": "assistant", "content": ""}, "done": True,
               "done_reason": _STOP.get(stop or "end_turn", stop),
               "prompt_eval_count": usage.get("inputTokens"), "eval_count": usage.get("outputTokens")}

    # ------------------------------------------------------------------ embeddings
    async def embed(self, texts: list[str], model: str, kind: str = "document",
                    dimensions: int | None = None) -> list[list[float]]:
        family = model_family(model)
        if family.startswith("amazon.titan-embed"):
            limit = asyncio.Semaphore(EMBED_CONCURRENCY)

            async def one(text: str) -> list[float]:
                body: dict[str, Any] = {"inputText": text}
                if "v2" in family:
                    body["normalize"] = True
                    if dimensions:
                        body["dimensions"] = dimensions          # 256, 512 or 1024
                async with limit:
                    return (await self._invoke(model, body))["embedding"]
            return list(await asyncio.gather(*(one(t) for t in texts)))
        if family.startswith("cohere.embed"):
            vectors: list[list[float]] = []
            for i in range(0, len(texts), COHERE_BATCH):
                body = {"texts": texts[i:i + COHERE_BATCH], "truncate": "END",
                        "input_type": "search_query" if kind == "query" else "search_document"}
                if "v4" in family:
                    body["embedding_types"] = ["float"]
                    if dimensions:
                        body["output_dimension"] = dimensions
                data = (await self._invoke(model, body))["embeddings"]
                vectors.extend(data["float"] if isinstance(data, dict) else data)
            return vectors
        raise LLMError(f"{SERVICE}: {model} is not a supported embedding model here "
                       "(amazon.titan-embed-text-v2:0, amazon.titan-embed-text-v1, cohere.embed-* )",
                       retryable=False)

    async def _invoke(self, model: str, body: dict) -> dict:
        try:
            resp = await asyncio.to_thread(self._client.invoke_model, modelId=model, body=json.dumps(body),
                                           contentType="application/json", accept="application/json")
            return json.loads(await asyncio.to_thread(resp["body"].read))
        except Exception as exc:
            raise to_error(exc) from exc


_PROFILE_PREFIXES = ("us.", "eu.", "apac.", "global.", "jp.", "au.", "ca.", "us-gov.")


def model_family(model: str) -> str:
    """'apac.amazon.titan-embed-text-v2:0' (an inference profile) -> 'amazon.titan-embed-text-v2:0'."""
    return next((model[len(p):] for p in _PROFILE_PREFIXES if model.startswith(p)), model)


def _parse_json_object(raw: str) -> dict:
    try:
        value = json.loads(raw or "{}")
        return value if isinstance(value, dict) else {}
    except ValueError:
        return {}


async def _drain_in_thread(stream) -> AsyncIterator[dict]:
    """
    Read a botocore EventStream (blocking) in a thread and yield its events here. If the consumer stops early
    (the user pressed stop, the agent loop ended), the stream is closed and the thread ends.
    """
    loop = asyncio.get_running_loop()
    queue: asyncio.Queue = asyncio.Queue(maxsize=64)
    stopped = threading.Event()
    done = object()

    def put(item) -> None:
        asyncio.run_coroutine_threadsafe(queue.put(item), loop).result()

    def reader() -> None:
        try:
            for event in stream:
                if stopped.is_set():
                    break
                put(event)
            put(done)
        except BaseException as exc:            # delivered to the consumer, translated there
            if not stopped.is_set():
                put(exc)
        finally:
            try:
                stream.close()
            except Exception:
                pass

    thread = threading.Thread(target=reader, name="bedrock-stream", daemon=True)
    thread.start()
    try:
        while True:
            item = await queue.get()
            if item is done:
                return
            if isinstance(item, BaseException):
                raise to_error(item) from item
            yield item
    finally:
        stopped.set()
        while not queue.empty():                 # unblock a reader waiting on a full queue
            queue.get_nowait()
