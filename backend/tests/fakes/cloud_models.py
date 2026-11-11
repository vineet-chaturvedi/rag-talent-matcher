"""
A stand-in for Amazon Bedrock and Google Vertex AI, served over real HTTP so the REAL SDKs (boto3,
google-auth, openai, anthropic) are tested end to end. Only the network is faked.

It answers like the services AND checks our requests the way they do (alternating roles, no empty text
blocks, tool results matched to tool calls, tool blocks only with a toolConfig, a valid OAuth token ...),
answering 400 on a violation so a test fails loudly instead of passing on a request the real service refuses.

Scripted behaviour (shared by every API):
  last turn is the user + tools offered  -> calls find_candidates({"must_have": ["Kubernetes"]})
  last turn is a tool result             -> answers with the first EMP-code in the result
  a JSON schema requested                -> a minimal object that satisfies it
Special model names make the service refuse things, to test the fallbacks:
  *notemp*        refuses temperature              *nonative*   refuses outputConfig (structured output)
  *notool*        refuses toolChoice (and nonative)  *throttle*  always 429 ThrottlingException
"""
import binascii
import hashlib
import json
import math
import re
import struct
import time
from urllib.parse import unquote

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response, StreamingResponse

TOKEN = "ya29.fake-google-token"
CALLS: list[dict] = []          # every request, for assertions


def vec(text: str, dim: int) -> list[float]:
    v = [0.0] * dim
    for w in re.findall(r"[a-z0-9+#]+", text.lower()):
        v[int(hashlib.md5(w.encode()).hexdigest(), 16) % dim] += 1
    n = math.sqrt(sum(x * x for x in v)) or 1
    return [x / n for x in v]


def instance(schema: dict, root: dict | None = None):
    """A minimal object that satisfies a JSON schema."""
    root = root or schema
    if "$ref" in schema:
        return instance(root.get("$defs", {})[schema["$ref"].split("/")[-1]], root)
    if "anyOf" in schema:
        return instance(next((s for s in schema["anyOf"] if s.get("type") != "null"), schema["anyOf"][0]), root)
    if "enum" in schema:
        return schema["enum"][0]
    t = schema.get("type")
    if t == "object" or "properties" in schema:
        return {k: instance(v, root) for k, v in schema.get("properties", {}).items()}
    return {"array": [], "string": "evidence", "integer": 1, "number": 0.5, "boolean": True}.get(t)


def has_ref(node) -> bool:
    if isinstance(node, dict):
        return "$ref" in node or any(has_ref(v) for v in node.values())
    if isinstance(node, list):
        return any(has_ref(v) for v in node)
    return False


def brain(tool_result: str | None, tools_offered: bool) -> tuple[dict | None, str]:
    """-> (tool call {"name", "input"} or None, answer text)"""
    if tool_result is not None:
        code = re.search(r"EMP-\d+", tool_result)
        return None, f"The best match is {code.group(0) if code else 'nobody'}."
    if tools_offered:
        return {"name": "find_candidates", "input": {"must_have": ["Kubernetes"], "top_k": 3}}, ""
    return None, "Hello from the stand-in model."


# =========================================================================== AWS event stream (ConverseStream)
def _header(name: str, value: str) -> bytes:
    n, v = name.encode(), value.encode()
    return struct.pack("B", len(n)) + n + b"\x07" + struct.pack(">H", len(v)) + v


def event_message(event_type: str, payload: dict, message_type: str = "event") -> bytes:
    """One message of the AWS event-stream binary format: prelude, CRC, headers, payload, CRC."""
    if message_type == "exception":
        headers = _header(":message-type", "exception") + _header(":exception-type", event_type)
    else:
        headers = _header(":message-type", "event") + _header(":event-type", event_type)
    headers += _header(":content-type", "application/json")
    body = json.dumps(payload).encode()
    total = 12 + len(headers) + len(body) + 4
    prelude = struct.pack(">II", total, len(headers))
    prelude += struct.pack(">I", binascii.crc32(prelude) & 0xFFFFFFFF)
    message = prelude + headers + body
    return message + struct.pack(">I", binascii.crc32(message) & 0xFFFFFFFF)


# =========================================================================== the app
def make_app() -> FastAPI:
    app = FastAPI()

    def aws_error(code: str, message: str, status: int = 400) -> JSONResponse:
        CALLS.append({"api": "bedrock-error", "code": code, "message": message})
        return JSONResponse({"message": message}, status_code=status, headers={"x-amzn-ErrorType": code})

    # ------------------------------------------------------------------ Bedrock: Converse
    def check_converse(model: str, b: dict) -> JSONResponse | None:
        msgs = b.get("messages") or []
        if not msgs or msgs[0]["role"] != "user":
            return aws_error("ValidationException", "A conversation must start with a user message.")
        for a, c in zip(msgs, msgs[1:]):
            if a["role"] == c["role"]:
                return aws_error("ValidationException", "A conversation must alternate between user and assistant roles.")
        open_ids: list[str] = []
        has_tool_blocks = False
        for m in msgs:
            for blk in m["content"]:
                if "text" in blk and not blk["text"].strip():
                    return aws_error("ValidationException", "The text field in the ContentBlock object is blank.")
                if "toolUse" in blk:
                    has_tool_blocks = True
                    open_ids.append(blk["toolUse"]["toolUseId"])
                if "toolResult" in blk:
                    has_tool_blocks = True
                    if blk["toolResult"]["toolUseId"] not in open_ids:
                        return aws_error("ValidationException", "toolResult without a matching toolUse")
                    open_ids.remove(blk["toolResult"]["toolUseId"])
        tool_config = b.get("toolConfig")
        if has_tool_blocks and not tool_config:
            return aws_error("ValidationException", "The toolConfig field must be defined when using toolUse and toolResult content blocks.")
        if "notemp" in model and "temperature" in (b.get("inferenceConfig") or {}):
            return aws_error("ValidationException", "temperature is not supported by this model.")
        if ("nonative" in model or "notool" in model) and b.get("outputConfig"):
            return aws_error("ValidationException", "This model doesn't support structured output (outputConfig).")
        if "notool" in model and tool_config and "toolChoice" in tool_config:
            return aws_error("ValidationException", "This model doesn't support the toolChoice field.")
        for t in (tool_config or {}).get("tools", []):
            if has_ref(t["toolSpec"]["inputSchema"]["json"]):
                return aws_error("ValidationException", "inputSchema must not contain $ref")
        if "throttle" in model:
            return aws_error("ThrottlingException", "Too many requests, please wait before trying again.", 429)
        return None

    def converse_answer(model: str, b: dict) -> tuple[list[dict], str]:
        msgs = b["messages"]
        CALLS.append({"api": "converse", "model": model, "keys": sorted(b), "inference": b.get("inferenceConfig"),
                      "tool_choice": (b.get("toolConfig") or {}).get("toolChoice"),
                      "output_config": bool(b.get("outputConfig")), "system": b.get("system")})
        if b.get("outputConfig"):
            schema = json.loads(b["outputConfig"]["textFormat"]["structure"]["jsonSchema"]["schema"])
            return [{"text": json.dumps(instance(schema))}], "end_turn"
        choice = (b.get("toolConfig") or {}).get("toolChoice") or {}
        if "tool" in choice:
            spec = next(t["toolSpec"] for t in b["toolConfig"]["tools"] if t["toolSpec"]["name"] == choice["tool"]["name"])
            return [{"toolUse": {"toolUseId": "tu_ans", "name": spec["name"],
                                 "input": instance(spec["inputSchema"]["json"])}}], "tool_use"
        system = " ".join(s["text"] for s in b.get("system", []))
        if "JSON schema" in system:     # prompt mode: answer JSON wrapped in prose and a code fence
            schema = json.loads(system.split("\n", 1)[1])
            return [{"text": "Here it is:\n```json\n" + json.dumps(instance(schema)) + "\n```"}], "end_turn"
        last = msgs[-1]["content"]
        result = next((blk["toolResult"]["content"][0]["text"] for blk in reversed(last) if "toolResult" in blk), None)
        call, text = brain(result, bool(b.get("toolConfig")))
        if call:
            return [{"toolUse": {"toolUseId": "tu_1", **call}}], "tool_use"
        return [{"text": text}], "end_turn"

    @app.post("/model/{model_id:path}/converse")
    async def converse(model_id: str, r: Request):
        model, b = unquote(model_id), await r.json()
        if not r.headers.get("authorization", "").startswith("AWS4-HMAC-SHA256"):
            return aws_error("UnrecognizedClientException", "The security token included in the request is invalid.", 403)
        if err := check_converse(model, b):
            return err
        content, stop = converse_answer(model, b)
        return {"output": {"message": {"role": "assistant", "content": content}}, "stopReason": stop,
                "usage": {"inputTokens": 100, "outputTokens": 20, "totalTokens": 120}, "metrics": {"latencyMs": 5}}

    @app.post("/model/{model_id:path}/converse-stream")
    async def converse_stream(model_id: str, r: Request):
        model, b = unquote(model_id), await r.json()
        if err := check_converse(model, b):
            return err
        content, stop = converse_answer(model, b)

        def gen():
            yield event_message("messageStart", {"role": "assistant"})
            for i, blk in enumerate(content):
                if "text" in blk:
                    for word in re.split(r"(\s+)", blk["text"]):
                        if word:
                            yield event_message("contentBlockDelta", {"contentBlockIndex": i, "delta": {"text": word}})
                else:
                    use = blk["toolUse"]
                    yield event_message("contentBlockStart", {"contentBlockIndex": i, "start": {
                        "toolUse": {"toolUseId": use["toolUseId"], "name": use["name"]}}})
                    raw = json.dumps(use["input"])
                    for piece in (raw[: len(raw) // 2], raw[len(raw) // 2:]):
                        yield event_message("contentBlockDelta", {"contentBlockIndex": i,
                                                                  "delta": {"toolUse": {"input": piece}}})
                yield event_message("contentBlockStop", {"contentBlockIndex": i})
            yield event_message("messageStop", {"stopReason": stop})
            yield event_message("metadata", {"usage": {"inputTokens": 100, "outputTokens": 20, "totalTokens": 120},
                                             "metrics": {"latencyMs": 5}})
        return StreamingResponse(gen(), media_type="application/vnd.amazon.eventstream")

    @app.post("/model/{model_id:path}/invoke")
    async def invoke(model_id: str, r: Request):
        model, b = unquote(model_id), json.loads(await r.body())
        CALLS.append({"api": "invoke", "model": model, "body": b})
        if model.startswith("amazon.titan-embed-text-v2"):
            if set(b) - {"inputText", "dimensions", "normalize"} or not isinstance(b.get("inputText"), str):
                return aws_error("ValidationException", "Malformed input request")
            return {"embedding": vec(b["inputText"], b.get("dimensions") or 1024), "inputTextTokenCount": 5}
        if model.startswith("cohere.embed"):
            if b.get("input_type") not in ("search_query", "search_document") or len(b["texts"]) > 96:
                return aws_error("ValidationException", "Malformed input request")
            dim = b.get("output_dimension") or 1024
            vectors = [vec(t, dim) for t in b["texts"]]
            embeddings = {"float": vectors} if b.get("embedding_types") else vectors
            return {"id": "e1", "embeddings": embeddings, "texts": b["texts"], "response_type": "embeddings_floats"}
        return aws_error("ValidationException", f"The provided model identifier is invalid: {model}")

    # ------------------------------------------------------------------ Google OAuth token endpoint
    @app.post("/token")
    async def token(r: Request):
        form = await r.form()
        if form.get("grant_type") != "urn:ietf:params:oauth:grant-type:jwt-bearer" or not form.get("assertion"):
            return JSONResponse({"error": "invalid_grant"}, status_code=400)
        CALLS.append({"api": "google-token"})
        return {"access_token": TOKEN, "expires_in": 3600, "token_type": "Bearer"}

    def google_auth_ok(r: Request) -> bool:
        return r.headers.get("authorization") == f"Bearer {TOKEN}"

    # ------------------------------------------------------------------ Vertex: OpenAI-compatible chat
    @app.post("/v1/projects/{project}/locations/{location}/endpoints/openapi/chat/completions")
    async def vertex_chat(project: str, location: str, r: Request):
        if not google_auth_ok(r):
            return JSONResponse({"error": {"code": 401, "message": "Request had invalid authentication credentials."}},
                                status_code=401)
        b = await r.json()
        model, msgs = b["model"], b["messages"]
        CALLS.append({"api": "vertex-chat", "project": project, "location": location, "model": model,
                      "stream": b.get("stream", False), "response_format": (b.get("response_format") or {}).get("type")})
        if "/" not in model:
            return JSONResponse({"error": {"code": 400, "message": "model must be <publisher>/<model>"}}, status_code=400)
        open_ids: list[str] = []
        for m in msgs:
            for c in m.get("tool_calls") or []:
                open_ids.append(c["id"])
            if m["role"] == "tool":
                if m.get("tool_call_id") not in open_ids:
                    return JSONResponse({"error": {"code": 400, "message": "tool_call_id without a call"}}, status_code=400)
                open_ids.remove(m["tool_call_id"])
        rf = b.get("response_format")
        call = None
        if rf and rf.get("type") == "json_schema":
            text = json.dumps(instance(rf["json_schema"]["schema"]))
        else:
            last = msgs[-1]
            call, text = brain(last["content"] if last["role"] == "tool" else None, bool(b.get("tools")))
        usage = {"prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120}
        if b.get("stream"):
            def gen():
                base = {"id": "c1", "object": "chat.completion.chunk", "created": 1, "model": model}
                if call:
                    raw = json.dumps(call["input"])
                    yield "data: " + json.dumps({**base, "choices": [{"index": 0, "delta": {"role": "assistant", "tool_calls": [
                        {"index": 0, "id": "c0", "type": "function",
                         "function": {"name": call["name"], "arguments": raw[:5]}}]}, "finish_reason": None}]}) + "\n\n"
                    yield "data: " + json.dumps({**base, "choices": [{"index": 0, "delta": {"tool_calls": [
                        {"index": 0, "function": {"arguments": raw[5:]}}]}, "finish_reason": None}]}) + "\n\n"
                else:
                    for word in re.split(r"(\s+)", text):
                        if word:
                            yield "data: " + json.dumps({**base, "choices": [{"index": 0, "delta": {"content": word},
                                                                               "finish_reason": None}]}) + "\n\n"
                yield "data: " + json.dumps({**base, "choices": [{"index": 0, "delta": {},
                                                                   "finish_reason": "tool_calls" if call else "stop"}]}) + "\n\n"
                yield "data: " + json.dumps({**base, "choices": [], "usage": usage}) + "\n\n"
                yield "data: [DONE]\n\n"
            return StreamingResponse(gen(), media_type="text/event-stream")
        msg: dict = {"role": "assistant", "content": None if call else text}
        if call:
            msg["tool_calls"] = [{"id": "c0", "type": "function",
                                  "function": {"name": call["name"], "arguments": json.dumps(call["input"])}}]
        return {"id": "c1", "object": "chat.completion", "created": 1, "model": model, "usage": usage,
                "choices": [{"index": 0, "message": msg, "finish_reason": "tool_calls" if call else "stop"}]}

    # ------------------------------------------------------------------ Vertex: embeddings (:predict)
    @app.post("/v1/projects/{project}/locations/{location}/publishers/google/models/{model}:predict")
    async def vertex_predict(project: str, location: str, model: str, r: Request):
        if not google_auth_ok(r):
            return JSONResponse({"error": {"code": 401}}, status_code=401)
        b = await r.json()
        instances = b["instances"]
        CALLS.append({"api": "vertex-embed", "model": model, "n": len(instances),
                      "task": sorted({i["task_type"] for i in instances}), "params": b.get("parameters")})
        if model.startswith("gemini-embedding") and len(instances) > 1:
            return JSONResponse({"error": {"code": 400, "message": "Only one instance per request"}}, status_code=400)
        dim = (b.get("parameters") or {}).get("outputDimensionality") or 768
        return {"predictions": [{"embeddings": {"values": vec(i["content"], dim),
                                                "statistics": {"token_count": 5, "truncated": False}}}
                                for i in instances]}

    # ------------------------------------------------------------------ Vertex: Claude (Anthropic API)
    @app.post("/v1/projects/{project}/locations/{region}/publishers/anthropic/models/{model_action}")
    async def vertex_claude(project: str, region: str, model_action: str, r: Request):
        if not google_auth_ok(r):
            return JSONResponse({"type": "error", "error": {"type": "authentication_error"}}, status_code=401)
        model, _, action = model_action.partition(":")
        b = await r.json()
        CALLS.append({"api": "vertex-claude", "region": region, "model": model, "action": action,
                      "version": b.get("anthropic_version"), "tool_choice": b.get("tool_choice")})
        # Vertex wants the version in the body and the model in the URL, never in the body
        if not b.get("anthropic_version") or "model" in b or "max_tokens" not in b:
            return JSONResponse({"type": "error", "error": {"type": "invalid_request_error",
                                                            "message": "bad Vertex request"}}, status_code=400)
        msgs = b["messages"]
        for a, c in zip(msgs, msgs[1:]):
            if a["role"] == c["role"]:
                return JSONResponse({"type": "error", "error": {"type": "invalid_request_error",
                                                                "message": "roles must alternate"}}, status_code=400)
        tc = b.get("tool_choice") or {}
        if tc.get("type") == "tool":
            schema = next(t["input_schema"] for t in b["tools"] if t["name"] == tc["name"])
            content, stop = [{"type": "tool_use", "id": "toolu_ans", "name": tc["name"], "input": instance(schema)}], "tool_use"
        else:
            last = msgs[-1]["content"]
            blocks = last if isinstance(last, list) else [{"type": "text", "text": last}]
            result = next((blk["content"] for blk in reversed(blocks) if blk["type"] == "tool_result"), None)
            call, text = brain(result, bool(b.get("tools")))
            if call:
                content, stop = [{"type": "tool_use", "id": "toolu_1", **call}], "tool_use"
            else:
                content, stop = [{"type": "text", "text": text}], "end_turn"
        message = {"id": "msg_1", "type": "message", "role": "assistant", "model": model, "content": content,
                   "stop_reason": stop, "stop_sequence": None, "usage": {"input_tokens": 100, "output_tokens": 20}}
        if action == "rawPredict":
            return message

        def ev(name: str, data: dict) -> str:
            return f"event: {name}\ndata: {json.dumps(data)}\n\n"

        def gen():
            yield ev("message_start", {"type": "message_start", "message": {
                **message, "content": [], "stop_reason": None, "usage": {"input_tokens": 100, "output_tokens": 1}}})
            for i, blk in enumerate(content):
                if blk["type"] == "text":
                    yield ev("content_block_start", {"type": "content_block_start", "index": i,
                                                     "content_block": {"type": "text", "text": ""}})
                    for word in re.split(r"(\s+)", blk["text"]):
                        if word:
                            yield ev("content_block_delta", {"type": "content_block_delta", "index": i,
                                                             "delta": {"type": "text_delta", "text": word}})
                else:
                    yield ev("content_block_start", {"type": "content_block_start", "index": i, "content_block": {
                        "type": "tool_use", "id": blk["id"], "name": blk["name"], "input": {}}})
                    yield ev("content_block_delta", {"type": "content_block_delta", "index": i, "delta": {
                        "type": "input_json_delta", "partial_json": json.dumps(blk["input"])}})
                yield ev("content_block_stop", {"type": "content_block_stop", "index": i})
            yield ev("message_delta", {"type": "message_delta", "delta": {"stop_reason": stop, "stop_sequence": None},
                                       "usage": {"output_tokens": 20}})
            yield ev("message_stop", {"type": "message_stop"})
        return StreamingResponse(gen(), media_type="text/event-stream")

    @app.get("/health")
    async def health():
        return Response("ok")

    return app


def wait_until_up(port: int, timeout: float = 15.0) -> None:
    import httpx
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            if httpx.get(f"http://127.0.0.1:{port}/health", timeout=1).status_code == 200:
                return
        except httpx.HTTPError:
            time.sleep(0.1)
    raise RuntimeError("stand-in server did not start")
