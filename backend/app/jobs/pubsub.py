"""
QUEUE_BACKEND=pubsub: Google Cloud Pub/Sub.          PUBSUB_TOPIC, PUBSUB_SUBSCRIPTION (+ project), ADC credentials

Set up (doc 21): a topic and a PULL subscription with
  - ack deadline 600 s (the worker extends it while a long LLM step runs)
  - a dead-letter topic (max delivery attempts ~ 5) and retry policy with exponential backoff
The service account needs roles/pubsub.publisher on the topic (API) and roles/pubsub.subscriber on the
subscription (worker). Names may be short ("resume-jobs") or full ("projects/p/topics/resume-jobs").

Synchronous pull (one request, up to N messages) keeps the worker in control of how much it takes on;
the client library is synchronous here, so calls run in worker threads.
"""
import asyncio

from app.jobs.base import Job, QueueError

MAX_ACK_DEADLINE = 600       # Pub/Sub's limit for one ack deadline extension


def _sdk():
    try:
        from google.cloud import pubsub_v1
    except ImportError as exc:
        raise QueueError("QUEUE_BACKEND=pubsub needs google-cloud-pubsub: pip install -r requirements-cloud.txt") \
            from exc
    return pubsub_v1


def full_name(kind: str, name: str, project: str | None) -> str:
    if name.startswith("projects/"):
        return name
    if not project:
        raise QueueError(f"Set PUBSUB_PROJECT (or GOOGLE_CLOUD_PROJECT), or give the full {kind} path")
    return f"projects/{project}/{kind}s/{name}"


class PubSubDelivery:
    def __init__(self, queue: "PubSubQueue", job: Job, ack_id: str):
        self.job, self._queue, self._ack_id = job, queue, ack_id

    async def ack(self) -> None:
        await self._queue._call(self._queue._subscriber.acknowledge,
                                request={"subscription": self._queue.subscription, "ack_ids": [self._ack_id]})

    async def retry(self, delay_seconds: float) -> None:
        # Redelivered once the deadline passes (0 = at once); the subscription's retry policy adds backoff.
        await self._queue._call(self._queue._subscriber.modify_ack_deadline, request={
            "subscription": self._queue.subscription, "ack_ids": [self._ack_id],
            "ack_deadline_seconds": int(min(max(delay_seconds, 0), MAX_ACK_DEADLINE))})

    async def extend(self, seconds: float) -> None:
        await self._queue._call(self._queue._subscriber.modify_ack_deadline, request={
            "subscription": self._queue.subscription, "ack_ids": [self._ack_id],
            "ack_deadline_seconds": int(min(max(seconds, 10), MAX_ACK_DEADLINE))})


class PubSubQueue:
    name = "pubsub"

    def __init__(self, topic: str | None, subscription: str | None, project: str | None,
                 publisher=None, subscriber=None):
        if not topic or not subscription:
            raise QueueError("PUBSUB_TOPIC and PUBSUB_SUBSCRIPTION must be set in backend/.env")
        self.topic = full_name("topic", topic, project)
        self.subscription = full_name("subscription", subscription, project)
        if publisher is None or subscriber is None:
            pubsub_v1 = _sdk()
            publisher = publisher or pubsub_v1.PublisherClient()
            subscriber = subscriber or pubsub_v1.SubscriberClient()
        self._publisher, self._subscriber = publisher, subscriber

    def describe(self) -> str:
        return f"Google Pub/Sub {self.topic}"

    async def _call(self, fn, **kwargs):
        try:
            return await asyncio.to_thread(fn, **kwargs)
        except Exception as exc:
            raise QueueError(f"Pub/Sub: {type(exc).__name__}: {exc}") from exc

    async def publish(self, job: Job, delay_seconds: float = 0) -> None:
        # Pub/Sub has no per-message delay: a delayed job is published now and the worker's claim decides
        # (a retry delay is applied on the receiving side through the ack deadline instead).
        future = await self._call(self._publisher.publish, topic=self.topic, data=job.encode().encode())
        await self._call(future.result, timeout=30)

    async def receive(self, max_messages: int, wait_seconds: float) -> list[PubSubDelivery]:
        try:
            resp = await self._call(self._subscriber.pull, request={
                "subscription": self.subscription, "max_messages": max(1, max_messages)},
                timeout=max(wait_seconds, 1.0))
        except QueueError as exc:
            if "DeadlineExceeded" in str(exc):           # nothing arrived within the wait: an empty pull
                return []
            raise
        out = []
        for received in resp.received_messages:
            try:
                out.append(PubSubDelivery(self, Job.decode(received.message.data), received.ack_id))
            except ValueError:
                await self._call(self._subscriber.acknowledge,
                                 request={"subscription": self.subscription, "ack_ids": [received.ack_id]})
        return out

    async def close(self) -> None:
        await self._call(self._subscriber.close)
