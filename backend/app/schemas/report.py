from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, field_validator
import json

from .chart_data import ChartData


class ReportBase(BaseModel):
    content: Optional[str] = None


class Report(ReportBase):
    id: int
    job_id: int
    # Typed rather than `Any` so the shape reaches the OpenAPI document and the
    # frontend can generate its types from it instead of retyping them by hand.
    chart_data: Optional[ChartData] = None
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
