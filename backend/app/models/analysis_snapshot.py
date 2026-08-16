from sqlalchemy import Column, Float, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from ..db.base_class import Base, TimestampMixin


class AnalysisSnapshot(Base, TimestampMixin):
    """
    What the model concluded about a ticker, and at what price, at one moment.

    The report itself is a document; this is the small structured record needed
    to answer "how has this changed since last time?" and "were the past calls
    any good?". Neither question can be answered retroactively, which is why
    the row is written at analysis time rather than derived later.
    """

    __tablename__ = "analysissnapshots"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    job_id = Column(Integer, ForeignKey("analysisjobs.id"), unique=True, nullable=False)
    ticker = Column(String, nullable=False, index=True)

    # The call and the reasoning behind it.
    recommendation = Column(String, nullable=True)
    composite_score = Column(Float, nullable=True)
    confidence = Column(Integer, nullable=True)

    # The market's view at the same moment, so later performance is measurable.
    price = Column(Float, nullable=True)
    dcf_value = Column(Float, nullable=True)
    risk_rating = Column(String, nullable=True)

    owner = relationship("User")
    job = relationship("AnalysisJob")

    def __repr__(self) -> str:
        return (
            f"<AnalysisSnapshot(ticker={self.ticker}, "
            f"recommendation={self.recommendation}, price={self.price})>"
        )
