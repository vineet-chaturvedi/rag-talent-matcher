"""Canonical skills and the resume<->skill link (many-to-many with extra data)."""
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.resume import Resume


class Skill(Base):
    """One row per distinct skill, stored under its canonical name ("Kubernetes", not "k8s")."""
    __tablename__ = "skills"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    category: Mapped[str | None] = mapped_column(String(50))  # language / framework / cloud / devops / ...

    resume_links: Mapped[list["ResumeSkill"]] = relationship(back_populates="skill")


class ResumeSkill(Base):
    """Link table: which resume has which skill, for how long, and the proof."""
    __tablename__ = "resume_skills"

    resume_id: Mapped[int] = mapped_column(ForeignKey("resumes.id", ondelete="CASCADE"), primary_key=True)
    skill_id: Mapped[int] = mapped_column(ForeignKey("skills.id", ondelete="CASCADE"), primary_key=True, index=True)
    years: Mapped[float | None]            # e.g. 4.5
    last_used_year: Mapped[int | None]     # e.g. 2026; recent skills matter more than old ones
    evidence: Mapped[str | None] = mapped_column(Text)  # quote from the resume supporting this skill

    resume: Mapped["Resume"] = relationship(back_populates="skills")
    skill: Mapped["Skill"] = relationship(back_populates="resume_links")