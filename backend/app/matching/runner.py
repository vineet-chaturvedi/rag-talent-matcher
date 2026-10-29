"""
Step 8, part 3: a MATCH RUN - retrieval, rule scoring and LLM judging for one role, saved for audit.

    POST /api/roles/{id}/match
      ├─ now (~0.1 s):   retrieve (Step 7) → rule score → save run + results (status RUNNING) → reply 202
      └─ background:     LLM judge the top N one by one (~35-80 s each on a CPU), saving after each
                         → mix judge score into the final score → re-rank → status COMPLETED

Why in the background? Judging 5 people takes minutes on a CPU; an HTTP request should not wait that long.
The browser (Step 13) polls GET /api/match-runs/{id} and shows results filling in.
Why saved? So every recommendation can be explained later: who was suggested, with what scores,
which model, which weights (match_runs.settings). That's the audit trail.
"""
import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import Settings
from app.db.enums import MatchRunStatus
from app.db.models import MatchResult, MatchRun, ProjectRole, Resume, ResumeChunk, ResumeProfile
from app.db.session import SessionLocal
from app.llm.ollama_client import OllamaClient, OllamaError
from app.matching.judge import JudgeError, build_dossier, judge_candidate
from app.matching.requirements import effective_requirements
from app.matching.retrieval import retrieve_candidates
from app.matching.scoring import score_candidates

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)    # stored as naive UTC, like func.now()


def _facts(cand) -> dict:
    """What retrieval found, kept with the result so the UI can show it without re-running anything."""
    return {
        "must_matched": [vars(m) for m in cand.must_matched],
        "must_missing": cand.must_missing,
        "nice_matched": [vars(m) for m in cand.nice_matched],
        "keyword_snippets": cand.keyword_snippets,
        "availability": {**vars(cand.availability),
                         "available_from": cand.availability.available_from.isoformat()
                         if cand.availability.available_from else None},
    }


# --------------------------------------------------------------------------- part 1: synchronous
async def create_match_run(session: AsyncSession, ollama: OllamaClient, settings: Settings, role: ProjectRole,
                           top_k: int, judge_top_n: int, only_available: bool,
                           created_by_id: int | None = None) -> MatchRun:
    requirements = effective_requirements(role)
    weights = settings.score_weights
    candidates, timings = await retrieve_candidates(session, ollama, settings, role, top_k=top_k,
                                                    only_available=only_available)
    years = dict((await session.execute(
        select(Resume.employee_id, ResumeProfile.total_experience_years)
        .join(ResumeProfile, ResumeProfile.resume_id == Resume.id)
        .where(Resume.id.in_([c.resume_id for c in candidates]))
    )).all()) if candidates else {}
    scored = score_candidates(candidates, role, requirements, years, weights)

    run = MatchRun(
        role_id=role.id, status=MatchRunStatus.RUNNING, created_by_id=created_by_id,
        settings={
            "top_k": top_k, "judge_top_n": judge_top_n, "only_available": only_available,
            "weights": weights.as_dict(), "judge_weight": settings.judge_weight,
            "judge_model": settings.judge_model if judge_top_n else None,
            "embed_model": settings.embed_model, "rrf_k": settings.rrf_k,
            "requirements": requirements, "retrieval_timings": timings,
        },
    )
    run.results = [
        MatchResult(
            employee_id=cand.employee.id, resume_id=cand.resume_id, rank=i + 1,
            final_score=breakdown["rule_score"], score_breakdown=breakdown,
            explanation={"facts": _facts(cand), "judge": None,
                         "judge_status": "pending" if i < judge_top_n else "not_requested"},
        )
        for i, (cand, breakdown) in enumerate(scored)
    ]
    if judge_top_n == 0 or not run.results:
        run.status, run.finished_at = MatchRunStatus.COMPLETED, _now()
    session.add(run)
    await session.commit()
    return run


# --------------------------------------------------------------------------- part 2: background judging
async def _dossier_for(session: AsyncSession, resume_id: int, max_chars: int) -> tuple[str, str]:
    resume = await session.get(Resume, resume_id, options=[selectinload(Resume.profile),
                                                            selectinload(Resume.experiences)])
    chunks = (await session.execute(
        select(ResumeChunk.section, ResumeChunk.text).where(ResumeChunk.resume_id == resume_id)
        .order_by(ResumeChunk.chunk_index)
    )).all()
    lines = []
    if resume.profile and resume.profile.total_experience_years is not None:
        lines.append(f"Total experience (calculated from job dates): {resume.profile.total_experience_years} years")
    jobs = sorted(resume.experiences, key=lambda e: e.start_date.isoformat() if e.start_date else "", reverse=True)
    if jobs:
        lines.append("Jobs: " + "; ".join(
            f"{j.title or 'Role'} ({j.start_date.year if j.start_date else '?'} - "
            f"{'present' if j.is_current else (j.end_date.year if j.end_date else '?')})" for j in jobs))
    return build_dossier(lines, [(str(sec), text) for sec, text in chunks], max_chars)


async def judge_run(run_id: int, ollama: OllamaClient, settings: Settings) -> None:
    """Judge the pending results of one run, one at a time, saving after each."""
    try:
        async with SessionLocal() as session:
            run = await session.get(MatchRun, run_id, options=[selectinload(MatchRun.results),
                                                               selectinload(MatchRun.role)])
            requirements = run.settings["requirements"]
            judge_weight = run.settings["judge_weight"]
            for result in sorted(run.results, key=lambda r: r.rank):
                if result.explanation.get("judge_status") != "pending":
                    continue
                explanation = dict(result.explanation)        # a NEW dict, so SQLAlchemy sees the JSON change
                dossier, evidence = await _dossier_for(session, result.resume_id, settings.judge_max_dossier_chars)
                try:
                    verdict = await judge_candidate(
                        ollama, settings.judge_model, settings.llm_num_ctx, settings.judge_max_output_tokens,
                        run.role.title, requirements, dossier, evidence,
                    )
                except (JudgeError, OllamaError) as exc:
                    logger.warning("Run %s: judging employee %s failed: %s", run_id, result.employee_id, exc)
                    explanation.update(judge_status="failed", judge_error=str(exc))
                else:
                    explanation.update(judge_status="done", judge=verdict)
                    rule = result.score_breakdown["rule_score"]
                    if verdict["judge_score"] is not None:
                        result.final_score = round((1 - judge_weight) * rule + judge_weight * verdict["judge_score"], 4)
                    result.score_breakdown = {**result.score_breakdown, "judge_score": verdict["judge_score"],
                                              "final_score": result.final_score}
                result.explanation = explanation
                await session.commit()                          # progress is visible while the run continues
                logger.info("Run %s: judged employee %s (%s)", run_id, result.employee_id,
                            explanation["judge_status"])

            # Re-rank ONLY the judged top N by their final score. The others keep their places below:
            # judge scores and rule scores are on different scales, so mixing them across the whole list
            # would unfairly push judged people under unjudged ones ("rerank the top N" pattern).
            top = sorted(run.results, key=lambda r: r.rank)[: run.settings["judge_top_n"]]
            for rank, result in enumerate(sorted(top, key=lambda r: -r.final_score), start=1):
                result.rank = rank
            run.status, run.finished_at = MatchRunStatus.COMPLETED, _now()
            await session.commit()
    except asyncio.CancelledError:
        await _fail(run_id, "Stopped because the server shut down; start a new run.")
        raise
    except Exception as exc:                                    # never leave a run stuck in RUNNING
        logger.exception("Run %s failed", run_id)
        await _fail(run_id, f"{type(exc).__name__}: {exc}")


async def _fail(run_id: int, message: str) -> None:
    async with SessionLocal() as session:
        await session.execute(update(MatchRun).where(MatchRun.id == run_id)
                              .values(status=MatchRunStatus.FAILED, error_message=message, finished_at=_now()))
        await session.commit()


async def recover_interrupted_runs() -> int:
    """At startup: runs still RUNNING were interrupted by a stop/crash. Mark them FAILED (clearly, not silently)."""
    async with SessionLocal() as session:
        result = await session.execute(
            update(MatchRun).where(MatchRun.status == MatchRunStatus.RUNNING)
            .values(status=MatchRunStatus.FAILED, error_message="Interrupted by a server restart; start a new run.",
                    finished_at=_now())
        )
        await session.commit()
        return result.rowcount
