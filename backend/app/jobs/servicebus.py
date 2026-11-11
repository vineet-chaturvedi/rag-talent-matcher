"""
QUEUE_BACKEND=servicebus: Azure Service Bus (a queue).
  SERVICEBUS_QUEUE                       the queue name
  SERVICEBUS_NAMESPACE                   <namespace>.servicebus.windows.net   (recommended: managed identity)
  SERVICEBUS_CONNECTION_STRING           alternative for development (contains a secret: keep out of git)

Set up (doc 21): a queue with lock duration 5 min (the worker renews the lock while a long LLM step runs),
max delivery count ~ 5 (then the built-in dead-letter sub-queue), and the identity given "Azure Service Bus
Data Sender" (API) / "Data Receiver" (worker). Uses the SDK's async client (no threads needed).
"""
from datetime import datetime, timedelta, timezone

from app.jobs.base import Job, QueueError


def _sdk():
    try:
        from azure.servicebus import ServiceBusMessage, ServiceBusReceiveMode
        from azure.servicebus.aio import ServiceBusClient
    except ImportError as exc:
        raise QueueError("QUEUE_BACKEND=servicebus needs azure-servicebus and azure-identity: "
                         "pip install -r requirements-cloud.txt") from exc
    return ServiceBusClient, ServiceBusMessage, ServiceBusReceiveMode


class ServiceBusDelivery:
    def __init__(self, queue: "ServiceBusQueue", job: Job, message):
        self.job, self._queue, self._message = job, queue, message

    async def ack(self) -> None:
        await self._queue._guard(self._queue._receiver.complete_message(self._message))

    async def retry(self, delay_seconds: float) -> None:
        if delay_seconds <= 0:
            await self._queue._guard(self._queue._receiver.abandon_message(self._message))
            return
        # Service Bus can't delay an abandoned message: schedule a fresh copy, then complete this one.
        await self._queue.publish(self.job, delay_seconds)
        await self._queue._guard(self._queue._receiver.complete_message(self._message))

    async def extend(self, seconds: float) -> None:
        await self._queue._guard(self._queue._receiver.renew_message_lock(self._message))


class ServiceBusQueue:
    name = "servicebus"

    def __init__(self, queue_name: str | None, namespace: str | None, connection_string: str | None, client=None):
        if not queue_name:
            raise QueueError("SERVICEBUS_QUEUE is not set in backend/.env")
        ServiceBusClient, self._message_cls, receive_mode = _sdk()
        self._credential = None
        if client is None:
            if connection_string:
                client = ServiceBusClient.from_connection_string(connection_string)
            elif namespace:
                from azure.identity.aio import DefaultAzureCredential
                self._credential = DefaultAzureCredential()
                client = ServiceBusClient(namespace, self._credential)
            else:
                raise QueueError("Set SERVICEBUS_NAMESPACE (managed identity) or SERVICEBUS_CONNECTION_STRING")
        self.queue_name = queue_name
        self._client = client
        self._sender = client.get_queue_sender(queue_name)
        self._receiver = client.get_queue_receiver(queue_name, receive_mode=receive_mode.PEEK_LOCK)

    def describe(self) -> str:
        return f"Azure Service Bus queue {self.queue_name}"

    @staticmethod
    async def _guard(awaitable):
        try:
            return await awaitable
        except Exception as exc:
            raise QueueError(f"Service Bus: {type(exc).__name__}: {exc}") from exc

    async def publish(self, job: Job, delay_seconds: float = 0) -> None:
        message = self._message_cls(job.encode(), content_type="application/json")
        if delay_seconds > 0:
            when = datetime.now(timezone.utc) + timedelta(seconds=delay_seconds)
            await self._guard(self._sender.schedule_messages(message, when))
        else:
            await self._guard(self._sender.send_messages(message))

    async def receive(self, max_messages: int, wait_seconds: float) -> list[ServiceBusDelivery]:
        messages = await self._guard(self._receiver.receive_messages(max_message_count=max(1, max_messages),
                                                                     max_wait_time=max(wait_seconds, 1)))
        out = []
        for m in messages:
            try:
                out.append(ServiceBusDelivery(self, Job.decode(b"".join(m.body)), m))
            except ValueError:
                await self._guard(self._receiver.dead_letter_message(m, reason="not a job"))
        return out

    async def close(self) -> None:
        await self._sender.close()
        await self._receiver.close()
        await self._client.close()
        if self._credential is not None:
            await self._credential.close()
