from sqlalchemy import Column, DateTime
from sqlalchemy.orm import as_declarative, declared_attr
from sqlalchemy.sql import func


@as_declarative()
class Base:
    id: int
    __name__: str

    @declared_attr
    def __tablename__(cls) -> str:
        """Generate __tablename__ automatically as lowercase plural."""
        return cls.__name__.lower() + "s"

    # Common timestamp columns for all models
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
