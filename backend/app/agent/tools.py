"""
The agent's tools (Step 10): small, READ-ONLY functions the LLM may ask us to run.

An LLM can't search a database. What it CAN do is write a request like
    {"name": "find_candidates", "arguments": {"must_have": ["Kubernetes", "AWS"], "start_date": "2026-12-01"}}
Our code checks the request (Pydantic), runs the real function (Steps 6-8 code), and gives the result back
to the model as text. The model never touches the database itself.

Each tool = a name + a description (the model reads it to decide WHEN to use the tool) + an argument
schema (WHAT to pass) + a Python function. Every tool is read-only: the agent can look things up and
recommend, but it cannot upload, delete or change anything ("least privilege").
"""
import json
import logging
from dataclasses import dataclass
from datetime import date

from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import Settings
from app.db.enums import MatchRunStatus, ResumeStatus
from app.db.models import (Employee, MatchResult, MatchRun, Project, Resume, ResumeProfile,
                           ResumeSkill, User)
from app.llm.ollama_client import OllamaClient
from app.matching.requirements import normalise_skill_sections
from app.matching.retrieval import check_availability, retrieve_candidates
from app.matching.scoring import score_candidates
from app.rag.search import semantic_search
from app.rag.vector_store import get_vector_store

logger = logging.getLogger(__name__)


@dataclass
class ToolContext:
    """What every tool may use. `user` is the person chatting: tools run with THEIR permissions."""
    session: AsyncSession
    ollama: OllamaClient
    settings: Settings
    user: User


@dataclass
class AdHocRole:
    """A role described in the chat, not saved as a project (has the fields retrieval and scoring read)."""
    title: str
    description: str
    requirements: dict
    allocation_percent: int = 100
    start_date: date | None = None
    location: str | None = None


# --------------------------------------------------------------------------- argument schemas
class SearchArgs(BaseModel):
    query: str = Field(..., description="What to look for, in plain words, e.g. 'payments systems in Java'")
    top_k: int = Field(5, ge=1, le=10)


class FindCandidatesArgs(BaseModel):
    must_have: list[str] = Field(..., description="Required skills as short names, e.g. ['Kubernetes', 'AWS']")
    nice_to_have: list[str] = Field([], description="Optional skills")
    min_total_years: float | None = Field(None, description="Minimum years of total experience, if stated")
    description: str = Field("", description="One sentence describing the work, used for meaning search")
    location: str | None = Field(None, description="Work location (city) if stated, else null")
    start_date: date | None = Field(None, description="When the person must start, if stated")
    allocation_percent: int = Field(100, ge=10, le=100, description="Share of the person's time needed")
    only_available: bool = Field(False, description="True to return only people free enough by the start date")
    top_k: int = Field(5, ge=1, le=10)


class EmployeeArgs(BaseModel):
    employee_code: str = Field(..., description="Employee code like EMP-1003")


class AvailabilityArgs(BaseModel):
    employee_code: str = Field(..., description="Employee code like EMP-1003")
    start_date: date | None = Field(None, description="Planned start date")
    allocation_percent: int = Field(100, ge=10, le=100)


class NoArgs(BaseModel):
    pass


class RoleArgs(BaseModel):
    role_id: int = Field(..., description="Role id from list_projects")


# --------------------------------------------------------------------------- the tools
async def search_employees(ctx: ToolContext, a: SearchArgs) -> dict:
    matches, _ = await semantic_search(ctx.session, ctx.ollama, get_vector_store(), ctx.settings.embed_model,
                                       a.query, top_k=a.top_k)
    return {"results": [{
        "employee_code": m.employee.employee_code, "name": m.employee.full_name,
        "designation": m.employee.designation, "location": m.employee.location,
        "availability": m.employee.availability_status.value, "allocation_percent": m.employee.allocation_percent,
        "similarity": round(m.score, 3),
        "evidence": m.chunks[0].text.split("\n", 1)[-1][:300] if m.chunks else None,
    } for m in matches]}


async def find_candidates(ctx: ToolContext, a: FindCandidatesArgs) -> dict:
    requirements = normalise_skill_sections({
        "must_have": [{"name": s, "min_years": None} for s in a.must_have],
        "nice_to_have": [{"name": s, "min_years": None} for s in a.nice_to_have],
    })
    skills = ", ".join(s["name"] for s in requirements["must_have"])
    requirements.update(title="Ad-hoc request", seniority="unspecified", min_total_years=a.min_total_years,
                        location=a.location, domain=[], edited_by_user=True,   # stated by a person: no grounding
                        search_summary=a.description or f"Experience with {skills}")
    role = AdHocRole("Ad-hoc request", a.description, requirements, a.allocation_percent, a.start_date, a.location)
    candidates, _ = await retrieve_candidates(ctx.session, ctx.ollama, ctx.settings, role, top_k=a.top_k,
                                              only_available=a.only_available)
    years = dict((await ctx.session.execute(
        select(Resume.employee_id, ResumeProfile.total_experience_years)
        .join(ResumeProfile, ResumeProfile.resume_id == Resume.id)
        .where(Resume.id.in_([c.resume_id for c in candidates]))
    )).all()) if candidates else {}
    scored = score_candidates(candidates, role, requirements, years, ctx.settings.score_weights)
    return {
        "requirements_used": {"must_have": [s["name"] for s in requirements["must_have"]],
                              "nice_to_have": [s["name"] for s in requirements["nice_to_have"]]},
        "candidates": [{
            "employee_code": c.employee.employee_code, "name": c.employee.full_name,
            "designation": c.employee.designation, "location": c.employee.location,
            "score": b["rule_score"], "total_years": b["total_years"],
            "matched": [f"{m.required} (via {m.matched_with}" + (f", {m.years} y" if m.years else "")
                        + (f", last used {m.last_used_year})" if m.last_used_year else ")") for m in c.must_matched],
            "missing": c.must_missing,
            "nice_matched": [m.required for m in c.nice_matched],
            "availability": c.availability.note,
        } for c, b in scored],
    }


async def _employee(ctx: ToolContext, code: str) -> Employee | None:
    return await ctx.session.scalar(select(Employee).where(func.upper(Employee.employee_code) == code.strip().upper()))


async def get_employee_profile(ctx: ToolContext, a: EmployeeArgs) -> dict:
    emp = await _employee(ctx, a.employee_code)
    if emp is None:
        return {"error": f"No employee with code {a.employee_code}."}
    resume = await ctx.session.scalar(
        select(Resume).where(Resume.employee_id == emp.id, Resume.is_current.is_(True),
                             Resume.status == ResumeStatus.READY)
        .options(selectinload(Resume.profile), selectinload(Resume.experiences),
                 selectinload(Resume.skills).selectinload(ResumeSkill.skill)))
    out = {"employee_code": emp.employee_code, "name": emp.full_name, "designation": emp.designation,
           "department": emp.department, "location": emp.location,
           "availability": emp.availability_status.value, "allocation_percent": emp.allocation_percent,
           "available_from": emp.available_from.isoformat() if emp.available_from else None,
           "current_project": emp.current_project_name}
    if resume is None or resume.profile is None:
        return {**out, "profile": "No processed resume yet."}
    skills = sorted(resume.skills, key=lambda s: -(s.years or 0))[:15]
    out.update(
        headline=resume.profile.headline, total_years=resume.profile.total_experience_years,
        skills=[f"{s.skill.name}" + (f" ({s.years} y, last used {s.last_used_year})" if s.years else "") for s in skills],
        jobs=[f"{j.title} at {j.company} ({j.start_date.year if j.start_date else '?'}-"
              f"{'present' if j.is_current else (j.end_date.year if j.end_date else '?')})"
              for j in sorted(resume.experiences, key=lambda j: j.start_date or date.min, reverse=True)],
        certifications=resume.profile.certifications or [],
    )
    return out


async def check_employee_availability(ctx: ToolContext, a: AvailabilityArgs) -> dict:
    emp = await _employee(ctx, a.employee_code)
    if emp is None:
        return {"error": f"No employee with code {a.employee_code}."}
    role = AdHocRole("availability check", "", {}, a.allocation_percent, a.start_date)
    av = check_availability(emp, role)
    return {"employee_code": emp.employee_code, "name": emp.full_name, "fits": av.fits, "note": av.note,
            "current_project": emp.current_project_name}


async def list_projects(ctx: ToolContext, a: NoArgs) -> dict:
    projects = (await ctx.session.scalars(select(Project).options(selectinload(Project.roles)).order_by(Project.id))).all()
    return {"projects": [{
        "project": p.name, "status": p.status.value,
        "roles": [{"role_id": r.id, "title": r.title, "allocation_percent": r.allocation_percent,
                   "start_date": r.start_date.isoformat() if r.start_date else None,
                   "requirements_parsed": bool(r.requirements)} for r in p.roles],
    } for p in projects]}


async def get_match_results(ctx: ToolContext, a: RoleArgs) -> dict:
    run = await ctx.session.scalar(
        select(MatchRun).where(MatchRun.role_id == a.role_id, MatchRun.status == MatchRunStatus.COMPLETED)
        .order_by(MatchRun.id.desc()).limit(1)
        .options(selectinload(MatchRun.results).selectinload(MatchResult.employee), selectinload(MatchRun.role)))
    if run is None:
        return {"error": "No completed match run for this role yet. Start one in the portal (Find best matches)."}
    results = []
    for r in sorted(run.results, key=lambda r: r.rank)[:5]:
        judge = (r.explanation or {}).get("judge") or {}
        results.append({"rank": r.rank, "employee_code": r.employee.employee_code, "name": r.employee.full_name,
                        "final_score": r.final_score, "judge_rating": judge.get("rating"),
                        "judge_summary": judge.get("summary"),
                        "missing": (r.explanation or {}).get("facts", {}).get("must_missing", []),
                        "availability": (r.explanation or {}).get("facts", {}).get("availability", {}).get("note")})
    return {"role": run.role.title, "match_run_id": run.id, "finished_at": str(run.finished_at), "top": results}


# --------------------------------------------------------------------------- registry
TOOLS = {
    "search_employees": (search_employees, SearchArgs,
        "Find employees whose resumes MEAN something similar to a free-text query (experience, domain, "
        "achievements). Use for open questions like 'who has worked on insurance claims?'."),
    "find_candidates": (find_candidates, FindCandidatesArgs,
        "Rank employees for a staffing need given required skills (and optionally years, location, start date, "
        "allocation). Uses skill matching, keyword and meaning search, experience and availability. "
        "Use this for 'who can do X' or 'find someone for Y' questions."),
    "get_employee_profile": (get_employee_profile, EmployeeArgs,
        "Details of one employee: skills with years and last used year, jobs, certifications, availability."),
    "check_employee_availability": (check_employee_availability, AvailabilityArgs,
        "Whether one employee can take a role with a given allocation from a given start date."),
    "list_projects": (list_projects, NoArgs,
        "List internal projects and their open roles (with role ids)."),
    "get_match_results": (get_match_results, RoleArgs,
        "The latest saved match results for a project role (ranked, with the LLM judge's rating and summary)."),
}


def _simplify(prop: dict) -> dict:
    """Pydantic's schema -> a smaller one that small models read more reliably (and fewer tokens)."""
    prop = {k: v for k, v in prop.items() if k not in ("title", "default")}
    if "anyOf" in prop:                                # "number or null" -> "number" (optional = not required)
        types = [t for t in prop.pop("anyOf") if t.get("type") != "null"]
        if types:
            prop.update(types[0])
    if prop.get("format") == "date":
        prop["description"] = prop.get("description", "") + " (YYYY-MM-DD)"
        prop.pop("format")
    return prop


def tool_specs() -> list[dict]:
    """The tool list in the format Ollama (and OpenAI-style APIs) expect."""
    specs = []
    for name, (_fn, args_model, description) in TOOLS.items():
        schema = args_model.model_json_schema()
        specs.append({"type": "function", "function": {
            "name": name, "description": description,
            "parameters": {"type": "object",
                           "properties": {k: _simplify(v) for k, v in schema.get("properties", {}).items()},
                           "required": schema.get("required", [])},
        }})
    return specs


async def run_tool(ctx: ToolContext, name: str, arguments: dict | str | None, max_chars: int) -> dict:
    """Validate the model's arguments, run the tool, and never let an error crash the conversation."""
    if name not in TOOLS:
        return {"error": f"Unknown tool '{name}'. Available: {', '.join(TOOLS)}."}
    fn, args_model, _ = TOOLS[name]
    if isinstance(arguments, str):                    # some models send arguments as a JSON string
        try:
            arguments = json.loads(arguments or "{}")
        except json.JSONDecodeError:
            return {"error": "Arguments were not valid JSON."}
    try:
        args = args_model.model_validate(arguments or {})
    except ValidationError as exc:                     # tell the model what was wrong, so it can retry
        return {"error": f"Invalid arguments: {exc.errors(include_url=False)}"}
    try:
        result = await fn(ctx, args)
    except Exception as exc:                           # a broken tool must not break the chat
        logger.exception("Tool %s failed", name)
        return {"error": f"The tool failed: {type(exc).__name__}: {exc}"}
    text = json.dumps(result, default=str)
    if len(text) > max_chars:                          # protect the context window
        result = {"truncated": True, "partial": text[:max_chars]}
    return result
