"""
Step 14c: turns the portal's 👍 / 👎 into test data.

  1. Match labels, per role: who colleagues said IS a good match and who is NOT (with the reasons).
     Several votes on one person for one role are added up; the majority decides, a tie is "disputed".
     This is the labelled set Step 14d tunes the score weights on.
  2. Draft agent test cases from 👎 answers, in the format of evaluation/agent_cases.json, with the question,
     what the agent did and the person's reason. A human finishes the "expect" part (only they know the
     right answer), then copies the case into agent_cases.json, so the same mistake is caught next time.

Reads the database directly (no server needed). Writes, git-ignored because they name real employees:
    evaluation/reports/feedback-labels-<time>.json
    evaluation/reports/agent-cases-from-feedback-<time>.json
Run from backend/:
    python -m scripts.export_feedback
"""
import asyncio
import json
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from sqlalchemy import select

from app.db.enums import FeedbackRating, FeedbackTarget
from app.db.models import Employee, Feedback, ProjectRole
from app.db.session import SessionLocal, init_db

BACKEND = Path(__file__).resolve().parents[1]
REPORTS = BACKEND / "evaluation" / "reports"
CODE = re.compile(r"\bEMP-\d{3,6}\b", re.IGNORECASE)

# What a 👎 reason suggests the test should check (a starting point for the human writing "expect").
SUGGEST = {
    "wrong_people": "add the wrongly named codes to a check: only_people_with_any / mention_none",
    "missed_someone": "add the missing person to mention_all",
    "wrong_numbers": "grounded years should catch it; if not, add contains_all with the right number",
    "misunderstood": "check tools_any and must_have_includes / args",
    "too_long": "check at most 5 people; consider a shorter-answer rule in the prompt",
}


async def main() -> None:
    await init_db()
    async with SessionLocal() as db:
        rows = (await db.execute(
            select(Feedback, ProjectRole.title, Employee.employee_code, Employee.full_name)
            .outerjoin(ProjectRole, ProjectRole.id == Feedback.role_id)
            .outerjoin(Employee, Employee.id == Feedback.employee_id)
            .order_by(Feedback.id)
        )).all()

    # ---- 1. match labels
    roles: dict[int, dict] = {}
    votes: dict[tuple[int, str], dict] = defaultdict(lambda: {"up": 0, "down": 0, "reasons": [], "comments": []})
    for fb, role_title, code, name in rows:
        if fb.target != FeedbackTarget.MATCH_RESULT or fb.role_id is None or code is None:
            continue
        ctx = fb.context or {}
        roles.setdefault(fb.role_id, {"role_id": fb.role_id, "title": role_title or ctx.get("role_title"),
                                      "must_have": ctx.get("must_have", []), "nice_to_have": ctx.get("nice_to_have", [])})
        v = votes[(fb.role_id, code)]
        v["name"] = name
        v["up" if fb.rating == FeedbackRating.UP else "down"] += 1
        if fb.reason:
            v["reasons"].append(fb.reason)
        if fb.comment:
            v["comments"].append(fb.comment)
    for role in roles.values():
        role.update(good=[], not_good=[], disputed=[])
    for (role_id, code), v in sorted(votes.items()):
        entry = {"code": code, "name": v["name"], "up": v["up"], "down": v["down"],
                 "reasons": sorted(set(v["reasons"])), "comments": v["comments"]}
        key = "good" if v["up"] > v["down"] else "not_good" if v["down"] > v["up"] else "disputed"
        roles[role_id][key].append(entry)

    # ---- 2. draft agent cases from thumbs down
    drafts = []
    for fb, *_ in rows:
        if fb.target != FeedbackTarget.AGENT_ANSWER or fb.rating != FeedbackRating.DOWN:
            continue
        ctx = fb.context or {}
        question = ctx.get("question")
        if not question:
            continue
        named = sorted({c.upper() for c in CODE.findall(ctx.get("answer") or "")})
        drafts.append({
            "id": f"F{fb.id:03d}",
            "title": f"From feedback: {fb.reason or 'thumbs down'}",
            "draft": True,
            "feedback": {"reason": fb.reason, "comment": fb.comment, "answer_then": ctx.get("answer"),
                         "tools_then": [c.get("name") for c in ctx.get("tool_calls", [])],
                         "people_named_then": named, "suggestion": SUGGEST.get(fb.reason or "", "")},
            "turns": [{"question": question,
                       "expect": {"tools_any": sorted({c.get("name") for c in ctx.get("tool_calls", [])} - {None})
                                  or ["find_candidates"]}}],
        })

    REPORTS.mkdir(parents=True, exist_ok=True)
    stamp = f"{datetime.now():%Y%m%d-%H%M%S}"
    labels_path = REPORTS / f"feedback-labels-{stamp}.json"
    labels_path.write_text(json.dumps({"created": datetime.now().isoformat(timespec="seconds"),
                                       "roles": list(roles.values())}, indent=1), encoding="utf-8")
    cases_path = REPORTS / f"agent-cases-from-feedback-{stamp}.json"
    cases_path.write_text(json.dumps({"about": "Drafts: finish each 'expect' (doc 19, section 3.2), drop 'draft' "
                                               "and 'feedback', then copy into evaluation/agent_cases.json.",
                                      "cases": drafts}, indent=1), encoding="utf-8")

    total = sum(len(r["good"]) + len(r["not_good"]) + len(r["disputed"]) for r in roles.values())
    print(f"Match labels: {total} people over {len(roles)} roles "
          f"({sum(len(r['good']) for r in roles.values())} good, "
          f"{sum(len(r['not_good']) for r in roles.values())} not good, "
          f"{sum(len(r['disputed']) for r in roles.values())} disputed)")
    for r in roles.values():
        print(f"  {r['title']}: good {[e['code'] for e in r['good']]}  not good {[e['code'] for e in r['not_good']]}")
    print(f"Draft agent cases from 👎 answers: {len(drafts)}")
    print(f"Wrote {labels_path.relative_to(BACKEND)} and {cases_path.relative_to(BACKEND)}")


if __name__ == "__main__":
    asyncio.run(main())
