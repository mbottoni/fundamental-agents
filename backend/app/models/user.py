from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship

from ..db.base_class import Base, TableNameMixin, TimestampMixin


class User(Base, TableNameMixin, TimestampMixin):
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    stripe_customer_id = Column(String, unique=True, nullable=True)
    subscription_status = Column(String, default="free", nullable=False)

    analysis_jobs = relationship(
        "AnalysisJob",
        back_populates="owner",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<User(id={self.id}, email={self.email})>"
