"""API shapes for an extracted resume profile (Step 5)."""
from datetime import date

from pydantic import BaseModel


class EducationOut(BaseModel):
    degree: str | None = None
    institution: str | None = None
    year: str | None = None


class ProfileSkillOut(BaseModel):
    name: str
    category: str | None
    years: float | None
    last_used_year: int | None
    evidence: str | None
    uses: int = 0                       # jobs + projects that used it (doc 18)
    source: str | None = None           # job / project / skills list / certified / mentioned / learning
    years_basis: str | None = None      # jobs / projects / stated / estimated: how the years were found
    level: str | None = None            # basic / expert, when the resume says so


class ProfileProjectOut(BaseModel):
    name: str
    role: str | None
    duration_months: int | None
    duration_text: str | None
    technologies: list[str]
    description: str | None
    link: str | None
    company: str | None                 # the job it was written under, when known
    company_basis: str | None           # "inside job" / "only employer"


class ProfileJobOut(BaseModel):
    title: str | None
    company: str | None
    start_date: date | None
    end_date: date | None
    is_current: bool
    description: str | None


class ProfileOut(BaseModel):
    resume_id: int
    employee_code: str
    employee_name: str
    status: str
    extraction_model: str | None
    headline: str | None
    summary: str | None
    total_experience_years: float | None
    experience_basis: str | None = None   # "dated jobs" / "stated in resume"
    stated_years: float | None = None     # "6+ years" as written
    skills: list[ProfileSkillOut]
    experience: list[ProfileJobOut]
    projects: list[ProfileProjectOut] = []
    education: list[EducationOut]
    certifications: list[str]
    rejected_skills: list[dict]     # what the hallucination check removed
    warnings: list[str]
    stats: dict | None              # tokens and seconds of the LLM call
