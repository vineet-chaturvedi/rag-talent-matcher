"""
QUEUE_BACKEND=local: no message broker. The database IS the queue (each resume's status, each run's lease),
exactly as before Step 15: the worker looks for waiting work, most urgent first (leases.find_work).

publish() only wakes the worker in THIS process, so an upload starts at once. A worker in another process
(python -m app.worker) finds the same work by looking every WORKER_POLL_SECONDS. Safe with several workers:
the database claim decides who does what.
"""
import asyncio
import time

from app.jobs.base import Job
from app.jobs.leases import find_work


class LocalDelivery:
    def __init__(self, queue: "LocalQueue", job: Job):
        self.job, self._queue = job, queue

    async def ack(self) -> None:
        self._queue._in_flight.discard(self.job)

    async def retry(self, delay_seconds: float) -> None:
        self._queue._in_flight.discard(self.job)
        self._queue._not_before[self.job] = time.monotonic() + delay_seconds

    async def extend(self, seconds: float) -> None:
        pass                                   # the database lease is what counts here


class LocalQueue:
    name = "local"

    def __init__(self, poll_seconds: float):
        self._poll = poll_seconds
        self._wake = asyncio.Event()
        self._in_flight: set[Job] = set()                 # handed to a consumer of this process
        self._not_before: dict[Job, float] = {}           # retried later: not before this time

    def describe(self) -> str:
        return "database (no broker)"

    async def publish(self, job: Job, delay_seconds: float = 0) -> None:
        if delay_seconds:
            self._not_before[job] = time.monotonic() + delay_seconds
        self._wake.set()

    async def receive(self, max_messages: int, wait_seconds: float) -> list[LocalDelivery]:
        deadline = time.monotonic() + wait_seconds
        while True:
            self._wake.clear()
            now = time.monotonic()
            self._not_before = {j: t for j, t in self._not_before.items() if t > now}
            jobs = [job for job in (Job(kind, i) for kind, i in await find_work(max_messages + len(self._in_flight)
                                                                                + len(self._not_before)))
                    if job not in self._in_flight and job not in self._not_before][:max_messages]
            if jobs:
                self._in_flight.update(jobs)
                return [LocalDelivery(self, j) for j in jobs]
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return []
            try:
                await asyncio.wait_for(self._wake.wait(), timeout=min(remaining, self._poll))
            except TimeoutError:
                pass

    async def close(self) -> None:
        pass
