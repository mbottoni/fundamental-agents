from sqlalchemy import Column, Integer, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from ..db.base_class import Base

class Report(Base):
    id = Column(Integer, primary_key=True, index=True)
    content = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    job_id = Column(Integer, ForeignKey("analysisjobs.id"), unique=True)

    job = relationship("AnalysisJob", back_populates="report") 