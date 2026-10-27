"""API shapes for employees and the CSV import."""
from datetime import date

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.db.enums import AvailabilityStatus
from app.schemas.resume import ResumeOut


class EmployeeRow(BaseModel):
    """
    One row of the HR CSV, validated. Column names = these field names.
    Only employee_code and full_name are required; blank cells are treated as "not provided".
    """
    model_config = ConfigDict(str_strip_whitespace=True)

    employee_code: str = Field(min_length=1, max_length=50)
    full_name: str = Field(min_length=1, max_length=200)
    email: str | None = Field(None, max_length=255, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    department: str | None = Field(None, max_length=100)
    designation: str | None = Field(None, max_length=100)
    location: str | None = Field(None, max_length=100)
    date_joined: date | None = None                       # YYYY-MM-DD
    availability_status: AvailabilityStatus = AvailabilityStatus.AVAILABLE
    allocation_percent: int = Field(0, ge=0, le=100)
    available_from: date | None = None
    current_project_name: str | None = Field(None, max_length=200)
    manager_name: str | None = Field(None, max_length=200)

    @model_validator(mode="before")
    @classmethod
    def drop_blank_cells(cls, data):
        """An empty CSV cell arrives as '' - remove it so the field counts as 'not provided'."""
        if isinstance(data, dict):
            return {k: v for k, v in data.items() if not (isinstance(v, str) and v.strip() == "")}
        return data

    @field_validator("availability_status", mode="before")
    @classmethod
    def normalise_status(cls, value):
        """Accept 'Available', 'ON LEAVE', 'on-leave'... -> 'available', 'on_leave'."""
        if isinstance(value, str):
            return value.strip().lower().replace(" ", "_").replace("-", "_")
        return value


class RowError(BaseModel):
    line: int                     # line number in the CSV file (header = line 1)
    employee_code: str | None
    message: str


class EmployeeImportResult(BaseModel):
    created: int
    updated: int
    failed: int
    errors: list[RowError]


class EmployeeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    employee_code: str
    full_name: str
    email: str | None
    department: str | None
    designation: str | None
    location: str | None
    availability_status: AvailabilityStatus
    allocation_percent: int
    available_from: date | None
    current_project_name: str | None
    is_active: bool


class EmployeeListItem(EmployeeOut):
    current_resume: ResumeOut | None = None


class EmployeeDetail(EmployeeOut):
    date_joined: date | None
    manager_name: str | None
    resumes: list[ResumeOut]      # all versions, newest first
