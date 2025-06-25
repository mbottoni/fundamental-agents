import datetime
from pydantic import BaseModel
from typing import Optional

class ReportBase(BaseModel):
    content: Optional[str] = None

class Report(ReportBase):
    id: int
    created_at: datetime.datetime

    class Config:
        from_attributes = True 