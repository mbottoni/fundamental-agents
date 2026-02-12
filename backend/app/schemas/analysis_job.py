import re
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, field_validator


class AnalysisJobBase(BaseModel):
    ticker: str

    @field_validator("ticker")
    @classmethod
    def validate_ticker(cls, v: str) -> str:
        v = v.strip().upper()
        if not re.match(r"^[A-Z]{1,5}$", v):
            raise ValueError(
                "Ticker must be 1 to 5 uppercase letters (e.g. AAPL, MSFT)."
            )
        return v


class AnalysisJobCreate(AnalysisJobBase):
    pass


class AnalysisJob(AnalysisJobBase):
    id: int
    user_id: int
    status: str
    report_id: Optional[int] = None
    created_at: datetime

    model_config = {"from_attributes": True}
