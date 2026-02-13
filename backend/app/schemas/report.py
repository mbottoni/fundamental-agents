from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, field_validator
import json


class ReportBase(BaseModel):
    content: Optional[str] = None


class Report(ReportBase):
    id: int
    job_id: int
    chart_data: Optional[Any] = None
    created_at: datetime

    model_config = {"from_attributes": True}

    @field_validator("chart_data", mode="before")
    @classmethod
    def parse_chart_data(cls, v: Any) -> Any:
        """Deserialize JSON string from DB into a dict."""
        if isinstance(v, str):
            try:
                return json.loads(v)
            except (json.JSONDecodeError, TypeError):
                return None
        return v
