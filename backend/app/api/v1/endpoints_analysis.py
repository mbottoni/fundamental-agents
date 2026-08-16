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

    A recent completed analysis of the same ticker is returned as-is unless
    `force` is set: the underlying filings are quarterly, so re-running minutes
    later spends eleven provider requests and one of the user's daily analyses
    to rebuild the same report. Free-tier users are limited to a daily cap.
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

    # Enforce free-tier daily limit
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
