"""
Importing this package imports EVERY model, which registers each table on Base.metadata.
create_all() only creates tables it knows about, so a model not imported here would
silently never get a table.
"""
from app.db.models.employee import Employee
from app.db.models.matching import MatchResult, MatchRun
from app.db.models.project import Project, ProjectRole
from app.db.models.resume import Experience, Resume, ResumeChunk, ResumeProfile
from app.db.models.skill import ResumeSkill, Skill
from app.db.models.user import User

__all__ = [
    "Employee", "Experience", "MatchResult", "MatchRun", "Project", "ProjectRole",
    "Resume", "ResumeChunk", "ResumeProfile", "ResumeSkill", "Skill", "User",
]