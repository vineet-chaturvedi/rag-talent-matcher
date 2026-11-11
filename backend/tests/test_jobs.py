"""
Background jobs (app/jobs): the real pipeline end to end through the worker, claims under contention,
recovery from dead workers, graceful shutdown, and the queue backends' shared contract.
"""
import asyncio
import io
import uuid
from datetime import timedelta

import pytest
from sqlalchemy import update

from app.config import get_settings
from app.db.enums import MatchRunStatus, ResumeStatus
from app.db.models import Employee, MatchRun, ProjectRole, Resume
from app.db.session import SessionLocal
from app.jobs import Job, dispatch
from app.jobs.leases import claim_resume, recover_expired, utcnow
from app.jobs.local import LocalQueue
from app.jobs.worker import Worker, workers_online
from app.services.resumes import add_resume
from tests.fakes.models import FakeModels

pytestmark = pytest.mark.usefixtures("database")
RESUME_TEXT = ("Priya Sharma — Senior Backend Engineer. Experience: Acme Insurance, Senior Python Developer, "
               "Jan 2018 – Present. Built claims-processing REST APIs with Python, Django and PostgreSQL; "
               "deployed on Kubernetes. Skills: Python, Django, PostgreSQL, Kubernetes, Docker.")


def docx(text: str) -> bytes:
    from docx import Document

    d = Document()
    for line in text.split(". "):
        d.add_paragraph(line)
    buf = io.BytesIO()
    d.save(buf)
    return buf.getvalue()


def settings(**changes):
    base = {"worker_poll_seconds": 0.2, "worker_sweep_seconds": 0.5, "worker_lease_seconds": 30.0,
            "worker_shutdown_seconds": 2.0, "ollama_retry_seconds": 0.5}
    return get_settings().model_copy(update=base | changes)


async def new_resume(text: str = RESUME_TEXT) -> int:
    async with SessionLocal() as s:
        emp = Employee(employee_code=f"EMP-J{uuid.uuid4().hex[:6]}", full_name="Priya Sharma")
        s.add(emp)
        await s.commit()
        return (await add_resume(s, get_settings(), emp, "cv.docx", docx(text + " " + uuid.uuid4().hex))).id


async def park_other_work() -> None:
    """Tests share one database: mark resumes and runs left waiting by earlier tests as done, so a worker
    started by this test only sees this test's work."""
    async with SessionLocal() as s:
        await s.execute(update(Resume).where(Resume.status.notin_([ResumeStatus.READY, ResumeStatus.FAILED]))
                        .values(status=ResumeStatus.FAILED, error_message="parked by a test", lease_expires_at=None))
        await s.execute(update(MatchRun).where(MatchRun.status == MatchRunStatus.RUNNING)
                        .values(status=MatchRunStatus.FAILED))
        await s.commit()


async def status_of(resume_id: int) -> Resume:
    async with SessionLocal() as s:
        return await s.get(Resume, resume_id)


async def wait_for(predicate, timeout: float = 20.0):
    deadline = asyncio.get_running_loop().time() + timeout
    while asyncio.get_running_loop().time() < deadline:
        if result := await predicate():
            return result
        await asyncio.sleep(0.1)
    raise AssertionError("timed out")


# --------------------------------------------------------------------------- end to end (local queue)
async def test_upload_to_ready_then_judge_through_the_worker():
    await park_other_work()
    models, queue = FakeModels(), LocalQueue(0.2)
    worker = Worker(settings(), models, queue)
    worker.start()
    try:
        rid = await new_resume()
        await dispatch([Job("ingest", rid)], queue)
        resume = await wait_for(lambda: _ready(rid))
        assert resume.lease_expires_at is None and resume.attempts == 0 and resume.raw_text
        assert await workers_online() >= 0                       # heartbeats are written (asynchronously)

        # a match run whose judge runs as a job
        from app.matching.runner import create_match_run
        async with SessionLocal() as s:
            from app.db.models import Project
            project = Project(name=f"P{uuid.uuid4().hex[:4]}")
            s.add(project)
            await s.flush()
            role = ProjectRole(project_id=project.id, title="Python developer", description="Python and Django",
                               requirements={"title": "Python developer", "seniority": "unspecified",
                                             "must_have": [{"name": "Python", "min_years": None}],
                                             "nice_to_have": [], "min_total_years": None, "location": None,
                                             "domain": [], "search_summary": "Python Django developer"})
            s.add(role)
            await s.commit()
            run = await create_match_run(s, models, worker.settings, role, top_k=3, judge_top_n=1,
                                         only_available=False)
            run_id, run_status = run.id, run.status
        assert run_status == MatchRunStatus.RUNNING                # Priya has Python: one person to judge
        await dispatch([Job("judge", run_id)], queue)
        done = await wait_for(lambda: _run_finished(run_id))
        assert done.status == MatchRunStatus.COMPLETED and done.attempts == 1
    finally:
        await worker.stop()


async def _ready(rid):
    r = await status_of(rid)
    assert r.status != ResumeStatus.FAILED, r.error_message
    return r if r.status == ResumeStatus.READY else None


async def _run_finished(run_id):
    async with SessionLocal() as s:
        run = await s.get(MatchRun, run_id)
        return run if run.status != MatchRunStatus.RUNNING else None


async def test_parse_hands_the_resume_back_so_a_batch_is_parsed_first():
    """After PARSE a resume goes back to the queue: every upload is parsed (broken files reported) before the
    long LLM steps; after EXTRACT it goes straight on to EMBED (ready as soon as its own LLM step ends)."""
    from app.jobs.handlers import Handlers

    models = FakeModels()
    rid = await new_resume()
    delivery = type("D", (), {"job": Job("ingest", rid), "extend": lambda self, s: asyncio.sleep(0)})()
    outcome = await Handlers(settings(), models).ingest(delivery)
    assert outcome.next_job == Job("ingest", rid) and (await status_of(rid)).status == ResumeStatus.PARSED
    outcome = await Handlers(settings(), models).ingest(delivery)
    assert outcome.next_job is None and (await status_of(rid)).status == ResumeStatus.READY


async def test_model_outage_keeps_the_attempt_and_retries_later():
    from app.jobs.handlers import Handlers

    models = FakeModels()
    rid = await new_resume()
    delivery = type("D", (), {"job": Job("ingest", rid), "extend": lambda self, s: asyncio.sleep(0)})()
    await Handlers(settings(), models).ingest(delivery)                 # parsed
    models.down = True
    outcome = await Handlers(settings(), models).ingest(delivery)
    r = await status_of(rid)
    assert outcome.retry_after and outcome.pause and r.status == ResumeStatus.PARSED and r.attempts == 0
    assert "Waiting for the model service" in r.error_message


# --------------------------------------------------------------------------- claims and leases
async def test_only_one_of_many_concurrent_claims_wins():
    rid = await new_resume()
    claims = await asyncio.gather(*(claim_resume(rid, 30) for _ in range(8)))
    assert sum(c is not None for c in claims) == 1
    r = await status_of(rid)
    assert r.status == ResumeStatus.PARSING and r.attempts == 1 and r.lease_expires_at > utcnow()


async def test_dead_worker_lease_runs_out_and_the_work_returns():
    rid = await new_resume()
    assert await claim_resume(rid, 30)
    assert rid not in (await recover_expired(3))[0]                    # lease still live: untouched
    async with SessionLocal() as s:
        await s.execute(update(Resume).where(Resume.id == rid).values(lease_expires_at=utcnow() - timedelta(seconds=1)))
        await s.commit()
    assert rid in (await recover_expired(3))[0]
    assert (await status_of(rid)).status == ResumeStatus.QUEUED
    for _ in range(2):                         # attempts 2 and 3 die too: after the 3rd it gives up
        assert await claim_resume(rid, 30)
        await recover_expired(3, force=True)
    assert await claim_resume(rid, 30) is None
    r = await status_of(rid)
    assert r.status == ResumeStatus.FAILED and "stopped responding 3 times" in r.error_message


async def test_graceful_shutdown_hands_a_running_job_back():
    await park_other_work()
    models, queue = FakeModels(), LocalQueue(0.2)
    models.hold = asyncio.Event()                                       # the LLM step never finishes
    worker = Worker(settings(worker_shutdown_seconds=0.5), models, queue)
    rid = await new_resume()
    worker.start()
    await dispatch([Job("ingest", rid)], queue)
    await wait_for(lambda: _in(rid, ResumeStatus.EXTRACTING))
    await worker.stop()                                                 # waits 0.5 s, then cancels the job
    r = await status_of(rid)
    assert r.status == ResumeStatus.PARSED and r.attempts == 0 and r.lease_expires_at is None


async def _in(rid, status):
    return (await status_of(rid)).status == status


# --------------------------------------------------------------------------- queue backends: one contract
class _FakePubSub:
    """In-memory stand-in for the google-cloud-pubsub clients (same call shapes)."""
    def __init__(self):
        self.messages, self.leased, self.n = [], {}, 0

    def publish(self, topic, data):
        self.messages.append(data)
        return type("F", (), {"result": lambda self, timeout=None: "id"})()

    def pull(self, request, timeout=None):
        out = []
        while self.messages and len(out) < request["max_messages"]:
            self.n += 1
            ack_id, data = f"a{self.n}", self.messages.pop(0)
            self.leased[ack_id] = data
            out.append(type("R", (), {"ack_id": ack_id, "message": type("M", (), {"data": data})()})())
        if not out:
            from google.api_core.exceptions import DeadlineExceeded
            raise DeadlineExceeded("no messages")
        return type("P", (), {"received_messages": out})()

    def acknowledge(self, request):
        for a in request["ack_ids"]:
            self.leased.pop(a, None)

    def modify_ack_deadline(self, request):
        if request["ack_deadline_seconds"] == 0:
            for a in request["ack_ids"]:
                self.messages.append(self.leased.pop(a))

    def close(self):
        pass


class _FakeServiceBus:
    """In-memory stand-in for azure-servicebus's async client (same call shapes)."""
    def __init__(self):
        self.messages, self.scheduled = [], []
        outer = self

        class Msg:
            def __init__(self, body):
                self.body = [body.encode() if isinstance(body, str) else body]

        class Sender:
            async def send_messages(self, m):
                outer.messages.append(Msg(m.body if isinstance(m.body, str) else b"".join(m.body)))

            async def schedule_messages(self, m, when):
                outer.scheduled.append(when)

            async def close(self):
                pass

        class Receiver:
            async def receive_messages(self, max_message_count, max_wait_time):
                taken, outer.messages[:] = outer.messages[:max_message_count], outer.messages[max_message_count:]
                return taken

            async def complete_message(self, m):
                pass

            async def abandon_message(self, m):
                outer.messages.append(m)

            async def renew_message_lock(self, m):
                pass

            async def dead_letter_message(self, m, reason=None):
                pass

            async def close(self):
                pass
        self.sender, self.receiver = Sender(), Receiver()

    def get_queue_sender(self, name):
        return self.sender

    def get_queue_receiver(self, name, receive_mode=None):
        return self.receiver

    async def close(self):
        pass


@pytest.fixture(params=["local", "sqs", "pubsub", "servicebus"])
async def queue(request, monkeypatch):
    kind = request.param
    if kind == "local":
        yield LocalQueue(0.1)                       # database-backed: tested end to end above
        return
    if kind == "sqs":
        from moto import mock_aws

        from app.jobs.sqs import SqsQueue
        monkeypatch.setenv("AWS_ACCESS_KEY_ID", "t")
        monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "t")
        with mock_aws():
            import boto3
            url = boto3.client("sqs", region_name="ap-south-1").create_queue(QueueName="resume-jobs")["QueueUrl"]
            q = SqsQueue(url, "ap-south-1", None, visibility_seconds=30)
            yield q
            await q.close()
        return
    if kind == "pubsub":
        from app.jobs.pubsub import PubSubQueue
        fake = _FakePubSub()
        yield PubSubQueue("resume-jobs", "resume-jobs-worker", "talent-prod", publisher=fake, subscriber=fake)
        return
    from app.jobs.servicebus import ServiceBusQueue
    yield ServiceBusQueue("resume-jobs", None, None, client=_FakeServiceBus())


async def test_queue_contract(queue):
    if queue.name == "local":
        pytest.skip("the local queue reads the database: covered by the end-to-end tests")
    assert await queue.receive(1, 0.1) == []
    await queue.publish(Job("ingest", 7))
    [d] = await queue.receive(1, 1)
    assert d.job == Job("ingest", 7)
    await d.extend(60)
    await d.retry(0)                                               # back at once
    [d] = await queue.receive(1, 1)
    assert d.job == Job("ingest", 7)
    await d.ack()
    assert await queue.receive(1, 0.1) == []
    assert queue.describe()


def test_job_messages_are_validated():
    assert Job.decode(Job("judge", 3).encode()) == Job("judge", 3)
    for bad in ['{"kind": "drop tables", "id": 1}', '{"kind": "ingest", "id": "1"}', "not json"]:
        with pytest.raises(ValueError):
            Job.decode(bad)


def test_pubsub_names():
    from app.jobs.base import QueueError
    from app.jobs.pubsub import full_name
    assert full_name("topic", "jobs", "p1") == "projects/p1/topics/jobs"
    assert full_name("subscription", "projects/x/subscriptions/s", None) == "projects/x/subscriptions/s"
    with pytest.raises(QueueError):
        full_name("topic", "jobs", None)
