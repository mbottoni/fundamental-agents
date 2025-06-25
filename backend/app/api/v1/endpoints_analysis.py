from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app import crud, models, schemas
from app.agents.orchestrator import Orchestrator
from app.api import deps

router = APIRouter()

class TickerRequest(BaseModel):
    ticker: str

def run_analysis_background(db_url: str, job_id: int, ticker: str):
    db = next(deps.get_db())
    try:
        job = crud.get_analysis_job(db, job_id)
        if not job:
            return
        
        orchestrator = Orchestrator(ticker)
        orchestrator.run_analysis(db=db, job=job)
    finally:
        db.close()

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
    job_create = schemas.AnalysisJobCreate(ticker=request.ticker)
    job = crud.create_analysis_job(db=db, job=job_create, user_id=current_user.id)
    db_url = str(db.get_bind().url)
    background_tasks.add_task(run_analysis_background, db_url, job.id, request.ticker)
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
