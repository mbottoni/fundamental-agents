"""
Alerts
======
What the watchlist has noticed since the user last looked.
"""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app import models
from app.api.deps import get_current_user
from app.core.db import get_db
from app.models.alert import Alert
from app.services.alerts import evaluate_alerts

logger = logging.getLogger("stock_analyzer.api.alerts")
router = APIRouter()


def _serialise(alert: Alert) -> dict:
    return {
        "id": alert.id,
        "ticker": alert.ticker,
        "kind": alert.kind,
        "message": alert.message,
        "triggered_value": alert.triggered_value,
        "read": alert.read_at is not None,
        "created_at": alert.created_at,
    }


@router.get("/")
def list_alerts(
    unread_only: bool = Query(False),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """The user's alerts, newest first."""
    query = db.query(Alert).filter(Alert.user_id == current_user.id)
    if unread_only:
        query = query.filter(Alert.read_at.is_(None))

    alerts = query.order_by(Alert.created_at.desc()).limit(limit).all()
    unread = (
        db.query(Alert)
        .filter(Alert.user_id == current_user.id, Alert.read_at.is_(None))
        .count()
    )
    return {"unread_count": unread, "alerts": [_serialise(a) for a in alerts]}


@router.post("/check")
def check_now(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    Evaluate this user's watchlist immediately.

    The periodic task covers everyone on a schedule; this exists so a user does
    not have to wait for the next sweep after setting a target.
    """
    created = evaluate_alerts(db, user_id=current_user.id)
    return {"created": len(created), "alerts": [_serialise(a) for a in created]}


@router.post("/{alert_id}/read")
def mark_read(
    alert_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Mark one alert as read."""
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if alert is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found.")
    if alert.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to access this alert."
        )

    if alert.read_at is None:
        alert.read_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(alert)
    return _serialise(alert)


@router.post("/read-all")
def mark_all_read(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Clear the unread badge in one call."""
    now = datetime.now(timezone.utc)
    updated = (
        db.query(Alert)
        .filter(Alert.user_id == current_user.id, Alert.read_at.is_(None))
        .update({Alert.read_at: now}, synchronize_session=False)
    )
    db.commit()
    return {"marked_read": updated}
