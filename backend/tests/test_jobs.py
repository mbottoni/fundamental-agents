"""
Tests for analysis job lifecycle: failure reporting, quota accounting,
ticker validation, and recovery from an interrupted run.
"""

import pytest
from fastapi.testclient import TestClient

from app import crud
from app.agents.orchestrator import DataUnavailableError, Orchestrator
from app.models.analysis_job import AnalysisJob
from app.schemas.analysis_job import AnalysisJobCreate


def create_job(db, user_id: int, ticker: str = "AAPL", status: str = "pending") -> AnalysisJob:
    job = crud.create_analysis_job(db, AnalysisJobCreate(ticker=ticker), user_id=user_id)
    if status != "pending":
        crud.update_job_status(db, job_id=job.id, status=status)
    return job


class TestTickerValidation:
    @pytest.mark.parametrize("ticker", ["AAPL", "BRK.B", "BF-B", "RY.TO", "GOOGL", "ABCDEF"])
    def test_valid_tickers_are_accepted(self, client: TestClient, auth_headers, ticker):
        resp = client.post("/api/v1/analysis/", json={"ticker": ticker}, headers=auth_headers)
        assert resp.status_code == 202, ticker
        assert resp.json()["ticker"] == ticker

    @pytest.mark.parametrize("ticker", ["", "TOOLONGTICKER", "A@PL", "AA..B"])
    def test_invalid_tickers_are_rejected(self, client: TestClient, auth_headers, ticker):
        resp = client.post("/api/v1/analysis/", json={"ticker": ticker}, headers=auth_headers)
        assert resp.status_code == 422, ticker

    def test_tickers_are_normalised(self, client: TestClient, auth_headers):
        resp = client.post("/api/v1/analysis/", json={"ticker": " brk.b "}, headers=auth_headers)
        assert resp.json()["ticker"] == "BRK.B"


class TestFailureReporting:
    def test_failure_message_is_persisted_and_returned(
        self, client: TestClient, auth_headers, db
    ):
        create_resp = client.post(
            "/api/v1/analysis/", json={"ticker": "AAPL"}, headers=auth_headers
        )
        job_id = create_resp.json()["id"]

        crud.update_job_status(
            db, job_id=job_id, status="failed", error_message="No company profile was returned.",
        )

        resp = client.get(f"/api/v1/analysis/{job_id}", headers=auth_headers)
        assert resp.json()["status"] == "failed"
        assert resp.json()["error_message"] == "No company profile was returned."

    def test_advancing_status_clears_a_previous_message(self, client, auth_headers, db):
        job_id = client.post(
            "/api/v1/analysis/", json={"ticker": "AAPL"}, headers=auth_headers
        ).json()["id"]

        crud.update_job_status(db, job_id=job_id, status="failed", error_message="boom")
        crud.update_job_status(db, job_id=job_id, status="complete")

        job = crud.get_analysis_job(db, job_id)
        assert job.error_message is None

    def test_successful_jobs_have_no_message(self, client: TestClient, auth_headers):
        resp = client.post("/api/v1/analysis/", json={"ticker": "AAPL"}, headers=auth_headers)
        assert resp.json()["error_message"] is None


class TestOrchestratorMessages:
    def test_data_unavailable_message_reaches_the_user(self):
        orchestrator = Orchestrator("FAKE")
        message = orchestrator._failure_message(
            DataUnavailableError("No company profile was returned for 'FAKE'.")
        )
        assert "No company profile" in message

    def test_unexpected_errors_get_a_generic_but_useful_message(self):
        orchestrator = Orchestrator("AAPL")
        message = orchestrator._failure_message(KeyError("weightedAverageShsOut"))
        assert "AAPL" in message
        assert "try again" in message.lower()
        # Internal detail must not leak into user-facing text.
        assert "KeyError" not in message


class TestQuotaAccounting:
    def test_failed_jobs_do_not_consume_the_daily_allowance(self, client, auth_headers, db):
        user = crud.get_user_by_email(db, "test@example.com")

        for _ in range(3):
            job = create_job(db, user.id)
            crud.update_job_status(db, job_id=job.id, status="failed", error_message="upstream")

        assert crud.count_user_analyses_today(db, user.id) == 0
        resp = client.post("/api/v1/analysis/", json={"ticker": "MSFT"}, headers=auth_headers)
        assert resp.status_code == 202

    def test_successful_jobs_still_count(self, db, client, auth_headers):
        user = crud.get_user_by_email(db, "test@example.com")
        for _ in range(2):
            job = create_job(db, user.id)
            crud.update_job_status(db, job_id=job.id, status="complete")
        assert crud.count_user_analyses_today(db, user.id) == 2

    def test_limit_still_applies_to_non_failed_jobs(self, client, auth_headers, db):
        for ticker in ("AAPL", "MSFT", "GOOG"):
            assert client.post(
                "/api/v1/analysis/", json={"ticker": ticker}, headers=auth_headers
            ).status_code == 202

        blocked = client.post("/api/v1/analysis/", json={"ticker": "AMZN"}, headers=auth_headers)
        assert blocked.status_code == 429


class TestInterruptedJobRecovery:
    def test_in_progress_jobs_are_failed_with_an_explanation(self, db, client, auth_headers):
        user = crud.get_user_by_email(db, "test@example.com")
        running = [
            create_job(db, user.id, status=status)
            for status in ("pending", "gathering_data", "analyzing", "generating_report")
        ]

        reaped = crud.fail_stale_jobs(db, "Interrupted by a server restart.")
        assert reaped == len(running)

        for job in running:
            db.refresh(job)
            assert job.status == "failed"
            assert "restart" in job.error_message

    def test_terminal_jobs_are_left_alone(self, db, test_user):
        user = crud.get_user_by_email(db, test_user["email"])
        done = create_job(db, user.id, status="complete")
        failed = create_job(db, user.id, status="failed")

        crud.fail_stale_jobs(db, "Interrupted by a server restart.")

        db.refresh(done)
        db.refresh(failed)
        assert done.status == "complete"
        assert failed.error_message is None
