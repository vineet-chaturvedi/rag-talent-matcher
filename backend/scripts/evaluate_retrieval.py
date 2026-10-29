"""
Measures retrieval quality against the answer key in samples/roles.json ("expected_ranking").

For every role it runs the candidate search FOUR times - hybrid (all signals fused) and each
signal alone - and reports:
  recall@5   share of the expected people that appear in the top 5
  recall@10  same for the top 10
  MRR        1 / rank of the first expected person (1.0 = an expected person is #1)
  ranks      where each expected person landed (- = not found at all)

Retrieval's job is RECALL: get the right people into the shortlist. Getting them in the perfect
order is Step 8's job (scoring + LLM judge), so don't worry if #1 and #2 are swapped here.

Run from backend/ while the server is running (after scripts.load_roles):
    python -m scripts.evaluate_retrieval
"""
import argparse
import json
from pathlib import Path

import httpx

from scripts.api_login import login

RUNS = {"hybrid": ["skills", "keyword", "vector"], "skills": ["skills"], "keyword": ["keyword"], "vector": ["vector"]}


def recall_at(found: list[str], expected: list[str], k: int) -> float:
    return len(set(found[:k]) & set(expected)) / len(expected)


def mrr(found: list[str], expected: list[str]) -> float:
    return next((1 / (i + 1) for i, code in enumerate(found) if code in expected), 0.0)


def main(base_url: str, roles_file: Path) -> None:
    specs = {s["title"]: s for s in json.loads(roles_file.read_text(encoding="utf-8"))}
    totals = {run: [0.0, 0.0, 0.0] for run in RUNS}
    with httpx.Client(base_url=base_url, timeout=120) as client:
        login(client)
        roles = [r for p in client.get("/api/projects").raise_for_status().json() for r in p["roles"]
                 if r["title"] in specs]
        if not roles:
            raise SystemExit("No sample roles found - run `python -m scripts.load_roles` first.")

        for role in roles:
            expected = specs[role["title"]]["expected_ranking"]
            print(f"\n=== {role['title']}  (role {role['id']})   expected: {', '.join(expected)}")
            print(f"  {'run':<8} {'R@5':>5} {'R@10':>5} {'MRR':>5}   ranks of expected   | top 5")
            for run, signals in RUNS.items():
                body = client.post(f"/api/roles/{role['id']}/candidates",
                                   json={"top_k": 50, "signals": signals}).raise_for_status().json()
                found = [c["employee_code"] for c in body["candidates"]]
                r5, r10, m = recall_at(found, expected, 5), recall_at(found, expected, 10), mrr(found, expected)
                for i, v in enumerate((r5, r10, m)):
                    totals[run][i] += v
                ranks = " ".join(f"{found.index(c) + 1 if c in found else '-':>2}" for c in expected)
                print(f"  {run:<8} {r5:>5.2f} {r10:>5.2f} {m:>5.2f}   {ranks:<19} | {' '.join(found[:5])}")

        n = len(roles)
        print(f"\n=== Average over {n} roles")
        print(f"  {'run':<8} {'R@5':>5} {'R@10':>5} {'MRR':>5}")
        for run, (r5, r10, m) in totals.items():
            print(f"  {run:<8} {r5 / n:>5.2f} {r10 / n:>5.2f} {m / n:>5.2f}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base-url", default="http://127.0.0.1:8010")
    parser.add_argument("--roles", type=Path, default=Path("../samples/roles.json"))
    args = parser.parse_args()
    main(args.base_url, args.roles)
