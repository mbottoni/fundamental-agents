"""
Tests for the analysis worker loop.

The pipeline itself is stubbed — what matters here is that the worker claims
work, bounds how much it runs at once, records outcomes, and survives a job
that blows up.
"""

import threading
import time

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app import crud, models
from app.core.config import settings
from app.schemas.analysis_job import AnalysisJobCreate
from app.services import job_queue
from app.worker import Worker


@pytest.fixture
def user(client: TestClient, db: Session) -> models.User:
    client.post(
        "/api/v1/auth/register",
        json={"email": "worker@example.com", "password": "TestPass123"},
    )
    return crud.get_user_by_email(db, email="worker@example.com")


@pytest.fixture
def session_factory(monkeypatch):
    """
    Point the worker at the test database.

    The worker opens its own sessions — it runs on threads outside the request
    lifecycle — so the `get_db` dependency override does not reach it.
    """
    from tests.conftest import TestSessionLocal

    monkeypatch.setattr("app.worker.SessionLocal", TestSessionLocal)
    monkeypatch.setattr("app.services.job_queue.settings", settings)
    return TestSessionLocal


def _queue(db: Session, user_id: int, ticker: str = "AAPL") -> models.AnalysisJob:
    return crud.create_analysis_job(db, job=AnalysisJobCreate(ticker=ticker), user_id=user_id)


class TestWorkerRunsJobs:
    def test_a_queued_job_is_picked_up_and_completed(
        self, db: Session, user, session_factory, monkeypatch
    ):
        ran = []

        class FakeOrchestrator:
            def __init__(self, ticker):
                self.ticker = ticker

            def run_analysis(self, db, job):
                ran.append(job.id)
                crud.update_job_status(db, job_id=job.id, status="complete")

        monkeypatch.setattr("app.worker.Orchestrator", FakeOrchestrator)
        job = _queue(db, user.id)

        from concurrent.futures import ThreadPoolExecutor

        worker = Worker(concurrency=1)
        with ThreadPoolExecutor(max_workers=1) as executor:
            assert worker.run_once(executor) is True

        time.sleep(0.5)
        db.refresh(job)
        assert ran == [job.id]
        assert job.status == "complete"
        assert job.locked_at is None, "a finished job releases its lease"

    def test_an_empty_queue_is_a_no_op(self, db: Session, user, session_factory):
        from concurrent.futures import ThreadPoolExecutor

        worker = Worker(concurrency=1)
        with ThreadPoolExecutor(max_workers=1) as executor:
            assert worker.run_once(executor) is False

    def test_concurrency_is_bounded(self, db: Session, user, session_factory, monkeypatch):
        """
        The reason the cap exists: each analysis fans out ~11 provider requests,
        so unbounded parallelism walks straight into the rate limit.
        """
        started = threading.Semaphore(0)
        hold = threading.Event()

        class BlockingOrchestrator:
            def __init__(self, ticker):
                pass

            def run_analysis(self, db, job):
                started.release()
                hold.wait(timeout=5)
                crud.update_job_status(db, job_id=job.id, status="complete")

        monkeypatch.setattr("app.worker.Orchestrator", BlockingOrchestrator)
        for ticker in ["AAPL", "MSFT", "GOOG", "AMZN"]:
            _queue(db, user.id, ticker)

        from concurrent.futures import ThreadPoolExecutor

        worker = Worker(concurrency=2)
        try:
            with ThreadPoolExecutor(max_workers=2) as executor:
                assert worker.run_once(executor) is True
                assert worker.run_once(executor) is True
                # Both slots are taken; the third claim must be refused.
                assert worker.run_once(executor) is False, "took more than its concurrency"

                assert started.acquire(timeout=5)
                assert started.acquire(timeout=5)
                hold.set()
        finally:
            hold.set()

        remaining = db.query(models.AnalysisJob).filter(
            models.AnalysisJob.status == "pending"
        ).count()
        assert remaining == 2, "the jobs it had no room for stay queued"


class TestWorkerHandlesFailure:
    def test_a_raising_job_is_requeued_rather_than_lost(
        self, db: Session, user, session_factory, monkeypatch
    ):
        class ExplodingOrchestrator:
            def __init__(self, ticker):
                pass

            def run_analysis(self, db, job):
                raise RuntimeError("provider exploded")

        monkeypatch.setattr("app.worker.Orchestrator", ExplodingOrchestrator)
        job = _queue(db, user.id)

        from concurrent.futures import ThreadPoolExecutor

        worker = Worker(concurrency=1)
        with ThreadPoolExecutor(max_workers=1) as executor:
            worker.run_once(executor)

        time.sleep(0.5)
        db.refresh(job)
        assert job.status == "pending", "a crash is retried, not abandoned"
        assert job.attempts == 1

    def test_a_job_failed_by_the_pipeline_is_retried(
        self, db: Session, user, session_factory, monkeypatch
    ):
        """
        Most pipeline failures are provider timeouts, which usually succeed on a
        second attempt.
        """
        class FailingOrchestrator:
            def __init__(self, ticker):
                pass

            def run_analysis(self, db, job):
                crud.update_job_status(
                    db, job_id=job.id, status="failed", error_message="No data.",
                )

        monkeypatch.setattr("app.worker.Orchestrator", FailingOrchestrator)
        job = _queue(db, user.id)

        from concurrent.futures import ThreadPoolExecutor

        worker = Worker(concurrency=1)
        with ThreadPoolExecutor(max_workers=1) as executor:
            worker.run_once(executor)

        time.sleep(0.5)
        db.refresh(job)
        assert job.status == "pending"

    def test_a_job_keeps_failing_and_eventually_stops(
        self, db: Session, user, session_factory, monkeypatch
    ):
        class FailingOrchestrator:
            def __init__(self, ticker):
                pass

            def run_analysis(self, db, job):
                crud.update_job_status(
                    db, job_id=job.id, status="failed", error_message="No data for XYZ.",
                )

        monkeypatch.setattr("app.worker.Orchestrator", FailingOrchestrator)
        job = _queue(db, user.id)

        from concurrent.futures import ThreadPoolExecutor

        worker = Worker(concurrency=1)
        with ThreadPoolExecutor(max_workers=1) as executor:
            for _ in range(settings.ANALYSIS_MAX_ATTEMPTS):
                worker.run_once(executor)
                time.sleep(0.4)

        db.refresh(job)
        assert job.status == "failed"
        assert job.error_message == "No data for XYZ."
        assert job.attempts == settings.ANALYSIS_MAX_ATTEMPTS
