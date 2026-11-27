"""
What /healthz reports, and the worker heartbeat behind one of its checks.

The deploy gate, the container health check and the uptime check all read this
endpoint, so "ok" has to mean the site can do its job: the database answers,
its schema is the one this code expects, and something is there to run the
analyses people queue. It makes no provider call: it is polled every few
seconds and the market-data plan allows 250 requests a day.
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from sqlalchemy import func, text
from sqlalchemy.orm import Session

from ..core.config import logger, settings
from ..db.migrate import schema_state
from ..models.worker_heartbeat import WorkerHeartbeat

# Heartbeat rows from workers that no longer exist (every container restart is
# a new worker id) are removed once they are this old.
HEARTBEAT_RETENTION = timedelta(days=1)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(value: datetime) -> datetime:
    # SQLite hands back naive datetimes even from a timezone-aware column.
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


def record_heartbeat(db: Session, worker_id: str) -> None:
    """Note that a worker is alive, and forget workers long gone."""
    now = _now()
    db.merge(WorkerHeartbeat(worker_id=worker_id, last_seen_at=now))
    db.query(WorkerHeartbeat).filter(
        WorkerHeartbeat.last_seen_at < now - HEARTBEAT_RETENTION
    ).delete(synchronize_session=False)
    db.commit()


def newest_heartbeat_age(db: Session) -> Optional[float]:
    """Seconds since any worker was last seen, or None if none ever was."""
    newest = db.query(func.max(WorkerHeartbeat.last_seen_at)).scalar()
    if newest is None:
        return None
    return (_now() - _aware(newest)).total_seconds()


def _worker_state(db: Session, inline_thread: Any) -> str:
    """
    ``inline``   the worker runs inside this process (local development)
    ``ok``       a standalone worker was seen recently
    ``stale``    one was seen, but not recently enough
    ``missing``  none has ever reported
    ``stopped``  the inline worker's thread has died
    """
    if settings.ANALYSIS_WORKER_INLINE:
        if inline_thread is not None and not inline_thread.is_alive():
            return "stopped"
        return "inline"
    age = newest_heartbeat_age(db)
    if age is None:
        return "missing"
    return "ok" if age <= settings.WORKER_HEARTBEAT_STALE_SECONDS else "stale"


def check(db: Session, inline_thread: Any = None) -> dict[str, Any]:
    """
    The health report. Never raises: a probe that errors tells the reader
    less than one that says what is wrong.
    """
    report: dict[str, Any] = {
        "status": "degraded",
        "database": False,
        "migrations": "unknown",
        "worker": "unknown",
        "version": settings.APP_VERSION,
    }
    try:
        db.execute(text("SELECT 1"))
        report["database"] = True
        report["migrations"] = schema_state(db.get_bind())
        # A database that is behind may not have the heartbeat table yet.
        if report["migrations"] != "behind":
            report["worker"] = _worker_state(db, inline_thread)
    except Exception as e:  # noqa: BLE001 - report it, do not raise it
        logger.error("Health check failed: %s", e)
        db.rollback()

    healthy = (
        report["database"]
        # "ahead" is a rollback: an older image on a newer schema. It runs.
        and report["migrations"] in ("current", "ahead")
        and report["worker"] in ("inline", "ok")
    )
    report["status"] = "ok" if healthy else "degraded"
    return report
