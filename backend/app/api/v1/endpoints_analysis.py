import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app import crud, models, schemas
from app.agents.orchestrator import Orchestrator
from app.api.deps import get_current_user
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
            crud.update_job_status(db, job_id=job_id, status="failed")
        except Exception:
            logger.error("Failed to update job %d status to 'failed'", job_id)
    finally:
        db.close()


@router.post("/", response_model=schemas.AnalysisJob, status_code=status.HTTP_202_ACCEPTED)
def start_analysis(
    request: schemas.AnalysisJobCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    Start a new stock analysis job for the given ticker.
    The analysis runs in the background and can be polled for status.
    """
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
