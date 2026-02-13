from sqlalchemy import Column, Integer, Text, ForeignKey
from sqlalchemy.orm import relationship

from ..db.base_class import Base, TableNameMixin, TimestampMixin


class Report(Base, TableNameMixin, TimestampMixin):
    id = Column(Integer, primary_key=True, index=True)
    content = Column(Text, nullable=False)
    chart_data = Column(Text, nullable=True)  # JSON string with structured data for frontend charts
    job_id = Column(Integer, ForeignKey("analysisjobs.id"), unique=True, nullable=False)

    job = relationship("AnalysisJob", back_populates="report")

    def __repr__(self) -> str:
        return f"<Report(id={self.id}, job_id={self.job_id})>"
