from sqlalchemy.orm import Session
from ..models.report import Report

def create_report(db: Session, content: str, job_id: int):
    db_report = Report(content=content, job_id=job_id)
    db.add(db_report)
    db.commit()
    db.refresh(db_report)
    return db_report

def get_report(db: Session, report_id: int):
    return db.query(Report).filter(Report.id == report_id).first() 