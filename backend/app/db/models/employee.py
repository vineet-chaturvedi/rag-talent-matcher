"""Staff members we match to project roles. Master data comes from HR (CSV import, Step 4)."""
from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, enum_column
from app.db.enums import AvailabilityStatus

if TYPE_CHECKING:  # only for editor type hints; avoids circular imports at runtime
    from app.db.models.resume import Resume


class Employee(TimestampMixin, Base):
    __tablename__ = "employees"

    id: Mapped[int] = mapped_column(primary_key=True)
    employee_code: Mapped[str] = mapped_column(String(50), unique=True)  # HR's ID, e.g. "EMP-0042"
    full_name: Mapped[str] = mapped_column(String(200))
    email: Mapped[str | None] = mapped_column(String(255), unique=True)
    department: Mapped[str | None] = mapped_column(String(100), index=True)
    designation: Mapped[str | None] = mapped_column(String(100))
    location: Mapped[str | None] = mapped_column(String(100), index=True)
    date_joined: Mapped[date | None]

    # ---- Availability: the internal-matching essentials ----
    availability_status: Mapped[AvailabilityStatus] = mapped_column(
        enum_column(AvailabilityStatus), default=AvailabilityStatus.AVAILABLE, index=True
    )
    allocation_percent: Mapped[int] = mapped_column(default=0)  # 0 = fully free, 100 = fully busy
    available_from: Mapped[date | None]                         # when they can start a new project
    current_project_name: Mapped[str | None] = mapped_column(String(200))
    manager_name: Mapped[str | None] = mapped_column(String(200))

    is_active: Mapped[bool] = mapped_column(default=True, index=True)  # False = left the company

    # One employee -> many resumes (versions). Deleting the employee deletes their resumes.
    resumes: Mapped[list["Resume"]] = relationship(
        back_populates="employee",
        cascade="all, delete-orphan",
        order_by="Resume.created_at.desc()",
    )

    __table_args__ = (
        CheckConstraint("allocation_percent BETWEEN 0 AND 100", name="allocation_range"),
    )