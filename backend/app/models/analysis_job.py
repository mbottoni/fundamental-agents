from typing import Optional

from sqlalchemy import Column, DateTime, Integer, String, Text, ForeignKey
from sqlalchemy.orm import relationship

from ..db.base_class import Base, TimestampMixin

# Statuses a job can still move on from; anything else is terminal.
IN_PROGRESS_STATUSES = ("pending", "gathering_data", "analyzing", "generating_report")

# Waiting to be picked up by a worker. Separated from the statuses above because
# a pending job needs no rescue when a worker dies — it was never claimed.
QUEUED_STATUS = "pending"

# Claimed and being worked on. A job in one of these holds a lease; if its
# worker dies the lease expires and another worker takes it over.
RUNNING_STATUSES = ("gathering_data", "analyzing", "generating_report")


class AnalysisJob(Base, TimestampMixin):
    __tablename__ = "analysisjobs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    ticker = Column(String, index=True, nullable=False)
    status = Column(String, default="pending", nullable=False)
    # Why a job failed, in language the user can act on.
    error_message = Column(Text, nullable=True)

    # ── Queue bookkeeping ─────────────────────────────────────
    #
    # The job table doubles as the work queue. A worker claims a row, holds a
    # lease on it by refreshing `locked_at`, and releases it on success or
    # failure. A lease that stops being refreshed — because the worker was
    # killed mid-deploy — expires, and the job is picked up again rather than
    # being abandoned.
    attempts = Column(Integer, default=0, nullable=False, server_default="0")
    locked_at = Column(DateTime(timezone=True), nullable=True, index=True)
    locked_by = Column(String, nullable=True)

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
