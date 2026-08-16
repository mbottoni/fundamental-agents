"""
Tests for analysis snapshots, ticker history, and past-call performance.
"""

from datetime import datetime, timedelta, timezone

import httpx
import pytest
from fastapi.testclient import TestClient

from app import crud
from app.core import market_data
from app.models.analysis_snapshot import AnalysisSnapshot
from app.schemas.analysis_job import AnalysisJobCreate


@pytest.fixture(autouse=True)
def stub_quotes(monkeypatch):
    """Current prices come from the provider; hold them at 120."""
    market_data.CACHE.clear()

    def stub(url, params=None, timeout=None):
        return httpx.Response(
            200,
            json=[{"symbol": (params or {}).get("symbol", "AAPL"), "price": 120.0}],
            request=httpx.Request("GET", url),
        )

    monkeypatch.setattr(market_data.httpx, "get", stub)
    yield
    market_data.CACHE.clear()


def record(
    db,
    user_id: int,
    ticker: str = "AAPL",
    *,
    recommendation: str = "buy",
    score: float = 0.3,
    price: float = 100.0,
    age_days: float = 30,
) -> AnalysisSnapshot:
    """Create a completed job and its snapshot, backdated by `age_days`."""
    job = crud.create_analysis_job(db, AnalysisJobCreate(ticker=ticker), user_id=user_id)
    crud.update_job_status(db, job_id=job.id, status="complete")

    snapshot = crud.create_snapshot(
        db,
        user_id=user_id,
        job_id=job.id,
        ticker=ticker,
        assessment={"recommendation": recommendation, "composite_score": score, "confidence": 70},
        price=price,
        dcf_value=price * 1.2,
        risk_rating="moderate",
    )
    snapshot.created_at = datetime.now(timezone.utc) - timedelta(days=age_days)
    db.commit()
    db.refresh(snapshot)
    return snapshot


@pytest.fixture
def user(db, test_user):
    return crud.get_user_by_email(db, test_user["email"])


class TestSnapshotCreation:
    def test_snapshot_records_the_call_and_the_price(self, db, user):
        snapshot = record(db, user.id, price=101.5, recommendation="strong buy", score=0.42)
        assert snapshot.ticker == "AAPL"
        assert snapshot.recommendation == "strong buy"
        assert snapshot.composite_score == 0.42
        assert snapshot.price == 101.5

    def test_latest_snapshot_is_the_newest(self, db, user):
        record(db, user.id, score=0.1, age_days=30)
        record(db, user.id, score=0.5, age_days=1)
        assert crud.get_latest_snapshot(db, user.id, "AAPL").composite_score == 0.5


class TestTickerHistory:
    def test_requires_authentication(self, client: TestClient):
        assert client.get("/api/v1/history/AAPL").status_code == 401

    def test_history_is_oldest_first(self, client: TestClient, auth_headers, db, user):
        record(db, user.id, score=0.1, age_days=30)
        record(db, user.id, score=0.4, age_days=2)

        body = client.get("/api/v1/history/AAPL", headers=auth_headers).json()
        scores = [s["composite_score"] for s in body["snapshots"]]
        assert scores == [0.1, 0.4]

    def test_deltas_against_the_previous_run_are_included(
        self, client: TestClient, auth_headers, db, user
    ):
        record(db, user.id, score=0.1, price=100.0, recommendation="hold", age_days=30)
        record(db, user.id, score=0.4, price=110.0, recommendation="buy", age_days=2)

        latest = client.get("/api/v1/history/AAPL", headers=auth_headers).json()["snapshots"][-1]
        assert latest["score_change"] == pytest.approx(0.3)
        assert latest["price_change_pct"] == pytest.approx(0.1)
        assert latest["recommendation_changed"] is True

    def test_an_unchanged_call_is_reported_as_unchanged(
        self, client: TestClient, auth_headers, db, user
    ):
        record(db, user.id, recommendation="buy", age_days=20)
        record(db, user.id, recommendation="buy", age_days=1)

        latest = client.get("/api/v1/history/AAPL", headers=auth_headers).json()
        assert latest["latest_change"]["recommendation_changed"] is False

    def test_a_ticker_with_no_history_is_empty_not_an_error(
        self, client: TestClient, auth_headers
    ):
        body = client.get("/api/v1/history/NFLX", headers=auth_headers).json()
        assert body["snapshots"] == []
        assert body["latest_change"] is None

    def test_another_users_history_is_not_visible(self, client: TestClient, auth_headers, db, user):
        other = crud.create_user(
            db,
            __import__("app.schemas.user", fromlist=["UserCreate"]).UserCreate(
                email="nosy@example.com", password="NosyPass123"
            ),
        )
        record(db, other.id, ticker="TSLA")

        body = client.get("/api/v1/history/TSLA", headers=auth_headers).json()
        assert body["snapshots"] == []


class TestCallPerformance:
    def test_requires_authentication(self, client: TestClient):
        assert client.get("/api/v1/history/").status_code == 401

    def test_recent_calls_are_excluded_until_they_mature(
        self, client: TestClient, auth_headers, db, user
    ):
        record(db, user.id, age_days=1)
        body = client.get("/api/v1/history/?min_age_days=7", headers=auth_headers).json()
        assert body["sample_size"] == 0
        assert "old enough" in body["note"]

    def test_a_buy_that_rose_counts_as_directionally_right(
        self, client: TestClient, auth_headers, db, user
    ):
        # Bought at 100, currently 120.
        record(db, user.id, recommendation="buy", price=100.0, age_days=30)

        body = client.get("/api/v1/history/", headers=auth_headers).json()
        assert body["sample_size"] == 1
        assert body["calls"][0]["directionally_right"] is True
        assert body["overall_hit_rate"] == 1.0

    def test_a_sell_that_rose_counts_as_wrong(self, client: TestClient, auth_headers, db, user):
        record(db, user.id, recommendation="sell", price=100.0, age_days=30)

        body = client.get("/api/v1/history/", headers=auth_headers).json()
        assert body["calls"][0]["directionally_right"] is False
        assert body["overall_hit_rate"] == 0.0

    def test_holds_make_no_directional_claim(self, client: TestClient, auth_headers, db, user):
        record(db, user.id, recommendation="hold", price=100.0, age_days=30)

        body = client.get("/api/v1/history/", headers=auth_headers).json()
        assert body["calls"][0]["directionally_right"] is None
        assert body["overall_hit_rate"] is None

    def test_results_are_grouped_by_recommendation(
        self, client: TestClient, auth_headers, db, user
    ):
        # Every ticker is currently 120 in the stub, so entry prices below that
        # rose and entry prices above it fell.
        record(db, user.id, ticker="AAPL", recommendation="buy", price=100.0, age_days=30)
        record(db, user.id, ticker="MSFT", recommendation="buy", price=110.0, age_days=30)
        record(db, user.id, ticker="TSLA", recommendation="sell", price=100.0, age_days=30)

        buckets = client.get("/api/v1/history/", headers=auth_headers).json()["by_recommendation"]
        assert buckets["buy"]["count"] == 2
        assert buckets["sell"]["count"] == 1
        assert buckets["buy"]["hit_rate"] == 1.0
        assert buckets["sell"]["hit_rate"] == 0.0

    def test_a_buy_above_the_current_price_counts_as_wrong(
        self, client: TestClient, auth_headers, db, user
    ):
        record(db, user.id, ticker="AAPL", recommendation="buy", price=100.0, age_days=30)
        record(db, user.id, ticker="MSFT", recommendation="buy", price=150.0, age_days=30)

        buckets = client.get("/api/v1/history/", headers=auth_headers).json()["by_recommendation"]
        assert buckets["buy"]["hit_rate"] == 0.5

    def test_the_response_states_that_it_is_not_evidence_of_skill(
        self, client: TestClient, auth_headers, db, user
    ):
        """A hit rate over a handful of calls invites overreading."""
        record(db, user.id, age_days=30)
        body = client.get("/api/v1/history/", headers=auth_headers).json()
        assert "not" in body["note"].lower()
        assert body["sample_size"] == 1
