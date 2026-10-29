"""API shapes for match runs (Step 8)."""
from datetime import datetime

from pydantic import BaseModel, Field

from app.db.enums import MatchRunStatus


class MatchRequest(BaseModel):
    top_k: int = Field(10, ge=1, le=50, description="How many candidates to keep and score")
    judge_top_n: int = Field(5, ge=0, le=20, description="How many of them the LLM judge reads (0 = no judge)")
    only_available: bool = Field(False, description="Only people who can take the role's allocation by its start date")


class MatchResultOut(BaseModel):
    rank: int
    employee_id: int
    employee_code: str
    full_name: str
    designation: str | None
    location: str | None
    final_score: float
    score_breakdown: dict      # skills, experience, relevance, availability, location, rule_score, judge_score...
    explanation: dict | None   # facts from retrieval + the judge's verdict (judge_status: pending/done/failed/...)


class MatchRunOut(BaseModel):
    id: int
    role_id: int
    role_title: str
    status: MatchRunStatus
    started_at: datetime
    finished_at: datetime | None
    error_message: str | None
    judged: int                # how many results have a judge verdict so far
    to_judge: int              # how many were requested
    settings: dict | None
    results: list[MatchResultOut]


class MatchRunSummary(BaseModel):
    id: int
    status: MatchRunStatus
    started_at: datetime
    finished_at: datetime | None
    top: list[str]             # employee codes of the top 3