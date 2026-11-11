"""
The worker: takes jobs from the queue and runs them, safely, for as long as the process lives.

  consumers   WORKER_CONCURRENCY tasks, each taking one job at a time (an LLM on a CPU: keep 1; a GPU server
              or a cloud model: more)
  sweeper     every WORKER_SWEEP_SECONDS: work whose worker died goes back to the queue; with a message
              broker, jobs whose message may have been lost are sent again
  heartbeat   every 30 s: "this worker is alive" (worker_heartbeats), shown in the portal

It runs inside the API process (WORKER_ENABLED=true: one machine, development) or on its own, any number of
times (python -m app.worker: containers, autoscaling). Stopping is graceful: running jobs get
WORKER_SHUTDOWN_SECONDS to finish, then they are handed back (released), never lost.
"""
import asyncio
import contextlib
import logging
import os
import socket
import uuid
from datetime import timedelta

from sqlalchemy import delete, func, select

from app.config import Settings
from app.db.models import WorkerHeartbeat
from app.db.session import SessionLocal
from app.jobs.base import Job, JobQueue, QueueError
from app.jobs.handlers import Handlers, Outcome
from app.jobs.leases import recover_expired, stale_runs, stale_waiting, utcnow

logger = logging.getLogger(__name__)
HEARTBEAT_SECONDS = 30


class Worker:
    def __init__(self, settings: Settings, ollama, queue: JobQueue, concurrency: int | None = None):
        self.settings, self.queue = settings, queue
        self.concurrency = max(1, concurrency or settings.worker_concurrency)
        self.handlers = Handlers(settings, ollama)
        self.id = f"{socket.gethostname()}:{os.getpid()}:{uuid.uuid4().hex[:6]}"[:100]
        self.started_at = utcnow()
        self._stop = asyncio.Event()
        self._consumers: list[asyncio.Task] = []
        self._background: list[asyncio.Task] = []

    # ------------------------------------------------------------------ lifecycle
    def start(self) -> None:
        logger.info("Worker %s started: %d consumer(s), queue %s, extraction model %s", self.id, self.concurrency,
                    self.queue.describe(), self.settings.extraction_model)
        self._consumers = [asyncio.create_task(self._consume(i), name=f"worker-consumer-{i}")
                           for i in range(self.concurrency)]
        self._background = [asyncio.create_task(self._sweep_loop(), name="worker-sweeper"),
                            asyncio.create_task(self._heartbeat_loop(), name="worker-heartbeat")]

    @property
    def running(self) -> bool:
        return any(not t.done() for t in self._consumers)

    async def stop(self) -> None:
        """Graceful: no new jobs; running ones get WORKER_SHUTDOWN_SECONDS, then are released for others."""
        self._stop.set()
        if self._consumers:
            done, pending = await asyncio.wait(self._consumers, timeout=self.settings.worker_shutdown_seconds)
            for task in pending:
                task.cancel()                                  # the handler releases its claim
            await asyncio.gather(*pending, return_exceptions=True)
        for task in self._background:
            task.cancel()
        await asyncio.gather(*self._background, return_exceptions=True)
        with contextlib.suppress(Exception):
            async with SessionLocal() as session:
                await session.execute(delete(WorkerHeartbeat).where(WorkerHeartbeat.id == self.id))
                await session.commit()
        logger.info("Worker %s stopped", self.id)

    async def _sleep(self, seconds: float) -> None:
        """Sleep, but wake up at once when stopping."""
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(self._stop.wait(), timeout=seconds)

    # ------------------------------------------------------------------ consuming
    async def _consume(self, number: int) -> None:
        while not self._stop.is_set():
            try:
                deliveries = await self._receive()
            except QueueError as exc:
                logger.error("Queue unavailable (%s); retrying in %ds", exc, 10)
                await self._sleep(10)
                continue
            for delivery in deliveries:
                if self._stop.is_set():                          # received while stopping: give it straight back
                    with contextlib.suppress(Exception):
                        await delivery.retry(0)
                    continue
                outcome = await self._run(delivery)
                if outcome.pause:
                    await self._sleep(outcome.pause)

    async def _receive(self) -> list:
        """Wait for a job, but stop waiting at once when the worker is stopping."""
        receive = asyncio.create_task(self.queue.receive(1, self.settings.worker_poll_seconds))
        stopping = asyncio.create_task(self._stop.wait())
        done, _ = await asyncio.wait({receive, stopping}, return_when=asyncio.FIRST_COMPLETED)
        stopping.cancel()
        if receive in done:
            return receive.result()
        receive.cancel()
        with contextlib.suppress(asyncio.CancelledError, QueueError):
            await receive
        return []

    async def _run(self, delivery) -> Outcome:
        try:
            outcome = await self.handlers.handle(delivery)
        except asyncio.CancelledError:
            with contextlib.suppress(Exception):
                await asyncio.shield(delivery.retry(0))          # stopped mid-job: someone else takes it now
            raise
        except Exception:                                        # a bug in a handler: try again a bit later
            logger.exception("Job %s failed unexpectedly", delivery.job)
            outcome = Outcome(retry_after=60)
        try:
            if outcome.next_job is not None:
                await self.queue.publish(outcome.next_job)
            if outcome.retry_after is not None:
                await delivery.retry(outcome.retry_after)
            else:
                await delivery.ack()
        except QueueError as exc:            # the message comes back after its visibility timeout: no loss
            logger.warning("Could not settle %s: %s", delivery.job, exc)
        return outcome

    # ------------------------------------------------------------------ housekeeping
    async def _sweep_loop(self) -> None:
        first = True
        while not self._stop.is_set():
            try:
                await self.sweep(force=first and await self._alone())
            except Exception:
                logger.exception("Sweep failed")
            first = False
            await self._sleep(self.settings.worker_sweep_seconds)

    async def _alone(self) -> bool:
        """No other live worker: work left 'in progress' by an earlier run can be recovered at once."""
        since = utcnow() - timedelta(seconds=HEARTBEAT_SECONDS * 3)
        async with SessionLocal() as session:
            others = await session.scalar(select(func.count()).select_from(WorkerHeartbeat).where(
                WorkerHeartbeat.id != self.id, WorkerHeartbeat.last_seen_at > since))
        return not others

    async def sweep(self, force: bool = False) -> None:
        resumes, runs = await recover_expired(self.settings.worker_max_attempts, force=force)
        jobs = [Job("ingest", i) for i in resumes] + [Job("judge", i) for i in runs]
        if self.queue.name != "local":     # the local queue finds waiting work in the database by itself
            jobs += [Job("ingest", i) for i in await stale_waiting(self.settings.worker_redispatch_seconds)]
            jobs += [Job("judge", i) for i in await stale_runs(self.settings.worker_redispatch_seconds)
                     if Job("judge", i) not in jobs]
        for job in jobs:
            try:
                await self.queue.publish(job)
            except QueueError as exc:
                logger.warning("Could not re-dispatch %s: %s", job, exc)

    async def _heartbeat_loop(self) -> None:
        while not self._stop.is_set():
            try:
                async with SessionLocal() as session:
                    beat = await session.get(WorkerHeartbeat, self.id)
                    if beat is None:
                        session.add(WorkerHeartbeat(
                            id=self.id, hostname=socket.gethostname()[:255], pid=os.getpid(),
                            queue_backend=self.queue.name, concurrency=self.concurrency,
                            started_at=self.started_at, last_seen_at=utcnow()))
                    else:
                        beat.last_seen_at = utcnow()
                    # workers that vanished without saying goodbye (killed): forget them after a day
                    await session.execute(delete(WorkerHeartbeat).where(
                        WorkerHeartbeat.last_seen_at < utcnow() - timedelta(days=1)))
                    await session.commit()
            except Exception:
                logger.warning("Heartbeat failed", exc_info=True)
            await self._sleep(HEARTBEAT_SECONDS)


async def workers_online() -> int:
    """How many worker processes reported in the last 90 seconds."""
    since = utcnow() - timedelta(seconds=HEARTBEAT_SECONDS * 3)
    async with SessionLocal() as session:
        return int(await session.scalar(select(func.count()).select_from(WorkerHeartbeat)
                                        .where(WorkerHeartbeat.last_seen_at > since)) or 0)
