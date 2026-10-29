"""
Projects, roles and candidate retrieval (Step 7):
  POST /api/projects                         create a project
  GET  /api/projects                         list projects with their roles
  POST /api/projects/{id}/roles              add a role (position to fill) to a project
  GET  /api/roles/{id}                       one role with its requirements
  POST /api/roles/{id}/requirements/parse    LLM reads the description -> structured requirements
  PUT  /api/roles/{id}/requirements          a person corrects the requirements
  POST /api/roles/{id}/candidates            hybrid retrieval: skills + keyword + vector, fused with RRF
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_db, get_ollama
from app.auth.dependencies import get_current_user
from app.config import Settings, get_settings
from app.db.models import Project, ProjectRole, User
from app.llm.ollama_client import OllamaClient, OllamaError
from app.matching.requirements import RoleParseError, ground_in_description, normalise_skill_sections, parse_role
from app.matching.retrieval import retrieve_candidates
from app.schemas.project import (
    AvailabilityOut, CandidateOut, CandidatesRequest, CandidatesResponse, ChunkEvidence, ProjectCreate,
    ProjectOut, Requirements, RoleCreate, RoleOut, SkillMatchOut,
)

router = APIRouter(tags=["projects & matching"])


async def _get_role(db: AsyncSession, role_id: int) -> ProjectRole:
    role = await db.get(ProjectRole, role_id)
    if role is None:
        raise HTTPException(status_code=404, detail="Role not found")
    return role


def _effective(role: ProjectRole) -> dict:
    """The requirements exactly as the search uses them (normalised, and grounded unless a person edited them)."""
    req = normalise_skill_sections(role.requirements)
    return req if req.get("edited_by_user") else ground_in_description(req, role.title, role.description)


# --------------------------------------------------------------------------- projects & roles
@router.post("/api/projects", response_model=ProjectOut, status_code=201)
async def create_project(body: ProjectCreate, db: AsyncSession = Depends(get_db),
                         user: User = Depends(get_current_user)):
    project = Project(**body.model_dump(), created_by_id=user.id)
    project.roles = []
    db.add(project)
    await db.commit()
    await db.refresh(project, attribute_names=["roles"])
    return project


@router.get("/api/projects", response_model=list[ProjectOut])
async def list_projects(db: AsyncSession = Depends(get_db)):
    return (await db.scalars(select(Project).options(selectinload(Project.roles)).order_by(Project.id))).all()


@router.post("/api/projects/{project_id}/roles", response_model=RoleOut, status_code=201)
async def create_role(project_id: int, body: RoleCreate, db: AsyncSession = Depends(get_db)):
    if await db.get(Project, project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")
    role = ProjectRole(project_id=project_id, **body.model_dump())
    db.add(role)
    await db.commit()
    await db.refresh(role)
    return role


@router.get("/api/roles/{role_id}", response_model=RoleOut)
async def get_role(role_id: int, db: AsyncSession = Depends(get_db)):
    return await _get_role(db, role_id)


# --------------------------------------------------------------------------- requirements
@router.post("/api/roles/{role_id}/requirements/parse", response_model=RoleOut)
async def parse_requirements(
    role_id: int,
    db: AsyncSession = Depends(get_db),
    ollama: OllamaClient = Depends(get_ollama),
    settings: Settings = Depends(get_settings),
):
    """Takes ~30-60 s on a CPU: the LLM reads the role description once; the result is stored."""
    role = await _get_role(db, role_id)
    try:
        requirements = await parse_role(ollama, role.title, role.description,
                                        settings.role_parse_model, settings.llm_num_ctx)
    except OllamaError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except RoleParseError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    role.requirements = requirements
    # Fill role fields the person left empty with what the description says.
    if role.min_experience_years is None and requirements.get("min_total_years") is not None:
        role.min_experience_years = requirements["min_total_years"]
    if not role.location and requirements.get("location"):
        role.location = requirements["location"][:100]
    await db.commit()
    await db.refresh(role)
    return role


@router.put("/api/roles/{role_id}/requirements", response_model=RoleOut)
async def update_requirements(role_id: int, body: Requirements, db: AsyncSession = Depends(get_db)):
    """A resource manager corrects what the AI parsed (e.g. moves a skill from must-have to nice-to-have)."""
    role = await _get_role(db, role_id)
    data = body.model_dump()
    previous = role.requirements or {}
    data["title"] = data["title"] or role.title
    data["parsed_by"] = data["parsed_by"] or previous.get("parsed_by")     # keep who parsed it originally
    data["parsed_at"] = data["parsed_at"] or previous.get("parsed_at")
    data["edited_by_user"] = True
    data.update(normalise_skill_sections(data))     # "k8s" typed by a person -> "Kubernetes"
    role.requirements = data
    await db.commit()
    await db.refresh(role)
    return role


# --------------------------------------------------------------------------- candidates
@router.post("/api/roles/{role_id}/candidates", response_model=CandidatesResponse)
async def find_candidates(
    role_id: int,
    body: CandidatesRequest,
    db: AsyncSession = Depends(get_db),
    ollama: OllamaClient = Depends(get_ollama),
    settings: Settings = Depends(get_settings),
):
    role = await _get_role(db, role_id)
    if not role.requirements:
        raise HTTPException(status_code=409, detail="This role has no requirements yet: call /requirements/parse first.")
    try:
        candidates, timings = await retrieve_candidates(
            db, ollama, settings, role, top_k=body.top_k,
            only_available=body.only_available, signals=tuple(body.signals),
        )
    except OllamaError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    return CandidatesResponse(
        role_id=role.id, role_title=role.title, requirements=Requirements(**_effective(role)), timings=timings,
        candidates=[
            CandidateOut(
                rank=i + 1, employee_id=c.employee.id, employee_code=c.employee.employee_code,
                full_name=c.employee.full_name, designation=c.employee.designation, location=c.employee.location,
                fused_score=c.fused_score, ranks=c.ranks, skill_score=c.skill_score,
                must_matched=[SkillMatchOut(**vars(m)) for m in c.must_matched],
                must_missing=c.must_missing,
                nice_matched=[SkillMatchOut(**vars(m)) for m in c.nice_matched],
                keyword_snippets=c.keyword_snippets,
                vector_chunks=[ChunkEvidence(section=h.section, similarity=h.similarity, text=h.text) for h in c.vector_chunks],
                availability=AvailabilityOut(**vars(c.availability)),
            )
            for i, c in enumerate(candidates)
        ],
    )
