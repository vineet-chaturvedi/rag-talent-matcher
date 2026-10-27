"""
Employee endpoints:
  POST /api/employees/import     upload the HR CSV (create/update employees)
  GET  /api/employees            list employees with their current resume status
  GET  /api/employees/{id}       one employee with all resume versions
"""
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_db
from app.db.models import Employee, Resume
from app.schemas.employee import EmployeeDetail, EmployeeImportResult, EmployeeListItem
from app.schemas.resume import ResumeOut
from app.services.employees import InvalidCsvError, import_employees_csv

router = APIRouter(prefix="/api/employees", tags=["employees"])

MAX_CSV_BYTES = 5 * 1024 * 1024  # 5 MB is roughly 50,000 employee rows


@router.post("/import", response_model=EmployeeImportResult)
async def import_employees(
    file: UploadFile = File(..., description="HR export as CSV (UTF-8). Required columns: employee_code, full_name"),
    db: AsyncSession = Depends(get_db),
):
    content = await file.read(MAX_CSV_BYTES + 1)
    if len(content) > MAX_CSV_BYTES:
        raise HTTPException(status_code=413, detail="CSV file is larger than 5 MB.")
    try:
        return await import_employees_csv(db, content)
    except InvalidCsvError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("", response_model=list[EmployeeListItem])
async def list_employees(
    search: str | None = Query(None, description="Matches code, name, department or location"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Employee).order_by(Employee.employee_code).limit(limit).offset(offset)
    if search:
        pattern = f"%{search}%"
        stmt = stmt.where(or_(
            Employee.employee_code.ilike(pattern), Employee.full_name.ilike(pattern),
            Employee.department.ilike(pattern), Employee.location.ilike(pattern),
        ))
    employees = (await db.scalars(stmt)).all()

    # One extra query for the current resumes of exactly these employees (not one query per employee).
    ids = [e.id for e in employees]
    current = {
        r.employee_id: r
        for r in (await db.scalars(
            select(Resume).where(Resume.employee_id.in_(ids), Resume.is_current.is_(True))
        )).all()
    }
    return [
        EmployeeListItem.model_validate(e).model_copy(
            update={"current_resume": ResumeOut.model_validate(current[e.id]) if e.id in current else None}
        )
        for e in employees
    ]


@router.get("/{employee_id}", response_model=EmployeeDetail)
async def get_employee(employee_id: int, db: AsyncSession = Depends(get_db)):
    employee = await db.scalar(
        select(Employee).where(Employee.id == employee_id).options(selectinload(Employee.resumes))
    )
    if employee is None:
        raise HTTPException(status_code=404, detail="Employee not found")
    return EmployeeDetail.model_validate(employee)
