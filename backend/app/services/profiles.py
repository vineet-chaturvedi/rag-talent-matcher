"""
Saving an extracted profile into the database tables from Step 3:
resume_profiles, experiences, resume_projects (doc 18), skills and resume_skills.
"""
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.enums import ResumeStatus
from app.db.models import Experience, Resume, ResumeProfile, ResumeProject, ResumeSkill, Skill
from app.extraction.extractor import ExtractionOutcome


async def _get_or_create_skills(session: AsyncSession, names: list[str], categories: dict[str, str | None]) -> dict[str, Skill]:
    """Look up all skills in ONE query (case-insensitive); create the missing ones."""
    wanted = {n.lower(): n for n in names}
    existing = (await session.scalars(select(Skill).where(func.lower(Skill.name).in_(list(wanted))))).all()
    by_lower = {s.name.lower(): s for s in existing}
    for skill in existing:          # the catalogue's category wins, so older rows are corrected over time
        category = categories.get(wanted[skill.name.lower()])
        if category and skill.category != category:
            skill.category = category
    for lower, name in wanted.items():
        if lower not in by_lower:
            skill = Skill(name=name, category=categories.get(name))
            session.add(skill)
            by_lower[lower] = skill
    await session.flush()   # new skills get their ids
    return {name: by_lower[name.lower()] for name in names}


async def save_profile(session: AsyncSession, resume_id: int, outcome: ExtractionOutcome) -> bool:
    """Replace any previous extraction for this resume. Returns False if the resume no longer exists."""
    resume = await session.get(
        Resume, resume_id,
        options=[selectinload(Resume.profile), selectinload(Resume.experiences), selectinload(Resume.skills),
                 selectinload(Resume.projects)],
    )
    if resume is None:
        return False

    # 1. Remove the old extraction (re-running extraction must not create duplicates).
    resume.profile = None
    resume.experiences.clear()
    resume.skills.clear()
    resume.projects.clear()
    await session.flush()   # executes the DELETEs (delete-orphan cascade) before the new INSERTs

    profile = outcome.profile

    # 2. The profile row, including the model's raw answer for auditing.
    resume.profile = ResumeProfile(
        headline=(profile.headline or "")[:300] or None,
        summary=profile.summary,
        total_experience_years=profile.total_experience_years,
        education=profile.education,
        certifications=profile.certifications,
        raw_extraction={
            "llm_output": outcome.llm_output.model_dump(),
            "rejected_skills": profile.rejected_skills,
            "warnings": profile.warnings,
            "experience_basis": profile.experience_basis,   # "dated jobs" / "stated in resume"
            "stated_years": profile.stated_years,
            "stats": outcome.stats,
        },
        extraction_model=outcome.model,
    )

    # 3. Jobs
    resume.experiences = [
        Experience(
            company=(job.company or None) and job.company[:200],
            title=(job.title or None) and job.title[:200],
            start_date=job.start_date, end_date=job.end_date,
            is_current=job.is_current, description=job.description,
        )
        for job in profile.jobs
    ]

    # 3b. Projects (doc 18)
    resume.projects = [
        ResumeProject(
            position=i, name=p.name[:200], role=(p.role or None) and p.role[:200],
            duration_months=p.duration_months, duration_text=(p.duration_text or None) and p.duration_text[:100],
            technologies=p.technologies, description=p.description, link=(p.link or None) and p.link[:500],
            company=(profile.jobs[p.job_index].company or None) and profile.jobs[p.job_index].company[:200]
            if p.job_index is not None else None,
            company_basis=p.job_basis,
        )
        for i, p in enumerate(profile.projects)
    ]

    # 4. Skills (deduplicated case-insensitively)
    unique: dict[str, object] = {}
    for s in profile.skills:
        unique.setdefault(s.name[:100].lower(), s)
    skill_rows = await _get_or_create_skills(
        session, [s.name[:100] for s in unique.values()], {s.name[:100]: s.category for s in unique.values()}
    )
    resume.skills = [
        ResumeSkill(skill=skill_rows[s.name[:100]], years=s.years, last_used_year=s.last_used_year,
                    evidence=s.evidence, uses=s.uses, source=s.source)
        for s in unique.values()
    ]

    # 5. Advance the pipeline
    resume.status = ResumeStatus.EXTRACTED
    resume.attempts = 0
    resume.error_message = None
    resume.processed_at = func.now()
    await session.commit()
    return True
