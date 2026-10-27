"""
Compare the fast and quality models on resume extraction: speed AND correctness.

Run from backend/ with the SERVER STOPPED (otherwise its worker competes for the CPU):
    python -m scripts.compare_extraction
    python -m scripts.compare_extraction --models quality --codes EMP-1003 EMP-1011
Nothing is saved. Needs the Step 4 sample resumes to be parsed already.
"""
import argparse
import asyncio
import time

from sqlalchemy import select

from app.config import get_settings
from app.db.models import Employee, Resume
from app.db.session import SessionLocal, engine
from app.extraction.extractor import extract_profile
from app.extraction.postprocess import Profile
from app.llm.ollama_client import OllamaClient


def skill(p: Profile, name: str):
    return next((s for s in p.skills if s.name == name), None)


def has(name: str):
    return lambda p: skill(p, name) is not None


def years_between(name: str, low: float, high: float):
    return lambda p: skill(p, name) is not None and skill(p, name).years is not None and low <= skill(p, name).years <= high


def total_between(low: float, high: float):
    return lambda p: p.total_experience_years is not None and low <= p.total_experience_years <= high


def last_used_at_most(name: str, year: int):
    return lambda p: skill(p, name) is not None and skill(p, name).last_used_year is not None and skill(p, name).last_used_year <= year


# What a careful human reader would get from each tricky sample resume.
CHECKS = {
    "EMP-1001": [("Django >= 7 years", years_between("Django", 7, 10)),
                 ("PostgreSQL found", has("PostgreSQL")),
                 ("Total experience 8.5-10 years", total_between(8.5, 10))],
    "EMP-1002": [("Python 4-6.5 years (FastAPI + Flask jobs)", years_between("Python", 4, 6.5)),
                 ("Java <= 2 years", years_between("Java", 0.5, 2)),
                 ("Django found (listed as 'Django (basic)')", has("Django"))],
    "EMP-1003": [("Kubernetes found (resume only says 'k8s')", has("Kubernetes")),
                 ("Terraform found", has("Terraform")),
                 ("AWS found", has("AWS"))],
    "EMP-1011": [("'JS' normalised to JavaScript", has("JavaScript")),
                 ("Angular found ('Angular 2+')", has("Angular")),
                 ("AngularJS kept separate", has("AngularJS")),
                 ("AngularJS <= 3 years (only used 2016-2018)", years_between("AngularJS", 1, 3))],
    "EMP-1015": [("Django last used <= 2019 (manager since 2019)", last_used_at_most("Django", 2019)),
                 ("Django 4-7 years (hands-on 2013-2019)", years_between("Django", 4, 7)),
                 ("Total experience 12-14 years", total_between(12, 14))],
}


async def main(models: list[str], codes: list[str]) -> None:
    settings = get_settings()
    ollama = OllamaClient(settings.ollama_base_url, settings.ollama_timeout_seconds)
    async with SessionLocal() as session:
        rows = (await session.execute(
            select(Employee.employee_code, Resume.raw_text)
            .join(Resume, Resume.employee_id == Employee.id)
            .where(Employee.employee_code.in_(codes), Resume.is_current.is_(True), Resume.raw_text.is_not(None))
            .order_by(Employee.employee_code)
        )).all()
    if not rows:
        print("No parsed resumes found for", codes, "- run Step 4 (scripts.upload_samples) first.")
        return

    summary = []
    for role in models:
        model = settings.fast_llm_model if role == "fast" else settings.quality_llm_model
        print(f"\n{'=' * 70}\n{role.upper()} model: {model}\n{'=' * 70}")
        passed = total = 0
        seconds: list[float] = []
        for code, text in rows:
            started = time.perf_counter()
            try:
                outcome = await extract_profile(
                    ollama, text, model=model, num_ctx=settings.llm_num_ctx,
                    max_output_tokens=settings.extraction_max_output_tokens,
                    max_input_chars=settings.extraction_max_input_chars,
                )
            except Exception as exc:
                print(f"\n{code}: FAILED - {type(exc).__name__}: {exc}")
                total += len(CHECKS.get(code, []))
                continue
            seconds.append(time.perf_counter() - started)
            p = outcome.profile
            print(f"\n{code}  ({seconds[-1]:.0f}s, {outcome.stats['output_tokens']} output tokens)  {p.headline}")
            print(f"  total experience: {p.total_experience_years} years | jobs: {len(p.jobs)} | skills: {len(p.skills)}")
            print("  top skills: " + ", ".join(f"{s.name} ({s.years}y)" if s.years else s.name for s in p.skills[:8]))
            invented = [r["name"] for r in p.rejected_skills if "job" not in r]
            moved = [f"{r['name']} ({r['job']})" for r in p.rejected_skills if "job" in r]
            if invented:
                print(f"  REJECTED, not in resume: {', '.join(invented)}")
            if moved:
                print(f"  removed from jobs (not in that job's text): {', '.join(moved)}")
            for w in p.warnings:
                print(f"  WARNING: {w}")
            for label, check in CHECKS.get(code, []):
                ok = check(p)
                passed += ok
                total += 1
                print(f"  [{'PASS' if ok else 'FAIL'}] {label}")
        avg = sum(seconds) / len(seconds) if seconds else 0
        summary.append((role, model, passed, total, avg))

    print(f"\n{'=' * 70}\nSUMMARY")
    for role, model, passed, total, avg in summary:
        print(f"  {role:<8} {model:<14} checks passed {passed}/{total}   avg {avg:.0f}s per resume"
              f"   -> 2,000 resumes ~ {avg * 2000 / 3600:.0f} hours")
    await ollama.close()
    await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--models", nargs="+", default=["fast", "quality"], choices=["fast", "quality"])
    parser.add_argument("--codes", nargs="+", default=list(CHECKS))
    args = parser.parse_args()
    asyncio.run(main(args.models, args.codes))
