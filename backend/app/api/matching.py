"""
Match runs (Step 8):
  POST /api/roles/{id}/match         start a run: retrieve + rule-score now, LLM-judge the top N in a background
                                     worker (a "judge" job, app/jobs)
  GET  /api/match-runs/{id}          the run with its ranked results (poll this while status is "running")
  GET  /api/roles/{id}/match-runs    earlier runs for a role (history / audit)
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_db, get_ollama
from app.auth.dependencies import get_current_user
from app.config import Settings, get_settings
from app.db.enums import FeedbackRating, MatchRunStatus
from app.db.models import Feedback, MatchResult, MatchRun, ProjectRole, User
from app.jobs import Job, dispatch
from app.llm.ollama_client import OllamaClient, OllamaError
from app.matching.runner import create_match_run
from app.schemas.feedback import MyFeedback
from app.schemas.matching import MatchRequest, MatchResultOut, MatchRunOut, MatchRunSummary

router = APIRouter(tags=["match runs"])


async def _load_run(db: AsyncSession, run_id: int) -> MatchRun | None:
    return await db.get(MatchRun, run_id, populate_existing=True, options=[
        selectinload(MatchRun.role),
        selectinload(MatchRun.results).selectinload(MatchResult.employee),
    ])


async def _feedback(db: AsyncSession, run: MatchRun, user: User | None) -> tuple[dict, dict]:
    """(my rating per result id, {result id: [up, down]}) for the results of a run."""
    ids = [r.id for r in run.results]
    if not ids:
        return {}, {}
    rows = (await db.scalars(select(Feedback).where(Feedback.match_result_id.in_(ids)))).all()
    mine, counts = {}, {}
    for fb in rows:
        c = counts.setdefault(fb.match_result_id, [0, 0])
        c[0 if fb.rating == FeedbackRating.UP else 1] += 1
        if user is not None and fb.user_id == user.id:
            mine[fb.match_result_id] = MyFeedback(rating=fb.rating, reason=fb.reason, comment=fb.comment)
    return mine, counts


def _to_out(run: MatchRun, mine: dict | None = None, counts: dict | None = None) -> MatchRunOut:
    mine, counts = mine or {}, counts or {}
    results = sorted(run.results, key=lambda r: r.rank)
    statuses = [(r.explanation or {}).get("judge_status") for r in results]
    return MatchRunOut(
        id=run.id, role_id=run.role_id, role_title=run.role.title, status=run.status,
        started_at=run.started_at, finished_at=run.finished_at, error_message=run.error_message,
        judged=sum(s in ("done", "failed") for s in statuses),
        to_judge=sum(s in ("pending", "done", "failed") for s in statuses),
        settings=run.settings,
        results=[MatchResultOut(
            result_id=r.id, my_feedback=mine.get(r.id),
            feedback_up=counts.get(r.id, [0, 0])[0], feedback_down=counts.get(r.id, [0, 0])[1],
            rank=r.rank, employee_id=r.employee_id, employee_code=r.employee.employee_code,
            full_name=r.employee.full_name, designation=r.employee.designation, location=r.employee.location,
            final_score=r.final_score,
            score_breakdown=r.score_breakdown or {}, explanation=r.explanation or {},
        ) for r in results],
    )


@router.post("/api/roles/{role_id}/match", response_model=MatchRunOut, status_code=202)
async def start_match(
    role_id: int, body: MatchRequest,
    db: AsyncSession = Depends(get_db),
    ollama: OllamaClient = Depends(get_ollama),
    settings: Settings = Depends(get_settings),
    user: User = Depends(get_current_user),
):
    role = await db.get(ProjectRole, role_id)
    if role is None:
        raise HTTPException(status_code=404, detail="Role not found")
    if not role.requirements:
        raise HTTPException(status_code=409, detail="This role has no requirements yet: call /requirements/parse first.")
    try:
        run = await create_match_run(db, ollama, settings, role, body.top_k,
                                     min(body.judge_top_n, body.top_k), body.only_available,
                                     created_by_id=user.id)
    except OllamaError as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    if run.status == MatchRunStatus.RUNNING:
        # The LLM judge runs in a background worker (app/jobs); the page polls the run for progress.
        await dispatch([Job("judge", run.id)])
    return _to_out(await _load_run(db, run.id))


@router.get("/api/match-runs/{run_id}", response_model=MatchRunOut)
async def get_match_run(run_id: int, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    run = await _load_run(db, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Match run not found")
    return _to_out(run, *await _feedback(db, run, user))


@router.get("/api/roles/{role_id}/match-runs", response_model=list[MatchRunSummary])
async def list_match_runs(role_id: int, db: AsyncSession = Depends(get_db)):
    runs = (await db.scalars(
        select(MatchRun).where(MatchRun.role_id == role_id).order_by(MatchRun.id.desc())
        .options(selectinload(MatchRun.results).selectinload(MatchResult.employee))
    )).all()
    summaries = []
    for r in runs:
        top = sorted(r.results, key=lambda x: x.rank)[:3]
        summaries.append(MatchRunSummary(
            id=r.id, status=r.status, started_at=r.started_at, finished_at=r.finished_at,
            top=[x.employee.employee_code for x in top], top_names=[x.employee.full_name for x in top],
            judge_top_n=(r.settings or {}).get("judge_top_n", 0), result_count=len(r.results),
        ))
    return summaries
