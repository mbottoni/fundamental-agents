from sqlalchemy import Column, DateTime
from sqlalchemy.orm import declarative_base, declared_attr
from sqlalchemy.sql import func

Base = declarative_base()


class TimestampMixin:
    """Mixin that adds created_at and updated_at columns to any model."""

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class TableNameMixin:
    """Mixin that auto-generates __tablename__ as lowercase plural."""

    @declared_attr
    def __tablename__(cls) -> str:
        return cls.__name__.lower() + "s"
