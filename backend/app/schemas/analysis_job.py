import re
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, field_validator


class AnalysisJobBase(BaseModel):
    ticker: str

    @field_validator("ticker")
    @classmethod
    def validate_ticker(cls, v: str) -> str:
        # Allows class shares and exchange suffixes (BRK.B, BF-B, RY.TO) as well
        # as the six-character symbols a letters-only rule rejected.
        v = v.strip().upper()
        if not re.match(r"^[A-Z0-9]{1,6}([.\-][A-Z0-9]{1,4})?$", v):
            raise ValueError(
                "Ticker must be 1 to 6 characters, optionally followed by a class or "
                "exchange suffix (e.g. AAPL, BRK.B, RY.TO)."
            )
        return v


class AnalysisJobCreate(AnalysisJobBase):
    pass


class AnalysisJob(AnalysisJobBase):
    id: int
    user_id: int
    status: str
    error_message: Optional[str] = None
    report_id: Optional[int] = None
    created_at: datetime

    model_config = {"from_attributes": True}
