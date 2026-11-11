"""
QUEUE_BACKEND=sqs: Amazon SQS (a standard queue).          SQS_QUEUE_URL, AWS_REGION + AWS credentials

Set up (doc 21): a standard queue with
  - visibility timeout >= WORKER_LEASE_SECONDS (the worker extends it while a long LLM step runs)
  - a dead-letter queue (redrive policy, maxReceiveCount ~ 5) for messages that keep failing
  - SSE (SQS-managed or your KMS key); the messages only hold {"kind", "id"}, never resume content
IAM: sqs:SendMessage, ReceiveMessage, DeleteMessage, ChangeMessageVisibility on the queue.
boto3 is synchronous: calls run in worker threads.
"""
import asyncio

from app.jobs.base import Job, QueueError

MAX_DELAY = 900              # SQS limit for DelaySeconds and for a "retry later" visibility


def _sdk():
    try:
        import boto3
        import botocore
    except ImportError as exc:
        raise QueueError("QUEUE_BACKEND=sqs needs boto3: pip install -r requirements-cloud.txt") from exc
    return boto3, botocore


class SqsDelivery:
    def __init__(self, queue: "SqsQueue", job: Job, receipt: str):
        self.job, self._queue, self._receipt = job, queue, receipt

    async def ack(self) -> None:
        await self._queue._call("delete_message", ReceiptHandle=self._receipt)

    async def retry(self, delay_seconds: float) -> None:
        # Back on the queue after the delay (and counted as a receive: the dead-letter queue catches loops).
        await self._queue._call("change_message_visibility", ReceiptHandle=self._receipt,
                                VisibilityTimeout=int(min(max(delay_seconds, 0), MAX_DELAY)))

    async def extend(self, seconds: float) -> None:
        await self._queue._call("change_message_visibility", ReceiptHandle=self._receipt,
                                VisibilityTimeout=int(min(seconds, 43_200)))


class SqsQueue:
    name = "sqs"

    def __init__(self, queue_url: str | None, region: str | None, endpoint_url: str | None,
                 visibility_seconds: float, profile: str | None = None, client=None):
        if not queue_url:
            raise QueueError("SQS_QUEUE_URL is not set in backend/.env")
        boto3, botocore = _sdk()
        self.url, self._visibility = queue_url, int(visibility_seconds)
        self._client = client or boto3.Session(profile_name=profile or None, region_name=region or None).client(
            "sqs", endpoint_url=endpoint_url or None,
            config=botocore.config.Config(retries={"mode": "standard", "max_attempts": 5}, read_timeout=40))

    def describe(self) -> str:
        return f"Amazon SQS {self.url}"

    async def _call(self, method: str, **params):
        try:
            return await asyncio.to_thread(getattr(self._client, method), QueueUrl=self.url, **params)
        except Exception as exc:
            raise QueueError(f"SQS {method}: {exc}") from exc

    async def publish(self, job: Job, delay_seconds: float = 0) -> None:
        await self._call("send_message", MessageBody=job.encode(),
                         DelaySeconds=int(min(max(delay_seconds, 0), MAX_DELAY)))

    async def receive(self, max_messages: int, wait_seconds: float) -> list[SqsDelivery]:
        resp = await self._call("receive_message", MaxNumberOfMessages=max(1, min(max_messages, 10)),
                                WaitTimeSeconds=int(min(max(wait_seconds, 0), 20)),   # long polling
                                VisibilityTimeout=self._visibility)
        out = []
        for m in resp.get("Messages", []):
            try:
                out.append(SqsDelivery(self, Job.decode(m["Body"]), m["ReceiptHandle"]))
            except ValueError:            # not ours / corrupt: drop it (the dead-letter queue would keep it)
                await self._call("delete_message", ReceiptHandle=m["ReceiptHandle"])
        return out

    async def close(self) -> None:
        await asyncio.to_thread(self._client.close)
