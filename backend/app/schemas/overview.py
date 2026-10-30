"""API shapes for the health check and the dashboard overview (Step 11b).

Why these exist: the frontend generates its TypeScript types from FastAPI's OpenAPI document
(/openapi.json). An endpoint without a response model shows up there as "returns anything", and the
frontend loses its type safety. Every endpoint the UI reads should declare its response shape.
"""
from typing import Literal

from pydantic import BaseModel

from app.db.enums import MatchRunStatus, ProjectStatus, RoleStatus


# --------------------------------------------------------------------------- GET /api/health
class DatabaseHealth(BaseModel):
    reachable: bool
    error: str | None = None


class ModelHealth(BaseModel):
    name: str
    installed: bool


class OllamaHealth(BaseModel):
    reachable: bool
    version: str | None = None
    models: dict[str, ModelHealth] | None = None    # keys: embed_model, fast_llm_model, quality_llm_model
    error: str | None = None


class HealthOut(BaseModel):
    app: str
    environment: str
    status: Literal["ok", "degraded", "error"]
    database: DatabaseHealth
    ollama: OllamaHealth


# --------------------------------------------------------------------------- GET /api/overview
class EmployeeCounts(BaseModel):
    total: int
    active: int


class ProjectCounts(BaseModel):
    total: int
    by_status: dict[ProjectStatus, int]


class RoleCounts(BaseModel):
    total: int
    by_status: dict[RoleStatus, int]
    parsed: int                  # roles whose requirements the LLM has already parsed (Step 7)


class MatchRunCounts(BaseModel):
    total: int
    by_status: dict[MatchRunStatus, int]


class Overview(BaseModel):
    """Everything the dashboard's number tiles need, in one small response (counts, never rows)."""
    employees: EmployeeCounts
    projects: ProjectCounts
    roles: RoleCounts
    match_runs: MatchRunCounts
