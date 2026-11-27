"""
Tests for the analysis work queue.

Analyses used to run as FastAPI BackgroundTasks in the web process: a deploy
destroyed anything in flight, one transient provider error killed a job
outright, and nothing bounded how many ran at once.

The lease is the mechanism that fixes the first of those, so most of what is
tested here is lease behaviour: who may claim a job, what happens when the
worker holding it dies, and when a failure is worth retrying.
"""

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app import crud, models
from app.core.config import settings
from app.schemas.analysis_job import AnalysisJobCreate
from app.services import job_queue


@pytest.fixture
def user(client: TestClient, db: Session) -> models.User:
    client.post(
        "/api/v1/auth/register",
        json={"email": "queue@example.com", "password": "TestPass123"},
    )
    return crud.get_user_by_email(db, email="queue@example.com")


def _queue(db: Session, user_id: int, ticker: str = "AAPL") -> models.AnalysisJob:
    return crud.create_analysis_job(db, job=AnalysisJobCreate(ticker=ticker), user_id=user_id)


def _age_lease(db: Session, job: models.AnalysisJob, seconds: int) -> None:
    """Backdate a lease so it looks like the holding worker went quiet."""
    job.locked_at = datetime.now(timezone.utc) - timedelta(seconds=seconds)
    db.commit()


class TestClaiming:
    def test_a_queued_job_can_be_claimed(self, db: Session, user):
        job = _queue(db, user.id)

        claimed = job_queue.claim_next_job(db, worker_id="w1")

        assert claimed is not None
        assert claimed.id == job.id
        assert claimed.locked_by == "w1"
        assert claimed.locked_at is not None
        assert claimed.attempts == 1
        assert claimed.status == "gathering_data"

    def test_an_empty_queue_returns_nothing(self, db: Session, user):
        assert job_queue.claim_next_job(db, worker_id="w1") is None

    def test_a_claimed_job_is_not_handed_out_twice(self, db: Session, user):
        """The core guarantee: two workers must not run the same analysis."""
        _queue(db, user.id)

        first = job_queue.claim_next_job(db, worker_id="w1")
        second = job_queue.claim_next_job(db, worker_id="w2")

        assert first is not None
        assert second is None

    def test_jobs_are_claimed_oldest_first(self, db: Session, user):
        older = _queue(db, user.id, "AAPL")
        older.created_at = datetime.now(timezone.utc) - timedelta(hours=1)
        db.commit()
        _queue(db, user.id, "MSFT")

        claimed = job_queue.claim_next_job(db, worker_id="w1")

        assert claimed.id == older.id

    def test_a_finished_job_is_never_claimed(self, db: Session, user):
        job = _queue(db, user.id)
        crud.update_job_status(db, job_id=job.id, status="complete")

        assert job_queue.claim_next_job(db, worker_id="w1") is None


class TestLeaseExpiry:
    def test_a_job_whose_worker_died_is_reclaimed(self, db: Session, user):
        """
        The deploy case. The old behaviour marked this failed and told the user
        to run it again, spending another of their daily analyses.
        """
        job = _queue(db, user.id)
        job_queue.claim_next_job(db, worker_id="dead-worker")
        _age_lease(db, job, settings.ANALYSIS_LEASE_SECONDS * 2)

        reclaimed = job_queue.reclaim_expired_jobs(db)

        db.refresh(job)
        assert reclaimed == 1
        assert job.status == "pending"
        assert job.locked_at is None
        assert job.locked_by is None

    def test_a_reclaimed_job_can_be_run_by_another_worker(self, db: Session, user):
        job = _queue(db, user.id)
        job_queue.claim_next_job(db, worker_id="dead-worker")
        _age_lease(db, job, settings.ANALYSIS_LEASE_SECONDS * 2)
        job_queue.reclaim_expired_jobs(db)

        claimed = job_queue.claim_next_job(db, worker_id="live-worker")

        assert claimed is not None
        assert claimed.locked_by == "live-worker"
        assert claimed.attempts == 2, "the retry counts as an attempt"

    def test_a_live_lease_is_left_alone(self, db: Session, user):
        """A healthy worker midway through a long analysis must not be robbed."""
        job = _queue(db, user.id)
        job_queue.claim_next_job(db, worker_id="busy-worker")

        assert job_queue.reclaim_expired_jobs(db) == 0
        db.refresh(job)
        assert job.locked_by == "busy-worker"

    def test_a_heartbeat_keeps_a_long_job(self, db: Session, user):
        """Without this an analysis outliving its lease would be run twice."""
        job = _queue(db, user.id)
        job_queue.claim_next_job(db, worker_id="w1")
        _age_lease(db, job, settings.ANALYSIS_LEASE_SECONDS * 2)

        job_queue.heartbeat(db, job.id)

        assert job_queue.reclaim_expired_jobs(db) == 0

    def test_a_stranded_job_out_of_attempts_is_failed_not_looped(
        self, db: Session, user
    ):
        job = _queue(db, user.id)
        job_queue.claim_next_job(db, worker_id="w1")
        job.attempts = settings.ANALYSIS_MAX_ATTEMPTS
        db.commit()
        _age_lease(db, job, settings.ANALYSIS_LEASE_SECONDS * 2)

        job_queue.reclaim_expired_jobs(db)

        db.refresh(job)
        assert job.status == "failed"
        assert "attempts" in (job.error_message or "")


class TestRetries:
    def test_a_failure_is_retried(self, db: Session, user):
        job = _queue(db, user.id)
        job_queue.claim_next_job(db, worker_id="w1")

        retried = job_queue.requeue_or_fail(db, job.id, "provider timed out")

        db.refresh(job)
        assert retried is True
        assert job.status == "pending"
        assert job.locked_at is None

    def test_a_pending_retry_shows_no_error_to_the_user(self, db: Session, user):
        """Surfacing a failure that is about to be undone would be misleading."""
        job = _queue(db, user.id)
        job_queue.claim_next_job(db, worker_id="w1")

        job_queue.requeue_or_fail(db, job.id, "provider timed out")

        db.refresh(job)
        assert job.error_message is None

    def test_attempts_are_bounded(self, db: Session, user):
        job = _queue(db, user.id)

        for _ in range(settings.ANALYSIS_MAX_ATTEMPTS):
            assert job_queue.claim_next_job(db, worker_id="w1") is not None
            job_queue.requeue_or_fail(db, job.id, "provider timed out")

        db.refresh(job)
        assert job.status == "failed"
        assert job.error_message == "provider timed out"
        assert job_queue.claim_next_job(db, worker_id="w1") is None

    def test_release_clears_the_lease(self, db: Session, user):
        job = _queue(db, user.id)
        job_queue.claim_next_job(db, worker_id="w1")

        job_queue.release(db, job.id)

        db.refresh(job)
        assert job.locked_at is None
        assert job.locked_by is None


class TestEnqueueing:
    def test_starting_an_analysis_only_enqueues_it(
        self, client: TestClient, db: Session, auth_headers: dict
    ):
        """
        The endpoint no longer runs the pipeline in the web process, so the job
        is simply left for a worker.
        """
        resp = client.post("/api/v1/analysis/", json={"ticker": "AAPL"}, headers=auth_headers)

        assert resp.status_code == 202
        body = resp.json()
        assert body["status"] == "pending"

        job = crud.get_analysis_job(db, body["id"])
        assert job.locked_at is None, "nothing has claimed it yet"
        assert job.attempts == 0

    def test_an_enqueued_job_is_visible_to_a_worker(
        self, client: TestClient, db: Session, auth_headers: dict
    ):
        client.post("/api/v1/analysis/", json={"ticker": "AAPL"}, headers=auth_headers)

        assert job_queue.queue_depth(db) == 1
        assert job_queue.claim_next_job(db, worker_id="w1") is not None
