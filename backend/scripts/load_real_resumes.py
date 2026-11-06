"""
Puts the 9 real resumes of samples/real/ into the database, so the evaluations can run on them
(scripts/evaluate_real_retrieval.py finds them by file hash).

Each resume gets its OWN test employee. R7 and R8 are two versions of Vineet's resume; on one employee only the
newest would stay "current" (searchable), and the retrieval test needs both. Safe to run again: a file whose
exact bytes are already in the database is skipped.

The files are queued exactly like an upload from the portal (same checks, same storage). The worker inside the
running server processes them one by one (it checks the queue every few seconds), so start the server if it is
not running. --wait shows progress until every file is ready or failed.

Run from backend/:
    python -m scripts.load_real_resumes --wait
"""
import argparse
import asyncio
import hashlib
import sys
import time
from pathlib import Path

from sqlalchemy import select

from app.config import get_settings
from app.db.enums import ResumeStatus
from app.db.models import Employee, Resume
from app.db.session import SessionLocal, init_db
from app.ingestion.storage import InvalidFileError
from app.services.resumes import DuplicateResumeError, add_resume

FILES = Path(__file__).resolve().parents[2] / "samples" / "real"

# file -> (employee code, name, designation). R1 is Ajay (EMP-1017), uploaded earlier through the portal.
PEOPLE = {
    "R1_ajay_chandani.pdf": ("EMP-1017", "Ajay Chandani", "Lead Ecommerce & AI Solutions Engineer"),
    "R2_harsh_python.docx": ("EMP-1018", "Harsh", "Python Developer"),
    "R3_ravi_fullstack.doc": ("EMP-1019", "Ravi (Full-stack resume)", "Senior Full-stack Engineer"),
    "R4_mahesh_fullstack.pdf": ("EMP-1020", "Mahesh S.", "Full Stack Developer"),
    "R5_rajendra_fullstack.pdf": ("EMP-1021", "Rajendra", "Full Stack Developer"),
    "R6_ravi_react_native.pdf": ("EMP-1022", "Ravi (React Native resume)", "React Native Developer"),
    "R7_vineet_fullstack.pdf": ("EMP-1023", "Vineet (Full Stack resume)", "Full Stack Developer"),
    "R8_vineet_mern.pdf": ("EMP-1024", "Vineet (MERN resume)", "MERN Stack Developer"),
    "R9_vishal_golang.pdf": ("EMP-1025", "Vishal", "Golang Developer"),
}
FINISHED = {ResumeStatus.READY, ResumeStatus.FAILED}


async def load() -> list[int]:
    settings = get_settings()
    await init_db()
    ids: list[int] = []
    async with SessionLocal() as session:
        for filename, (code, name, designation) in PEOPLE.items():
            path = FILES / filename
            if not path.exists():
                print(f"  ! {filename}: not found in {FILES}")
                continue
            data = path.read_bytes()
            existing = await session.scalar(
                select(Resume).where(Resume.file_hash == hashlib.sha256(data).hexdigest()))
            if existing is not None:
                print(f"  = {filename}: already uploaded (resume #{existing.id}, {existing.status.value})")
                ids.append(existing.id)
                continue

            employee = await session.scalar(select(Employee).where(Employee.employee_code == code))
            if employee is None:
                employee = Employee(employee_code=code, full_name=name, designation=designation,
                                    department="Engineering")
                session.add(employee)
                await session.commit()
                await session.refresh(employee)
                print(f"  + employee {code} {name} created")
            elif employee.full_name != name:
                # Never attach a test resume to somebody else's record.
                print(f"  ! {filename}: {code} already belongs to {employee.full_name!r}; skipped. "
                      f"Change its code in PEOPLE in this script.")
                continue
            try:
                resume = await add_resume(session, settings, employee, filename, data)
            except (InvalidFileError, DuplicateResumeError) as exc:
                print(f"  ! {filename}: {exc}")
                continue
            print(f"  + {filename}: queued as resume #{resume.id} for {code}")
            ids.append(resume.id)
    return ids


async def wait_for(ids: list[int], timeout_seconds: float) -> bool:
    start = time.monotonic()
    last = ""
    while True:
        async with SessionLocal() as session:
            rows = (await session.execute(select(Resume.id, Resume.status, Resume.error_message)
                                          .where(Resume.id.in_(ids)))).all()
        counts: dict[str, int] = {}
        for _, status, _ in rows:
            counts[status.value] = counts.get(status.value, 0) + 1
        line = ", ".join(f"{k}={v}" for k, v in sorted(counts.items()))
        if line != last:
            print(f"  {time.monotonic() - start:5.0f}s  {line}")
            last = line
        if all(status in FINISHED for _, status, _ in rows):
            for rid, status, error in rows:
                if status == ResumeStatus.FAILED:
                    print(f"  x resume #{rid} failed: {error}")
            return all(status == ResumeStatus.READY for _, status, _ in rows)
        if time.monotonic() - start > timeout_seconds:
            print("  Still not finished. Is the server (and so the worker) running? Is Ollama running?")
            return False
        await asyncio.sleep(3)


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--wait", action="store_true", help="show progress until every resume is ready or failed")
    parser.add_argument("--timeout", type=float, default=1800, help="seconds to wait at most (default 1800)")
    args = parser.parse_args()
    print(f"Loading the real resumes from {FILES}")
    ids = await load()
    if not ids:
        return 1
    if not args.wait:
        print("Queued. The running server's worker processes them; add --wait to follow it.")
        return 0
    print("Waiting for the worker (it runs inside the server: start it if it is not running)...")
    return 0 if await wait_for(ids, args.timeout) else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
