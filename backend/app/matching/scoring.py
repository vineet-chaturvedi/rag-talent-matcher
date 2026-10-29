"""
Step 8, part 1: a transparent, rule-based score for every shortlisted candidate.

Retrieval (Step 7) found the right people (recall). Scoring puts them in a sensible ORDER using
facts retrieval ignores on purpose: total experience, seniority, availability and location.

    fit        = skills_share × skills + (1 − skills_share) × relevance
    rule score = fit × experience factor × availability factor × location factor

    skills       0..1  how well must-have / nice-to-have skills are covered (Step 7's skill score)
    relevance    0..1  position in Step 7's fused ranking (1 = first, 0 = last of the shortlist)
    experience   0..1  total years vs the role's minimum (or what its stated seniority implies)
    availability 0..1  free enough now, or before the role starts
    location     0..1  same city as the role, or the role has no location

    factor = floor + (1 − floor) × component        e.g. experience floor 0.6: 0 years → × 0.6, enough years → × 1.0

Why multiply instead of add? With a weighted SUM, someone with no relevant skills but who is free, local
and experienced still collects most of the points. With FACTORS, HR facts can only lower a skills-based fit,
never create one: availability can't make a Java developer a good DevOps candidate.
Every number is stored in the breakdown, so anyone can see WHY someone is ranked where they are.
"""
import re
from dataclasses import dataclass

from app.db.models import ProjectRole
from app.matching.retrieval import Candidate

# Years usually expected for a seniority word, used only when the role states no minimum years.
SENIORITY_YEARS = {"junior": 0.0, "mid": 3.0, "senior": 5.0, "lead": 7.0, "principal": 10.0}

_ANYWHERE = {"any", "anywhere", "remote", "any location", "flexible"}


@dataclass
class ScoreWeights:
    skills_share: float = 0.85         # fit = 85% skills, 15% retrieval relevance
    experience_floor: float = 0.6      # the most a lack of experience can reduce the score: × 0.6
    availability_floor: float = 0.7    # not available at all: × 0.7
    location_floor: float = 0.9        # another city (component 0.5): × 0.95

    def as_dict(self) -> dict[str, float]:
        return dict(vars(self))


def required_years(requirements: dict) -> float | None:
    """The role's minimum total years: stated, else implied by a stated seniority, else None (no requirement)."""
    if requirements.get("min_total_years") is not None:
        return float(requirements["min_total_years"])
    return SENIORITY_YEARS.get(requirements.get("seniority") or "") or None


def experience_fit(total_years: float | None, needed: float | None) -> float:
    """1.0 if the person has at least the required years; proportional below; 0.5 when unknown."""
    if not needed:
        return 1.0
    if total_years is None:
        return 0.5
    return round(min(1.0, total_years / needed), 3)


def availability_fit(cand: Candidate, needed_percent: int) -> float:
    """1.0 fits now · 0.9 fits before the start date · otherwise 0.8 × the share of the needed time that is free."""
    a = cand.availability
    if a.status == "on_leave":
        return 0.0
    if a.fits:
        return 1.0 if a.free_percent >= needed_percent else 0.9
    return round(max(0.0, min(1.0, a.free_percent / (needed_percent or 100))) * 0.8, 3)


def _city(text: str | None) -> str:
    """'Pune (hybrid)' -> 'pune'"""
    return re.sub(r"\(.*?\)", "", (text or "").lower()).strip(" ,.-")


def location_fit(role_location: str | None, employee_location: str | None) -> float:
    role_city = _city(role_location)
    if not role_city or role_city in _ANYWHERE:
        return 1.0
    if not employee_location:
        return 0.5
    emp_city = _city(employee_location)
    return 1.0 if role_city in emp_city or emp_city in role_city else 0.5


def _factor(floor: float, component: float) -> float:
    return floor + (1 - floor) * component


def score_candidates(candidates: list[Candidate], role: ProjectRole, requirements: dict,
                     total_years: dict[int, float | None], weights: ScoreWeights) -> list[tuple[Candidate, dict]]:
    """candidates must be in retrieval order (best first). Returns [(candidate, breakdown)], best rule score first."""
    needed_years = required_years(requirements)
    n = len(candidates)
    scored = []
    for position, cand in enumerate(candidates):
        years = total_years.get(cand.employee.id)
        parts = {
            "skills": round(cand.skill_score, 3),
            "relevance": round(1 - position / (n - 1), 3) if n > 1 else 1.0,
            "experience": experience_fit(years, needed_years),
            "availability": availability_fit(cand, role.allocation_percent or 100),
            "location": location_fit(role.location or requirements.get("location"), cand.employee.location),
        }
        fit = weights.skills_share * parts["skills"] + (1 - weights.skills_share) * parts["relevance"]
        factors = {
            "experience": _factor(weights.experience_floor, parts["experience"]),
            "availability": _factor(weights.availability_floor, parts["availability"]),
            "location": _factor(weights.location_floor, parts["location"]),
        }
        rule_score = fit * factors["experience"] * factors["availability"] * factors["location"]
        scored.append((cand, {
            **parts,
            "fit": round(fit, 4),
            "factors": {k: round(v, 3) for k, v in factors.items()},
            "rule_score": round(rule_score, 4),
            "total_years": years,
            "required_years": needed_years,
            "retrieval_ranks": cand.ranks,
        }))
    scored.sort(key=lambda pair: -pair[1]["rule_score"])
    return scored