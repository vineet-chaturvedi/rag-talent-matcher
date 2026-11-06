"""API shapes for feedback (Step 14c)."""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.db.enums import FeedbackRating, FeedbackTarget

# Reasons offered in the portal. Fixed lists, so feedback can be counted and turned into test cases.
MatchReason = Literal["missing_skill", "too_little_experience", "not_available", "profile_wrong",
                      "should_rank_higher", "should_rank_lower", "other"]
AgentReason = Literal["wrong_people", "missed_someone", "wrong_numbers", "misunderstood", "too_long", "other"]


class MatchFeedbackIn(BaseModel):
    rating: FeedbackRating
    reason: MatchReason | None = None
    comment: str | None = Field(None, max_length=1000)


class AgentFeedbackIn(BaseModel):
    rating: FeedbackRating
    reason: AgentReason | None = None
    comment: str | None = Field(None, max_length=1000)


class MyFeedback(BaseModel):
    """The signed-in person's own rating of one item (shown as the pressed thumb)."""
    rating: FeedbackRating
    reason: str | None = None
    comment: str | None = None


class FeedbackItem(BaseModel):
    """One rating in the admin list, with enough context to understand it."""
    id: int
    target: FeedbackTarget
    rating: FeedbackRating
    reason: str | None
    comment: str | None
    created_at: datetime
    updated_at: datetime
    user_name: str
    match_run_id: int | None = None
    role_id: int | None = None
    role_title: str | None = None
    employee_id: int | None = None
    employee_code: str | None = None
    employee_name: str | None = None
    context: dict | None = None


class FeedbackCounts(BaseModel):
    match_up: int = 0
    match_down: int = 0
    agent_up: int = 0
    agent_down: int = 0


class FeedbackList(BaseModel):
    counts: FeedbackCounts
    items: list[FeedbackItem]
