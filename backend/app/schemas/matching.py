"""API shapes for match runs (Step 8)."""
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.db.enums import AvailabilityStatus, MatchRunStatus
from app.schemas.project import Requirements, SkillMatchOut


class MatchRequest(BaseModel):
    top_k: int = Field(10, ge=1, le=50, description="How many candidates to keep and score")
    judge_top_n: int = Field(5, ge=0, le=20, description="How many of them the LLM judge reads (0 = no judge)")
    only_available: bool = Field(False, description="Only people who can take the role's allocation by its start date")


# ---------------------------------------------------------------------------------------------------
# Typed views of the JSON stored per result (Step 12b). The database keeps free-form JSON (it grew over
# Steps 7-8 and must stay readable); these models describe it for the API, so the portal gets exact
# TypeScript types instead of "any". Every field that older runs may lack has a default.
# ---------------------------------------------------------------------------------------------------
class ScoreFactors(BaseModel):
    experience: float = 1.0
    availability: float = 1.0
    location: float = 1.0


class ScoreBreakdown(BaseModel):
    """How the rule score was computed (Step 8): fit = 0.85*skills + 0.15*relevance, times the factors."""
    skills: float = 0.0
    relevance: float = 0.0
    experience: float = 1.0
    availability: float = 1.0
    location: float = 1.0
    fit: float = 0.0
    factors: ScoreFactors = ScoreFactors()
    rule_score: float = 0.0
    total_years: float | None = None
    required_years: float | None = None
    retrieval_ranks: dict[str, int | None] = {}
    judge_score: float | None = None        # only after the judge has read this candidate
    final_score: float | None = None


class AvailabilityFacts(BaseModel):
    status: AvailabilityStatus
    allocation_percent: int
    free_percent: int
    available_from: date | None = None
    fits: bool
    note: str


class RetrievalFacts(BaseModel):
    """What retrieval found (Step 7), saved with the result so the page needs no re-run."""
    must_matched: list[SkillMatchOut] = []
    must_missing: list[str] = []
    nice_matched: list[SkillMatchOut] = []
    keyword_snippets: list[str] = []
    availability: AvailabilityFacts | None = None


class MustHaveVerdictOut(BaseModel):
    requirement: str
    met: Literal["yes", "partly", "no"]
    claimed: Literal["yes", "partly", "no"] | None = None   # what the model said before verification
    quote: str | None = None
    verified: bool = False                                    # the quote really is in the resume
    note: str | None = None


class StrengthOut(BaseModel):
    point: str
    quote: str | None = None
    verified: bool = False


class JudgeStats(BaseModel):
    model: str | None = None
    seconds: float | None = None
    prompt_tokens: int | None = None
    output_tokens: int | None = None


class JudgeVerdictOut(BaseModel):
    """The LLM judge's verdict AFTER code verified its quotes and computed the score (Step 8)."""
    rating: Literal["strong", "good", "partial", "weak"]
    summary: str
    must_haves: list[MustHaveVerdictOut] = []
    strengths: list[StrengthOut] = []
    gaps: list[str] = []
    judge_score: float | None = None
    quotes_verified: int = 0
    quotes_total: int = 0
    stats: JudgeStats | None = None
    llm_output: dict | None = None        # exactly what the model returned, for audit


class Explanation(BaseModel):
    facts: RetrievalFacts = RetrievalFacts()
    judge: JudgeVerdictOut | None = None
    judge_status: Literal["pending", "done", "failed", "not_requested"] = "not_requested"
    judge_error: str | None = None


class MatchRunSettings(BaseModel):
    """What the run was started with, kept for audit: rerunning later may give different results."""
    top_k: int
    judge_top_n: int
    only_available: bool = False
    judge_weight: float | None = None
    judge_model: str | None = None
    embed_model: str | None = None
    requirements: Requirements | None = None
    retrieval_timings: dict | None = None


class MatchResultOut(BaseModel):
    rank: int
    employee_id: int
    employee_code: str
    full_name: str
    designation: str | None
    location: str | None
    final_score: float
    score_breakdown: ScoreBreakdown
    explanation: Explanation


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
    settings: MatchRunSettings | None
    results: list[MatchResultOut]


class MatchRunSummary(BaseModel):
    id: int
    status: MatchRunStatus
    started_at: datetime
    finished_at: datetime | None
    top: list[str]             # employee codes of the top 3
    top_names: list[str] = []  # their names, for the history list (Step 12b)
    judge_top_n: int = 0
    result_count: int = 0
