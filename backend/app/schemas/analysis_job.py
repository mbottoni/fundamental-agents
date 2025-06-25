from pydantic import BaseModel
from typing import Optional

class AnalysisJobBase(BaseModel):
    ticker: str

class AnalysisJobCreate(AnalysisJobBase):
    pass

class AnalysisJob(AnalysisJobBase):
    id: int
    user_id: int
    status: str
    report_id: Optional[int] = None

    class Config:
        from_attributes = True 