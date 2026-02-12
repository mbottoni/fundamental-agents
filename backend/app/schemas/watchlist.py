from datetime import datetime
from typing import Optional

from pydantic import BaseModel, field_validator


class WatchlistItemBase(BaseModel):
    ticker: str
    notes: Optional[str] = None

    @field_validator("ticker")
    @classmethod
    def ticker_must_be_valid(cls, v: str) -> str:
        v = v.strip().upper()
        if not v or len(v) > 10:
            raise ValueError("Ticker must be 1-10 characters.")
        return v


class WatchlistItemCreate(WatchlistItemBase):
    pass


class WatchlistItemUpdate(BaseModel):
    notes: Optional[str] = None


class WatchlistItem(WatchlistItemBase):
    id: int
    user_id: int
    created_at: datetime

    model_config = {"from_attributes": True}
