"""
Step 3 learning tool: insert demo data, run example queries, and clean it up again.

Run from backend/:
    python -m scripts.seed_demo            insert 2 demo employees (if missing) and run example queries
    python -m scripts.seed_demo --clean    delete the demo employees and show ON DELETE CASCADE at work

Demo employees use codes starting with "DEMO-" so they can never be confused with real or sample data.
Run --clean before Step 4: demo resumes are marked READY but have no chunks/embeddings.
"""
import argparse
import asyncio
from datetime import date

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.enums import AvailabilityStatus, ResumeStatus
from app.db.models import Employee, Experience, Resume, ResumeSkill, Skill
from app.db.session import SessionLocal, engine, init_db

DEMO_PREFIX = "DEMO-"


# --------------------------------------------------------------------------- insert
async def get_or_create_skill(session: AsyncSession, name: str, category: str) -> Skill:
    """Skills are shared: reuse the existing row if this skill already exists."""
    skill = await session.scalar(select(Skill).where(Skill.name == name))
    if skill is None:
        skill = Skill(name=name, category=category)
        session.add(skill)
        await session.flush()  # send the INSERT now (inside the transaction) so skill.id gets a value
    return skill


async def insert_demo_data(session: AsyncSession) -> None:
    python = await get_or_create_skill(session, "Python", "language")
    django = await get_or_create_skill(session, "Django", "framework")
    k8s = await get_or_create_skill(session, "Kubernetes", "devops")
    react = await get_or_create_skill(session, "React", "framework")

    # ---- Employee 1: available backend engineer ----
    asha = Employee(
        employee_code=f"{DEMO_PREFIX}001", full_name="Asha Rao (demo)", email="asha.demo@example.com",
        department="Engineering", designation="Senior Software Engineer", location="Pune",
        availability_status=AvailabilityStatus.AVAILABLE, allocation_percent=0,
        available_from=date(2026, 11, 1),
    )
    asha_resume = Resume(
        original_filename="asha_rao.pdf", stored_path="(demo - no real file)",
        file_hash="demo-hash-001", mime_type="application/pdf", file_size_bytes=120_000,
        status=ResumeStatus.READY,
    )
    asha_resume.skills = [
        ResumeSkill(skill=python, years=6, last_used_year=2026),
        ResumeSkill(skill=django, years=4, last_used_year=2026,
                    evidence="Built billing APIs with Django REST Framework (2022-present)"),
        ResumeSkill(skill=k8s, years=2, last_used_year=2025),
    ]
    asha_resume.experiences = [
        Experience(company="Our Company", title="Senior Software Engineer",
                   start_date=date(2022, 4, 1), is_current=True,
                   description="Backend services in Django, deployed on Kubernetes."),
    ]
    asha.resumes.append(asha_resume)

    # ---- Employee 2: fully allocated frontend engineer ----
    ravi = Employee(
        employee_code=f"{DEMO_PREFIX}002", full_name="Ravi Kumar (demo)", email="ravi.demo@example.com",
        department="Engineering", designation="Frontend Engineer", location="Bengaluru",
        availability_status=AvailabilityStatus.ALLOCATED, allocation_percent=100,
        current_project_name="Retail Portal",
    )
    ravi_resume = Resume(
        original_filename="ravi_kumar.docx", stored_path="(demo - no real file)",
        file_hash="demo-hash-002",
        mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        file_size_bytes=80_000, status=ResumeStatus.READY,
    )
    ravi_resume.skills = [
        ResumeSkill(skill=react, years=5, last_used_year=2026),
        ResumeSkill(skill=python, years=1, last_used_year=2023),
    ]
    ravi.resumes.append(ravi_resume)

    # add_all + cascade: adding the employees also saves their resumes, skill links and experiences
    session.add_all([asha, ravi])
    await session.commit()  # ONE transaction: everything is saved, or nothing is
    print("Inserted 2 demo employees.")


# --------------------------------------------------------------------------- queries
async def run_example_queries(session: AsyncSession) -> None:
    # ---- Query 1: the core matching filter, as SQL JOINs ----
    stmt = (
        select(Employee.full_name, Employee.location, ResumeSkill.years)
        .join(Employee.resumes)        # employees -> resumes
        .join(Resume.skills)           # resumes -> resume_skills
        .join(ResumeSkill.skill)       # resume_skills -> skills
        .where(
            Skill.name == "Python",
            ResumeSkill.years >= 3,
            Resume.is_current.is_(True),
            Employee.availability_status == AvailabilityStatus.AVAILABLE,
        )
    )
    rows = (await session.execute(stmt)).all()
    print("\nAvailable employees with Python >= 3 years:")
    for name, location, years in rows:
        print(f"  - {name} ({location}): {years} years")

    # ---- Query 2: load objects WITH their relationships (eager loading for async) ----
    stmt = (
        select(Employee)
        .options(selectinload(Employee.resumes).selectinload(Resume.skills).selectinload(ResumeSkill.skill))
        .order_by(Employee.employee_code)
    )
    employees = (await session.scalars(stmt)).all()
    print("\nAll employees and their skills:")
    for emp in employees:
        for res in emp.resumes:
            skills = ", ".join(f"{link.skill.name} ({link.years}y)" for link in res.skills)
            print(f"  - {emp.full_name} [{emp.availability_status}]: {skills}")


# --------------------------------------------------------------------------- clean
async def count_rows(session: AsyncSession) -> dict[str, int]:
    """Row counts of the tables that hang off an employee."""
    counts = {}
    for model in (Employee, Resume, ResumeSkill, Experience, Skill):
        counts[model.__tablename__] = await session.scalar(select(func.count()).select_from(model))
    return counts


async def delete_demo_data(session: AsyncSession) -> None:
    before = await count_rows(session)

    # A plain SQL DELETE on employees ONLY. We deliberately do NOT delete resumes, skill links or
    # experiences ourselves: if foreign keys are ON, the DATABASE removes them via ON DELETE CASCADE.
    result = await session.execute(
        delete(Employee).where(Employee.employee_code.like(f"{DEMO_PREFIX}%"))
    )
    await session.commit()

    if result.rowcount == 0:
        print("No demo employees found - nothing to delete.")
        return

    after = await count_rows(session)
    print(f"Deleted {result.rowcount} demo employee(s). Row counts before -> after:")
    for table in before:
        print(f"  {table:<15} {before[table]:>3} -> {after[table]:>3}")
    print(
        "\nresumes, resume_skills and experiences dropped too: ON DELETE CASCADE worked.\n"
        "skills did NOT change: skills are shared catalogue entries, not owned by one employee."
    )


# --------------------------------------------------------------------------- entry point
async def main(clean: bool) -> None:
    await init_db()
    async with SessionLocal() as session:
        if clean:
            await delete_demo_data(session)
        else:
            exists = await session.scalar(
                select(Employee).where(Employee.employee_code == f"{DEMO_PREFIX}001")
            )
            if exists:
                print("Demo data already present - skipping insert.")
            else:
                await insert_demo_data(session)
            await run_example_queries(session)
    await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Insert, query, or delete Step 3 demo data.")
    parser.add_argument("--clean", action="store_true", help="delete demo employees (shows cascade deletes)")
    args = parser.parse_args()
    asyncio.run(main(clean=args.clean))