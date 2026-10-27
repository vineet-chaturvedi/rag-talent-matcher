"""
Resume endpoints:
  POST   /api/employees/{id}/resumes   upload one resume for a known employee
  POST   /api/resumes/bulk             upload many; employee found from the filename (EMP-1001_name.pdf)
  GET    /api/resumes                  list (filter by status)
  GET    /api/resumes/stats            queue overview for the admin dashboard
  GET    /api/resumes/{id}             details + extracted text
  GET    /api/resumes/{id}/profile     the structured profile extracted by the LLM (Step 5)
  POST   /api/resumes/{id}/retry       re-queue a failed resume
  POST   /api/resumes/reextract        send all resumes back to LLM extraction (after a model/prompt change)
  POST   /api/resumes/reembed          rebuild all chunks + vectors (after a chunking/embedding change)
  DELETE /api/resumes/{id}             delete one resume version (file + rows)
"""
import asyncio
from datetime import date

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_db, get_worker
from app.config import Settings, get_settings
from app.db.enums import ResumeStatus
from app.db.models import Employee, Resume, ResumeSkill
from app.ingestion.storage import InvalidFileError
from app.ingestion.worker import IngestionWorker
from app.rag.vector_store import get_vector_store
from app.schemas.profile import ProfileOut
from app.schemas.resume import BulkUploadResult, QueueStats, ResumeDetail, ResumeOut, UploadItemResult
from app.services.indexing import requeue_for_embedding
from app.services.resumes import (
    DuplicateResumeError, add_resume, delete_resume, employee_code_from_filename, requeue_for_extraction,
    retry_resume,
)

router = APIRouter(tags=["resumes"])
PREVIEW_CHARS = 1500


def _wake(worker: IngestionWorker | None) -> None:
    if worker is not None:
        worker.notify()


@router.post("/api/employees/{employee_id}/resumes", response_model=ResumeOut, status_code=status.HTTP_201_CREATED)
async def upload_resume(
    employee_id: int,
    file: UploadFile = File(..., description="PDF or DOCX"),
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
    worker: IngestionWorker | None = Depends(get_worker),
):
    employee = await db.get(Employee, employee_id)
    if employee is None:
        raise HTTPException(status_code=404, detail="Employee not found")

    data = await file.read(settings.max_upload_bytes + 1)  # never read more than limit + 1 byte
    try:
        resume = await add_resume(db, settings, employee, file.filename or "", data)
    except InvalidFileError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except DuplicateResumeError as exc:
        raise HTTPException(status_code=409, detail=str(exc))

    _wake(worker)
    return resume


@router.post("/api/resumes/bulk", response_model=BulkUploadResult)
async def bulk_upload(
    files: list[UploadFile] = File(..., description="Many PDF/DOCX files named like EMP-1001_anything.pdf"),
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
    worker: IngestionWorker | None = Depends(get_worker),
):
    if len(files) > settings.max_files_per_batch:
        raise HTTPException(status_code=400, detail=f"At most {settings.max_files_per_batch} files per upload.")

    # Load the code -> employee map once for the whole batch.
    employees = {e.employee_code.upper(): e for e in (await db.scalars(select(Employee))).all()}

    items: list[UploadItemResult] = []
    for upload in files:
        name = upload.filename or ""
        code = employee_code_from_filename(name)
        employee = employees.get(code or "")
        if employee is None:
            items.append(UploadItemResult(filename=name, ok=False, employee_code=code,
                                          error=f"No employee with code '{code}'. Name files like EMP-1001_name.pdf"))
            continue
        data = await upload.read(settings.max_upload_bytes + 1)
        try:
            resume = await add_resume(db, settings, employee, name, data)
        except (InvalidFileError, DuplicateResumeError) as exc:
            items.append(UploadItemResult(filename=name, ok=False, employee_code=code, error=str(exc)))
            continue
        items.append(UploadItemResult(filename=name, ok=True, resume_id=resume.id, employee_code=code))

    _wake(worker)
    uploaded = sum(1 for i in items if i.ok)
    return BulkUploadResult(uploaded=uploaded, failed=len(items) - uploaded, items=items)


@router.get("/api/resumes", response_model=list[ResumeOut])
async def list_resumes(
    status_filter: ResumeStatus | None = Query(None, alias="status"),
    current_only: bool = True,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Resume).order_by(Resume.id.desc()).limit(limit).offset(offset)
    if status_filter is not None:
        stmt = stmt.where(Resume.status == status_filter)
    if current_only:
        stmt = stmt.where(Resume.is_current.is_(True))
    return (await db.scalars(stmt)).all()


@router.get("/api/resumes/stats", response_model=QueueStats)
async def queue_stats(
    db: AsyncSession = Depends(get_db),
    worker: IngestionWorker | None = Depends(get_worker),
):
    rows = (await db.execute(
        select(Resume.status, func.count()).where(Resume.is_current.is_(True)).group_by(Resume.status)
    )).all()
    by_status = {s.value: 0 for s in ResumeStatus} | {s: n for s, n in rows}
    return QueueStats(total=sum(by_status.values()), by_status=by_status,
                      worker_running=worker is not None and worker.running,
                      vector_count=await asyncio.to_thread(get_vector_store().count))


@router.post("/api/resumes/reextract")
async def reextract_all(
    db: AsyncSession = Depends(get_db),
    worker: IngestionWorker | None = Depends(get_worker),
):
    count = await requeue_for_extraction(db)
    _wake(worker)
    return {"requeued": count}


@router.post("/api/resumes/reembed")
async def reembed_all(worker: IngestionWorker | None = Depends(get_worker)):
    count = await requeue_for_embedding()
    _wake(worker)
    return {"requeued": count}


@router.get("/api/resumes/{resume_id}", response_model=ResumeDetail)
async def get_resume(resume_id: int, full_text: bool = False, db: AsyncSession = Depends(get_db)):
    resume = await db.scalar(
        select(Resume).where(Resume.id == resume_id).options(selectinload(Resume.employee))
    )
    if resume is None:
        raise HTTPException(status_code=404, detail="Resume not found")
    text = resume.raw_text or ""
    return ResumeDetail(
        **ResumeOut.model_validate(resume).model_dump(),
        employee_code=resume.employee.employee_code,
        employee_name=resume.employee.full_name,
        text_length=len(text),
        text=(text if full_text else text[:PREVIEW_CHARS]) or None,
    )


@router.get("/api/resumes/{resume_id}/profile", response_model=ProfileOut)
async def get_profile(resume_id: int, db: AsyncSession = Depends(get_db)):
    resume = await db.scalar(
        select(Resume).where(Resume.id == resume_id).options(
            selectinload(Resume.employee),
            selectinload(Resume.profile),
            selectinload(Resume.experiences),
            selectinload(Resume.skills).selectinload(ResumeSkill.skill),
        )
    )
    if resume is None:
        raise HTTPException(status_code=404, detail="Resume not found")
    if resume.profile is None:
        raise HTTPException(status_code=404, detail=f"No profile yet (resume status is '{resume.status}').")
    profile, raw = resume.profile, resume.profile.raw_extraction or {}
    skills = sorted(resume.skills, key=lambda link: (-(link.years or 0), link.skill.name.lower()))
    return ProfileOut(
        resume_id=resume.id,
        employee_code=resume.employee.employee_code,
        employee_name=resume.employee.full_name,
        status=resume.status,
        extraction_model=profile.extraction_model,
        headline=profile.headline,
        summary=profile.summary,
        total_experience_years=profile.total_experience_years,
        skills=[
            {"name": link.skill.name, "category": link.skill.category, "years": link.years,
             "last_used_year": link.last_used_year, "evidence": link.evidence}
            for link in skills
        ],
        experience=[
            {"title": e.title, "company": e.company, "start_date": e.start_date, "end_date": e.end_date,
             "is_current": e.is_current, "description": e.description}
            for e in sorted(resume.experiences, key=lambda e: e.start_date or date.min, reverse=True)
        ],
        education=profile.education or [],
        certifications=profile.certifications or [],
        rejected_skills=raw.get("rejected_skills", []),
        warnings=raw.get("warnings", []),
        stats=raw.get("stats"),
    )


@router.post("/api/resumes/{resume_id}/retry", response_model=ResumeOut)
async def retry(
    resume_id: int,
    db: AsyncSession = Depends(get_db),
    worker: IngestionWorker | None = Depends(get_worker),
):
    resume = await db.get(Resume, resume_id)
    if resume is None:
        raise HTTPException(status_code=404, detail="Resume not found")
    if resume.status != ResumeStatus.FAILED:
        raise HTTPException(status_code=409, detail=f"Only failed resumes can be retried (status is '{resume.status}').")
    resume = await retry_resume(db, resume)
    _wake(worker)
    return resume


@router.delete("/api/resumes/{resume_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove(resume_id: int, db: AsyncSession = Depends(get_db)):
    resume = await db.get(Resume, resume_id)
    if resume is None:
        raise HTTPException(status_code=404, detail="Resume not found")
    await delete_resume(db, resume)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
