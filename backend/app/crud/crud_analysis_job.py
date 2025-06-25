from typing import Optional
from sqlalchemy.orm import Session
from ..models.analysis_job import AnalysisJob
from ..schemas.analysis_job import AnalysisJobCreate

def create_analysis_job(db: Session, job: AnalysisJobCreate, user_id: int):
    db_job = AnalysisJob(ticker=job.ticker, user_id=user_id)
    db.add(db_job)
    db.commit()
    db.refresh(db_job)
    return db_job

def get_analysis_job(db: Session, job_id: int):
    return db.query(AnalysisJob).filter(AnalysisJob.id == job_id).first()

def get_user_jobs(db: Session, user_id: int):
    return db.query(AnalysisJob).filter(AnalysisJob.user_id == user_id).all()

def update_job_status(db: Session, job_id: int, status: str):
    db_job = get_analysis_job(db, job_id)
    if db_job:
        db_job.status = status
        db.commit()
        db.refresh(db_job)
    return db_job 