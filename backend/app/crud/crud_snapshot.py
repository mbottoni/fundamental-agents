"""Reads and writes for analysis snapshots."""

from typing import Any, Optional

from sqlalchemy.orm import Session

from ..core.config import logger
from ..models.analysis_snapshot import AnalysisSnapshot


def create_snapshot(
    db: Session,
    *,
    user_id: int,
    job_id: int,
    ticker: str,
    assessment: dict[str, Any],
    price: Optional[float],
    dcf_value: Optional[float],
    risk_rating: Optional[str],
) -> AnalysisSnapshot:
    """Record the conclusion and the price it was reached at."""
    snapshot = AnalysisSnapshot(
        user_id=user_id,
        job_id=job_id,
        ticker=ticker.upper(),
        recommendation=assessment.get("recommendation"),
        composite_score=assessment.get("composite_score"),
        confidence=assessment.get("confidence"),
        price=price,
        dcf_value=dcf_value,
        risk_rating=risk_rating,
    )
    db.add(snapshot)
    db.commit()
    db.refresh(snapshot)
    logger.info(
        "Recorded snapshot for %s: %s at %s",
        snapshot.ticker, snapshot.recommendation, snapshot.price,
    )
    return snapshot


def copy_snapshot(
    db: Session, source: AnalysisSnapshot, *, user_id: int, job_id: int
) -> AnalysisSnapshot:
    """
    Record the same conclusion for another user's job.

    A reused analysis still needs its own snapshot row: the history view, the
    past-call performance figures and the leaderboard are all per-user, and a
    user who never gets a row simply does not appear in them.

    The values are copied from the original rather than recomputed so both
    users' histories agree about what was concluded and at what price.
    """
    snapshot = AnalysisSnapshot(
        user_id=user_id,
        job_id=job_id,
        ticker=source.ticker,
        recommendation=source.recommendation,
        composite_score=source.composite_score,
        confidence=source.confidence,
        price=source.price,
        dcf_value=source.dcf_value,
        risk_rating=source.risk_rating,
    )
    db.add(snapshot)
    db.commit()
    db.refresh(snapshot)
    logger.info(
        "Copied snapshot for %s (%s) to job %d",
        snapshot.ticker, snapshot.recommendation, job_id,
    )
    return snapshot


def get_snapshot_by_job_id(db: Session, job_id: int) -> Optional[AnalysisSnapshot]:
    """The snapshot written for a job, if one was recorded."""
    return db.query(AnalysisSnapshot).filter(AnalysisSnapshot.job_id == job_id).first()


def get_ticker_history(
    db: Session, user_id: int, ticker: str, limit: int = 50
) -> list[AnalysisSnapshot]:
    """A user's snapshots for one ticker, oldest first so a chart reads left to right."""
    rows = (
        db.query(AnalysisSnapshot)
        .filter(AnalysisSnapshot.user_id == user_id, AnalysisSnapshot.ticker == ticker.upper())
        .order_by(AnalysisSnapshot.created_at.desc())
        .limit(limit)
        .all()
    )
    return list(reversed(rows))


def get_user_snapshots(db: Session, user_id: int, limit: int = 200) -> list[AnalysisSnapshot]:
    """Every snapshot for a user, newest first."""
    return (
        db.query(AnalysisSnapshot)
        .filter(AnalysisSnapshot.user_id == user_id)
        .order_by(AnalysisSnapshot.created_at.desc())
        .limit(limit)
        .all()
    )


def get_latest_snapshot(db: Session, user_id: int, ticker: str) -> Optional[AnalysisSnapshot]:
    return (
        db.query(AnalysisSnapshot)
        .filter(AnalysisSnapshot.user_id == user_id, AnalysisSnapshot.ticker == ticker.upper())
        .order_by(AnalysisSnapshot.created_at.desc())
        .first()
    )
