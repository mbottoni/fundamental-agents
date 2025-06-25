from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship

from ..db.base_class import Base

class AnalysisJob(Base):
    __tablename__ = "analysisjobs" # Manually set because of underscore
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    ticker = Column(String, index=True)
    status = Column(String, default="pending")
    report_id = Column(Integer, ForeignKey("reports.id"), nullable=True)

    owner = relationship("User", back_populates="analysis_jobs")
    report = relationship("Report")