from sqlalchemy import Column, DateTime, String

from ..db.base_class import Base, TableNameMixin


class WorkerHeartbeat(Base, TableNameMixin):
    """
    The last time each analysis worker was seen alive.

    A job's lease only shows that a worker is busy; an idle queue looks the
    same whether a worker is waiting or none exists. Without this row the
    health check could not tell "nothing to do" from "nobody to do it", and
    the second means every analysis stays pending forever.
    """

    worker_id = Column(String, primary_key=True)
    last_seen_at = Column(DateTime(timezone=True), nullable=False)

    def __repr__(self) -> str:
        return f"<WorkerHeartbeat(worker_id={self.worker_id}, last_seen_at={self.last_seen_at})>"
