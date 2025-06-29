from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import crud, schemas, models
from app.api import deps

router = APIRouter()

@router.get("/{report_id}", response_model=schemas.Report)
def get_report(
    report_id: int,
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user),
):
    report = crud.get_report(db, report_id=report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    
    if not report.job or report.job.user_id != current_user.id:
         raise HTTPException(status_code=403, detail="Not authorized to access this report")

    return report 