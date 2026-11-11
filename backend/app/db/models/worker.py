"""Background workers report here that they are alive (Step 15): the portal shows how many are running."""
from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class WorkerHeartbeat(Base):
    __tablename__ = "worker_heartbeats"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)     # host:pid:random, unique per process
    hostname: Mapped[str] = mapped_column(String(255))
    pid: Mapped[int]
    queue_backend: Mapped[str] = mapped_column(String(20))
    concurrency: Mapped[int]
    started_at: Mapped[datetime] = mapped_column(DateTime)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, index=True)
