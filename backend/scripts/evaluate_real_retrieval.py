"""
Retrieval quality on the 9 real resumes (doc 18): does the search put the right person near the top?

For each query in evaluation/real_retrieval.json (a role with its requirements written out) it runs the
candidate search with all signals together, with each signal alone, and (with --compare-rerank) with the
reranker on, then reports:
  hit@3    an expected person is in the top 3 (for Q5: at least N of them, see "expected_in_top")
  R@5      share of the expected people in the top 5
  MRR      1 / rank of the first expected person (1.0 = an expected person is #1)

Needs: the resumes of samples/real/ uploaded and READY (any employee; they are found by file hash) and
Ollama running (the vector signal embeds the query). No server needed; nothing is saved.
Run from backend/:
    python -m scripts.evaluate_real_retrieval
    python -m scripts.evaluate_real_retrieval --compare-rerank      # needs RERANK_MODEL and pip install fastembed
"""
import argparse
import asyncio
import hashlib
import json
import sys
from pathlib import Path

from sqlalchemy import select

from app.config import get_settings
from app.db.enums import ResumeStatus
from app.db.models import ProjectRole, Resume
from app.db.session import SessionLocal, init_db
from app.llm.router import make_model_client
from app.matching.retrieval import retrieve_candidates

ROOT = Path(__file__).resolve().parents[2]
QUERIES = Path(__file__).resolve().parents[1] / "evaluation" / "real_retrieval.json"
RESUMES = Path(__file__).resolve().parents[1] / "evaluation" / "real_resumes.json"
FILES = ROOT / "samples" / "real"

RUNS = {"hybrid": ("skills", "keyword", "vector"), "skills": ("skills",), "keyword": ("keyword",),
        "vector": ("vector",)}


def metrics(found: list[str], expected: list[str], need_in_top3: int) -> tuple[bool, float, float]:
    hit = len(set(found[:3]) & set(expected)) >= need_in_top3
    recall5 = len(set(found[:5]) & set(expected)) / len(expected)
    mrr = next((1 / (i + 1) for i, rid in enumerate(found) if rid in expected), 0.0)
    return hit, recall5, mrr


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--compare-rerank", action="store_true", help="also run with the reranker (RERANK_MODEL)")
    args = parser.parse_args()
    settings = get_settings()
    runs = dict(RUNS)
    if args.compare_rerank:
        if not settings.rerank_model:
            raise SystemExit("Set RERANK_MODEL in .env first (e.g. Xenova/ms-marco-MiniLM-L-6-v2).")
        runs["hybrid+rerank"] = ("skills", "keyword", "vector", "rerank")

    # The real resumes, found by their file's SHA-256 (the same fingerprint the upload stores).
    cases = json.loads(RESUMES.read_text(encoding="utf-8"))["resumes"]
    hash_to_id = {}
    for case in cases:
        path = FILES / case.get("file", "")
        if case.get("file") and path.exists():
            hash_to_id[hashlib.sha256(path.read_bytes()).hexdigest()] = case["id"]
    await init_db()
    async with SessionLocal() as session:
        rows = (await session.execute(
            select(Resume.employee_id, Resume.file_hash).where(Resume.is_current.is_(True),
                                                                Resume.status == ResumeStatus.READY)
        )).all()
    emp_to_id = {emp: hash_to_id[h] for emp, h in rows if h in hash_to_id}
    missing = sorted(set(hash_to_id.values()) - set(emp_to_id.values()))
    if missing:
        print(f"Not in the database as a ready, current resume: {', '.join(missing)}. Upload samples/real/ first.")
    if not emp_to_id:
        return 1

    queries = json.loads(QUERIES.read_text(encoding="utf-8"))["queries"]
    ollama = make_model_client(settings)
    totals = {run: [0, 0.0, 0.0, 0] for run in runs}
    try:
        for q in queries:
            role = ProjectRole(
                title=q["title"], description=q["description"], allocation_percent=0, start_date=None,
                requirements={
                    "must_have": [{"name": s, "min_years": None} for s in q["must_have"]],
                    "nice_to_have": [{"name": s, "min_years": None} for s in q["nice_to_have"]],
                    "search_summary": q["search_summary"], "seniority": "unspecified", "min_total_years": None,
                    "location": None, "domain": [], "edited_by_user": True,
                },
            )
            expected = [e for e in q["expected"] if e in emp_to_id.values()]
            if not expected:
                print(f"\n{q['id']} {q['title']}: skipped (its resumes are not uploaded)")
                continue
            need = min(q.get("expected_in_top", 1), len(expected))
            print(f"\n{q['id']} {q['title']}   expected: {', '.join(expected)}")
            print(f"  {'run':<14} {'hit@3':>5} {'R@5':>5} {'MRR':>5}   top 5")
            for run, signals in runs.items():
                async with SessionLocal() as session:
                    found, _ = await retrieve_candidates(session, ollama, settings, role, top_k=20, signals=signals)
                labels = [emp_to_id.get(c.employee.id, c.employee.employee_code) for c in found]
                hit, r5, mrr = metrics(labels, expected, need)
                t = totals[run]
                t[0] += hit
                t[1] += r5
                t[2] += mrr
                t[3] += 1
                print(f"  {run:<14} {'yes' if hit else 'NO':>5} {r5:>5.2f} {mrr:>5.2f}   {', '.join(labels[:5])}")
    finally:
        await ollama.close()

    print("\nAverage over the queries")
    print(f"  {'run':<14} {'hit@3':>6} {'R@5':>5} {'MRR':>5}")
    for run, (hits, r5, mrr, n) in totals.items():
        if n:
            print(f"  {run:<14} {hits}/{n:<4} {r5 / n:>5.2f} {mrr / n:>5.2f}")
    hybrid = totals["hybrid"]
    return 0 if hybrid[3] and hybrid[0] == hybrid[3] else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
