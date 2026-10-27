"""
Fixed lists of allowed values ("enumerations").

Using enums instead of free text means a typo like "avialable" is impossible:
Python rejects it, and the database stores only these exact values.
StrEnum members ARE strings, so they turn into JSON nicely for the frontend.
"""
from enum import StrEnum


class UserRole(StrEnum):
    ADMIN = "admin"                        # uploads resumes, manages employees and users
    RESOURCE_MANAGER = "resource_manager"  # creates project roles, runs matching


class AvailabilityStatus(StrEnum):
    AVAILABLE = "available"   # on the bench, can start now
    PARTIAL = "partial"       # partly allocated (see allocation_percent)
    ALLOCATED = "allocated"   # fully busy
    ON_LEAVE = "on_leave"


class ResumeStatus(StrEnum):
    # The processing pipeline, in order. The background worker (Step 4+) moves each
    # resume through these, so after a crash/restart we know exactly where it stopped.
    QUEUED = "queued"
    PARSING = "parsing"         # reading text from PDF/DOCX
    EXTRACTING = "extracting"   # LLM turns text into structured data
    EMBEDDING = "embedding"     # chunks -> vectors
    READY = "ready"             # searchable
    FAILED = "failed"           # see resumes.error_message


class ChunkSection(StrEnum):
    SUMMARY = "summary"
    SKILLS = "skills"
    EXPERIENCE = "experience"
    PROJECT = "project"
    EDUCATION = "education"
    CERTIFICATION = "certification"
    OTHER = "other"


class ProjectStatus(StrEnum):
    PLANNED = "planned"
    ACTIVE = "active"
    ON_HOLD = "on_hold"
    COMPLETED = "completed"


class RoleStatus(StrEnum):
    OPEN = "open"
    FILLED = "filled"
    CLOSED = "closed"


class MatchRunStatus(StrEnum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"