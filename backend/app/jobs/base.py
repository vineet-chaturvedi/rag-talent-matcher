"""
Jobs and the queue interface every backend implements.

A job is tiny: what to do and to which row, e.g. {"kind": "ingest", "id": 42}. Everything else (the stage a
resume is in, how many attempts it had, who holds it) lives in the database, which stays the source of
truth. So a message delivered twice, late, or after the work was already done is harmless: the worker
claims the row first (app/jobs/leases.py) and simply drops a message that has nothing left to do.
That is the standard "at-least-once delivery + idempotent consumer" design every cloud queue assumes.
"""
import json
from dataclasses import dataclass
from typing import Literal, Protocol

JobKind = Literal["ingest", "judge"]
KINDS: tuple[str, ...] = ("ingest", "judge")


@dataclass(frozen=True)
class Job:
    kind: JobKind      # ingest = take a resume through parse -> extract -> embed; judge = LLM-judge a match run
    id: int            # resumes.id or match_runs.id

    def encode(self) -> str:
        return json.dumps({"kind": self.kind, "id": self.id, "v": 1})

    @classmethod
    def decode(cls, body: str | bytes) -> "Job":
        data = json.loads(body)
        if data.get("kind") not in KINDS or not isinstance(data.get("id"), int):
            raise ValueError(f"Not a job: {body!r}")
        return cls(data["kind"], data["id"])


class QueueError(Exception):
    """The queue service failed or is misconfigured (the message is safe to log)."""


class Delivery(Protocol):
    """One received message. Exactly one of ack() / retry() must be called when the work is over."""
    job: Job

    async def ack(self) -> None:
        """Done (or nothing to do): remove the message for good."""

    async def retry(self, delay_seconds: float) -> None:
        """Not done (e.g. the model service is down): deliver it again after the delay."""

    async def extend(self, seconds: float) -> None:
        """Still working: keep the message hidden from other workers for this much longer."""


class JobQueue(Protocol):
    name: str

    def describe(self) -> str: ...

    async def publish(self, job: Job, delay_seconds: float = 0) -> None: ...

    async def receive(self, max_messages: int, wait_seconds: float) -> list[Delivery]:
        """Up to max_messages jobs; waits up to wait_seconds for the first one (long polling)."""

    async def close(self) -> None: ...
