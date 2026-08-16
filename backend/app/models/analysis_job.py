from typing import Optional

from sqlalchemy import Column, Integer, String, Text, ForeignKey
from sqlalchemy.orm import relationship

from ..db.base_class import Base, TimestampMixin

# Statuses a job can still move on from; anything else is terminal.
IN_PROGRESS_STATUSES = ("pending", "gathering_data", "analyzing", "generating_report")


class AnalysisJob(Base, TimestampMixin):
    __tablename__ = "analysisjobs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    ticker = Column(String, index=True, nullable=False)
    status = Column(String, default="pending", nullable=False)
    # Why a job failed, in language the user can act on.
    error_message = Column(Text, nullable=True)

    owner = relationship("User", back_populates="analysis_jobs")
    report = relationship(
        "Report",
        back_populates="job",
        uselist=False,
        cascade="all, delete-orphan",
    )

    @property
    def report_id(self) -> Optional[int]:
        """Return the linked report's ID, if any."""
        return self.report.id if self.report else None

    def __repr__(self) -> str:
        return f"<AnalysisJob(id={self.id}, ticker={self.ticker}, status={self.status})>"
