"""API shapes for an extracted resume profile (Step 5)."""
from datetime import date

from pydantic import BaseModel


class ProfileSkillOut(BaseModel):
    name: str
    category: str | None
    years: float | None
    last_used_year: int | None
    evidence: str | None


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
    skills: list[ProfileSkillOut]
    experience: list[ProfileJobOut]
    education: list[dict]
    certifications: list[str]
    rejected_skills: list[dict]     # what the hallucination check removed
    warnings: list[str]
    stats: dict | None              # tokens and seconds of the LLM call
