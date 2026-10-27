"""Internal projects and the roles (positions) they need filled."""
from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import JSON, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, enum_column
from app.db.enums import ProjectStatus, RoleStatus

if TYPE_CHECKING:
    from app.db.models.matching import MatchRun


class Project(TimestampMixin, Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    client_name: Mapped[str | None] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[ProjectStatus] = mapped_column(enum_column(ProjectStatus), default=ProjectStatus.PLANNED)
    start_date: Mapped[date | None]
    end_date: Mapped[date | None]
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))

    roles: Mapped[list["ProjectRole"]] = relationship(back_populates="project", cascade="all, delete-orphan")


class ProjectRole(TimestampMixin, Base):
    """A position to fill, e.g. 'Senior Backend Developer (Django), 100%, Pune, from 1 Dec'."""
    __tablename__ = "project_roles"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text)               # the free-text role description
    requirements: Mapped[dict | None] = mapped_column(JSON)      # LLM-parsed: must-have / nice-to-have skills (Step 7)
    min_experience_years: Mapped[float | None]
    location: Mapped[str | None] = mapped_column(String(100))
    allocation_percent: Mapped[int] = mapped_column(default=100)  # how much of a person's time is needed
    start_date: Mapped[date | None]
    headcount: Mapped[int] = mapped_column(default=1)
    status: Mapped[RoleStatus] = mapped_column(enum_column(RoleStatus), default=RoleStatus.OPEN, index=True)

    project: Mapped["Project"] = relationship(back_populates="roles")
    match_runs: Mapped[list["MatchRun"]] = relationship(back_populates="role", cascade="all, delete-orphan")