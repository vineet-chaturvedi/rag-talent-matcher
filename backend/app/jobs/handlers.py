"""
What a worker does with each kind of job. Every handler first CLAIMS its row (app/jobs/leases.py), so a
duplicate, late or already-finished message simply finds nothing to do.
"""
import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass

from app.config import Settings
from app.db.enums import ResumeStatus
from app.ingestion.pipeline import EXTRACT, PARSE, Claimed, run_stage, update_resume
from app.ingestion.text_extraction import ExtractionError
from app.jobs.base import Delivery, Job
from app.jobs.leases import claim_resume, claim_run, release_resume, release_run, renew_resume, renew_run
from app.llm.errors import LLMError
from app.matching.runner import judge_run

logger = logging.getLogger(__name__)


@dataclass
class Outcome:
    """How a job ended. Default: done (the message is removed)."""
    retry_after: float | None = None      # not done: deliver the same job again after this many seconds
    pause: float = 0.0                    # the model service is down: this consumer waits before taking more
    next_job: Job | None = None           # hand the work back to the queue (published before the ack)


@contextlib.asynccontextmanager
async def keep_alive(renew: Callable[[], Awaitable[None]], delivery: Delivery,
                     lease_seconds: float) -> AsyncIterator[None]:
    """While the work runs, renew the database lease and the message's invisibility every third of the lease,
    so a 10-minute LLM step on a CPU is never mistaken for a dead worker."""
    async def beat() -> None:
        while True:
            await asyncio.sleep(lease_seconds / 3)
            try:
                await renew()
                await delivery.extend(lease_seconds)
            except Exception:                                  # a missed beat is not fatal: the next one may work
                logger.warning("Could not renew the lease of %s", delivery.job, exc_info=True)
    task = asyncio.create_task(beat(), name=f"lease-{delivery.job.kind}-{delivery.job.id}")
    try:
        yield
    finally:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task


class Handlers:
    def __init__(self, settings: Settings, ollama):
        self.settings, self.ollama = settings, ollama

    async def handle(self, delivery: Delivery) -> Outcome:
        if delivery.job.kind == "ingest":
            return await self.ingest(delivery)
        return await self.judge(delivery)

    # ------------------------------------------------------------------ resumes
    async def ingest(self, delivery: Delivery) -> Outcome:
        """
        Take one resume through its stages. After PARSE (seconds) the resume goes back to the queue, so every
        upload of a batch is parsed (and a broken file reported) before the long LLM steps start; after
        EXTRACT it continues straight to EMBED, so each resume is searchable the moment its own LLM step ends.
        """
        s, resume_id = self.settings, delivery.job.id
        while True:
            claim = await claim_resume(resume_id, s.worker_lease_seconds)
            if claim is None:
                return Outcome()                                   # nothing (more) to do
            logger.info("Resume %s: %s (attempt %d)", resume_id, claim.stage.name, claim.attempt)
            try:
                async with keep_alive(lambda: renew_resume(resume_id, s.worker_lease_seconds), delivery,
                                      s.worker_lease_seconds):
                    await run_stage(claim, self.ollama, s)
            except asyncio.CancelledError:
                await asyncio.shield(release_resume(claim))        # shutting down: give the stage back now
                raise
            except ExtractionError as exc:
                # The file itself is the problem (scanned, corrupt, missing): retrying won't help.
                logger.warning("Resume %s failed permanently: %s", resume_id, exc)
                await update_resume(resume_id, status=ResumeStatus.FAILED, error_message=str(exc))
                return Outcome()
            except LLMError as exc:
                if not exc.retryable:
                    return await self._failed_attempt(claim, exc)   # this request was refused: a real attempt
                # The model service is down, busy or not set up: not the resume's fault. Undo the attempt.
                logger.warning("Model service unavailable (%s). Retrying in %.0fs.", exc, s.ollama_retry_seconds)
                await update_resume(resume_id, status=claim.stage.waiting, attempts=claim.attempt - 1,
                                    error_message=f"Waiting for the model service: {exc}")
                return Outcome(retry_after=s.ollama_retry_seconds, pause=s.ollama_retry_seconds)
            except Exception as exc:
                logger.exception("Resume %s: unexpected error during %s", resume_id, claim.stage.name)
                return await self._failed_attempt(claim, exc)
            if claim.stage is PARSE:
                return Outcome(next_job=Job("ingest", resume_id))
            if claim.stage is not EXTRACT:
                return Outcome()                                   # embedded: READY

    async def _failed_attempt(self, claim: Claimed, exc: Exception) -> Outcome:
        """Count one failed attempt: try again later (growing pause), or give up after WORKER_MAX_ATTEMPTS."""
        give_up = claim.attempt >= self.settings.worker_max_attempts
        note = f"gave up after {claim.attempt} attempts" if give_up else "will retry"
        await update_resume(claim.id, status=ResumeStatus.FAILED if give_up else claim.stage.waiting,
                            error_message=f"{claim.stage.name}: {type(exc).__name__}: {exc} ({note})")
        return Outcome() if give_up else Outcome(retry_after=min(10 * 2 ** (claim.attempt - 1), 300))

    # ------------------------------------------------------------------ match runs
    async def judge(self, delivery: Delivery) -> Outcome:
        s, run_id = self.settings, delivery.job.id
        if not await claim_run(run_id, s.worker_lease_seconds):
            return Outcome()                                       # finished, failed, or another worker has it
        logger.info("Run %s: judging", run_id)
        try:
            async with keep_alive(lambda: renew_run(run_id, s.worker_lease_seconds), delivery,
                                  s.worker_lease_seconds):
                await judge_run(run_id, self.ollama, s)            # saves after each person; completes the run
        except asyncio.CancelledError:
            await asyncio.shield(release_run(run_id))              # another worker continues where this stopped
            raise
        return Outcome()
