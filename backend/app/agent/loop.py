"""
The agent loop (Step 10): an LLM that decides, step by step, which tool to use until it can answer.

    messages = [system rules] + [earlier turns] + [the new question]
    repeat (at most AGENT_MAX_STEPS times):
        LLM(messages, tools)  ──▶  either text (the answer: stop)
                              └─▶  or tool calls: run each tool, append the results to messages, go again
    last round: tools are withheld, so the model must answer with what it has

This "reason → act → observe" cycle is the core of every agent (the ReAct pattern). The LLM plans;
our code acts. Everything is yielded as EVENTS, so the browser can show progress live:
    {"type": "tool_call", ...}  {"type": "tool_result", ...}  {"type": "token", "text": "Pri"}  {"type": "answer", ...}
Events whose type starts with "_" are internal (messages to save), not sent to the browser.
"""
import json
import time
from collections.abc import AsyncIterator

from app.agent.prompts import system_prompt
from app.agent.tools import ToolContext, run_tool, tool_specs


def _summary(name: str, result: dict) -> str:
    """One line for the progress display: what came back from a tool."""
    if "error" in result:
        return f"error: {result['error']}"
    for key in ("candidates", "results", "top"):
        if key in result:
            codes = [r.get("employee_code") for r in result[key]][:5]
            return f"{len(result[key])} found: {', '.join(c for c in codes if c)}"
    if "projects" in result:
        return f"{len(result['projects'])} projects"
    if "fits" in result:
        return result["note"]
    if "name" in result:
        return f"profile of {result['employee_code']} {result['name']}"
    return "done"


async def run_agent(ctx: ToolContext, model: str, history: list[dict], question: str) -> AsyncIterator[dict]:
    s = ctx.settings
    started = time.perf_counter()
    messages = [{"role": "system", "content": system_prompt(ctx.user.full_name)}, *history,
                {"role": "user", "content": question}]
    specs = tool_specs()
    tool_calls_made = 0

    for step in range(s.agent_max_steps + 1):
        last_round = step == s.agent_max_steps
        content, calls, final = "", [], {}
        async for chunk in ctx.ollama.chat_stream(messages, model, tools=None if last_round else specs,
                                                  temperature=s.agent_temperature, num_ctx=s.llm_num_ctx,
                                                  num_predict=s.agent_max_output_tokens):
            msg = chunk.get("message") or {}
            if msg.get("content"):
                content += msg["content"]
                yield {"type": "token", "text": msg["content"]}
            if msg.get("tool_calls"):
                calls.extend(msg["tool_calls"])
            if chunk.get("done"):
                final = chunk

        if not calls:                                   # no tool requested: this is the answer
            yield {"type": "_save", "message": {"role": "assistant", "content": content.strip()}}
            yield {"type": "answer", "text": content.strip(), "steps": step + 1, "tool_calls": tool_calls_made,
                   "seconds": round(time.perf_counter() - started, 1), "done_reason": final.get("done_reason")}
            return

        # The model asked for tools. Remember its request, run each tool, and give it the results.
        requested = [{"name": c["function"]["name"], "arguments": c["function"].get("arguments") or {}} for c in calls]
        messages.append({"role": "assistant", "content": content, "tool_calls": calls})
        yield {"type": "_save", "message": {"role": "assistant", "content": content, "tool_calls": requested}}
        for call in requested:
            tool_calls_made += 1
            yield {"type": "tool_call", "name": call["name"], "arguments": call["arguments"]}
            result = await run_tool(ctx, call["name"], call["arguments"], s.agent_tool_result_chars)
            text = json.dumps(result, default=str)
            messages.append({"role": "tool", "tool_name": call["name"], "content": text})
            yield {"type": "_save", "message": {"role": "tool", "tool_name": call["name"], "content": text}}
            yield {"type": "tool_result", "name": call["name"], "ok": "error" not in result,
                   "summary": _summary(call["name"], result)}
