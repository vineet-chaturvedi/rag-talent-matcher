"""Google Vertex AI (Gemini via the OpenAI-compatible endpoint, Claude via the Anthropic SDK, embeddings via
:predict) through the router, with real google-auth / openai / anthropic SDKs against the stand-in."""
import json

import pytest

from app.agent.tools import tool_specs
from app.extraction.schema import ResumeExtraction
from app.llm.errors import LLMError
from app.llm.router import ModelRouter, vertex_host
from app.matching.judge import JUDGE_SCHEMA
from tests.conftest import make_settings
from tests.fakes.cloud_models import CALLS

QUESTION = [{"role": "system", "content": "You are a staffing assistant."},
            {"role": "user", "content": "Who knows Kubernetes?"}]


@pytest.fixture
async def router(cloud_url, google_env):
    r = ModelRouter(make_settings(allow_cloud_models=True, vertex_project="talent-prod",
                                  vertex_location="asia-south1", vertex_claude_location="us-east5",
                                  vertex_base_url=f"{cloud_url}/v1", cloud_timeout_seconds=20))
    yield r
    await r.close()


def after_tool(calls):
    return QUESTION + [{"role": "assistant", "content": "", "tool_calls": calls},
                       {"role": "tool", "tool_name": "find_candidates",
                        "content": json.dumps({"candidates": [{"summary": "EMP-1003 Priya: Kubernetes 6.2 y"}]})}]


@pytest.mark.parametrize("model", ["vertex/gemini-2.5-flash", "vertex/claude-sonnet-4-5@20250929"])
async def test_chat_tools_stream_and_structured(router, model):
    d = await router.chat(QUESTION, model, tools=tool_specs())
    calls = d["message"]["tool_calls"]
    assert calls[0]["function"]["arguments"] == {"must_have": ["Kubernetes"], "top_k": 3}
    d2 = await router.chat(after_tool(calls), model, tools=tool_specs())
    assert "EMP-1003" in d2["message"]["content"] and d2["prompt_eval_count"] == 100

    chunks = [c async for c in router.chat_stream(QUESTION, model, tools=tool_specs())]
    assert [tc for c in chunks for tc in c["message"].get("tool_calls") or []][0]["function"]["name"] == "find_candidates"
    chunks = [c async for c in router.chat_stream(after_tool(calls), model, tools=tool_specs())]
    assert "".join(c["message"]["content"] for c in chunks) == "The best match is EMP-1003."

    d3 = await router.chat([{"role": "user", "content": "Extract."}], model,
                           json_schema=ResumeExtraction.model_json_schema())
    ResumeExtraction.model_validate_json(d3["message"]["content"])
    d4 = await router.chat([{"role": "user", "content": "Judge."}], model, json_schema=JUDGE_SCHEMA)
    assert isinstance(json.loads(d4["message"]["content"]), dict)


async def test_where_requests_go(router):
    await router.chat(QUESTION, "vertex/gemini-2.5-flash")
    await router.chat(QUESTION, "vertex/meta/llama-4-maverick-17b-128e-instruct-maas")
    await router.chat(QUESTION, "vertex/claude-sonnet-4-5@20250929")
    gemini, llama = [c for c in CALLS if c["api"] == "vertex-chat"][-2:]
    claude = next(c for c in reversed(CALLS) if c["api"] == "vertex-claude")
    assert (gemini["project"], gemini["location"], gemini["model"]) == ("talent-prod", "asia-south1", "google/gemini-2.5-flash")
    assert llama["model"] == "meta/llama-4-maverick-17b-128e-instruct-maas"       # publisher kept
    assert (claude["region"], claude["model"], claude["action"]) == ("us-east5", "claude-sonnet-4-5@20250929", "rawPredict")


async def test_token_is_fetched_once_and_reused(router):
    before = sum(c["api"] == "google-token" for c in CALLS)
    for _ in range(3):
        await router.chat(QUESTION, "vertex/gemini-2.5-flash")
    await router.embed(["x"], "vertex/text-embedding-005")
    assert sum(c["api"] == "google-token" for c in CALLS) - before <= 1


async def test_embeddings(router):
    before = len(CALLS)
    v = await router.embed(["chunk one", "chunk two", "chunk three"], "vertex/gemini-embedding-001")
    sent = [c for c in CALLS[before:] if c["api"] == "vertex-embed"]
    assert len(v) == 3 and len(v[0]) == 768 and [c["n"] for c in sent] == [1, 1, 1]   # one text per request
    before = len(CALLS)
    v = await router.embed([f"c{i}" for i in range(40)], "vertex/text-embedding-005", "query")
    sent = [c for c in CALLS[before:] if c["api"] == "vertex-embed"]
    assert len(v) == 40 and sorted(c["n"] for c in sent) == [8, 32] and sent[0]["task"] == ["RETRIEVAL_QUERY"]
    dims = ModelRouter(make_settings(allow_cloud_models=True, vertex_project="p", embed_dimensions=256,
                                     vertex_base_url=router.settings.vertex_base_url))
    try:
        assert len((await dims.embed(["x"], "vertex/gemini-embedding-001"))[0]) == 256
    finally:
        await dims.close()


async def test_configuration(google_env, monkeypatch):
    assert vertex_host("global") == "aiplatform.googleapis.com"
    assert vertex_host("asia-south1") == "asia-south1-aiplatform.googleapis.com"
    r = ModelRouter(make_settings(allow_cloud_models=True))
    assert r.configuration_problem("vertex/gemini-2.5-flash") == "VERTEX_PROJECT is not set"
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "from-env")
    assert r.configuration_problem("vertex/gemini-2.5-flash") is None
    blocked = ModelRouter(make_settings(allow_cloud_models=False, vertex_project="p"))
    with pytest.raises(LLMError, match="ALLOW_CLOUD_MODELS"):
        await blocked.embed(["x"], "vertex/gemini-embedding-001")
    await r.close(); await blocked.close()


async def test_project_comes_from_credentials_when_not_set(cloud_url, google_env):
    r = ModelRouter(make_settings(allow_cloud_models=True, vertex_base_url=f"{cloud_url}/v1"))
    try:
        await r.chat(QUESTION, "vertex/gemini-2.5-flash")
        assert next(c for c in reversed(CALLS) if c["api"] == "vertex-chat")["project"] == "adc-project"
    finally:
        await r.close()


async def test_missing_credentials_is_a_clear_error(monkeypatch, tmp_path):
    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", str(tmp_path / "missing.json"))
    r = ModelRouter(make_settings(allow_cloud_models=True, vertex_project="p"))
    with pytest.raises(LLMError, match="Google credentials"):
        await r.chat(QUESTION, "vertex/gemini-2.5-flash")
    await r.close()
