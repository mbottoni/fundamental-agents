from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship

from ..db.base_class import Base

class User(Base):
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    stripe_customer_id = Column(String, unique=True, nullable=True)
    subscription_status = Column(String, default="free")

    analysis_jobs = relationship("AnalysisJob", back_populates="owner") 