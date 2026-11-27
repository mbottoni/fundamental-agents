"""
The analysis work queue
=======================
The `analysisjobs` table doubles as the queue. There is no Redis or broker to
run: a worker claims a row, holds a lease on it, and releases it on success or
failure.

Why this exists at all. Analyses used to run as FastAPI `BackgroundTask`s inside
the web process, which meant:

  * **A deploy destroyed in-flight work.** `_reap_interrupted_jobs` existed to
    mark everything mid-flight as failed on the next boot, and the user was told
    to run it again — spending another of their daily analyses.
  * **No retries.** One transient provider failure killed the whole job.
  * **No bound on concurrency.** Each analysis fans out around eleven provider
    requests; twenty simultaneous users meant ~220 in flight against a 250/day
    quota, and the retry-on-429 logic then amplified it.

A lease rather than a lock is what makes the first point work. A worker that is
killed mid-job stops refreshing `locked_at`; the lease expires and another
worker picks the job up where the queue left it, instead of it being abandoned.
That is why jobs are reclaimed on a timer rather than failed at startup.
"""

import logging
import os
import socket
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session

from ..core.config import settings
from ..models.analysis_job import (
    QUEUED_STATUS,
    RUNNING_STATUSES,
    AnalysisJob,
)

logger = logging.getLogger("stock_analyzer.queue")


def worker_identity() -> str:
    """A name for this worker, so a held lease can be attributed to a process."""
    return f"{socket.gethostname()}:{os.getpid()}"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _supports_skip_locked(db: Session) -> bool:
    """
    PostgreSQL can hand each worker a different row; SQLite cannot.

    Under SQLite the whole database is locked for a write anyway, so claiming is
    serialised by the engine and the weaker query is still correct — it is only
    unusable under real concurrency, which SQLite does not offer either.
    """
    return db.bind.dialect.name == "postgresql"


def claim_next_job(
    db: Session, *, worker_id: str, lease_seconds: Optional[int] = None
) -> Optional[AnalysisJob]:
    """
    Take ownership of one queued job, or return None if there is nothing to do.

    `FOR UPDATE SKIP LOCKED` is what lets several workers poll the same table
    without handing the same row to two of them: a row another transaction has
    locked is skipped rather than waited for.
    """
    lease_seconds = lease_seconds or settings.ANALYSIS_LEASE_SECONDS
    expiry = _now() - timedelta(seconds=lease_seconds)

    query = (
        db.query(AnalysisJob)
        .filter(
            AnalysisJob.status == QUEUED_STATUS,
            # Either never claimed, or claimed by a worker that has since died.
            or_(AnalysisJob.locked_at.is_(None), AnalysisJob.locked_at < expiry),
        )
        .order_by(AnalysisJob.created_at.asc())
    )
    if _supports_skip_locked(db):
        query = query.with_for_update(skip_locked=True)

    job = query.first()
    if job is None:
        return None

    job.locked_at = _now()
    job.locked_by = worker_id
    job.attempts = (job.attempts or 0) + 1
    job.status = "gathering_data"
    job.error_message = None
    db.commit()
    db.refresh(job)

    logger.info(
        "Worker %s claimed job %d (%s), attempt %d",
        worker_id, job.id, job.ticker, job.attempts,
    )
    return job


def heartbeat(db: Session, job_id: int) -> None:
    """
    Refresh a job's lease.

    Without this a long analysis would look abandoned partway through and be
    picked up a second time while the first worker is still running it.
    """
    job = db.query(AnalysisJob).filter(AnalysisJob.id == job_id).first()
    if job is None:
        return
    job.locked_at = _now()
    db.commit()


def release(db: Session, job_id: int) -> None:
    """Drop the lease on a finished job so nothing reclaims it."""
    job = db.query(AnalysisJob).filter(AnalysisJob.id == job_id).first()
    if job is None:
        return
    job.locked_at = None
    job.locked_by = None
    db.commit()


def requeue_or_fail(db: Session, job_id: int, message: str) -> bool:
    """
    Put a failed job back on the queue, unless it has used up its attempts.

    Returns True when the job will be retried. The message is only shown to the
    user once the job is genuinely finished with — a user watching a job that is
    about to be retried should not see a failure that is about to be undone.
    """
    job = db.query(AnalysisJob).filter(AnalysisJob.id == job_id).first()
    if job is None:
        return False

    if (job.attempts or 0) < settings.ANALYSIS_MAX_ATTEMPTS:
        job.status = QUEUED_STATUS
        job.locked_at = None
        job.locked_by = None
        job.error_message = None
        db.commit()
        logger.warning(
            "Job %d (%s) failed on attempt %d, requeued: %s",
            job.id, job.ticker, job.attempts, message,
        )
        return True

    job.status = "failed"
    job.error_message = message
    job.locked_at = None
    job.locked_by = None
    db.commit()
    logger.error(
        "Job %d (%s) failed permanently after %d attempt(s): %s",
        job.id, job.ticker, job.attempts, message,
    )
    return False


def reclaim_expired_jobs(db: Session, lease_seconds: Optional[int] = None) -> int:
    """
    Return jobs whose worker died to the queue.

    This replaces failing everything in flight at startup. A job interrupted by
    a restart has not lost anything that cannot be recomputed, so retrying it is
    strictly better than telling the user to run it again — and it costs them
    nothing, since the daily cap was already charged when the job was created.

    Jobs that have exhausted their attempts are failed rather than looped
    forever.
    """
    lease_seconds = lease_seconds or settings.ANALYSIS_LEASE_SECONDS
    expiry = _now() - timedelta(seconds=lease_seconds)

    stranded = (
        db.query(AnalysisJob)
        .filter(
            AnalysisJob.status.in_(RUNNING_STATUSES),
            AnalysisJob.locked_at.isnot(None),
            AnalysisJob.locked_at < expiry,
        )
        .all()
    )

    reclaimed = 0
    for job in stranded:
        if (job.attempts or 0) >= settings.ANALYSIS_MAX_ATTEMPTS:
            job.status = "failed"
            job.error_message = (
                "This analysis was interrupted and could not be completed after "
                f"{job.attempts} attempts. Please try running it again."
            )
            job.locked_at = None
            job.locked_by = None
            logger.error("Job %d exhausted its attempts while stranded", job.id)
            continue
        job.status = QUEUED_STATUS
        job.locked_at = None
        job.locked_by = None
        reclaimed += 1

    if stranded:
        db.commit()
    if reclaimed:
        logger.warning("Reclaimed %d stranded job(s) back onto the queue", reclaimed)
    return reclaimed


def queue_depth(db: Session) -> int:
    """How many jobs are waiting. Used by the health endpoint."""
    return db.query(AnalysisJob).filter(AnalysisJob.status == QUEUED_STATUS).count()
