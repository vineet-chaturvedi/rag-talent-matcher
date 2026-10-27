"""
API shapes for resumes: what the endpoints accept and return.
(Separate from the database models on purpose: the API contract is not the same as the table layout.)
"""
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.db.enums import ResumeStatus


class ResumeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)  # allow building this from a SQLAlchemy object

    id: int
    employee_id: int
    original_filename: str
    mime_type: str
    file_size_bytes: int
    is_current: bool
    status: ResumeStatus
    error_message: str | None
    attempts: int
    page_count: int | None
    created_at: datetime
    processed_at: datetime | None


class ResumeDetail(ResumeOut):
    employee_code: str
    employee_name: str
    text_length: int
    text: str | None      # a preview, or the full text when ?full_text=true


class UploadItemResult(BaseModel):
    filename: str
    ok: bool
    resume_id: int | None = None
    employee_code: str | None = None
    error: str | None = None


class BulkUploadResult(BaseModel):
    uploaded: int
    failed: int
    items: list[UploadItemResult]


class QueueStats(BaseModel):
    total: int
    by_status: dict[str, int]
    worker_running: bool
    vector_count: int = 0         # chunks stored in ChromaDB (Step 6)
