"""
Try semantic search through the running API with queries that share FEW or NO words with the resumes.
That is the point of embeddings: matching by meaning, not by exact words.

Run from backend/ while the server is running:
    python -m scripts.try_search
    python -m scripts.try_search "people who have mentored a team"
"""
import sys

import httpx

DEMO_QUERIES = [
    ("container orchestration and infrastructure as code", "EMP-1003 (says 'k8s', 'Terraform modules')"),
    ("high-traffic backend APIs and database performance tuning", "EMP-1001 ('2M requests/day', 'p95 latency')"),
    ("retrieval-augmented generation with vector databases", "EMP-1007 (built a RAG assistant)"),
    ("automated UI and API testing", "EMP-1009 (Playwright, Selenium)"),
    ("design systems and component libraries for the web", "EMP-1005 (React + Storybook design system)"),
    ("event streaming between Java microservices", "EMP-1006 (Spring Boot + Kafka)"),
    ("experience in the insurance domain", "EMP-1001 / EMP-1007 ('claims')"),
]


def show(client: httpx.Client, query: str, expected: str | None) -> None:
    r = client.post("/api/search/semantic", json={"query": query, "top_k": 3})
    r.raise_for_status()
    data = r.json()
    print(f"\nQUERY: {query}")
    if expected:
        print(f"  expected near the top: {expected}")
    print(f"  ({data['timings']['total_ms']} ms, {data['timings']['chunks_considered']} chunks considered)")
    for res in data["results"]:
        best = res["matched_chunks"][0]
        body = best["text"].split("\n", 1)[-1].replace("\n", " ")[:90]
        print(f"  #{res['rank']} {res['employee_code']} {res['full_name']:<18} score {res['score']:.3f}"
              f"  [{best['section']}] {body}")


def main() -> None:
    with httpx.Client(base_url="http://127.0.0.1:8010", timeout=60) as client:
        if len(sys.argv) > 1:
            show(client, " ".join(sys.argv[1:]), None)
        else:
            for query, expected in DEMO_QUERIES:
                show(client, query, expected)


if __name__ == "__main__":
    main()
