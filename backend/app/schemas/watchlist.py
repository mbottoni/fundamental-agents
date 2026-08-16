from datetime import datetime
from typing import Optional

from pydantic import BaseModel, field_validator


class WatchlistItemBase(BaseModel):
    ticker: str
    notes: Optional[str] = None
    target_price: Optional[float] = None
    target_direction: Optional[str] = None

    @field_validator("target_direction")
    @classmethod
    def direction_must_be_known(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        v = v.strip().lower()
        if v not in ("above", "below"):
            raise ValueError("target_direction must be 'above' or 'below'.")
        return v

    @field_validator("target_price")
    @classmethod
    def target_must_be_positive(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and v <= 0:
            raise ValueError("target_price must be greater than zero.")
        return v

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
    target_price: Optional[float] = None
    target_direction: Optional[str] = None


class WatchlistItem(WatchlistItemBase):
    id: int
    user_id: int
    created_at: datetime

    model_config = {"from_attributes": True}
