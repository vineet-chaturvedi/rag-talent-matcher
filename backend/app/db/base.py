"""
Shared foundation for all database models.
"""
import logging
from datetime import datetime

from sqlalchemy import DateTime, Enum, MetaData, String, event, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

logger = logging.getLogger(__name__)

# Predictable names for indexes/constraints, e.g. "fk_resumes_employee_id_employees".
# Without this, databases invent random names, which makes future migrations (Alembic) painful.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Every model inherits from this. Base.metadata = the catalogue of all tables."""
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class TimestampMixin:
    """Adds created_at / updated_at to any model that includes it. Times are UTC."""
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )


def enum_column(enum_cls: type) -> Enum:
    """
    Column type for our StrEnums.
    - native_enum=False: store as plain text (works on SQLite AND PostgreSQL)
    - values_callable: store the VALUE ("available"), not the Python NAME ("AVAILABLE")
    """
    return Enum(
        enum_cls,
        native_enum=False,
        length=30,
        values_callable=lambda e: [member.value for member in e],
        validate_strings=True,
    )

# --------------------------------------------------------------------------- the same behaviour on every database
@event.listens_for(Base, "before_insert", propagate=True)
@event.listens_for(Base, "before_update", propagate=True)
def _fit_strings(_mapper, _connection, target) -> None:
    """
    Text longer than its column (String(n)) is cut to fit, with a warning. SQLite ignores the length, PostgreSQL
    refuses the whole row: without this, an unusually long job title written by the LLM would work on a laptop
    and fail in production. Now both databases store the same thing.
    """
    for column in target.__table__.columns:
        length = getattr(column.type, "length", None)
        if (not length or not isinstance(column.type, String) or isinstance(column.type, Enum)
                or column.key not in target.__dict__):
            continue
        value = target.__dict__[column.key]
        if isinstance(value, str) and len(value) > length:
            logger.warning("%s.%s: %d characters cut to the column's %d", target.__table__.name, column.key,
                           len(value), length)
            setattr(target, column.key, value[:length])
