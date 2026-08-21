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


def copy_report(db: Session, source: Report, job_id: int) -> Report:
    """
    Attach a copy of an existing report to another job.

    `chart_data` is carried across as the stored string rather than decoded and
    re-encoded: it is already the exact payload the frontend expects, and a
    round trip through json only creates opportunities to change it.

    Reports are copied rather than shared because `Report.job_id` is unique and
    jobs are owner-scoped — the ownership checks in endpoints_reports stay
    exactly as they are.
    """
    db_report = Report(
        content=source.content,
        job_id=job_id,
        chart_data=source.chart_data,
    )
    db.add(db_report)
    db.commit()
    db.refresh(db_report)
    logger.info("Copied report %d to job %d", source.id, job_id)
    return db_report


def get_report(db: Session, report_id: int) -> Optional[Report]:
    """Retrieve a report by its ID."""
    return db.query(Report).filter(Report.id == report_id).first()


def get_report_by_job_id(db: Session, job_id: int) -> Optional[Report]:
    """Retrieve a report by its linked job ID."""
    return db.query(Report).filter(Report.job_id == job_id).first()
