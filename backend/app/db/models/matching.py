"""Results of running the matcher for a role: kept for history, caching and audit."""
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import JSON, DateTime, ForeignKey, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, enum_column
from app.db.enums import MatchRunStatus

if TYPE_CHECKING:
    from app.db.models.employee import Employee
    from app.db.models.project import ProjectRole


class MatchRun(Base):
    """One execution of 'find the best employees for this role'."""
    __tablename__ = "match_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    role_id: Mapped[int] = mapped_column(ForeignKey("project_roles.id", ondelete="CASCADE"), index=True)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    status: Mapped[MatchRunStatus] = mapped_column(enum_column(MatchRunStatus), default=MatchRunStatus.RUNNING)
    settings: Mapped[dict | None] = mapped_column(JSON)   # weights, filters, models used -> reproducibility
    started_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)
    error_message: Mapped[str | None] = mapped_column(Text)

    role: Mapped["ProjectRole"] = relationship(back_populates="match_runs")
    results: Mapped[list["MatchResult"]] = relationship(
        back_populates="run", cascade="all, delete-orphan", order_by="MatchResult.rank"
    )


class MatchResult(Base):
    """One ranked employee within a run, with the reasons."""
    __tablename__ = "match_results"

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("match_runs.id", ondelete="CASCADE"), index=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"), index=True)
    resume_id: Mapped[int | None] = mapped_column(ForeignKey("resumes.id", ondelete="SET NULL"))
    rank: Mapped[int]
    final_score: Mapped[float]
    score_breakdown: Mapped[dict] = mapped_column(JSON)  # {"skills": 0.8, "experience": 0.6, "llm_judge": 0.75, ...}
    explanation: Mapped[dict | None] = mapped_column(JSON)  # strengths, gaps, evidence quotes from the LLM judge
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    run: Mapped["MatchRun"] = relationship(back_populates="results")
    employee: Mapped["Employee"] = relationship()

    __table_args__ = (UniqueConstraint("run_id", "employee_id"),)