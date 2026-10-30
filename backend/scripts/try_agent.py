"""
Chat with the staffing agent in the terminal (Step 10), and watch what it does:
    → find_candidates({"must_have": ["Kubernetes", "AWS"], ...})      the tool the LLM chose, and its arguments
    ← 5 found: EMP-1003, EMP-1013, ...                               what the tool returned
    then the answer appears word by word (streamed)

Run from backend/ while the server is running:
    python -m scripts.try_agent            # interactive; type 'exit' to stop
    python -m scripts.try_agent --demo     # three example questions, one after another
"""
import argparse
import json
import time

import httpx

from scripts.api_login import login

DEMO = [
    "Who could join a Kubernetes migration on AWS from 1 December, full time?",
    "Tell me more about the first person: how many years of Kubernetes, and when did they last use it?",
    "Is anyone with RAG or LLM experience free half-time from mid-November?",
]


def ask(client: httpx.Client, conversation_id: int, question: str) -> None:
    started = time.perf_counter()
    with client.stream("POST", f"/api/agent/conversations/{conversation_id}/messages",
                       json={"content": question, "stream": True}) as response:
        if response.status_code != 200:
            print(f"Error {response.status_code}: {response.read().decode()}")
            return
        answering = False
        for line in response.iter_lines():
            if not line.startswith("data: "):
                continue
            event = json.loads(line[6:])
            kind = event["type"]
            if kind == "tool_call":
                answering = False
                print(f"\n  → {event['name']}({json.dumps(event['arguments'])})")
            elif kind == "tool_result":
                print(f"  ← {event['summary']}")
            elif kind == "token":
                if not answering:
                    print("\nAgent: ", end="")
                    answering = True
                print(event["text"], end="", flush=True)
            elif kind == "answer":
                print(f"\n\n  ({event['steps']} LLM steps, {event['tool_calls']} tool calls, {event['seconds']} s)")
            elif kind == "error":
                print(f"\n  ERROR: {event['message']}")
    print(f"  total {time.perf_counter() - started:.0f} s")


def main(base_url: str, demo: bool) -> None:
    with httpx.Client(base_url=base_url, timeout=httpx.Timeout(900, connect=5)) as client:
        login(client)
        conv = client.post("/api/agent/conversations", json={"title": "Terminal chat"}).raise_for_status().json()
        print(f"Conversation {conv['id']} (saved; see GET /api/agent/conversations/{conv['id']})")
        questions = iter(DEMO) if demo else None
        while True:
            if questions is not None:
                question = next(questions, None)
                if question is None:
                    break
                print(f"\nYou: {question}")
            else:
                question = input("\nYou: ").strip()
                if question.lower() in ("exit", "quit", ""):
                    break
            ask(client, conv["id"], question)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base-url", default="http://127.0.0.1:8010")
    parser.add_argument("--demo", action="store_true", help="run three example questions")
    args = parser.parse_args()
    main(args.base_url, args.demo)
