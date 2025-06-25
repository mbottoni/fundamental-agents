from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app import crud, models, schemas
from app.agents.orchestrator import Orchestrator
from app.api import deps

router = APIRouter()

class TickerRequest(BaseModel):
    ticker: str

def run_analysis_background(db: Session, orchestrator: Orchestrator, job: models.AnalysisJob):
    # Re-create a db session for the background task
    db_session = Session(bind=db.get_bind())
    orchestrator.run_analysis(db=db_session, job=job)
    db_session.close()

@router.post("/", response_model=schemas.AnalysisJob)
def run_analysis(
    request: TickerRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user),
):
    """
    Kicks off a new stock analysis job for the given ticker.
    """
    job = crud.create_analysis_job(db=db, ticker=request.ticker, user_id=current_user.id)
    orchestrator = Orchestrator(ticker=request.ticker)
    background_tasks.add_task(run_analysis_background, db, orchestrator, job)
    return job

@router.get("/{job_id}", response_model=schemas.AnalysisJob)
def get_job_status(
    job_id: int,
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user),
):
    job = crud.get_analysis_job(db, job_id=job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to access this job")
    return job

@router.get("/", response_model=list[schemas.AnalysisJob])
def get_user_jobs(
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user),
):
    return crud.get_user_jobs(db, user_id=current_user.id)
