"""
Check resume extraction against the 9 real resumes (doc 18) and their expected profiles.

Two modes (run from backend/):
    python -m scripts.evaluate_real_resumes --offline     # the code alone: text extraction + post-processing,
                                                          # fed a CORRECT model answer from the test set (seconds)
    python -m scripts.evaluate_real_resumes               # the whole pipeline with your real model (minutes;
                                                          # stop the server first so its worker doesn't compete)
    python -m scripts.evaluate_real_resumes --only R1 R4 --show

The resume files are personal data: put them in samples/real/ (not committed). The expectations are in
evaluation/real_resumes.json. Nothing is saved to the database.
Exit code 0 when every check passes, 1 otherwise, so it can run in CI later (Step 14).
"""
import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

from app.config import get_settings
from app.extraction.extractor import extract_profile
from app.extraction.postprocess import Profile, build_profile
from app.extraction.schema import ResumeExtraction
from app.ingestion.storage import InvalidFileError, validate_resume_file
from app.ingestion.text_extraction import extract_text

ROOT = Path(__file__).resolve().parents[2]
TEST_SET = Path(__file__).resolve().parents[1] / "evaluation" / "real_resumes.json"
FILES = ROOT / "samples" / "real"


def _in_range(value, bounds) -> bool:
    return value is not None and bounds[0] <= value <= bounds[1]


def check(profile: Profile, expect: dict) -> list[tuple[str, bool, str]]:
    """Every expectation as (description, passed, what we got)."""
    by_name = {s.name: s for s in profile.skills}
    projects = {p.name.lower(): p for p in profile.projects}

    def project(name: str):
        key = name.lower()
        return projects.get(key) or next((p for n, p in projects.items() if n.startswith(key) or key in n), None)

    results = []
    if "experience_basis" in expect:
        results.append((f"experience from {expect['experience_basis']}",
                        profile.experience_basis == expect["experience_basis"], str(profile.experience_basis)))
    if "total_years" in expect:
        results.append((f"total years {expect['total_years']}", _in_range(profile.total_experience_years,
                                                                         expect["total_years"]),
                        str(profile.total_experience_years)))
    for key, actual in (("jobs", len(profile.jobs)), ("projects", len(profile.projects))):
        if key in expect:
            results.append((f"{expect[key]} {key}", actual == expect[key], str(actual)))
    missing = [s for s in expect.get("skills_present", []) if s not in by_name]
    results.append((f"{len(expect.get('skills_present', []))} expected skills found", not missing,
                    "missing: " + ", ".join(missing) if missing else "all"))
    wrong = [s for s in expect.get("skills_absent", []) if s in by_name]
    results.append(("no headings / activities / exposure stored as skills", not wrong,
                    "present: " + ", ".join(wrong) if wrong else "none"))
    if "max_unknown_skills" in expect:
        unknown = [s.name for s in profile.skills if s.category is None]
        results.append((f"at most {expect['max_unknown_skills']} skills outside the catalogue",
                        len(unknown) <= expect["max_unknown_skills"], ", ".join(unknown) or "none"))
    for name, bounds in expect.get("skill_years", {}).items():
        got = by_name[name].years if name in by_name else None
        results.append((f"{name} years {bounds}", _in_range(got, bounds), str(got)))
    for key, attr in (("skill_basis", "years_basis"), ("skill_levels", "level"), ("skill_sources", "source")):
        for name, wanted in expect.get(key, {}).items():
            got = getattr(by_name[name], attr) if name in by_name else "skill not found"
            results.append((f"{name} {attr} = {wanted}", got == wanted, str(got)))
    if profile.total_experience_years is not None:
        over = [f"{s.name} {s.years}" for s in profile.skills if s.years and s.years > profile.total_experience_years]
        results.append(("no skill has more years than the whole career", not over, ", ".join(over) or "none"))
    for name, least in expect.get("min_uses", {}).items():
        got = by_name[name].uses if name in by_name else 0
        results.append((f"{name} used in >= {least} jobs/projects", got >= least, str(got)))
    for name, role in expect.get("project_roles", {}).items():
        p = project(name)
        results.append((f"role on {name}: {role}", p is not None and (p.role or "").strip() == role,
                        p.role if p else "project not found"))
    for name, months in expect.get("project_months", {}).items():
        p = project(name)
        results.append((f"{name} lasted {months} months", p is not None and p.duration_months == months,
                        str(p.duration_months) if p else "project not found"))
    for name, techs in expect.get("project_tech", {}).items():
        p = project(name)
        absent = [t for t in techs if not p or t not in p.technologies]
        results.append((f"{name} technologies include {', '.join(techs)}", not absent,
                        "missing: " + ", ".join(absent) if absent else "all"))
    if "education_years" in expect:
        got = [e.get("year") for e in profile.education]
        results.append((f"education years {expect['education_years']}", got == expect["education_years"], str(got)))
    return results


def show(profile: Profile) -> None:
    print(f"    total {profile.total_experience_years} y ({profile.experience_basis}); stated {profile.stated_years}")
    for job in profile.jobs:
        print(f"    job: {job.title} @ {job.company} {job.start_date}..{job.end_date or 'present'}: {', '.join(job.skills)}")
    for p in profile.projects:
        print(f"    project: {p.name} [{p.role}] {p.duration_months or ''} {p.job_basis or ''}: {', '.join(p.technologies)}")
    print("    skills: " + ", ".join(f"{s.name}({s.years or '-'}y {s.years_basis or ''},{s.uses}x,{s.source}"
                                    f"{',' + s.level if s.level else ''})" for s in profile.skills))
    for w in profile.warnings:
        print(f"    warning: {w}")


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--offline", action="store_true", help="use the test set's correct model answers (no Ollama)")
    parser.add_argument("--only", nargs="*", help="resume ids, e.g. R1 R4")
    parser.add_argument("--show", action="store_true", help="print each profile")
    args = parser.parse_args()

    data = json.loads(TEST_SET.read_text(encoding="utf-8"))
    by_id = {r["id"]: r for r in data["resumes"]}
    settings = get_settings()
    ollama = None
    if not args.offline:
        from app.llm.ollama_client import OllamaClient
        ollama = OllamaClient(settings.ollama_base_url, timeout=settings.ollama_timeout_seconds)

    passed = failed = 0
    try:
        for case in data["resumes"]:
            if args.only and case["id"] not in args.only:
                continue
            if "text" in case:                       # a synthetic resume written into the test set
                started = time.perf_counter()
                answer = case["llm"] if args.offline else None
                if answer is None:
                    outcome = await extract_profile(
                        ollama, case["text"], model=settings.extraction_model, num_ctx=settings.llm_num_ctx,
                        max_output_tokens=settings.extraction_max_output_tokens,
                        max_input_chars=settings.extraction_max_input_chars,
                    )
                    profile = outcome.profile
                else:
                    profile = build_profile(ResumeExtraction.model_validate(answer), case["text"])
                results = check(profile, case["expect"])
                ok = sum(r[1] for r in results)
                print(f"\n{case['id']} (synthetic): {ok}/{len(results)} checks ({time.perf_counter() - started:.1f} s)")
                for description, good, got in results:
                    if not good or args.show:
                        print(f"  {'PASS' if good else 'FAIL'}  {description}  -> {got}")
                if args.show:
                    show(profile)
                passed += ok
                failed += len(results) - ok
                continue
            path = FILES / case["file"]
            if not path.exists():
                print(f"{case['id']}: {path} not found - put the resume files in samples/real/")
                failed += 1
                continue
            started = time.perf_counter()
            try:
                file = validate_resume_file(path.name, path.read_bytes(), settings.max_upload_bytes)
            except InvalidFileError as exc:
                print(f"\n{case['id']} {case['file']}: REFUSED at upload: {exc}")
                failed += 1
                continue
            text = extract_text(path, file.mime_type, settings.min_chars_per_page).text
            if args.offline:
                answer = dict(by_id[case.get("same_llm_as", case["id"])]["llm"], **case.get("llm_overrides", {}))
                profile = build_profile(ResumeExtraction.model_validate(answer), text)
            else:
                outcome = await extract_profile(
                    ollama, text, model=settings.extraction_model, num_ctx=settings.llm_num_ctx,
                    max_output_tokens=settings.extraction_max_output_tokens,
                    max_input_chars=settings.extraction_max_input_chars,
                )
                profile = outcome.profile
            seconds = time.perf_counter() - started
            results = check(profile, case["expect"])
            ok = sum(r[1] for r in results)
            print(f"\n{case['id']} {case['file']}: {ok}/{len(results)} checks ({seconds:.1f} s)")
            for description, good, got in results:
                if not good or args.show:
                    print(f"  {'PASS' if good else 'FAIL'}  {description}  -> {got}")
            if args.show:
                show(profile)
            passed += ok
            failed += len(results) - ok
    finally:
        if ollama is not None:
            await ollama.close()
    print(f"\n{passed} passed, {failed} failed")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
