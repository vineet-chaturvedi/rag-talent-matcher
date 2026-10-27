"""Uploaded resume files and everything derived from them."""
import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, enum_column
from app.db.enums import ChunkSection, ResumeStatus

if TYPE_CHECKING:
    from app.db.models.employee import Employee
    from app.db.models.skill import ResumeSkill


class Resume(TimestampMixin, Base):
    """One uploaded file. An employee may have several (versions); one is_current."""
    __tablename__ = "resumes"

    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"), index=True)

    # ---- The file ----
    original_filename: Mapped[str] = mapped_column(String(255))
    stored_path: Mapped[str] = mapped_column(String(500))          # where we saved it under data/uploads
    file_hash: Mapped[str] = mapped_column(String(64), unique=True)  # SHA-256: blocks duplicate uploads
    mime_type: Mapped[str] = mapped_column(String(100))
    file_size_bytes: Mapped[int]
    is_current: Mapped[bool] = mapped_column(default=True, index=True)

    # ---- Processing pipeline (restart-safe queue) ----
    status: Mapped[ResumeStatus] = mapped_column(
        enum_column(ResumeStatus), default=ResumeStatus.QUEUED, index=True
    )
    error_message: Mapped[str | None] = mapped_column(Text)
    attempts: Mapped[int] = mapped_column(default=0)   # retry counter; give up after N
    raw_text: Mapped[str | None] = mapped_column(Text)  # text extracted from the file
    page_count: Mapped[int | None]
    processed_at: Mapped[datetime | None] = mapped_column(DateTime)

    uploaded_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))

    # ---- Relationships ----
    employee: Mapped["Employee"] = relationship(back_populates="resumes")
    profile: Mapped[Optional["ResumeProfile"]] = relationship(
        back_populates="resume", cascade="all, delete-orphan"
    )
    experiences: Mapped[list["Experience"]] = relationship(
        back_populates="resume", cascade="all, delete-orphan", order_by="Experience.start_date.desc()"
    )
    skills: Mapped[list["ResumeSkill"]] = relationship(back_populates="resume", cascade="all, delete-orphan")
    chunks: Mapped[list["ResumeChunk"]] = relationship(
        back_populates="resume", cascade="all, delete-orphan", order_by="ResumeChunk.chunk_index"
    )


class ResumeProfile(TimestampMixin, Base):
    """Structured data the LLM extracts from one resume (Step 5). One-to-one with Resume."""
    __tablename__ = "resume_profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    resume_id: Mapped[int] = mapped_column(ForeignKey("resumes.id", ondelete="CASCADE"), unique=True)
    headline: Mapped[str | None] = mapped_column(String(300))   # e.g. "Senior Backend Engineer"
    summary: Mapped[str | None] = mapped_column(Text)
    total_experience_years: Mapped[float | None]
    education: Mapped[list | None] = mapped_column(JSON)        # [{"degree": ..., "institution": ..., "year": ...}]
    certifications: Mapped[list | None] = mapped_column(JSON)   # ["AWS SAA", ...]
    raw_extraction: Mapped[dict | None] = mapped_column(JSON)   # full LLM output, kept for auditing/debugging
    extraction_model: Mapped[str | None] = mapped_column(String(100))  # which model produced it

    resume: Mapped["Resume"] = relationship(back_populates="profile")


class Experience(Base):
    """One job/role entry from a resume's work history."""
    __tablename__ = "experiences"

    id: Mapped[int] = mapped_column(primary_key=True)
    resume_id: Mapped[int] = mapped_column(ForeignKey("resumes.id", ondelete="CASCADE"), index=True)
    company: Mapped[str | None] = mapped_column(String(200))
    title: Mapped[str | None] = mapped_column(String(200))
    start_date: Mapped[date | None]
    end_date: Mapped[date | None]       # None + is_current=True means "present"
    is_current: Mapped[bool] = mapped_column(default=False)
    description: Mapped[str | None] = mapped_column(Text)

    resume: Mapped["Resume"] = relationship(back_populates="experiences")


class ResumeChunk(Base):
    """
    A piece of resume text that gets embedded. The vector lives in ChromaDB under the SAME id;
    this table is the source of truth, so the vector store can always be rebuilt from here.
    """
    __tablename__ = "resume_chunks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    resume_id: Mapped[int] = mapped_column(ForeignKey("resumes.id", ondelete="CASCADE"), index=True)
    section: Mapped[ChunkSection] = mapped_column(enum_column(ChunkSection))
    chunk_index: Mapped[int]                       # order within the resume: 0, 1, 2...
    text: Mapped[str] = mapped_column(Text)
    token_count: Mapped[int | None]
    embedding_model: Mapped[str | None] = mapped_column(String(100))  # detect when re-embedding is needed
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    resume: Mapped["Resume"] = relationship(back_populates="chunks")

    __table_args__ = (UniqueConstraint("resume_id", "chunk_index"),)