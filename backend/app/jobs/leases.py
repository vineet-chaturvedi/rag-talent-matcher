"""
Who is working on what: claims and leases in the database (the source of truth for every job).

A worker CLAIMS a row with one conditional UPDATE ("set it to working, if it is still waiting"): if two
workers try at the same moment, the database lets exactly one succeed (rowcount 1), on SQLite and PostgreSQL
alike, so no job is ever done twice at once. The claim holds a LEASE (lease_expires_at), which the worker
renews while it works. If the worker dies (crash, deploy, out of memory), the lease runs out and the sweeper
(any worker, every minute) puts the job back: nothing is lost, nothing stays stuck.
"""
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, func, or_, select, update

from app.db.enums import MatchRunStatus, ResumeStatus
from app.db.models import MatchRun, Resume
from app.db.session import SessionLocal
from app.ingestion.pipeline import STAGE_FOR_WAITING, STAGES, WAITING, WORKING, Claimed

logger = logging.getLogger(__name__)


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)        # stored as naive UTC, like func.now()


def _lease(seconds: float) -> datetime:
    return utcnow() + timedelta(seconds=seconds)


# --------------------------------------------------------------------------- resumes
async def claim_resume(resume_id: int, lease_seconds: float) -> Claimed | None:
    """Claim this resume's next stage. None = nothing to do (done, failed, deleted, replaced or taken)."""
    async with SessionLocal() as session:
        row = (await session.execute(
            select(Resume.status, Resume.attempts, Resume.stored_path, Resume.mime_type, Resume.raw_text)
            .where(Resume.id == resume_id, Resume.is_current.is_(True), Resume.status.in_(WAITING)))).first()
        if row is None:
            return None
        stage = STAGE_FOR_WAITING[row.status]
        result = await session.execute(
            update(Resume)
            .where(Resume.id == resume_id, Resume.status == stage.waiting)          # still waiting: the guard
            .values(status=stage.working, attempts=Resume.attempts + 1, error_message=None,
                    lease_expires_at=_lease(lease_seconds)))
        if result.rowcount != 1:                                                  # another worker was faster
            await session.rollback()
            return None
        await session.commit()
        return Claimed(resume_id, stage, row.attempts + 1, row.stored_path, row.mime_type, row.raw_text)


async def renew_resume(resume_id: int, lease_seconds: float) -> None:
    async with SessionLocal() as session:
        await session.execute(update(Resume).where(Resume.id == resume_id, Resume.status.in_(WORKING))
                              .values(lease_expires_at=_lease(lease_seconds)))
        await session.commit()


async def release_resume(claim: Claimed) -> None:
    """Give an unfinished stage back (shutting down): waiting again, the attempt not counted."""
    async with SessionLocal() as session:
        await session.execute(update(Resume).where(Resume.id == claim.id, Resume.status == claim.stage.working)
                              .values(status=claim.stage.waiting, attempts=Resume.attempts - 1,
                                      lease_expires_at=None))
        await session.commit()


# --------------------------------------------------------------------------- match runs (the LLM judge)
async def claim_run(run_id: int, lease_seconds: float) -> bool:
    """Claim a running match run for judging, if nobody holds a live lease on it."""
    now = utcnow()
    async with SessionLocal() as session:
        result = await session.execute(
            update(MatchRun)
            .where(MatchRun.id == run_id, MatchRun.status == MatchRunStatus.RUNNING,
                   or_(MatchRun.lease_expires_at.is_(None), MatchRun.lease_expires_at < now))
            .values(lease_expires_at=now + timedelta(seconds=lease_seconds), attempts=MatchRun.attempts + 1))
        await session.commit()
        return result.rowcount == 1


async def renew_run(run_id: int, lease_seconds: float) -> None:
    async with SessionLocal() as session:
        await session.execute(update(MatchRun).where(MatchRun.id == run_id, MatchRun.status == MatchRunStatus.RUNNING)
                              .values(lease_expires_at=_lease(lease_seconds)))
        await session.commit()


async def release_run(run_id: int) -> None:
    """Shutting down mid-run: free it at once for another worker (the judged results are kept)."""
    async with SessionLocal() as session:
        await session.execute(update(MatchRun).where(MatchRun.id == run_id, MatchRun.status == MatchRunStatus.RUNNING)
                              .values(lease_expires_at=None, attempts=MatchRun.attempts - 1))
        await session.commit()


# --------------------------------------------------------------------------- finding and recovering work
async def find_work(limit: int) -> list[tuple[str, int]]:
    """
    For the local queue (no message broker): the jobs waiting in the database, most urgent first.
      1. resumes waiting for EMBED  (seconds: a resume whose profile is done becomes searchable at once)
      2. resumes waiting for PARSE  (seconds: a broken or scanned file is reported right after upload)
      3. match runs waiting for the judge, oldest first
      4. resumes waiting for EXTRACT (minutes of LLM), oldest upload first
    """
    jobs: list[tuple[str, int]] = []
    now = utcnow()
    async with SessionLocal() as session:
        def resumes_in(status: ResumeStatus):
            return select(Resume.id).where(Resume.status == status, Resume.is_current.is_(True)) \
                .order_by(Resume.created_at, Resume.id).limit(limit)
        by_stage = {s.name: [("ingest", i) for i in (await session.scalars(resumes_in(s.waiting))).all()]
                    for s in STAGES}
        runs = [("judge", i) for i in (await session.scalars(
            select(MatchRun.id).where(MatchRun.status == MatchRunStatus.RUNNING,
                                      or_(MatchRun.lease_expires_at.is_(None), MatchRun.lease_expires_at < now))
            .order_by(MatchRun.id).limit(limit))).all()]
    for group in (by_stage["embed"], by_stage["parse"], runs, by_stage["extract"]):
        jobs.extend(group)
    return jobs[:limit]


async def recover_expired(max_attempts: int, force: bool = False) -> tuple[list[int], list[int]]:
    """
    The sweeper: work whose worker stopped renewing its lease (crashed, killed, out of memory).
    Resumes go back to waiting (or FAILED after max_attempts tries); match runs are offered to another worker
    (or FAILED after max_attempts). Returns the (resume ids, run ids) to dispatch again.
    force: treat every lease as run out (the only worker starting up: whatever is "in progress" was interrupted).
    """
    now = utcnow()
    resumes: list[int] = []
    async with SessionLocal() as session:
        expired = or_(Resume.lease_expires_at.is_(None), Resume.lease_expires_at < now)   # None: before Step 15
        if force:
            expired = Resume.id.is_not(None)
        for stage in STAGES:
            rows = (await session.execute(select(Resume.id, Resume.attempts).where(
                Resume.status == stage.working, expired))).all()
            for rid, attempts in rows:
                give_up = attempts >= max_attempts
                done = await session.execute(update(Resume).where(Resume.id == rid, Resume.status == stage.working,
                                                                  expired).values(
                    status=ResumeStatus.FAILED if give_up else stage.waiting, lease_expires_at=None,
                    error_message=(f"{stage.name}: the worker stopped responding {attempts} times (gave up)"
                                   if give_up else None)))
                if done.rowcount and not give_up:
                    resumes.append(rid)
                if done.rowcount:
                    logger.warning("Resume %s: worker lease ran out during %s (%s)", rid, stage.name,
                                   "gave up" if give_up else "back in the queue")
        expired_run = and_(MatchRun.status == MatchRunStatus.RUNNING, MatchRun.lease_expires_at.is_not(None),
                           MatchRun.lease_expires_at < now if not force else MatchRun.id.is_not(None))
        await session.execute(update(MatchRun).where(expired_run, MatchRun.attempts >= max_attempts).values(
            status=MatchRunStatus.FAILED, finished_at=now, lease_expires_at=None,
            error_message=f"The judge stopped {max_attempts} times (worker restarts or crashes); start a new run."))
        runs = list((await session.scalars(select(MatchRun.id).where(expired_run))).all())
        if runs:                                # free them now, so the next claim needn't wait for the time
            await session.execute(update(MatchRun).where(MatchRun.id.in_(runs)).values(lease_expires_at=None))
        await session.commit()
    if runs:
        logger.warning("Match runs %s: judge lease ran out; offered to another worker", runs)
    return resumes, runs


async def stale_waiting(older_than_seconds: float) -> list[int]:
    """
    Resumes waiting longer than this without anyone taking them: their message may have been lost (a
    publish that failed after the database commit). Touched now, so they are offered again only once per
    period; delivering a job twice is harmless (the claim decides).
    """
    cutoff = utcnow() - timedelta(seconds=older_than_seconds)
    async with SessionLocal() as session:
        ids = list((await session.scalars(select(Resume.id).where(
            Resume.status.in_(WAITING), Resume.is_current.is_(True), Resume.updated_at < cutoff))).all())
        if ids:
            await session.execute(update(Resume).where(Resume.id.in_(ids)).values(updated_at=func.now()))
            await session.commit()
        return ids


async def stale_runs(older_than_seconds: float) -> list[int]:
    """Match runs waiting for the judge for longer than this, never taken (a lost message): offer them again."""
    cutoff = utcnow() - timedelta(seconds=older_than_seconds)
    async with SessionLocal() as session:
        return list((await session.scalars(select(MatchRun.id).where(
            MatchRun.status == MatchRunStatus.RUNNING, MatchRun.lease_expires_at.is_(None),
            MatchRun.started_at < cutoff))).all())


async def waiting_resumes() -> list[int]:
    """Every current resume waiting for a stage (after a bulk re-queue: re-extract all, re-embed all)."""
    async with SessionLocal() as session:
        return list((await session.scalars(select(Resume.id).where(
            Resume.status.in_(WAITING), Resume.is_current.is_(True)).order_by(Resume.id))).all())
