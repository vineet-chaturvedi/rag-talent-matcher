"""An in-process stand-in for the model client (any provider): valid structured answers, hashed embeddings."""
import asyncio
import hashlib
import json
import math
import re

from tests.fakes.cloud_models import instance


def vec(text: str, dim: int = 64) -> list[float]:
    v = [0.0] * dim
    for w in re.findall(r"[a-z0-9+#]+", text.lower()):
        v[int(hashlib.md5(w.encode()).hexdigest(), 16) % dim] += 1
    n = math.sqrt(sum(x * x for x in v)) or 1
    return [x / n for x in v]


class FakeModels:
    """chat() answers any JSON schema with a minimal valid object; embed() is deterministic.
    block: an asyncio.Event; when set, chat() waits until it is cleared... (used to hold a job mid-stage)."""

    def __init__(self):
        self.calls: list[str] = []
        self.hold: asyncio.Event | None = None     # while set, chat() waits (a job "in the middle" of an LLM step)
        self.down = False                          # True: the model service is unreachable

    async def chat(self, messages, model, temperature=0.0, num_ctx=None, json_schema=None, num_predict=None,
                   tools=None):
        from app.llm.errors import LLMError

        self.calls.append("chat")
        if self.down:
            raise LLMError("Cannot reach Ollama")
        if self.hold is not None:
            await self.hold.wait()
        content = json.dumps(instance(json_schema)) if json_schema else "ok"
        return {"message": {"role": "assistant", "content": content}, "done": True, "done_reason": "stop",
                "prompt_eval_count": 10, "eval_count": 5, "eval_duration": 1_000_000}

    async def embed(self, texts, model, kind="document"):
        self.calls.append("embed")
        return [vec(t) for t in texts]

    async def close(self):
        pass
