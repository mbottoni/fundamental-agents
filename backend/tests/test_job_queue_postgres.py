"""
The concurrency guarantee, against a real PostgreSQL.

`claim_next_job` relies on `FOR UPDATE SKIP LOCKED` so that several workers can
poll the same table without two of them running the same analysis. SQLite has
no such clause — the rest of the suite exercises the surrounding logic but
cannot exercise this, because SQLite serialises writers anyway and would pass
whether or not the clause were there.

Skipped unless TEST_POSTGRES_URL points at a database this may create tables in.
The compose stack provides one:

    TEST_POSTGRES_URL=postgresql://user:password@db:5432/stock-analyzer
"""

import os
import threading

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.db.base_class import Base
from app.models.analysis_job import AnalysisJob
from app.services import job_queue

POSTGRES_URL = os.environ.get("TEST_POSTGRES_URL")

pytestmark = pytest.mark.skipif(
    not POSTGRES_URL, reason="TEST_POSTGRES_URL is not set"
)


@pytest.fixture
def pg_sessions():
    """A clean schema on the real database, torn down afterwards."""
    import app.db.base  # noqa: F401 - registers every model

    engine = create_engine(POSTGRES_URL, pool_size=10, max_overflow=10)
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA IF EXISTS queue_test CASCADE"))
        conn.execute(text("CREATE SCHEMA queue_test"))
        conn.execute(text("SET search_path TO queue_test"))

    scoped = create_engine(
        POSTGRES_URL,
        connect_args={"options": "-csearch_path=queue_test"},
        pool_size=10,
        max_overflow=10,
    )
    Base.metadata.create_all(bind=scoped)

    yield sessionmaker(autocommit=False, autoflush=False, bind=scoped)

    scoped.dispose()
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA IF EXISTS queue_test CASCADE"))
    engine.dispose()


def _seed(Session, count: int) -> None:
    db = Session()
    try:
        db.execute(
            text(
                "INSERT INTO users (email, hashed_password, is_verified, "
                "subscription_status, created_at, updated_at) "
                "VALUES ('pg@example.com', 'x', false, 'free', now(), now())"
            )
        )
        db.commit()
        user_id = db.execute(text("SELECT id FROM users LIMIT 1")).scalar()
        for i in range(count):
            db.add(AnalysisJob(ticker=f"TCK{i}", user_id=user_id, status="pending"))
        db.commit()
    finally:
        db.close()


def test_concurrent_workers_never_claim_the_same_job(pg_sessions):
    """
    Twelve workers race for four jobs. Every job must go to exactly one worker.

    Without SKIP LOCKED the losers block on the winner's row lock and then read
    it again — which, depending on isolation level, hands the same job out
    twice or deadlocks the pollers.
    """
    Session = pg_sessions
    _seed(Session, count=4)

    claimed: list[int] = []
    lock = threading.Lock()
    start = threading.Barrier(12)

    def claim(worker_index: int) -> None:
        db = Session()
        try:
            start.wait(timeout=10)
            job = job_queue.claim_next_job(db, worker_id=f"w{worker_index}")
            if job is not None:
                with lock:
                    claimed.append(job.id)
        finally:
            db.close()

    threads = [threading.Thread(target=claim, args=(i,)) for i in range(12)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=20)

    assert len(claimed) == 4, f"expected all four jobs claimed, got {len(claimed)}"
    assert len(set(claimed)) == len(claimed), "a job was claimed by two workers"


def test_a_second_worker_finds_nothing_while_one_holds_everything(pg_sessions):
    Session = pg_sessions
    _seed(Session, count=1)

    first, second = Session(), Session()
    try:
        assert job_queue.claim_next_job(first, worker_id="w1") is not None
        assert job_queue.claim_next_job(second, worker_id="w2") is None
    finally:
        first.close()
        second.close()
