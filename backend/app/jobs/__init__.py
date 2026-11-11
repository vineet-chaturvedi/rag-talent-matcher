"""
Background jobs (Step 15d, doc 21): resume processing and the LLM judge, through a queue.

QUEUE_BACKEND in .env picks where jobs travel; the work, the claims and the results stay the same:
  local        the database is the queue (no extra service): one machine, development        (default)
  sqs          Amazon SQS                                                                       AWS
  pubsub       Google Cloud Pub/Sub                                                             Google Cloud
  servicebus   Azure Service Bus                                                                Azure

The API publishes ({"kind": "ingest" | "judge", "id": ...}); workers (inside the API with WORKER_ENABLED=true,
or separate processes: python -m app.worker) take jobs, claim the row in the database and do the work.
"""
import logging
from collections.abc import Iterable
from functools import lru_cache

from app.jobs.base import Delivery, Job, JobQueue, QueueError

__all__ = ["Delivery", "Job", "JobQueue", "QueueError", "dispatch", "dispatch_waiting", "get_queue", "make_queue"]
logger = logging.getLogger(__name__)


def make_queue(settings) -> JobQueue:
    kind = settings.queue_backend
    if kind == "local":
        from app.jobs.local import LocalQueue
        return LocalQueue(settings.worker_poll_seconds)
    if kind == "sqs":
        from app.jobs.sqs import SqsQueue
        return SqsQueue(settings.sqs_queue_url, settings.sqs_region or settings.aws_region, settings.sqs_endpoint_url,
                        settings.worker_lease_seconds, settings.aws_profile)
    if kind == "pubsub":
        import os

        from app.jobs.pubsub import PubSubQueue
        return PubSubQueue(settings.pubsub_topic, settings.pubsub_subscription,
                           settings.pubsub_project or os.environ.get("GOOGLE_CLOUD_PROJECT"))
    if kind == "servicebus":
        from app.jobs.servicebus import ServiceBusQueue
        return ServiceBusQueue(settings.servicebus_queue, settings.servicebus_namespace,
                               settings.servicebus_connection_string)
    raise QueueError(f"Unknown QUEUE_BACKEND {kind!r}: use local, sqs, pubsub or servicebus")


@lru_cache
def get_queue() -> JobQueue:
    """One per process: in local mode the API and its built-in worker must share it (publish wakes the worker)."""
    from app.config import get_settings
    return make_queue(get_settings())


async def dispatch(jobs: Iterable[Job], queue: JobQueue | None = None) -> None:
    """
    Publish jobs AFTER their rows are committed. A failed publish is logged, not raised: the database already
    holds the work, and the sweeper offers it again (WORKER_REDISPATCH_SECONDS), so nothing is lost.
    """
    queue = queue or get_queue()
    for job in jobs:
        try:
            await queue.publish(job)
        except QueueError as exc:
            logger.warning("Could not publish %s (it will be re-dispatched): %s", job, exc)


async def dispatch_waiting(queue: JobQueue | None = None) -> int:
    """After a bulk change (re-extract all, re-embed all, model change): a job for every waiting resume."""
    from app.jobs.leases import waiting_resumes

    ids = await waiting_resumes()
    await dispatch((Job("ingest", i) for i in ids), queue)
    return len(ids)
