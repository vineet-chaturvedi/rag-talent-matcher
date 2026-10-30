"""
GET /api/overview: the numbers for the dashboard tiles (Step 11b).

Before this endpoint the dashboard downloaded up to 500 employee rows just to show "how many".
The database can count much faster than it can send rows, so this endpoint returns counts only:
a handful of `SELECT status, COUNT(*) ... GROUP BY status` queries, a few hundred bytes of JSON,
the same speed with 50 employees or 50,000.
"""
from enum import StrEnum

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.db.enums import MatchRunStatus, ProjectStatus, RoleStatus
from app.db.models import Employee, MatchRun, Project, ProjectRole
from app.schemas.overview import EmployeeCounts, MatchRunCounts, Overview, ProjectCounts, RoleCounts

router = APIRouter(prefix="/api", tags=["overview"])


async def _count_by_status[E: StrEnum](db: AsyncSession, column, enum: type[E]) -> dict[E, int]:
    """{every status: 0} filled in with the real counts, so the UI never sees a missing key."""
    rows = (await db.execute(select(column, func.count()).group_by(column))).all()
    return {s: 0 for s in enum} | {enum(s): n for s, n in rows}


@router.get("/overview", response_model=Overview)
async def overview(db: AsyncSession = Depends(get_db)) -> Overview:
    total_employees = await db.scalar(select(func.count()).select_from(Employee)) or 0
    active_employees = await db.scalar(
        select(func.count()).select_from(Employee).where(Employee.is_active.is_(True))) or 0

    projects = await _count_by_status(db, Project.status, ProjectStatus)
    roles = await _count_by_status(db, ProjectRole.status, RoleStatus)
    # A JSON column can hold SQL NULL *or* the JSON value null, so "IS NOT NULL" alone would miscount.
    # Roles are few (tens to hundreds), so reading just this one column and counting in Python is cheap.
    parsed = sum(1 for req in (await db.scalars(select(ProjectRole.requirements))).all() if req)
    runs = await _count_by_status(db, MatchRun.status, MatchRunStatus)

    return Overview(
        employees=EmployeeCounts(total=total_employees, active=active_employees),
        projects=ProjectCounts(total=sum(projects.values()), by_status=projects),
        roles=RoleCounts(total=sum(roles.values()), by_status=roles, parsed=parsed),
        match_runs=MatchRunCounts(total=sum(runs.values()), by_status=runs),
    )
