"""
The agent's API (Step 10). Every user sees only their own conversations.
  POST   /api/agent/conversations                 start a conversation
  GET    /api/agent/conversations                 my conversations, newest first
  GET    /api/agent/conversations/{id}            one conversation with all messages (incl. tool calls)
  DELETE /api/agent/conversations/{id}            delete it
  POST   /api/agent/conversations/{id}/messages   ask; the reply streams as Server-Sent Events:
         data: {"type": "tool_call", "name": "find_candidates", "arguments": {...}}
         data: {"type": "tool_result", "name": "find_candidates", "ok": true, "summary": "5 found: EMP-1003, ..."}
         data: {"type": "token", "text": "Priya"}          (the answer, piece by piece)
         data: {"type": "answer", "text": "...", "steps": 2, "seconds": 74.1}
"""
import json
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.agent.loop import run_agent
from app.agent.tools import ToolContext
from app.api.deps import get_db, get_ollama
from app.auth.dependencies import get_current_user
from app.config import Settings, get_settings
from app.db.models import AgentConversation, AgentMessage, User
from app.db.session import SessionLocal
from app.llm.ollama_client import OllamaClient, OllamaError
from app.schemas.agent import AskRequest, AskResponse, ConversationCreate, ConversationDetail, ConversationOut

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/agent", tags=["agent"])


async def _own_conversation(db: AsyncSession, conversation_id: int, user: User, with_messages=False):
    options = [selectinload(AgentConversation.messages)] if with_messages else []
    conv = await db.get(AgentConversation, conversation_id, options=options)
    if conv is None or conv.user_id != user.id:      # someone else's conversation looks the same as none
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Conversation not found")
    return conv


@router.post("/conversations", response_model=ConversationOut, status_code=status.HTTP_201_CREATED)
async def create_conversation(body: ConversationCreate, db: AsyncSession = Depends(get_db),
                              user: User = Depends(get_current_user)):
    conv = AgentConversation(user_id=user.id, title=body.title or "New conversation")
    db.add(conv)
    await db.commit()
    await db.refresh(conv)
    return conv


@router.get("/conversations", response_model=list[ConversationOut])
async def list_conversations(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    return (await db.scalars(select(AgentConversation).where(AgentConversation.user_id == user.id)
                             .order_by(AgentConversation.updated_at.desc(), AgentConversation.id.desc()))).all()


@router.get("/conversations/{conversation_id}", response_model=ConversationDetail)
async def get_conversation(conversation_id: int, db: AsyncSession = Depends(get_db),
                           user: User = Depends(get_current_user)):
    return await _own_conversation(db, conversation_id, user, with_messages=True)


@router.delete("/conversations/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(conversation_id: int, db: AsyncSession = Depends(get_db),
                              user: User = Depends(get_current_user)):
    await db.delete(await _own_conversation(db, conversation_id, user))
    await db.commit()


async def _history(db: AsyncSession, conversation_id: int, limit: int) -> list[dict]:
    """Short-term memory: the last few questions and FINAL answers (not old tool results, to save context)."""
    rows = (await db.scalars(
        select(AgentMessage).where(AgentMessage.conversation_id == conversation_id,
                                   AgentMessage.role.in_(("user", "assistant")),
                                   AgentMessage.tool_calls.is_(None), AgentMessage.content != "")
        .order_by(AgentMessage.id.desc()).limit(limit)
    )).all()
    return [{"role": m.role, "content": m.content} for m in reversed(rows)]


@router.post("/conversations/{conversation_id}/messages", response_model=AskResponse)
async def ask(conversation_id: int, body: AskRequest, db: AsyncSession = Depends(get_db),
              user: User = Depends(get_current_user), ollama: OllamaClient = Depends(get_ollama),
              settings: Settings = Depends(get_settings)):
    conv = await _own_conversation(db, conversation_id, user)
    history = await _history(db, conv.id, settings.agent_history_messages)
    db.add(AgentMessage(conversation_id=conv.id, role="user", content=body.content))
    if conv.title == "New conversation":
        conv.title = body.content[:80]
    await db.commit()
    user_id, conv_id = user.id, conv.id

    async def events():
        # Its own session: the request's session may already be closed while the stream is still running.
        async with SessionLocal() as session:
            ctx = ToolContext(session, ollama, settings, await session.get(User, user_id))
            try:
                async for event in run_agent(ctx, settings.agent_model, history, body.content):
                    if event["type"] == "_save":
                        session.add(AgentMessage(conversation_id=conv_id, **event["message"]))
                    else:
                        yield event
            except OllamaError as exc:
                yield {"type": "error", "message": str(exc)}
            except Exception as exc:
                logger.exception("Agent failed in conversation %s", conv_id)
                yield {"type": "error", "message": f"The agent failed: {type(exc).__name__}"}
            finally:
                await session.execute(update(AgentConversation).where(AgentConversation.id == conv_id)
                                      .values(updated_at=func.now()))
                await session.commit()          # keep whatever happened, for memory and audit

    if body.stream:
        async def sse():
            async for event in events():
                yield f"data: {json.dumps(event, default=str)}\n\n"
        return StreamingResponse(sse(), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    collected = [e async for e in events()]
    answer = next((e["text"] for e in collected if e["type"] == "answer"), "")
    errors = [e["message"] for e in collected if e["type"] == "error"]
    if errors and not answer:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, errors[0])
    return AskResponse(answer=answer, events=[e for e in collected if e["type"] != "token"])
