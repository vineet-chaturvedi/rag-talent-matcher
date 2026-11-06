"""
Step 14: checks the staffing agent end to end on fixed test questions (evaluation/agent_cases.json).

Each question goes through the REAL agent loop (same prompt, tools, model and database as the chat page), and
the answer is checked automatically, without asking another LLM for an opinion:

  case checks (from the test file)
    tools_any            the agent called one of these tools
    must_have_includes   find_candidates was asked for these skills (any spelling: "Golang" = "Go")
    args                 a tool was called with these arguments (e.g. employee_code, start_date)
    mention_all/any/none which employee codes the answer must / may / must not name
    first_is_one_of      the first person named
    first_has_most_years the first person named has the most years of this skill (among recent users named)
    only_people_with_any everyone named has at least one of these skills (skill row, implied skill, or text)
    contains_*/not_contains  words that must / must not appear
    no_tools             answered without tools (off-topic, prompt injection)
  checks on EVERY answer
    grounded codes       every employee code in the answer came from a tool result (no invented people)
    grounded years       every "N years" / "N y" in the answer is a number some tool returned (no invented numbers)
    tool order           people appear in the order find_candidates ranked them
    at most 5 people · no email addresses or phone numbers · no error · not empty

Needs Ollama running with the agent's model; no server needed. Nothing is saved to the conversations.
A report is written to evaluation/reports/agent-<date-time>.json.
Run from backend/:
    python -m scripts.evaluate_agent
    python -m scripts.evaluate_agent --only A01 A04 --show
"""
import argparse
import asyncio
import json
import re
import sys
import time
from datetime import date, datetime
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.agent.loop import run_agent
from app.agent.tools import ToolContext, mentions
from app.config import get_settings
from app.db.enums import ResumeStatus, UserRole
from app.db.models import Employee, Resume, ResumeSkill, Skill, User
from app.db.session import SessionLocal, init_db
from app.extraction.skills import implied_by, normalize_skill
from app.llm.ollama_client import OllamaClient, OllamaError
from app.matching.retrieval import ESTIMATE_WEIGHT

BACKEND = Path(__file__).resolve().parents[1]
CASES = BACKEND / "evaluation" / "agent_cases.json"
REPORTS = BACKEND / "evaluation" / "reports"
MAX_PEOPLE = 5

CODE = re.compile(r"\bEMP-\d{3,6}\b", re.IGNORECASE)
YEARS = re.compile(r"(?<![\d.])(\d+(?:\.\d+)?)\s*\+?\s*(?:y\b|yrs?\b|years?\b)", re.IGNORECASE)
EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
PHONE_RUN = re.compile(r"\+?\d[\d\s().-]{8,}\d")
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


# --------------------------------------------------------------------------- small helpers
def codes_in(text: str) -> list[str]:
    """Employee codes in order of first mention."""
    seen: list[str] = []
    for m in CODE.finditer(text or ""):
        code = m.group(0).upper()
        if code not in seen:
            seen.append(code)
    return seen


def canonical(skill: str) -> str:
    names = normalize_skill(skill)
    return (names[0] if names else skill).lower()


def phones_in(text: str) -> list[str]:
    found = []
    for m in PHONE_RUN.finditer(text or ""):
        run = m.group(0).strip()
        if DATE.match(run) or sum(ch.isdigit() for ch in run) < 10:
            continue
        found.append(run)
    return found


def number_returned(number: str, texts: list[str]) -> bool:
    """Is this number (as written, or 5 = 5.0) somewhere in the tool results?"""
    variants = {number}
    if "." not in number:
        variants.add(f"{number}.0")
    elif number.endswith(".0"):
        variants.add(number[:-2])
    return any(re.search(rf"(?<![\d.]){re.escape(v)}(?![\d])", t) for v in variants for t in texts)


# --------------------------------------------------------------------------- one turn
async def ask(ctx: ToolContext, model: str, history: list[dict], question: str) -> dict:
    started = time.perf_counter()
    turn = {"question": question, "calls": [], "results": [], "answer": "", "error": None}
    try:
        async for event in run_agent(ctx, model, history, question):
            if event["type"] == "tool_call":
                turn["calls"].append({"name": event["name"], "arguments": event["arguments"] or {}})
            elif event["type"] == "_save" and event["message"]["role"] == "tool":
                turn["results"].append({"name": event["message"]["tool_name"], "text": event["message"]["content"]})
            elif event["type"] == "answer":
                turn["answer"] = event["text"]
                turn["llm_steps"] = event["steps"]
    except OllamaError as exc:
        turn["error"] = str(exc)
    except Exception as exc:  # report and continue with the next case
        turn["error"] = f"{type(exc).__name__}: {exc}"
    turn["seconds"] = round(time.perf_counter() - started, 1)
    return turn


async def person_has(session, code: str, skills: list[str]) -> bool:
    """Has this employee's current resume one of these skills (directly, implied, or named in the text)?"""
    emp = await session.scalar(select(Employee).where(Employee.employee_code == code))
    if emp is None:
        return False
    resume = await session.scalar(
        select(Resume).where(Resume.employee_id == emp.id, Resume.is_current.is_(True))
        .options(selectinload(Resume.skills).selectinload(ResumeSkill.skill)))
    if resume is None:
        return False
    wanted = {canonical(s) for s in skills}
    for link in resume.skills:
        names = {link.skill.name.lower(), *(i.lower() for i in implied_by(link.skill.name))}
        if names & wanted:
            return True
    return any(mentions(resume.raw_text or "", s) for s in skills)


async def skill_years(session, code: str, skill: str) -> tuple[float, int | None] | None:
    """(years as matching counts them, last used year) of one skill on the current resume, or None."""
    row = (await session.execute(
        select(ResumeSkill.years, ResumeSkill.last_used_year, ResumeSkill.years_basis)
        .join(Resume, Resume.id == ResumeSkill.resume_id).join(Employee, Employee.id == Resume.employee_id)
        .join(Skill, Skill.id == ResumeSkill.skill_id)
        .where(Employee.employee_code == code, Resume.is_current.is_(True),
               func.lower(Skill.name) == canonical(skill)))).first()
    if row is None or row.years is None:
        return None
    return row.years * (ESTIMATE_WEIGHT if row.years_basis == "estimated" else 1.0), row.last_used_year


def find_ranking(turn: dict) -> list[str]:
    """The order of the LAST find_candidates result of this turn."""
    for r in reversed(turn["results"]):
        if r["name"] == "find_candidates":
            try:
                return [c["employee_code"] for c in json.loads(r["text"]).get("candidates", [])]
            except (ValueError, AttributeError):
                return []
    return []


async def check_turn(session, turn: dict, expect: dict, earlier_texts: list[str], previous_answer: str) -> list[dict]:
    checks: list[dict] = []

    def add(name: str, ok: bool, detail: str = "") -> None:
        checks.append({"check": name, "ok": bool(ok), "detail": detail})

    answer = turn["answer"]
    low = answer.lower()
    called = [c["name"] for c in turn["calls"]]
    tool_texts = [r["text"] for r in turn["results"]]
    known_texts = tool_texts + earlier_texts + [turn["question"]]
    named = codes_in(answer)

    add("no error", turn["error"] is None, turn["error"] or "")
    add("answer not empty", bool(answer.strip()))
    if turn["error"]:
        return checks

    # ---- from the test file
    if "tools_any" in expect:
        add("tool choice", any(t in called for t in expect["tools_any"]),
            f"wanted one of {expect['tools_any']}, called {called or 'none'}")
    if expect.get("no_tools"):
        add("no tools", not called, f"called {called}")
    if "must_have_includes" in expect:
        asked = {canonical(s) for c in turn["calls"] if c["name"] == "find_candidates"
                 for s in (c["arguments"].get("must_have") or []) + (c["arguments"].get("nice_to_have") or [])}
        wanted = {canonical(s) for s in expect["must_have_includes"]}
        add("skills asked", wanted <= asked, f"wanted {sorted(wanted)}, asked {sorted(asked)}")
    for key, value in (expect.get("args") or {}).items():
        values = [str(c["arguments"].get(key, "")) for c in turn["calls"]]
        add(f"argument {key}", any(v.upper().startswith(str(value).upper()) for v in values),
            f"wanted {value}, got {values}")
    if expect.get("args_from_previous_first"):
        key = expect["args_from_previous_first"]
        first = (codes_in(previous_answer) or [None])[0]
        values = [str(c["arguments"].get(key, "")).upper() for c in turn["calls"]]
        add(f"argument {key} = first person before", first is not None and first in values,
            f"first before: {first}, got {values}")
    if "mention_all" in expect:
        missing = [c for c in expect["mention_all"] if c not in named]
        add("names the expected people", not missing, f"missing {missing}" if missing else "")
    if "mention_any" in expect:
        add("names one of the expected people", any(c in named for c in expect["mention_any"]),
            f"wanted one of {expect['mention_any']}, named {named}")
    if expect.get("mention_none"):
        add("names nobody", not named, f"named {named}")
    if "first_is_one_of" in expect:
        add("best person first", bool(named) and named[0] in expect["first_is_one_of"],
            f"first named {named[:1]}, wanted {expect['first_is_one_of']}")
    if "first_has_most_years" in expect:
        # Among the people named who used the skill recently, the first has the most years of it.
        skill = expect["first_has_most_years"]
        recent = date.today().year - 1
        facts = {c: await skill_years(session, c, skill) for c in named}
        current = {c: f[0] for c, f in facts.items() if f and (f[1] is None or f[1] >= recent)}
        best = max(current.values(), default=None)
        first = named[0] if named else None
        ok = first in current and best is not None and current[first] >= best - 0.05
        add("most experienced first", ok, "" if ok else f"first {first} {facts.get(first)}, years named: {current}")
    if "only_people_with_any" in expect:
        lacking = [c for c in named if not await person_has(session, c, expect["only_people_with_any"])]
        add("only people with the skill", not lacking, f"without {expect['only_people_with_any']}: {lacking}")
    if "contains_all" in expect:
        missing = [w for w in expect["contains_all"] if w.lower() not in low]
        add("contains the expected words", not missing, f"missing {missing}" if missing else "")
    if "contains_any" in expect:
        add("contains one of the words", any(w.lower() in low for w in expect["contains_any"]),
            f"wanted one of {expect['contains_any']}")
    if "not_contains" in expect:
        found = [w for w in expect["not_contains"] if w.lower() in low]
        add("leaves out forbidden text", not found, f"found {found}" if found else "")

    # ---- on every answer
    invented = [c for c in named if not any(c in t.upper() for t in known_texts)]
    add("grounded codes", not invented, f"no tool returned {invented}" if invented else "")
    years = [m.group(1) for m in YEARS.finditer(answer)]
    unknown = [y for y in years if not number_returned(y, known_texts)]
    add("grounded years", not unknown, f"no tool returned {unknown}" if unknown else "")
    ranking = find_ranking(turn)
    ranked = [c for c in named if c in ranking]
    add("tool order kept", ranked == sorted(ranked, key=ranking.index),
        f"answer {ranked}, tool {ranking[:len(ranked) + 2]}" if ranked != sorted(ranked, key=ranking.index) else "")
    add(f"at most {MAX_PEOPLE} people", len(named) <= MAX_PEOPLE, f"named {len(named)}")
    private = EMAIL.findall(answer) + phones_in(answer)
    add("no contact details", not private, f"found {private}" if private else "")
    return checks


# --------------------------------------------------------------------------- main
async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--only", nargs="*", help="case ids, e.g. A01 A04")
    parser.add_argument("--show", action="store_true", help="print every question, tool call and answer")
    parser.add_argument("--email", help="run as this portal user (default: the first active admin)")
    parser.add_argument("--no-report", action="store_true", help="don't write a report file")
    args = parser.parse_args()

    settings = get_settings()
    data = json.loads(CASES.read_text(encoding="utf-8"))
    cases = [c for c in data["cases"] if not args.only or c["id"] in args.only]
    await init_db()
    ollama = OllamaClient(settings.ollama_base_url, settings.ollama_timeout_seconds)
    model = settings.agent_model
    results = []
    started = time.perf_counter()
    try:
        async with SessionLocal() as session:
            query = select(User).where(User.is_active.is_(True))
            query = query.where(User.email == args.email) if args.email else query.where(User.role == UserRole.ADMIN)
            user = await session.scalar(query.order_by(User.id).limit(1))
            if user is None:
                raise SystemExit("No such active user. Create one: python -m scripts.create_user --role admin ...")
            user_id, user_email = user.id, user.email
            ready = set((await session.scalars(
                select(Employee.employee_code).join(Resume, Resume.employee_id == Employee.id)
                .where(Resume.is_current.is_(True), Resume.status == ResumeStatus.READY))).all())
        print(f"Agent model: {model} · running as {user_email} · {len(cases)} cases\n")

        for case in cases:
            missing = [c for c in case.get("requires", []) if c not in ready]
            if missing:
                print(f"{case['id']} {case['title']}: skipped (no ready resume for {', '.join(missing)})")
                results.append({"id": case["id"], "title": case["title"], "skipped": True})
                continue
            history: list[dict] = []
            earlier_texts: list[str] = []
            previous_answer = ""
            turns_out = []
            for t in case["turns"]:
                # A fresh session per question, like each chat request (the tools only read).
                async with SessionLocal() as session:
                    ctx = ToolContext(session, ollama, settings, await session.get(User, user_id))
                    turn = await ask(ctx, model, history, t["question"])
                    turn["checks"] = await check_turn(session, turn, t.get("expect", {}), earlier_texts,
                                                      previous_answer)
                turns_out.append(turn)
                earlier_texts += [r["text"] for r in turn["results"]] + [turn["answer"]]
                history += [{"role": "user", "content": t["question"]},
                            {"role": "assistant", "content": turn["answer"]}]
                previous_answer = turn["answer"]
            passed = sum(c["ok"] for t in turns_out for c in t["checks"])
            total = sum(len(t["checks"]) for t in turns_out)
            seconds = sum(t["seconds"] for t in turns_out)
            ok = passed == total
            print(f"{case['id']} {case['title']}: {'PASS' if ok else 'FAIL'}  {passed}/{total} checks  ({seconds:.0f} s)")
            for t in turns_out:
                if args.show:
                    print(f"   Q: {t['question']}")
                    for c in t["calls"]:
                        print(f"   → {c['name']}({json.dumps(c['arguments'])})")
                    print("   A: " + (t["answer"] or t["error"] or "").replace("\n", "\n      "))
                for c in t["checks"]:
                    if not c["ok"]:
                        print(f"   FAIL  {c['check']}: {c['detail']}")
            results.append({"id": case["id"], "title": case["title"], "ok": ok, "passed": passed,
                            "total": total, "seconds": round(seconds, 1), "turns": turns_out})
    finally:
        await ollama.close()

    run = [r for r in results if not r.get("skipped")]
    checks = [c for r in run for t in r["turns"] for c in t["checks"]]
    by_check: dict[str, list[int]] = {}
    for c in checks:
        by_check.setdefault(c["check"], [0, 0])
        by_check[c["check"]][0] += c["ok"]
        by_check[c["check"]][1] += 1
    summary = {
        "cases_passed": sum(r["ok"] for r in run), "cases_run": len(run),
        "cases_skipped": len(results) - len(run),
        "checks_passed": sum(c["ok"] for c in checks), "checks_total": len(checks),
        "seconds_per_case": round(sum(r["seconds"] for r in run) / len(run), 1) if run else None,
        "by_check": {k: f"{v[0]}/{v[1]}" for k, v in sorted(by_check.items())},
    }
    skipped = f", {summary['cases_skipped']} skipped" if summary["cases_skipped"] else ""
    print(f"\nCases: {summary['cases_passed']}/{summary['cases_run']} passed{skipped}"
          f" · checks {summary['checks_passed']}/{summary['checks_total']}"
          f" · {summary['seconds_per_case']} s per case · {time.perf_counter() - started:.0f} s in all")
    weak = {k: v for k, v in summary["by_check"].items() if v.split("/")[0] != v.split("/")[1]}
    if weak:
        print("Checks that failed somewhere: " + ", ".join(f"{k} {v}" for k, v in weak.items()))

    if not args.no_report:
        REPORTS.mkdir(parents=True, exist_ok=True)
        path = REPORTS / f"agent-{datetime.now():%Y%m%d-%H%M%S}.json"
        path.write_text(json.dumps({"kind": "agent", "created": datetime.now().isoformat(timespec="seconds"),
                                    "model": model, "summary": summary, "cases": results},
                                   indent=1, default=str), encoding="utf-8")
        print(f"Report: {path.relative_to(BACKEND)}")
    return 0 if run and summary["cases_passed"] == len(run) else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
