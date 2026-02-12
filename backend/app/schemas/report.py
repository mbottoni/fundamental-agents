from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class ReportBase(BaseModel):
    content: Optional[str] = None


class Report(ReportBase):
    id: int
    job_id: int
    created_at: datetime

    model_config = {"from_attributes": True}
