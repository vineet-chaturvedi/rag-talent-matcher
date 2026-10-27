"""API shapes for search (Step 6: semantic search)."""
from pydantic import BaseModel, Field

from app.db.enums import AvailabilityStatus


class SemanticSearchRequest(BaseModel):
    query: str = Field(..., min_length=2, max_length=2000,
                       examples=["container orchestration and infrastructure as code"])
    top_k: int = Field(10, ge=1, le=50, description="How many employees to return")


class MatchedChunk(BaseModel):
    section: str
    similarity: float
    text: str


class EmployeeResult(BaseModel):
    rank: int
    employee_id: int
    employee_code: str
    full_name: str
    designation: str | None
    location: str | None
    availability_status: AvailabilityStatus
    allocation_percent: int
    score: float
    matched_chunks: list[MatchedChunk]


class SemanticSearchResponse(BaseModel):
    query: str
    results: list[EmployeeResult]
    timings: dict
