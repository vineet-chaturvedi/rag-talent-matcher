"""
User management, admins only (Step 9):
  GET   /api/users          list portal users
  POST  /api/users          create a user (admin or resource manager)
  PATCH /api/users/{id}     rename, change role, (de)activate, reset password
Users are never deleted: deactivating keeps the history ("who ran this match?") intact.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.auth.dependencies import require_admin
from app.auth.passwords import hash_password, password_problem
from app.db.enums import UserRole
from app.db.models import User
from app.schemas.auth import UserCreate, UserOut, UserUpdate

router = APIRouter(prefix="/api/users", tags=["users (admin)"], dependencies=[Depends(require_admin)])


@router.get("", response_model=list[UserOut])
async def list_users(db: AsyncSession = Depends(get_db)):
    return (await db.scalars(select(User).order_by(User.id))).all()


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def create_user(body: UserCreate, db: AsyncSession = Depends(get_db)):
    if problem := password_problem(body.password):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, problem)
    if await db.scalar(select(User).where(func.lower(User.email) == body.email)):
        raise HTTPException(status.HTTP_409_CONFLICT, "A user with this email already exists.")
    user = User(email=body.email, full_name=body.full_name, role=body.role,
                hashed_password=hash_password(body.password))
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@router.patch("/{user_id}", response_model=UserOut)
async def update_user(user_id: int, body: UserUpdate, db: AsyncSession = Depends(get_db)):
    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    losing_admin = user.role == UserRole.ADMIN and (
        (body.role is not None and body.role != UserRole.ADMIN) or body.is_active is False)
    if losing_admin:
        active_admins = await db.scalar(select(func.count()).select_from(User)
                                        .where(User.role == UserRole.ADMIN, User.is_active.is_(True)))
        if active_admins <= 1:
            raise HTTPException(status.HTTP_409_CONFLICT, "This is the last active admin; create another admin first.")
    if body.full_name is not None:
        user.full_name = body.full_name
    if body.role is not None:
        user.role = body.role
    if body.is_active is not None:
        user.is_active = body.is_active
    if body.password is not None:
        if problem := password_problem(body.password):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, problem)
        user.hashed_password = hash_password(body.password)
    await db.commit()
    await db.refresh(user)
    return user
