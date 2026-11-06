"""
Feedback (Step 14c): people rate match results and agent answers; every rating is a labelled example.
  PUT    /api/match-results/{id}/feedback     rate one candidate of a match run (any signed-in user)
  DELETE /api/match-results/{id}/feedback     take my rating back
  PUT    /api/agent/messages/{id}/feedback    rate one answer of MY conversation
  DELETE /api/agent/messages/{id}/feedback
  GET    /api/feedback                        all ratings with context, newest first (admins)
One rating per person per item: rating again replaces it.
"""
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_db
from app.auth.dependencies import get_current_user, require_admin
from app.db.enums import FeedbackRating, FeedbackTarget
from app.db.models import AgentConversation, AgentMessage, Employee, Feedback, MatchResult, MatchRun, ProjectRole, User
from app.schemas.feedback import (
    AgentFeedbackIn, FeedbackCounts, FeedbackItem, FeedbackList, MatchFeedbackIn, MyFeedback,
)

router = APIRouter(tags=["feedback"])


def _mine(fb: Feedback) -> MyFeedback:
    return MyFeedback(rating=fb.rating, reason=fb.reason, comment=fb.comment)


def _clean(text: str | None) -> str | None:
    text = (text or "").strip()
    return text or None


async def _upsert(db: AsyncSession, user: User, where, values: dict) -> Feedback:
    fb = await db.scalar(select(Feedback).where(Feedback.user_id == user.id, where))
    if fb is None:
        fb = Feedback(user_id=user.id, **values)
        db.add(fb)
    else:
        for key, value in values.items():
            setattr(fb, key, value)
    await db.commit()
    await db.refresh(fb)
    return fb


# --------------------------------------------------------------------------- match results
@router.put("/api/match-results/{result_id}/feedback", response_model=MyFeedback)
async def rate_match_result(result_id: int, body: MatchFeedbackIn, db: AsyncSession = Depends(get_db),
                            user: User = Depends(get_current_user)):
    result = await db.get(MatchResult, result_id, options=[selectinload(MatchResult.run).selectinload(MatchRun.role)])
    if result is None:
        raise HTTPException(status_code=404, detail="Match result not found")
    breakdown = result.score_breakdown or {}
    judge = (result.explanation or {}).get("judge") or {}
    requirements = (result.run.settings or {}).get("requirements") or {}
    context = {
        "run_id": result.run_id, "rank": result.rank, "final_score": result.final_score,
        "rule_score": breakdown.get("rule_score"), "judge_rating": judge.get("rating"),
        "role_title": result.run.role.title,
        "must_have": [s.get("name") for s in requirements.get("must_have", [])],
        "nice_to_have": [s.get("name") for s in requirements.get("nice_to_have", [])],
    }
    fb = await _upsert(db, user, Feedback.match_result_id == result.id, {
        "target": FeedbackTarget.MATCH_RESULT, "rating": body.rating, "reason": body.reason,
        "comment": _clean(body.comment), "match_result_id": result.id, "match_run_id": result.run_id,
        "role_id": result.run.role_id, "employee_id": result.employee_id, "context": context,
    })
    return _mine(fb)


@router.delete("/api/match-results/{result_id}/feedback", status_code=status.HTTP_204_NO_CONTENT)
async def unrate_match_result(result_id: int, db: AsyncSession = Depends(get_db),
                              user: User = Depends(get_current_user)):
    fb = await db.scalar(select(Feedback).where(Feedback.user_id == user.id, Feedback.match_result_id == result_id))
    if fb is not None:
        await db.delete(fb)
        await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --------------------------------------------------------------------------- agent answers
async def _own_answer(db: AsyncSession, message_id: int, user: User) -> AgentMessage:
    msg = await db.get(AgentMessage, message_id)
    conv = await db.get(AgentConversation, msg.conversation_id) if msg else None
    # Someone else's message answers 404, not 403: don't reveal that it exists.
    if msg is None or conv is None or conv.user_id != user.id:
        raise HTTPException(status_code=404, detail="Answer not found")
    if msg.role != "assistant" or msg.tool_calls or not msg.content.strip():
        raise HTTPException(status_code=409, detail="Only the assistant's final answers can be rated.")
    return msg


@router.put("/api/agent/messages/{message_id}/feedback", response_model=MyFeedback)
async def rate_agent_answer(message_id: int, body: AgentFeedbackIn, db: AsyncSession = Depends(get_db),
                            user: User = Depends(get_current_user)):
    msg = await _own_answer(db, message_id, user)
    # The question and what the agent did for it: the messages between the previous user message and this answer.
    earlier = (await db.scalars(
        select(AgentMessage).where(AgentMessage.conversation_id == msg.conversation_id, AgentMessage.id < msg.id)
        .order_by(AgentMessage.id.desc()).limit(30)
    )).all()
    question, calls = None, []
    for m in earlier:                      # newest first, back to the question
        if m.role == "user":
            question = m.content
            break
        if m.role == "assistant" and m.tool_calls:
            calls = list(m.tool_calls) + calls
    context = {"conversation_id": msg.conversation_id, "question": question, "answer": msg.content,
               "tool_calls": calls}
    fb = await _upsert(db, user, Feedback.agent_message_id == msg.id, {
        "target": FeedbackTarget.AGENT_ANSWER, "rating": body.rating, "reason": body.reason,
        "comment": _clean(body.comment), "agent_message_id": msg.id, "context": context,
    })
    return _mine(fb)


@router.delete("/api/agent/messages/{message_id}/feedback", status_code=status.HTTP_204_NO_CONTENT)
async def unrate_agent_answer(message_id: int, db: AsyncSession = Depends(get_db),
                              user: User = Depends(get_current_user)):
    await _own_answer(db, message_id, user)
    fb = await db.scalar(select(Feedback).where(Feedback.user_id == user.id, Feedback.agent_message_id == message_id))
    if fb is not None:
        await db.delete(fb)
        await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --------------------------------------------------------------------------- admin overview
@router.get("/api/feedback", response_model=FeedbackList, dependencies=[Depends(require_admin)])
async def list_feedback(target: FeedbackTarget | None = None, rating: FeedbackRating | None = None,
                        limit: int = Query(50, ge=1, le=500), offset: int = Query(0, ge=0),
                        db: AsyncSession = Depends(get_db)):
    counts = FeedbackCounts()
    for t, r, n in (await db.execute(
            select(Feedback.target, Feedback.rating, func.count()).group_by(Feedback.target, Feedback.rating))).all():
        key = f"{'match' if t == FeedbackTarget.MATCH_RESULT else 'agent'}_{r.value}"
        setattr(counts, key, n)

    query = (select(Feedback, User.full_name, ProjectRole.title, Employee.employee_code, Employee.full_name)
             .join(User, User.id == Feedback.user_id)
             .outerjoin(ProjectRole, ProjectRole.id == Feedback.role_id)
             .outerjoin(Employee, Employee.id == Feedback.employee_id))
    if target:
        query = query.where(Feedback.target == target)
    if rating:
        query = query.where(Feedback.rating == rating)
    rows = (await db.execute(query.order_by(Feedback.updated_at.desc(), Feedback.id.desc())
                             .limit(limit).offset(offset))).all()
    items = [FeedbackItem(
        id=fb.id, target=fb.target, rating=fb.rating, reason=fb.reason, comment=fb.comment,
        created_at=fb.created_at, updated_at=fb.updated_at, user_name=user_name,
        match_run_id=fb.match_run_id, role_id=fb.role_id, role_title=role_title,
        employee_id=fb.employee_id, employee_code=code, employee_name=emp_name, context=fb.context,
    ) for fb, user_name, role_title, code, emp_name in rows]
    return FeedbackList(counts=counts, items=items)
