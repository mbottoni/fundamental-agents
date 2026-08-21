"""
Tests for reusing a completed analysis across users.

A report depends only on the ticker and the provider data behind it, so two
users analysing the same ticker were each spending eleven provider requests to
build byte-identical documents against a 250 call/day quota.
"""

import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app import crud, models


def _register(client: TestClient, email: str) -> dict:
    """Create a user and return auth headers for them."""
    password = "TestPass123"
    client.post("/api/v1/auth/register", json={"email": email, "password": password})
    resp = client.post(
        "/api/v1/auth/login", data={"username": email, "password": password}
    )
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _completed_analysis(
    db: Session,
    user_id: int,
    ticker: str = "AAPL",
    content: str = "# AAPL Report\n\nEverything looks fine.",
    with_snapshot: bool = True,
) -> models.AnalysisJob:
    """A finished job with a report, as the pipeline would leave it."""
    from app.schemas.analysis_job import AnalysisJobCreate

    job = crud.create_analysis_job(db, job=AnalysisJobCreate(ticker=ticker), user_id=user_id)
    crud.create_report(
        db,
        content=content,
        job_id=job.id,
        chart_data={"ticker": ticker, "prices": [{"date": "2026-01-02", "close": 1.0}]},
    )
    if with_snapshot:
        crud.create_snapshot(
            db,
            user_id=user_id,
            job_id=job.id,
            ticker=ticker,
            assessment={"recommendation": "BUY", "composite_score": 71.5, "confidence": 80},
            price=190.0,
            dcf_value=210.0,
            risk_rating="Moderate",
        )
    crud.update_job_status(db, job_id=job.id, status="complete")
    db.refresh(job)
    return job


@pytest.fixture
def other_user(client: TestClient, db: Session) -> models.User:
    """A second user who already ran an analysis."""
    _register(client, "author@example.com")
    return crud.get_user_by_email(db, email="author@example.com")


class TestSharedReuse:
    def test_another_users_report_is_reused_without_running_the_pipeline(
        self, client: TestClient, db: Session, auth_headers: dict, other_user
    ):
        source = _completed_analysis(db, other_user.id)

        resp = client.post("/api/v1/analysis/", json={"ticker": "AAPL"}, headers=auth_headers)

        assert resp.status_code == 202
        body = resp.json()
        assert body["status"] == "complete", "a reused analysis is already finished"
        assert body["id"] != source.id, "the requester gets their own job"

    def test_the_copied_report_is_identical(
        self, client: TestClient, db: Session, auth_headers: dict, other_user
    ):
        source = _completed_analysis(db, other_user.id)
        source_report = crud.get_report_by_job_id(db, job_id=source.id)

        job_id = client.post(
            "/api/v1/analysis/", json={"ticker": "AAPL"}, headers=auth_headers
        ).json()["id"]

        copied = crud.get_report_by_job_id(db, job_id=job_id)
        assert copied.content == source_report.content
        assert json.loads(copied.chart_data) == json.loads(source_report.chart_data)
        assert copied.id != source_report.id, "rows are copied, not shared"

    def test_the_requester_can_read_the_report_they_were_given(
        self, client: TestClient, db: Session, auth_headers: dict, other_user
    ):
        """The whole point: ownership checks must pass for the new owner."""
        _completed_analysis(db, other_user.id)

        job = client.post(
            "/api/v1/analysis/", json={"ticker": "AAPL"}, headers=auth_headers
        ).json()

        resp = client.get(f"/api/v1/reports/{job['report_id']}", headers=auth_headers)
        assert resp.status_code == 200
        assert "AAPL Report" in resp.json()["content"]

    def test_the_source_owner_still_owns_their_own_report(
        self, client: TestClient, db: Session, auth_headers: dict, other_user
    ):
        """Copying must not move the original or change who can read it."""
        source = _completed_analysis(db, other_user.id)
        source_report_id = crud.get_report_by_job_id(db, job_id=source.id).id

        client.post("/api/v1/analysis/", json={"ticker": "AAPL"}, headers=auth_headers)

        assert crud.get_report(db, source_report_id) is not None
        assert crud.get_analysis_job(db, source.id).user_id == other_user.id
        # And the requester cannot read the *original* through its own id.
        resp = client.get(f"/api/v1/reports/{source_report_id}", headers=auth_headers)
        assert resp.status_code in (403, 404)

    def test_a_snapshot_is_written_for_the_new_owner(
        self, client: TestClient, db: Session, auth_headers: dict, other_user, test_user
    ):
        """History, past-call performance and the leaderboard are per-user."""
        _completed_analysis(db, other_user.id)
        requester = crud.get_user_by_email(db, email=test_user["email"])

        client.post("/api/v1/analysis/", json={"ticker": "AAPL"}, headers=auth_headers)

        snapshot = crud.get_latest_snapshot(db, user_id=requester.id, ticker="AAPL")
        assert snapshot is not None
        assert snapshot.recommendation == "BUY"
        assert snapshot.price == 190.0
        assert snapshot.composite_score == 71.5

    def test_reuse_survives_a_source_with_no_snapshot(
        self, client: TestClient, db: Session, auth_headers: dict, other_user
    ):
        """Jobs predating snapshots must not break the copy."""
        _completed_analysis(db, other_user.id, with_snapshot=False)

        resp = client.post("/api/v1/analysis/", json={"ticker": "AAPL"}, headers=auth_headers)

        assert resp.status_code == 202
        assert resp.json()["status"] == "complete"


class TestReuseBoundaries:
    def test_a_different_ticker_is_not_reused(
        self, client: TestClient, db: Session, auth_headers: dict, other_user
    ):
        _completed_analysis(db, other_user.id, ticker="AAPL")

        resp = client.post("/api/v1/analysis/", json={"ticker": "MSFT"}, headers=auth_headers)

        assert resp.json()["status"] == "pending", "MSFT must actually run"

    def test_force_bypasses_shared_reuse(
        self, client: TestClient, db: Session, auth_headers: dict, other_user
    ):
        _completed_analysis(db, other_user.id)

        resp = client.post(
            "/api/v1/analysis/?force=true", json={"ticker": "AAPL"}, headers=auth_headers
        )

        assert resp.json()["status"] == "pending", "force must re-run the pipeline"

    def test_a_stale_analysis_is_not_reused(
        self, client: TestClient, db: Session, auth_headers: dict, other_user
    ):
        from datetime import datetime, timedelta, timezone

        source = _completed_analysis(db, other_user.id)
        source.created_at = datetime.now(timezone.utc) - timedelta(days=30)
        db.commit()

        resp = client.post("/api/v1/analysis/", json={"ticker": "AAPL"}, headers=auth_headers)

        assert resp.json()["status"] == "pending", "a month-old report is not fresh"

    def test_an_incomplete_analysis_is_not_reused(
        self, client: TestClient, db: Session, auth_headers: dict, other_user
    ):
        from app.schemas.analysis_job import AnalysisJobCreate

        crud.create_analysis_job(
            db, job=AnalysisJobCreate(ticker="AAPL"), user_id=other_user.id
        )  # left 'pending'

        resp = client.post("/api/v1/analysis/", json={"ticker": "AAPL"}, headers=auth_headers)

        assert resp.json()["status"] == "pending"

    def test_a_complete_job_without_a_report_is_not_reused(
        self, client: TestClient, db: Session, auth_headers: dict, other_user
    ):
        """
        A job can reach 'complete' with no report row if the report insert
        failed. Copying nothing would hand the user an empty analysis.
        """
        from app.schemas.analysis_job import AnalysisJobCreate

        job = crud.create_analysis_job(
            db, job=AnalysisJobCreate(ticker="AAPL"), user_id=other_user.id
        )
        crud.update_job_status(db, job_id=job.id, status="complete")

        resp = client.post("/api/v1/analysis/", json={"ticker": "AAPL"}, headers=auth_headers)

        assert resp.json()["status"] == "pending"

    def test_the_users_own_recent_analysis_is_returned_as_is(
        self, client: TestClient, db: Session, auth_headers: dict, test_user
    ):
        """Unchanged behaviour: no second job when they already have one."""
        requester = crud.get_user_by_email(db, email=test_user["email"])
        mine = _completed_analysis(db, requester.id)

        resp = client.post("/api/v1/analysis/", json={"ticker": "AAPL"}, headers=auth_headers)

        assert resp.json()["id"] == mine.id


class TestFreeTierInteraction:
    def test_a_reused_analysis_still_counts_against_the_daily_cap(
        self, client: TestClient, db: Session, auth_headers: dict, other_user
    ):
        """
        Exempting reuse would spend no quota but would quietly make the free
        tier unlimited for any popular ticker — a pricing change, not a
        caching one.
        """
        from app.core.config import settings

        for ticker in ["AAPL", "MSFT", "GOOG", "AMZN", "META"][
            : settings.FREE_TIER_DAILY_ANALYSES
        ]:
            _completed_analysis(db, other_user.id, ticker=ticker)
            resp = client.post(
                "/api/v1/analysis/", json={"ticker": ticker}, headers=auth_headers
            )
            assert resp.status_code == 202

        _completed_analysis(db, other_user.id, ticker="NVDA")
        resp = client.post("/api/v1/analysis/", json={"ticker": "NVDA"}, headers=auth_headers)
        assert resp.status_code == 429
