"""
Hybrid retrieval: find the employees most relevant to a project role, using THREE independent signals,
then merge their rankings with Reciprocal Rank Fusion (RRF).

    requirements (from the role)
        │
        ├─▶ ① SKILLS   structured match on Step 5 data: must/nice skills, years, recency   (SQL)
        ├─▶ ② KEYWORD  BM25 full-text search over chunks for the skills' exact spellings    (FTS5)
        └─▶ ③ VECTOR   meaning search with the role's summary                               (ChromaDB)
                        │
                        ▼
        RRF: score = Σ weight / (k + rank in each list)  → one ranked candidate list

Each signal covers another's blind spot (see the Step 6 findings): skills know "k8s" = Kubernetes and
count years; keywords catch exact rare terms; vectors catch meaning ("design systems" ≈ "component
library"). An employee found by several signals rises to the top.

Retrieval's job is RECALL: never miss the right people. Ordering them precisely, with availability and
an explanation, is Step 8's job.
"""
import asyncio
import math
import time
from dataclasses import dataclass, field
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import Settings
from app.db.enums import AvailabilityStatus, ResumeStatus
from app.db.models import Employee, ProjectRole, Resume, ResumeSkill
from app.extraction.skills import implied_by
from app.llm.ollama_client import OllamaClient
from app.matching.requirements import ground_in_description, normalise_skill_sections, search_terms, vector_query
from app.rag.embeddings import embed_query
from app.rag.keyword_index import keyword_search
from app.rag.vector_store import ChunkHit, get_vector_store

SIGNALS = ("skills", "keyword", "vector")


# --------------------------------------------------------------------------- result shapes
@dataclass
class SkillMatch:
    required: str                 # what the role asks for
    matched_with: str             # the employee's skill that satisfies it
    direct: bool                  # False = implied (e.g. "Amazon EKS" for "Kubernetes")
    years: float | None
    last_used_year: int | None
    credit: float                 # 0..1 how well this requirement is covered
    evidence: str | None
    weight: float = 1.0           # rarity of the requirement among eligible people (rare skills count more)


@dataclass
class Availability:
    status: str
    allocation_percent: int
    free_percent: int
    available_from: date | None
    fits: bool
    note: str


@dataclass
class Candidate:
    employee: Employee
    resume_id: int
    fused_score: float = 0.0
    ranks: dict[str, int | None] = field(default_factory=lambda: {s: None for s in SIGNALS})
    skill_score: float = 0.0
    must_matched: list[SkillMatch] = field(default_factory=list)
    must_missing: list[str] = field(default_factory=list)
    nice_matched: list[SkillMatch] = field(default_factory=list)
    keyword_snippets: list[str] = field(default_factory=list)
    vector_chunks: list[ChunkHit] = field(default_factory=list)
    availability: Availability | None = None


# --------------------------------------------------------------------------- availability (facts from HR)
def check_availability(emp: Employee, role: ProjectRole) -> Availability:
    free = 100 - (emp.allocation_percent or 0)
    needed = role.allocation_percent or 100
    start = role.start_date
    if emp.availability_status == AvailabilityStatus.ON_LEAVE:
        fits_now = False
    else:
        fits_now = free >= needed
    # Busy now, but free before the role starts?
    fits_later = bool(emp.available_from and start and emp.available_from <= start)
    fits = fits_now or fits_later
    if fits_now:
        note = f"{free}% free now (role needs {needed}%)"
    elif fits_later:
        note = f"free from {emp.available_from:%d %b %Y}, before the role starts ({start:%d %b %Y})"
    else:
        when = f"; available from {emp.available_from:%d %b %Y}" if emp.available_from else ""
        note = f"only {free}% free (role needs {needed}%){when}"
    return Availability(emp.availability_status.value, emp.allocation_percent or 0, free,
                        emp.available_from, fits, note)


# --------------------------------------------------------------------------- ① skills signal
def _credit(direct: bool, years: float | None, last_used: int | None, needed_years: float) -> float:
    """
    How well one employee skill covers one requirement (0..1):
      base     1.0 for the exact skill, 0.6 for an implied one (EKS for Kubernetes)
      years    0.4 + 0.6 * min(1, years / needed)   (unknown years -> 0.6)
      recency  used this/last year 1.0 · within 3 years 0.8 · older 0.5 · unknown 0.8
    """
    base = 1.0 if direct else 0.6
    years_factor = 0.6 if years is None else 0.4 + 0.6 * min(1.0, years / needed_years)
    if last_used is None:
        recency = 0.8
    else:
        age = date.today().year - last_used
        recency = 1.0 if age <= 1 else 0.8 if age <= 3 else 0.5
    return round(base * years_factor * recency, 3)


def _best_match(required: str, min_years: float | None, links: list[ResumeSkill],
                default_years: float) -> SkillMatch | None:
    needed = min_years or default_years
    best: SkillMatch | None = None
    req = required.lower()
    for link in links:
        name = link.skill.name
        direct = name.lower() == req                      # case-insensitive: "LLM evaluation" = "llm evaluation"
        if not direct and req not in {i.lower() for i in implied_by(name)}:
            continue
        credit = _credit(direct, link.years, link.last_used_year, needed)
        if best is None or credit > best.credit:
            best = SkillMatch(required, name, direct, link.years, link.last_used_year, credit, link.evidence)
    return best


def rarity_weight(people_with_skill: int, people_total: int) -> float:
    """
    IDF ("inverse document frequency", the idea behind BM25) applied to skills:
        weight = 1 + ln((N + 1) / (n + 1))      N = eligible people, n = people who have the skill
    Python that 12 of 14 people have -> ~1.1 ; RAG that 1 of 14 has -> ~3.0.
    Without it, a common must-have (Python) plus a few nice-to-haves could outweigh the rare
    must-have that actually defines the role (LLMs, RAG).
    """
    return round(1.0 + math.log((people_total + 1) / (people_with_skill + 1)), 3)


def skills_signal(candidates: dict[int, Candidate], skills_by_resume: dict[int, list[ResumeSkill]],
                  requirements: dict, default_years: float) -> list[int]:
    """
    Score every candidate on must/nice coverage; return employee ids, best first (only those with a match).
        must part   = Σ 2 × rarity × credit   over must-haves       (max: Σ 2 × rarity)
        nice part   = Σ 1 × rarity × credit   over nice-to-haves    (max: Σ 1 × rarity)
        coverage    = must part ÷ its max     (0..1; 1 when the role has no must-haves)
        skill score = (must part + nice part × coverage) ÷ (max must + max nice)
    Nice-to-haves only count in proportion to how well the must-haves are met, so FastAPI + Docker
    can't lift someone without the role's core skills above someone who has some of them.
    """
    must = requirements.get("must_have", [])
    nice = requirements.get("nice_to_have", [])
    total = len(candidates)
    matches: dict[int, list[tuple[str, dict, SkillMatch | None]]] = {}
    have_count: dict[str, int] = {}
    for emp_id, cand in candidates.items():
        links = skills_by_resume.get(cand.resume_id, [])
        rows = []
        for kind, reqs in (("must", must), ("nice", nice)):
            for req in reqs:
                m = _best_match(req["name"], req.get("min_years"), links, default_years)
                rows.append((kind, req, m))
                if m:
                    have_count[req["name"]] = have_count.get(req["name"], 0) + 1
        matches[emp_id] = rows

    weights = {req["name"]: rarity_weight(have_count.get(req["name"], 0), total) for req in must + nice}
    max_must = sum(2 * weights[r["name"]] for r in must)
    max_nice = sum(weights[r["name"]] for r in nice)
    for emp_id, rows in matches.items():
        cand = candidates[emp_id]
        must_part = nice_part = 0.0
        for kind, req, m in rows:
            if m:
                m.weight = weights[req["name"]]
                if kind == "must":
                    must_part += 2 * m.weight * m.credit
                    cand.must_matched.append(m)
                else:
                    nice_part += m.weight * m.credit
                    cand.nice_matched.append(m)
            elif kind == "must":
                cand.must_missing.append(req["name"])
        coverage = must_part / max_must if max_must else 1.0
        cand.skill_score = round((must_part + nice_part * coverage) / ((max_must + max_nice) or 1.0), 3)
    ranked = sorted((c for c in candidates.values() if c.skill_score > 0), key=lambda c: -c.skill_score)
    return [c.employee.id for c in ranked]


# --------------------------------------------------------------------------- RRF
def reciprocal_rank_fusion(rankings: dict[str, list[int]], weights: dict[str, float], k: int) -> dict[int, float]:
    """
    rankings: signal -> employee ids, best first.
    Each employee gets  Σ weight / (k + rank)  over the lists it appears in (rank starts at 1).
    k (60 by convention) keeps one #1 from dominating: being good in SEVERAL lists wins.
    """
    scores: dict[int, float] = {}
    for signal, ids in rankings.items():
        for rank, emp_id in enumerate(ids, start=1):
            scores[emp_id] = scores.get(emp_id, 0.0) + weights.get(signal, 1.0) / (k + rank)
    return scores


# --------------------------------------------------------------------------- the whole pipeline
async def retrieve_candidates(
    session: AsyncSession, ollama: OllamaClient, settings: Settings, role: ProjectRole,
    top_k: int = 15, only_available: bool = False, signals: tuple[str, ...] = SIGNALS,
) -> tuple[list[Candidate], dict]:
    # Normalise again at search time: older or hand-edited requirements get the latest catalog rules.
    requirements = normalise_skill_sections(role.requirements or {})
    if not requirements.get("edited_by_user"):          # a person's edits are trusted as they are
        requirements = ground_in_description(requirements, role.title, role.description)
    t0 = time.perf_counter()

    # 0. Who can be considered at all: active employees with a current, fully processed resume.
    resumes = (await session.scalars(
        select(Resume)
        .join(Employee, Employee.id == Resume.employee_id)
        .where(Resume.is_current.is_(True), Resume.status == ResumeStatus.READY, Employee.is_active.is_(True))
        .options(selectinload(Resume.employee), selectinload(Resume.skills).selectinload(ResumeSkill.skill))
    )).all()
    candidates: dict[int, Candidate] = {}
    skills_by_resume: dict[int, list[ResumeSkill]] = {}
    for r in resumes:
        cand = Candidate(employee=r.employee, resume_id=r.id, availability=check_availability(r.employee, role))
        if only_available and not cand.availability.fits:
            continue
        candidates[r.employee.id] = cand
        skills_by_resume[r.id] = list(r.skills)
    timings = {"eligible": len(candidates)}
    if not candidates:
        return [], timings
    resume_ids = [c.resume_id for c in candidates.values()]
    employee_ids = list(candidates)
    rankings: dict[str, list[int]] = {}

    # ① Skills (structured)
    if "skills" in signals:
        rankings["skills"] = skills_signal(candidates, skills_by_resume, requirements, settings.default_skill_min_years)
    t1 = time.perf_counter()

    # ② Keyword (BM25 over chunks)
    if "keyword" in signals:
        hits = await keyword_search(session, search_terms(requirements), resume_ids, settings.retrieval_keyword_pool)
        order: list[int] = []
        for hit in hits:                                   # best first
            cand = candidates.get(hit.employee_id)
            if cand is None:
                continue
            if hit.employee_id not in order:
                order.append(hit.employee_id)
            if len(cand.keyword_snippets) < 2:
                cand.keyword_snippets.append(hit.snippet)
        rankings["keyword"] = order
    t2 = time.perf_counter()

    # ③ Vector (meaning)
    if "vector" in signals:
        vec = await embed_query(ollama, vector_query(requirements), settings.embed_model)
        chunk_hits = await asyncio.to_thread(
            get_vector_store().query, vec, settings.retrieval_vector_pool,
            {"employee_id": {"$in": employee_ids}} if len(employee_ids) > 1 else {"employee_id": employee_ids[0]},
        )
        order = []
        for hit in chunk_hits:
            cand = candidates.get(hit.employee_id)
            if cand is None or hit.resume_id != cand.resume_id:
                continue
            if hit.employee_id not in order:
                order.append(hit.employee_id)
            if len(cand.vector_chunks) < 2:
                cand.vector_chunks.append(hit)
        rankings["vector"] = order
    t3 = time.perf_counter()

    # Fusion
    weights = {"skills": settings.rrf_weight_skills, "keyword": settings.rrf_weight_keyword,
               "vector": settings.rrf_weight_vector}
    fused = reciprocal_rank_fusion(rankings, weights, settings.rrf_k)
    for signal, ids in rankings.items():
        for rank, emp_id in enumerate(ids, start=1):
            candidates[emp_id].ranks[signal] = rank
    for emp_id, score in fused.items():
        candidates[emp_id].fused_score = round(score, 5)

    ranked = sorted((c for c in candidates.values() if c.fused_score > 0), key=lambda c: -c.fused_score)
    timings.update({
        "skills_ms": round((t1 - t0) * 1000), "keyword_ms": round((t2 - t1) * 1000),
        "vector_ms": round((t3 - t2) * 1000), "total_ms": round((time.perf_counter() - t0) * 1000),
        "found_by": {s: len(ids) for s, ids in rankings.items()},
    })
    return ranked[:top_k], timings
