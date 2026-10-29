"""
Measures the FINAL ranking (Step 8) against samples/roles.json, and compares it with retrieval alone.

For every role it starts a match run, waits for the LLM judge to finish, and reports:
  nDCG@5     are the expected people near the top, in the expected order? (1.0 = perfect)
  MRR        1 / rank of the first expected person
  pairs      share of expected pairs in the right order (e.g. EMP-1001 above EMP-1002)
  ranks      where each expected person landed (- = not in the results)

Run from backend/ while the server is running (after scripts.load_roles):
    python -m scripts.evaluate_matching                 # rule score + LLM judge (slow on a CPU: minutes per role)
    python -m scripts.evaluate_matching --judge-top-n 0 # rule score only (seconds)
"""
import argparse
import json
import math
import time
from pathlib import Path

import httpx

from scripts.api_login import login


def ndcg_at(found: list[str], expected: list[str], k: int) -> float:
    """Graded relevance: the 1st expected person is worth most, the last expected person least."""
    gain = {code: len(expected) - i for i, code in enumerate(expected)}
    dcg = sum(gain.get(code, 0) / math.log2(i + 2) for i, code in enumerate(found[:k]))
    ideal = sum(g / math.log2(i + 2) for i, g in enumerate(sorted(gain.values(), reverse=True)[:k]))
    return dcg / ideal if ideal else 0.0


def mrr(found: list[str], expected: list[str]) -> float:
    return next((1 / (i + 1) for i, code in enumerate(found) if code in expected), 0.0)


def pair_order(found: list[str], expected: list[str]) -> float:
    """Of all expected pairs (A should be above B), how many are in the right order?"""
    pos = {code: found.index(code) if code in found else len(found) for code in expected}
    pairs = [(a, b) for i, a in enumerate(expected) for b in expected[i + 1:]]
    return sum(pos[a] < pos[b] for a, b in pairs) / len(pairs) if pairs else 1.0


def wait_for(client: httpx.Client, run_id: int) -> dict:
    while True:
        run = client.get(f"/api/match-runs/{run_id}").raise_for_status().json()
        if run["status"] != "running":
            return run
        print(f"    judging... {run['judged']}/{run['to_judge']}", end="\r", flush=True)
        time.sleep(5)


def main(base_url: str, roles_file: Path, judge_top_n: int, top_k: int) -> None:
    specs = {s["title"]: s for s in json.loads(roles_file.read_text(encoding="utf-8"))}
    totals = {"ndcg@5": 0.0, "mrr": 0.0, "pairs": 0.0}
    with httpx.Client(base_url=base_url, timeout=120) as client:
        login(client)
        roles = [r for p in client.get("/api/projects").raise_for_status().json() for r in p["roles"]
                 if r["title"] in specs]
        if not roles:
            raise SystemExit("No sample roles found - run `python -m scripts.load_roles` first.")
        for role in roles:
            expected = specs[role["title"]]["expected_ranking"]
            print(f"\n=== {role['title']}   expected: {', '.join(expected)}")
            started = time.perf_counter()
            run = client.post(f"/api/roles/{role['id']}/match",
                              json={"top_k": top_k, "judge_top_n": judge_top_n}).raise_for_status().json()
            run = wait_for(client, run["id"])
            found = [r["employee_code"] for r in run["results"]]
            scores = {"ndcg@5": ndcg_at(found, expected, 5), "mrr": mrr(found, expected),
                      "pairs": pair_order(found, expected)}
            for key, value in scores.items():
                totals[key] += value
            ranks = " ".join(f"{found.index(c) + 1 if c in found else '-':>2}" for c in expected)
            print(f"\r  run {run['id']} {run['status']} in {time.perf_counter() - started:.0f} s | "
                  f"nDCG@5 {scores['ndcg@5']:.2f}  MRR {scores['mrr']:.2f}  pairs {scores['pairs']:.2f} | ranks {ranks}")
            if run["error_message"]:
                print(f"  ERROR: {run['error_message']}")
            print(f"  {'#':>2} {'code':<9} {'final':>5} {'rule':>5} {'judge':>5} {'skill':>5} {'exp':>4} {'avail':>5}  rating   quotes")
            for r in run["results"][:6]:
                b, ex = r["score_breakdown"], r["explanation"] or {}
                j = ex.get("judge") or {}
                judge = f"{b['judge_score']:.2f}" if b.get("judge_score") is not None else "  -  "
                quotes = f"{j['quotes_verified']}/{j['quotes_total']}" if j else ex.get("judge_status", "")
                mark = "*" if r["employee_code"] in expected else " "
                print(f"  {r['rank']:>2} {r['employee_code']:<8}{mark} {r['final_score']:>5.2f} {b['rule_score']:>5.2f} "
                      f"{judge:>5} {b['skills']:>5.2f} {b['experience']:>4.1f} {b['availability']:>5.2f}  "
                      f"{j.get('rating', '-'):<8} {quotes}")
        n = len(roles)
        print(f"\n=== Average over {n} roles: " + "  ".join(f"{k} {v / n:.2f}" for k, v in totals.items()))
        print("(* = in the expected list)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base-url", default="http://127.0.0.1:8010")
    parser.add_argument("--roles", type=Path, default=Path("../samples/roles.json"))
    parser.add_argument("--judge-top-n", type=int, default=5, help="0 = rule score only")
    parser.add_argument("--top-k", type=int, default=10)
    args = parser.parse_args()
    main(args.base_url, args.roles, args.judge_top_n, args.top_k)
