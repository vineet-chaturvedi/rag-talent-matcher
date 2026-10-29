"""Small user-related queries shared by startup and scripts (Step 9)."""
from sqlalchemy import func, select

from app.db.models import User
from app.db.session import SessionLocal


async def count_users() -> int:
    async with SessionLocal() as session:
        return await session.scalar(select(func.count()).select_from(User))
