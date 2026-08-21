import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app import crud, models, schemas
from app.agents.orchestrator import Orchestrator
from app.api.deps import get_current_user
from app.core.config import settings
from app.core.db import get_db, get_standalone_session

logger = logging.getLogger("stock_analyzer.api.analysis")

router = APIRouter()


def run_analysis_background(job_id: int, ticker: str) -> None:
    """
    Background task that runs the full analysis pipeline.

    Uses a standalone DB session since background tasks run outside the
    request lifecycle.
    """
    db = get_standalone_session()
    try:
        job = crud.get_analysis_job(db, job_id)
        if not job:
            logger.error("Background task: job %d not found", job_id)
            return

        orchestrator = Orchestrator(ticker)
        orchestrator.run_analysis(db=db, job=job)
    except Exception as e:
        logger.error("Background task failed for job %d: %s", job_id, e, exc_info=True)
        try:
            crud.update_job_status(
                db,
                job_id=job_id,
                status="failed",
                error_message=(
                    f"The analysis of {ticker} could not be started. Please try again "
                    "in a moment."
                ),
            )
        except Exception:
            logger.error("Failed to update job %d status to 'failed'", job_id)
    finally:
        db.close()


def _reuse_existing_analysis(
    db: Session, source: models.AnalysisJob, user_id: int, ticker: str
) -> models.AnalysisJob:
    """
    Give the user their own completed job backed by an existing report.

    The report is copied rather than shared: `Report.job_id` is unique and every
    ownership check keys off the job's owner, so a shared row would either break
    the constraint or hand one user a job they do not own.
    """
    job = crud.create_analysis_job(
        db, job=schemas.AnalysisJobCreate(ticker=ticker), user_id=user_id
    )
    crud.copy_report(db, source=source.report, job_id=job.id)

    # The snapshot backs the per-user history, past-call performance and
    # leaderboard views. A user with no row simply never appears in them.
    source_snapshot = crud.get_snapshot_by_job_id(db, job_id=source.id)
    if source_snapshot is not None:
        try:
            crud.copy_snapshot(db, source_snapshot, user_id=user_id, job_id=job.id)
        except Exception as e:  # noqa: BLE001 - never fail a finished report
            logger.error("Could not copy snapshot for job %d: %s", job.id, e)
    else:
        # Jobs predating snapshots, or one whose snapshot insert failed.
        logger.info("Source job %d has no snapshot to copy", source.id)

    crud.update_job_status(db, job_id=job.id, status="complete")
    db.refresh(job)
    return job


@router.post("/", response_model=schemas.AnalysisJob, status_code=status.HTTP_202_ACCEPTED)
def start_analysis(
    request: schemas.AnalysisJobCreate,
    background_tasks: BackgroundTasks,
    force: bool = Query(
        False, description="Re-run even if a recent analysis of this ticker exists"
    ),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    Start a new stock analysis job for the given ticker.

    A recent completed analysis of the same ticker is reused unless `force` is
    set: the underlying filings are quarterly, so re-running minutes later
    spends eleven provider requests to rebuild the same report. Free-tier users
    are limited to a daily cap.

    Reuse happens at two levels. The user's own recent analysis is returned
    as-is — they already have that report. Failing that, any user's recent
    analysis of the ticker is copied into a new job for this user: nothing in a
    report depends on who asked for it, so rebuilding one costs eleven provider
    requests to produce an identical document.
    """
    if not force:
        recent = crud.get_recent_complete_job(
            db,
            user_id=current_user.id,
            ticker=request.ticker,
            within_hours=settings.ANALYSIS_REUSE_HOURS,
        )
        if recent is not None:
            logger.info(
                "Reusing analysis job %d for %s (user %d)",
                recent.id, request.ticker, current_user.id,
            )
            return recent

    # Enforce free-tier daily limit.
    #
    # This deliberately also covers the shared-reuse path below. That path
    # spends no provider quota, but exempting it would quietly turn the free
    # tier into unlimited analyses for any already-popular ticker — a pricing
    # change, not a caching one.
    if current_user.subscription_status != "active":
        today_count = crud.count_user_analyses_today(db, current_user.id)
        if today_count >= settings.FREE_TIER_DAILY_ANALYSES:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=(
                    f"Free plan limit reached ({settings.FREE_TIER_DAILY_ANALYSES} analyses/day). "
                    "Upgrade to Premium for unlimited analyses."
                ),
            )

    if not force:
        shared = crud.get_reusable_job(
            db,
            ticker=request.ticker,
            within_hours=settings.ANALYSIS_REUSE_HOURS,
        )
        if shared is not None:
            job = _reuse_existing_analysis(
                db, source=shared, user_id=current_user.id, ticker=request.ticker
            )
            logger.info(
                "Copied analysis job %d to job %d for %s (user %d) — no provider calls",
                shared.id, job.id, request.ticker, current_user.id,
            )
            return job

    job = crud.create_analysis_job(db=db, job=request, user_id=current_user.id)
    background_tasks.add_task(run_analysis_background, job.id, request.ticker)
    logger.info("Analysis job %d queued for %s by user %d", job.id, request.ticker, current_user.id)
    return job


@router.get("/{job_id}", response_model=schemas.AnalysisJob)
def get_job_status(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Get the current status of an analysis job."""
    job = crud.get_analysis_job(db, job_id=job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.")
    if job.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to access this job.")
    return job


@router.get("/", response_model=list[schemas.AnalysisJob])
def list_user_jobs(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """List all analysis jobs for the current user."""
    return crud.get_user_jobs(db, user_id=current_user.id)
