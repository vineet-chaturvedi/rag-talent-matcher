"""Portal users (people who log in) - NOT the employees being matched."""
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, enum_column
from app.db.enums import UserRole


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True)
    full_name: Mapped[str] = mapped_column(String(200))
    hashed_password: Mapped[str] = mapped_column(String(255))  # NEVER the real password (Step 9)
    role: Mapped[UserRole] = mapped_column(enum_column(UserRole), default=UserRole.RESOURCE_MANAGER)
    is_active: Mapped[bool] = mapped_column(default=True)  # disable login without deleting history