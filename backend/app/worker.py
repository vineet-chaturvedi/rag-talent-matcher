"""
A background worker on its own (Step 15d, doc 21):   python -m app.worker   (from backend/)

Runs resume processing and the LLM judge from the queue (QUEUE_BACKEND), with the same .env as the API.
Start as many as you need, on any machines: the database decides who does what. Typical setups:
  one machine         the API's built-in worker (WORKER_ENABLED=true) is enough; you don't need this
  containers / cloud  API with WORKER_ENABLED=false + N of these (autoscale on the queue's length)

Stopping (Ctrl+C, or SIGTERM from Docker / ECS / Kubernetes / Cloud Run): running jobs get
WORKER_SHUTDOWN_SECONDS to finish, then are handed back to the queue. Nothing is lost.

    python -m app.worker --concurrency 4      override WORKER_CONCURRENCY
    python -m app.worker --healthcheck        exit 0 if a worker on this host reported in the last 90 s
                                              (container health checks)
"""
import argparse
import asyncio
import logging
import signal
import socket
import sys


async def run(concurrency: int | None) -> int:
    from app.config import get_settings
    from app.db.session import engine, init_db
    from app.jobs import get_queue
    from app.jobs.worker import Worker
    from app.llm.router import make_model_client
    from app.rag.keyword_index import ensure_keyword_index
    from app.storage import get_storage

    settings = get_settings()
    logging.basicConfig(level=settings.log_level, format="%(asctime)s %(levelname)-7s [%(name)s] %(message)s")
    logger = logging.getLogger("app.worker")
    await init_db()
    await ensure_keyword_index()
    models = make_model_client(settings)
    queue = get_queue()
    worker = Worker(settings, models, queue, concurrency)

    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop.set)
        except (NotImplementedError, AttributeError, ValueError):     # Windows: no loop signal handlers
            signal.signal(sig, lambda *_: loop.call_soon_threadsafe(stop.set))
    worker.start()
    logger.info("Files: %s · models: extraction %s, judge %s", get_storage().describe(),
                settings.extraction_model, settings.judge_model)
    try:
        await stop.wait()
    finally:
        logger.info("Stopping (running jobs get %.0fs to finish)...", settings.worker_shutdown_seconds)
        await worker.stop()
        await queue.close()
        await models.close()
        await get_storage().close()
        await engine.dispose()
    return 0


async def healthcheck() -> int:
    from datetime import timedelta

    from sqlalchemy import func, select

    from app.db.models import WorkerHeartbeat
    from app.db.session import SessionLocal, engine
    from app.jobs.leases import utcnow
    from app.jobs.worker import HEARTBEAT_SECONDS

    try:
        async with SessionLocal() as session:
            alive = await session.scalar(select(func.count()).select_from(WorkerHeartbeat).where(
                WorkerHeartbeat.hostname == socket.gethostname()[:255],
                WorkerHeartbeat.last_seen_at > utcnow() - timedelta(seconds=HEARTBEAT_SECONDS * 3)))
    finally:
        await engine.dispose()
    return 0 if alive else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.worker", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--concurrency", type=int, help="jobs at once (default: WORKER_CONCURRENCY)")
    parser.add_argument("--healthcheck", action="store_true", help="exit 0 if this host's worker is alive")
    args = parser.parse_args(argv)
    return asyncio.run(healthcheck() if args.healthcheck else run(args.concurrency))


if __name__ == "__main__":
    sys.exit(main())
