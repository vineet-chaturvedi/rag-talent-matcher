"""API shapes for projects, roles, requirements and candidates (Step 7)."""
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.db.enums import AvailabilityStatus, ProjectStatus, RoleStatus


# --------------------------------------------------------------------------- projects & roles
class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=200)
    client_name: str | None = Field(None, max_length=200)
    description: str | None = None
    status: ProjectStatus = ProjectStatus.PLANNED
    start_date: date | None = None
    end_date: date | None = None


class RoleCreate(BaseModel):
    title: str = Field(..., min_length=2, max_length=200, examples=["DevOps / Platform Engineer (Kubernetes)"])
    description: str = Field(..., min_length=20, examples=["Platform engineer to migrate 60 services to Kubernetes on AWS..."])
    location: str | None = Field(None, max_length=100)
    allocation_percent: int = Field(100, ge=1, le=100)
    start_date: date | None = None
    headcount: int = Field(1, ge=1, le=50)
    min_experience_years: float | None = Field(None, ge=0, le=50)


class RequiredSkill(BaseModel):
    name: str
    min_years: float | None = None
    as_written: str | None = None


class Requirements(BaseModel):
    """Parsed by the LLM, and editable by a person (PUT) when the AI got something wrong."""
    title: str | None = None
    seniority: Literal["junior", "mid", "senior", "lead", "principal", "unspecified"] = "unspecified"
    must_have: list[RequiredSkill] = []
    nice_to_have: list[RequiredSkill] = []
    min_total_years: float | None = None
    location: str | None = None
    domain: list[str] = []
    search_summary: str = ""
    parsed_by: str | None = None
    parsed_at: str | None = None
    edited_by_user: bool = False


class RoleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    title: str
    description: str
    location: str | None
    allocation_percent: int
    start_date: date | None
    headcount: int
    min_experience_years: float | None
    status: RoleStatus
    requirements: Requirements | None
    created_at: datetime


class ProjectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    client_name: str | None
    description: str | None
    status: ProjectStatus
    start_date: date | None
    end_date: date | None
    roles: list[RoleOut] = []


# --------------------------------------------------------------------------- candidates
class CandidatesRequest(BaseModel):
    top_k: int = Field(15, ge=1, le=100)
    only_available: bool = Field(False, description="Exclude people who can't take the role's allocation by its start date")
    signals: list[Literal["skills", "keyword", "vector"]] = ["skills", "keyword", "vector"]


class SkillMatchOut(BaseModel):
    required: str
    matched_with: str
    direct: bool
    years: float | None
    last_used_year: int | None
    credit: float
    evidence: str | None
    weight: float


class AvailabilityOut(BaseModel):
    status: AvailabilityStatus
    allocation_percent: int
    free_percent: int
    available_from: date | None
    fits: bool
    note: str


class ChunkEvidence(BaseModel):
    section: str
    similarity: float
    text: str


class CandidateOut(BaseModel):
    rank: int
    employee_id: int
    employee_code: str
    full_name: str
    designation: str | None
    location: str | None
    fused_score: float
    ranks: dict[str, int | None]           # rank in each signal (None = not found by it)
    skill_score: float
    must_matched: list[SkillMatchOut]
    must_missing: list[str]
    nice_matched: list[SkillMatchOut]
    keyword_snippets: list[str]
    vector_chunks: list[ChunkEvidence]
    availability: AvailabilityOut


class CandidatesResponse(BaseModel):
    role_id: int
    role_title: str
    requirements: Requirements
    candidates: list[CandidateOut]
    timings: dict
