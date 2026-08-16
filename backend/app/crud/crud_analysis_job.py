from typing import Optional

from sqlalchemy.orm import Session

from ..core.config import logger
from ..models.analysis_job import IN_PROGRESS_STATUSES, AnalysisJob
from ..schemas.analysis_job import AnalysisJobCreate


def create_analysis_job(
    db: Session, job: AnalysisJobCreate, user_id: int
) -> AnalysisJob:
    """Create a new analysis job for a user."""
    db_job = AnalysisJob(ticker=job.ticker, user_id=user_id)
    db.add(db_job)
    db.commit()
    db.refresh(db_job)
    logger.info("Created analysis job %d for ticker %s (user %d)", db_job.id, job.ticker, user_id)
    return db_job


def get_analysis_job(db: Session, job_id: int) -> Optional[AnalysisJob]:
    """Retrieve an analysis job by its ID."""
    return db.query(AnalysisJob).filter(AnalysisJob.id == job_id).first()


def get_user_jobs(db: Session, user_id: int) -> list[AnalysisJob]:
    """Retrieve all analysis jobs for a user, ordered by most recent first."""
    return (
        db.query(AnalysisJob)
        .filter(AnalysisJob.user_id == user_id)
        .order_by(AnalysisJob.created_at.desc())
        .all()
    )


def update_job_status(
    db: Session, job_id: int, status: str, error_message: Optional[str] = None
) -> Optional[AnalysisJob]:
    """
    Update the status of an analysis job.

    A failure message is recorded alongside the status so the user gets a
    reason rather than a bare "failed"; advancing to any other status clears
    any message left by an earlier attempt.
    """
    db_job = get_analysis_job(db, job_id)
    if not db_job:
        logger.warning("Cannot update status: job %d not found", job_id)
        return None
    db_job.status = status
    db_job.error_message = error_message
    db.commit()
    db.refresh(db_job)
    logger.info("Job %d status updated to '%s'", job_id, status)
    return db_job


def fail_stale_jobs(db: Session, message: str) -> int:
    """
    Mark jobs that were still running as failed.

    Analyses run as in-process background tasks, so a restart leaves them
    stranded in a non-terminal status and the frontend polls them forever.
    """
    stale = (
        db.query(AnalysisJob)
        .filter(AnalysisJob.status.in_(IN_PROGRESS_STATUSES))
        .all()
    )
    for job in stale:
        job.status = "failed"
        job.error_message = message
    if stale:
        db.commit()
        logger.warning("Marked %d interrupted job(s) as failed", len(stale))
    return len(stale)
