"""
Match runs (Step 8):
  POST /api/roles/{id}/match         start a run: retrieve + rule-score now, LLM-judge the top N in the background
  GET  /api/match-runs/{id}          the run with its ranked results (poll this while status is "running")
  GET  /api/roles/{id}/match-runs    earlier runs for a role (history / audit)
"""
import asyncio

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_db, get_ollama
from app.config import Settings, get_settings
from app.db.models import MatchResult, MatchRun, ProjectRole
from app.llm.ollama_client import OllamaClient, OllamaError
from app.matching.runner import create_match_run, judge_run
from app.schemas.matching import MatchRequest, MatchResultOut, MatchRunOut, MatchRunSummary

router = APIRouter(tags=["match runs"])


async def _load_run(db: AsyncSession, run_id: int) -> MatchRun | None:
    return await db.get(MatchRun, run_id, populate_existing=True, options=[
        selectinload(MatchRun.role),
        selectinload(MatchRun.results).selectinload(MatchResult.employee),
    ])


def _to_out(run: MatchRun) -> MatchRunOut:
    results = sorted(run.results, key=lambda r: r.rank)
    statuses = [(r.explanation or {}).get("judge_status") for r in results]
    return MatchRunOut(
        id=run.id, role_id=run.role_id, role_title=run.role.title, status=run.status,
        started_at=run.started_at, finished_at=run.finished_at, error_message=run.error_message,
        judged=sum(s in ("done", "failed") for s in statuses),
        to_judge=sum(s in ("pending", "done", "failed") for s in statuses),
        settings=run.settings,
        results=[MatchResultOut(
            rank=r.rank, employee_id=r.employee_id, employee_code=r.employee.employee_code,
            full_name=r.employee.full_name, designation=r.employee.designation, location=r.employee.location,
            final_score=r.final_score, score_breakdown=r.score_breakdown, explanation=r.explanation,
        ) for r in results],
    )


@router.post("/api/roles/{role_id}/match", response_model=MatchRunOut, status_code=202)
async def start_match(
    role_id: int, body: MatchRequest, request: Request,
    db: AsyncSession = Depends(get_db),
    ollama: OllamaClient = Depends(get_ollama),
    settings: Settings = Depends(get_settings),
):
    role = await db.get(ProjectRole, role_id)
    if role is None:
        raise HTTPException(status_code=404, detail="Role not found")
    if not role.requirements:
        raise HTTPException(status_code=409, detail="This role has no requirements yet: call /requirements/parse first.")
    try:
        run = await create_match_run(db, ollama, settings, role, body.top_k,
                                     min(body.judge_top_n, body.top_k), body.only_available)
    except OllamaError as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    if run.status == "running":
        # Judge in the background; keep a reference so the task isn't garbage-collected mid-run.
        task = asyncio.create_task(judge_run(run.id, ollama, settings), name=f"judge-run-{run.id}")
        request.app.state.match_tasks.add(task)
        task.add_done_callback(request.app.state.match_tasks.discard)
    return _to_out(await _load_run(db, run.id))


@router.get("/api/match-runs/{run_id}", response_model=MatchRunOut)
async def get_match_run(run_id: int, db: AsyncSession = Depends(get_db)):
    run = await _load_run(db, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Match run not found")
    return _to_out(run)


@router.get("/api/roles/{role_id}/match-runs", response_model=list[MatchRunSummary])
async def list_match_runs(role_id: int, db: AsyncSession = Depends(get_db)):
    runs = (await db.scalars(
        select(MatchRun).where(MatchRun.role_id == role_id).order_by(MatchRun.id.desc())
        .options(selectinload(MatchRun.results).selectinload(MatchResult.employee))
    )).all()
    return [MatchRunSummary(
        id=r.id, status=r.status, started_at=r.started_at, finished_at=r.finished_at,
        top=[x.employee.employee_code for x in sorted(r.results, key=lambda x: x.rank)[:3]],
    ) for r in runs]