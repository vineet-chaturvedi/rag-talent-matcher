"""Amazon Bedrock (app/llm/bedrock.py) through the router, with the real boto3 against the stand-in."""
import asyncio
import json

import pytest

from app.agent.tools import tool_specs
from app.extraction.schema import ResumeExtraction
from app.llm.bedrock import model_family, to_converse
from app.llm.errors import LLMError
from app.llm.router import ModelRouter
from app.matching.judge import JUDGE_SCHEMA
from tests.conftest import make_settings
from tests.fakes.cloud_models import CALLS

QUESTION = [{"role": "system", "content": "You are a staffing assistant."},
            {"role": "user", "content": "Who knows Kubernetes?"}]


@pytest.fixture
async def router(cloud_url, aws_env):
    r = ModelRouter(make_settings(allow_cloud_models=True, aws_region="ap-south-1",
                                  bedrock_endpoint_url=cloud_url, cloud_timeout_seconds=20))
    yield r
    await r.close()


def after_tool(calls):
    return QUESTION + [{"role": "assistant", "content": "", "tool_calls": calls},
                       {"role": "tool", "tool_name": "find_candidates",
                        "content": json.dumps({"candidates": [{"summary": "EMP-1003 Priya: Kubernetes 6.2 y"}]})}]


async def test_tool_call_then_answer(router):
    d = await router.chat(QUESTION, "bedrock/anthropic.claude-x", tools=tool_specs(), num_predict=200)
    calls = d["message"]["tool_calls"]
    assert calls[0]["function"] == {"name": "find_candidates", "arguments": {"must_have": ["Kubernetes"], "top_k": 3}}
    d2 = await router.chat(after_tool(calls), "bedrock/anthropic.claude-x", tools=tool_specs())
    assert "EMP-1003" in d2["message"]["content"]
    assert (d2["prompt_eval_count"], d2["eval_count"], d2["done_reason"]) == (100, 20, "stop")
    sent = next(c for c in reversed(CALLS) if c["api"] == "converse")
    assert sent["system"] == [{"text": "You are a staffing assistant."}]
    assert sent["inference"] == {"temperature": 0.0, "maxTokens": 4096}     # BEDROCK_MAX_TOKENS default


async def test_streaming_tool_call_and_answer(router):
    chunks = [c async for c in router.chat_stream(QUESTION, "bedrock/meta.llama-x", tools=tool_specs())]
    calls = [tc for c in chunks for tc in c["message"].get("tool_calls") or []]
    assert calls == [{"function": {"name": "find_candidates", "arguments": {"must_have": ["Kubernetes"], "top_k": 3}}}]
    assert chunks[-1]["done"] and chunks[-1]["prompt_eval_count"] == 100
    chunks = [c async for c in router.chat_stream(after_tool(calls), "bedrock/meta.llama-x", tools=tool_specs())]
    text = "".join(c["message"]["content"] for c in chunks)
    assert text == "The best match is EMP-1003." and len(chunks) > 4


async def test_stream_stopped_early_does_not_hang(router):
    async def first_two():
        out = []
        async for c in router.chat_stream(after_tool([{"function": {"name": "find_candidates", "arguments": {}}}]),
                                          "bedrock/meta.llama-x", tools=tool_specs()):
            out.append(c)
            if len(out) == 2:
                break
        return out
    assert len(await asyncio.wait_for(first_two(), timeout=10)) == 2


@pytest.mark.parametrize("model, expected_mode", [
    ("bedrock/anthropic.claude-x", "native"),
    ("bedrock/mistral.nonative-x", "tool"),
    ("bedrock/meta.notool-x", "prompt"),
])
async def test_structured_output_modes(router, model, expected_mode):
    for schema, cls in ((ResumeExtraction.model_json_schema(), ResumeExtraction), (JUDGE_SCHEMA, None)):
        d = await router.chat([{"role": "user", "content": "Extract."}], model, json_schema=schema)
        data = json.loads(d["message"]["content"])
        if cls:
            cls.model_validate(data)
        assert isinstance(data, dict)
    provider = router._chat_provider("bedrock")
    assert provider._structured[model.split("/", 1)[1]] == expected_mode
    # remembered: the next structured call goes straight to the working mode (one request, no refusals)
    before = len(CALLS)
    await router.chat([{"role": "user", "content": "Again."}], model, json_schema=JUDGE_SCHEMA)
    assert [c["api"] for c in CALLS[before:]] == ["converse"]


async def test_temperature_refused_is_dropped(router):
    d = await router.chat(QUESTION, "bedrock/deepseek.notemp-x")
    assert d["message"]["content"] == "Hello from the stand-in model."
    assert "temperature" not in (next(c for c in reversed(CALLS) if c["api"] == "converse")["inference"] or {})


async def test_tool_history_without_tools_is_written_as_text(router):
    history = after_tool([{"function": {"name": "find_candidates", "arguments": {"must_have": ["Go"]}}}])
    d = await router.chat(history + [{"role": "user", "content": "Thanks"}], "bedrock/anthropic.claude-x")
    assert d["message"]["content"]          # no "toolConfig must be defined" refusal


async def test_throttling_is_retryable(router):
    with pytest.raises(LLMError) as err:
        await router.chat(QUESTION, "bedrock/x.throttle")
    assert err.value.retryable and "ThrottlingException" in str(err.value)


async def test_embeddings(router):
    r = ModelRouter(make_settings(allow_cloud_models=True, aws_region="ap-south-1", embed_dimensions=256,
                                  bedrock_endpoint_url=router.settings.bedrock_endpoint_url))
    try:
        v = await r.embed(["a resume chunk", "another chunk"], "bedrock/amazon.titan-embed-text-v2:0")
        assert len(v) == 2 and len(v[0]) == 256
        texts = [f"chunk {i}" for i in range(100)]
        before = len(CALLS)
        v = await r.embed(texts, "bedrock/cohere.embed-v4:0", "query")
        sent = [c for c in CALLS[before:] if c["api"] == "invoke"]
        assert len(v) == 100 and len(v[0]) == 256 and [len(c["body"]["texts"]) for c in sent] == [96, 4]
        assert {c["body"]["input_type"] for c in sent} == {"search_query"}
        v = await r.embed(["x"], "bedrock/cohere.embed-multilingual-v3")
        assert len(v[0]) == 1024                          # v3: plain list of vectors
        with pytest.raises(LLMError) as err:
            await r.embed(["x"], "bedrock/acme.unknown-embed")
        assert not err.value.retryable
    finally:
        await r.close()


async def test_cloud_switch_and_configuration(aws_env, monkeypatch, cloud_url):
    blocked = ModelRouter(make_settings(allow_cloud_models=False, aws_region="ap-south-1"))
    with pytest.raises(LLMError, match="ALLOW_CLOUD_MODELS"):
        await blocked.chat(QUESTION, "bedrock/anthropic.claude-x")
    monkeypatch.delenv("AWS_REGION", raising=False)
    monkeypatch.delenv("AWS_DEFAULT_REGION", raising=False)
    no_region = ModelRouter(make_settings(allow_cloud_models=True))
    assert no_region.configuration_problem("bedrock/anthropic.claude-x") == "AWS_REGION is not set"
    ok = ModelRouter(make_settings(allow_cloud_models=True, aws_region="eu-west-1"))
    assert ok.configuration_problem("bedrock/anthropic.claude-x") is None
    assert ok.model_health("bedrock/amazon.titan-embed-text-v2:0", None, "embed")["provider"] == "Amazon Bedrock"
    await blocked.close(); await no_region.close(); await ok.close()


def test_message_translation_rules():
    system, msgs = to_converse([
        {"role": "system", "content": "rules"},
        {"role": "assistant", "content": "Hi"},                       # must not start the conversation
        {"role": "user", "content": "a"}, {"role": "user", "content": "b"},   # merged: roles alternate
        {"role": "assistant", "content": "", "tool_calls": [{"function": {"name": "f", "arguments": '{"x": 1}'}}]},
        {"role": "tool", "content": "result"},
    ], with_tools=True)
    assert system == [{"text": "rules"}]
    assert [m["role"] for m in msgs] == ["user", "assistant", "user", "assistant", "user"]
    assert msgs[2]["content"] == [{"text": "a"}, {"text": "b"}]
    assert msgs[3]["content"] == [{"toolUse": {"toolUseId": "tooluse_0001", "name": "f", "input": {"x": 1}}}]
    assert msgs[4]["content"][0]["toolResult"]["toolUseId"] == "tooluse_0001"
    assert model_family("apac.amazon.titan-embed-text-v2:0") == "amazon.titan-embed-text-v2:0"
