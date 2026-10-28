"""
From the LLM's raw answer to a clean, checked profile - all in plain Python.

  1. Verify every skill against the resume text  -> drop hallucinations
  2. Normalise skill names                        -> "k8s" becomes "Kubernetes"
  3. Parse dates, compute total years             -> overlapping jobs counted once
  4. Job-level grounding                          -> a job keeps only skills written in ITS OWN text
  5. Years + last-used year per skill             -> from the jobs that used it
"""
import re
from dataclasses import asdict, dataclass, field
from datetime import date
from difflib import SequenceMatcher

from app.extraction.dates import interval, months_to_years, parse_range, total_months
from app.extraction.schema import ResumeExtraction
from app.extraction.skills import IMPLIED_LANGUAGE, category_of, normalize_skill, spellings


@dataclass
class ProfileSkill:
    name: str
    category: str | None
    years: float | None          # None = listed, but no dated job shows it
    last_used_year: int | None
    evidence: str | None


@dataclass
class ProfileJob:
    title: str | None
    company: str | None
    start_date: date | None
    end_date: date | None
    is_current: bool
    months: int | None
    description: str | None
    skills: list[str]


@dataclass
class Profile:
    headline: str | None
    summary: str | None
    total_experience_years: float | None
    jobs: list[ProfileJob]
    skills: list[ProfileSkill]
    education: list[dict]
    certifications: list[str]
    rejected_skills: list[dict] = field(default_factory=list)   # what we threw away, and why
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


# --------------------------------------------------------------------------- hallucination check
def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9+#.]+", " ", text.lower())).strip()


normalize_for_match = _norm   # public name, used by chunking (Step 7)


def appears_in(snippet: str | None, text_norm: str, min_ratio: float = 0.8) -> bool:
    """Does the snippet really occur in the resume? Exact match, or a near-exact one (small LLM copy slips)."""
    if not snippet:
        return False
    s = _norm(snippet)
    if not s:
        return False
    if s in text_norm:
        return True
    match = SequenceMatcher(None, text_norm, s, autojunk=False).find_longest_match(0, len(text_norm), 0, len(s))
    return match.size / len(s) >= min_ratio


_STATED_YEARS = re.compile(r"(\d+(?:\.\d+)?)\s*\+?\s*(?:yrs?|years?)\b", re.IGNORECASE)


def stated_years(raw_name: str) -> float | None:
    """'React (1 yr)' -> 1.0   'Python 5+ years' -> 5.0   'Docker' -> None"""
    match = _STATED_YEARS.search(raw_name or "")
    return float(match.group(1)) if match else None


# --------------------------------------------------------------------------- job-level grounding
def contains_phrase(text_norm: str, phrase: str) -> bool:
    """Whole-word match: 'go' must not match inside 'google', 'java' not inside 'javascript'."""
    p = _norm(phrase)
    return bool(p) and re.search(rf"(?<![a-z0-9]){re.escape(p)}(?![a-z0-9])", text_norm) is not None


def _find_job_start(title: str | None, company: str | None, text_norm: str, start_at: int) -> int | None:
    """
    Where does this job's entry begin in the resume? Look for the title with the company name close by
    (a title alone can also appear in the header/summary), else the company alone.
    Search after the previous job first (resumes list jobs in order), then from the top.
    """
    t, c = _norm(title or ""), _norm(company or "")
    for begin in dict.fromkeys((start_at, 0)):
        if t:
            for m in re.finditer(re.escape(t), text_norm[begin:]):
                pos = begin + m.start()
                window = text_norm[max(0, pos - 100): pos + len(t) + 100]
                if not c or c in window:
                    return pos
        if c:
            idx = text_norm.find(c, begin)
            if idx >= 0:
                return idx
    return None


def locate_job_blocks(jobs: list, text_norm: str, max_block: int = 1500) -> list[tuple[int, int] | None]:
    """Each job's own slice of the resume text: from its start to the next job's start."""
    starts: list[int | None] = []
    cursor = 0
    for job in jobs:
        pos = _find_job_start(job.title, job.company, text_norm, cursor)
        starts.append(pos)
        if pos is not None:
            cursor = pos + 1
    found = sorted(p for p in starts if p is not None)
    blocks: list[tuple[int, int] | None] = []
    for pos in starts:
        if pos is None:
            blocks.append(None)
            continue
        nxt = next((p for p in found if p > pos), len(text_norm))
        blocks.append((pos, min(nxt, pos + max_block)))
    return blocks


def ground_job_skills(skills: list[str], block_text: str) -> tuple[list[str], list[str]]:
    """
    Keep a skill for a job only if it is written in that job's text (any known spelling),
    or it is a language implied by a framework written there (FastAPI -> Python).
    Returns (kept, removed).
    """
    written = [s for s in skills if any(contains_phrase(block_text, sp) for sp in spellings(s))]
    implied = {IMPLIED_LANGUAGE[s] for s in written if s in IMPLIED_LANGUAGE}
    kept = [s for s in skills if s in written or s in implied]
    return kept, [s for s in skills if s not in kept]


# --------------------------------------------------------------------------- main function
def build_profile(llm: ResumeExtraction, resume_text: str, today: date | None = None) -> Profile:
    today = today or date.today()
    text_norm = _norm(resume_text)
    warnings: list[str] = []
    rejected: list[dict] = []

    # ---- 1. Jobs: parse dates, normalise the skills used in each job
    jobs: list[ProfileJob] = []
    job_intervals: list[tuple[int, int] | None] = []
    for job in llm.experience:
        start, end, current = parse_range(job.start, job.end)
        span = interval(start, end, current, today)
        if job.start and span is None:
            warnings.append(f"Could not read dates for '{job.title}' ({job.start} - {job.end})")
        job_skills: list[str] = []
        for raw in job.skills_used:
            for name in normalize_skill(raw):
                if name not in job_skills:
                    job_skills.append(name)
        jobs.append(ProfileJob(
            title=job.title, company=job.company,
            start_date=start.as_date() if start else None,
            end_date=end.as_date() if end else None,
            is_current=current,
            months=(span[1] - span[0] + 1) if span else None,
            description=job.description, skills=job_skills,
        ))
        job_intervals.append(span)

    # ---- 1b. Job-level grounding: models tend to copy the whole skills section into every job,
    #          which inflates years. A job keeps only skills written in its own part of the resume.
    removed_from_jobs: list[str] = []
    for job, block in zip(jobs, locate_job_blocks(llm.experience, text_norm)):
        if block is None:
            if job.skills:
                warnings.append(f"Could not find the text of job '{job.title}' in the resume; its skills were not verified")
            continue
        job.skills, removed = ground_job_skills(job.skills, text_norm[block[0]:block[1]])
        for name in removed:
            removed_from_jobs.append(name)
            rejected.append({"name": name, "job": job.title,
                             "reason": "listed for this job, but not written in this job's part of the resume "
                                       "(the skill is kept if the resume mentions it elsewhere, without years)"})

    valid_spans = [s for s in job_intervals if s]
    total_years = months_to_years(total_months(valid_spans)) if valid_spans else None

    # ---- 2. Skills: verify against the text, normalise, merge duplicates
    evidence_for: dict[str, str] = {}
    stated_for: dict[str, float] = {}
    for mention in llm.skills:
        if not (appears_in(mention.evidence, text_norm) or appears_in(mention.name, text_norm)):
            rejected.append({"name": mention.name, "evidence": mention.evidence,
                             "reason": "neither the skill nor its evidence appears in the resume"})
            continue
        for name in normalize_skill(mention.name):
            evidence_for.setdefault(name, mention.evidence if appears_in(mention.evidence, text_norm) else None)
            if (stated := stated_years(mention.name) or stated_years(mention.evidence)) is not None:
                stated_for[name] = stated

    # Skills used in jobs count too (e.g. Python implied by "FastAPI" in a job).
    all_names = list(evidence_for)
    for job in jobs:
        for name in job.skills:
            if name not in evidence_for:
                all_names.append(name)
                evidence_for[name] = None

    # Skills taken away from jobs still count as skills if the resume mentions them somewhere
    # (e.g. only in the skills section) - they just get no years, because no dated job shows them.
    for name in removed_from_jobs:
        if name not in evidence_for and any(contains_phrase(text_norm, sp) for sp in spellings(name)):
            all_names.append(name)
            evidence_for[name] = None

    # ---- 3. Years and last-used year per skill, from the jobs that used it
    skills: list[ProfileSkill] = []
    for name in all_names:
        spans = [span for job, span in zip(jobs, job_intervals) if span and name in job.skills]
        last_used = None
        for job in jobs:
            if name in job.skills and (job.end_date or job.is_current):
                year = today.year if job.is_current else job.end_date.year
                last_used = max(last_used or 0, year)
        evidence = evidence_for[name]
        if evidence is None:
            using = [j for j in jobs if name in j.skills]
            if using:
                evidence = f"Used as {using[0].title or 'role'} at {using[0].company or 'unknown company'}"
            else:
                evidence = "Mentioned in the resume (no dated job shows it)"
        # Years = time covered by the jobs that used the skill. That over-counts a skill used briefly
        # inside a long job, so a duration written next to the skill ("React (1 yr)") caps it.
        years = months_to_years(total_months(spans)) if spans else None
        if name in stated_for:
            years = min(years, stated_for[name]) if years is not None else stated_for[name]
        skills.append(ProfileSkill(
            name=name, category=category_of(name),
            years=years,
            last_used_year=last_used, evidence=evidence,
        ))
    skills.sort(key=lambda s: (-(s.years or 0), s.name.lower()))

    return Profile(
        headline=llm.headline, summary=llm.summary, total_experience_years=total_years,
        jobs=jobs, skills=skills,
        education=[e.model_dump() for e in llm.education if e.degree or e.institution],
        certifications=[c for c in llm.certifications if c.strip()],
        rejected_skills=rejected, warnings=warnings,
    )
