"""
Business logic for employees: importing the HR CSV.
No HTTP here - the API layer (app/api/employees.py) calls these functions.
"""
import csv
import io

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Employee
from app.schemas.employee import EmployeeImportResult, EmployeeRow, RowError

REQUIRED_COLUMNS = {"employee_code", "full_name"}


class InvalidCsvError(ValueError):
    """The file as a whole can't be imported. Message is safe to show to the user."""


def _format_validation_error(exc: ValidationError) -> str:
    # e.g. "allocation_percent: Input should be less than or equal to 100"
    return "; ".join(f"{'.'.join(str(p) for p in err['loc']) or 'row'}: {err['msg']}" for err in exc.errors())


async def import_employees_csv(session: AsyncSession, content: bytes) -> EmployeeImportResult:
    """
    Create or update ("upsert") employees from an HR CSV, matched by employee_code.
    Valid rows are saved; invalid rows are reported with their line number.
    """
    # 1. Bytes -> text. "utf-8-sig" also strips the invisible BOM that Excel puts at the start.
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise InvalidCsvError("The file is not UTF-8 text. In Excel use 'Save As' -> 'CSV UTF-8'.") from exc

    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise InvalidCsvError("The CSV file is empty.")
    headers = {h.strip().lower() for h in reader.fieldnames if h}
    missing = REQUIRED_COLUMNS - headers
    if missing:
        raise InvalidCsvError(f"Missing required column(s): {', '.join(sorted(missing))}")

    # 2. Validate every row; collect errors instead of stopping at the first one.
    valid: list[EmployeeRow] = []
    errors: list[RowError] = []
    seen_codes: set[str] = set()
    for line_no, raw in enumerate(reader, start=2):        # line 1 is the header
        row = {(k or "").strip().lower(): v for k, v in raw.items() if k}
        code = (row.get("employee_code") or "").strip() or None
        try:
            parsed = EmployeeRow.model_validate(row)
        except ValidationError as exc:
            errors.append(RowError(line=line_no, employee_code=code, message=_format_validation_error(exc)))
            continue
        if parsed.employee_code in seen_codes:
            errors.append(RowError(line=line_no, employee_code=code, message="Duplicate employee_code in this file"))
            continue
        seen_codes.add(parsed.employee_code)
        valid.append(parsed)

    # 3. One query to find which employees already exist (not one query per row).
    existing = {
        e.employee_code: e
        for e in (await session.scalars(select(Employee).where(Employee.employee_code.in_(seen_codes)))).all()
    }

    # 4. Insert new ones, update existing ones.
    created = updated = 0
    for row in valid:
        employee = existing.get(row.employee_code)
        if employee is None:
            session.add(Employee(**row.model_dump()))
            created += 1
        else:
            # exclude_unset: only overwrite fields that actually have a value in the CSV
            for field, value in row.model_dump(exclude_unset=True).items():
                setattr(employee, field, value)
            updated += 1

    # 5. Save everything in ONE transaction: all valid rows, or nothing.
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise InvalidCsvError(
            "Import cancelled, nothing was saved: two employees would end up with the same email "
            f"(or another uniqueness rule was broken). Details: {exc.orig}"
        ) from exc

    return EmployeeImportResult(created=created, updated=updated, failed=len(errors), errors=errors)
