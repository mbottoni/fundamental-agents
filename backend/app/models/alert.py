from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from ..db.base_class import Base, TimestampMixin

# What triggered an alert. Kept as plain strings so adding a kind needs no
# migration.
KIND_PRICE_TARGET = "price_target"
KIND_RECOMMENDATION_CHANGE = "recommendation_change"
KIND_SCORE_MOVE = "score_move"


class Alert(Base, TimestampMixin):
    """
    Something on a user's watchlist that is worth their attention.

    The watchlist stored tickers and did nothing with them. An alert is the
    smallest useful thing it can do: notice when a price target is reached or
    when the model changes its mind, without the user re-running analyses by
    hand to find out.
    """

    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    ticker = Column(String, nullable=False, index=True)
    kind = Column(String, nullable=False)
    message = Column(Text, nullable=False)
    triggered_value = Column(Float, nullable=True)
    read_at = Column(DateTime(timezone=True), nullable=True)

    owner = relationship("User")

    def __repr__(self) -> str:
        return f"<Alert(ticker={self.ticker}, kind={self.kind})>"
