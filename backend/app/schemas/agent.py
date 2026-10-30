"""API shapes for the agent (Step 10)."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ConversationCreate(BaseModel):
    title: str | None = Field(None, max_length=200)


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    role: str                      # user / assistant / tool
    content: str
    tool_calls: list | None
    tool_name: str | None
    created_at: datetime


class ConversationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    created_at: datetime
    updated_at: datetime


class ConversationDetail(ConversationOut):
    messages: list[MessageOut]


class AskRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=4000,
                         examples=["Who could lead a Kubernetes migration on AWS starting 1 December?"])
    stream: bool = Field(True, description="true = Server-Sent Events while the agent works; false = one JSON reply")


class AskResponse(BaseModel):
    answer: str
    events: list[dict]             # tool calls and results, in order (what the agent did)
