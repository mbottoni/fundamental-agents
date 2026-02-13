import json
from typing import Any, Optional

from sqlalchemy.orm import Session

from ..core.config import logger
from ..models.report import Report


def create_report(
    db: Session,
    content: str,
    job_id: int,
    chart_data: Optional[dict[str, Any]] = None,
) -> Report:
    """Create a new report linked to an analysis job."""
    db_report = Report(
        content=content,
        job_id=job_id,
        chart_data=json.dumps(chart_data) if chart_data else None,
    )
    db.add(db_report)
    db.commit()
    db.refresh(db_report)
    logger.info("Created report %d for job %d (chart_data=%s)", db_report.id, job_id, "yes" if chart_data else "no")
    return db_report


def get_report(db: Session, report_id: int) -> Optional[Report]:
    """Retrieve a report by its ID."""
    return db.query(Report).filter(Report.id == report_id).first()


def get_report_by_job_id(db: Session, job_id: int) -> Optional[Report]:
    """Retrieve a report by its linked job ID."""
    return db.query(Report).filter(Report.job_id == job_id).first()
