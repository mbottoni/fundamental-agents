from sqlalchemy import Column, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import relationship

from ..db.base_class import Base, TableNameMixin, TimestampMixin


class WatchlistItem(Base, TableNameMixin, TimestampMixin):
    """A stock ticker saved to a user's watchlist."""

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    ticker = Column(String(10), nullable=False)
    notes = Column(String(500), nullable=True)

    owner = relationship("User", back_populates="watchlist_items")

    __table_args__ = (
        UniqueConstraint("user_id", "ticker", name="uq_user_ticker"),
    )

    def __repr__(self) -> str:
        return f"<WatchlistItem(id={self.id}, user_id={self.user_id}, ticker={self.ticker})>"
