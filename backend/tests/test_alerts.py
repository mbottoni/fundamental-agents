"""
Tests for watchlist alerts: price targets, recommendation changes, and the
deduplication that keeps a hovering price from spamming.
"""

from datetime import datetime, timedelta, timezone

import httpx
import pytest
from fastapi.testclient import TestClient

from app import crud
from app.core import market_data
from app.models.alert import Alert
from app.schemas.analysis_job import AnalysisJobCreate
from app.services.alerts import evaluate_alerts

PRICE = {"value": 150.0}


@pytest.fixture(autouse=True)
def stub_quotes(monkeypatch):
    """Quote every ticker at PRICE['value'], adjustable per test."""
    market_data.CACHE.clear()

    def stub(url, params=None, timeout=None):
        return httpx.Response(
            200,
            json=[{"symbol": (params or {}).get("symbol", "AAPL"), "price": PRICE["value"]}],
            request=httpx.Request("GET", url),
        )

    monkeypatch.setattr(market_data.httpx, "get", stub)
    PRICE["value"] = 150.0
    yield
    market_data.CACHE.clear()


@pytest.fixture
def user(db, test_user):
    return crud.get_user_by_email(db, test_user["email"])


def watch(client, auth_headers, ticker="AAPL", target=None, direction=None):
    payload = {"ticker": ticker}
    if target is not None:
        payload |= {"target_price": target, "target_direction": direction}
    return client.post("/api/v1/watchlist/", json=payload, headers=auth_headers).json()


def snapshot(db, user_id, ticker, recommendation, *, score=0.2, age_days=1):
    job = crud.create_analysis_job(db, AnalysisJobCreate(ticker=ticker), user_id=user_id)
    crud.update_job_status(db, job_id=job.id, status="complete")
    row = crud.create_snapshot(
        db,
        user_id=user_id,
        job_id=job.id,
        ticker=ticker,
        assessment={"recommendation": recommendation, "composite_score": score, "confidence": 70},
        price=100.0,
        dcf_value=110.0,
        risk_rating="moderate",
    )
    row.created_at = datetime.now(timezone.utc) - timedelta(days=age_days)
    db.commit()
    return row


class TestPriceTargets:
    def test_an_upward_target_fires_when_reached(self, client, auth_headers, db, user):
        watch(client, auth_headers, target=140.0, direction="above")
        PRICE["value"] = 150.0

        alerts = evaluate_alerts(db, user_id=user.id)
        assert len(alerts) == 1
        assert "at or above" in alerts[0].message

    def test_an_upward_target_stays_quiet_below_it(self, client, auth_headers, db, user):
        watch(client, auth_headers, target=200.0, direction="above")
        PRICE["value"] = 150.0
        assert evaluate_alerts(db, user_id=user.id) == []

    def test_a_downward_target_fires_when_price_falls(self, client, auth_headers, db, user):
        watch(client, auth_headers, target=160.0, direction="below")
        PRICE["value"] = 150.0

        alerts = evaluate_alerts(db, user_id=user.id)
        assert len(alerts) == 1
        assert "at or below" in alerts[0].message

    def test_items_without_a_target_never_fire(self, client, auth_headers, db, user):
        watch(client, auth_headers)
        assert evaluate_alerts(db, user_id=user.id) == []

    def test_repeated_sweeps_do_not_duplicate(self, client, auth_headers, db, user):
        """A price sitting on a target must not produce an alert every sweep."""
        watch(client, auth_headers, target=140.0, direction="above")

        assert len(evaluate_alerts(db, user_id=user.id)) == 1
        assert evaluate_alerts(db, user_id=user.id) == []
        assert evaluate_alerts(db, user_id=user.id) == []


class TestRecommendationChanges:
    def test_a_changed_call_raises_an_alert(self, client, auth_headers, db, user):
        watch(client, auth_headers)
        snapshot(db, user.id, "AAPL", "hold", age_days=10)
        snapshot(db, user.id, "AAPL", "buy", age_days=1)

        alerts = evaluate_alerts(db, user_id=user.id)
        assert len(alerts) == 1
        assert "HOLD to BUY" in alerts[0].message

    def test_an_unchanged_call_is_silent(self, client, auth_headers, db, user):
        watch(client, auth_headers)
        snapshot(db, user.id, "AAPL", "buy", age_days=10)
        snapshot(db, user.id, "AAPL", "buy", age_days=1)

        assert evaluate_alerts(db, user_id=user.id) == []

    def test_a_single_analysis_is_not_a_change(self, client, auth_headers, db, user):
        watch(client, auth_headers)
        snapshot(db, user.id, "AAPL", "buy")
        assert evaluate_alerts(db, user_id=user.id) == []

    def test_only_watched_tickers_are_considered(self, client, auth_headers, db, user):
        watch(client, auth_headers, ticker="AAPL")
        snapshot(db, user.id, "TSLA", "hold", age_days=10)
        snapshot(db, user.id, "TSLA", "sell", age_days=1)

        assert evaluate_alerts(db, user_id=user.id) == []


class TestAlertsApi:
    def test_requires_authentication(self, client: TestClient):
        assert client.get("/api/v1/alerts/").status_code == 401
        assert client.post("/api/v1/alerts/check").status_code == 401

    def test_check_creates_and_lists_alerts(self, client, auth_headers):
        watch(client, auth_headers, target=140.0, direction="above")

        created = client.post("/api/v1/alerts/check", headers=auth_headers).json()
        assert created["created"] == 1

        listed = client.get("/api/v1/alerts/", headers=auth_headers).json()
        assert listed["unread_count"] == 1
        assert listed["alerts"][0]["ticker"] == "AAPL"

    def test_marking_read_clears_the_badge(self, client, auth_headers):
        watch(client, auth_headers, target=140.0, direction="above")
        client.post("/api/v1/alerts/check", headers=auth_headers)

        alert_id = client.get("/api/v1/alerts/", headers=auth_headers).json()["alerts"][0]["id"]
        assert client.post(f"/api/v1/alerts/{alert_id}/read", headers=auth_headers).status_code == 200
        assert client.get("/api/v1/alerts/", headers=auth_headers).json()["unread_count"] == 0

    def test_read_all(self, client, auth_headers):
        watch(client, auth_headers, ticker="AAPL", target=140.0, direction="above")
        watch(client, auth_headers, ticker="MSFT", target=140.0, direction="above")
        client.post("/api/v1/alerts/check", headers=auth_headers)

        marked = client.post("/api/v1/alerts/read-all", headers=auth_headers).json()
        assert marked["marked_read"] == 2
        assert client.get("/api/v1/alerts/", headers=auth_headers).json()["unread_count"] == 0

    def test_unread_filter(self, client, auth_headers):
        watch(client, auth_headers, target=140.0, direction="above")
        client.post("/api/v1/alerts/check", headers=auth_headers)
        client.post("/api/v1/alerts/read-all", headers=auth_headers)

        unread = client.get("/api/v1/alerts/?unread_only=true", headers=auth_headers).json()
        assert unread["alerts"] == []

    def test_another_users_alert_cannot_be_read(self, client, auth_headers, db, user):
        watch(client, auth_headers, target=140.0, direction="above")
        client.post("/api/v1/alerts/check", headers=auth_headers)
        alert_id = db.query(Alert).first().id

        client.post(
            "/api/v1/auth/register",
            json={"email": "nosy@example.com", "password": "NosyPass123"},
        )
        token = client.post(
            "/api/v1/auth/login",
            data={"username": "nosy@example.com", "password": "NosyPass123"},
        ).json()["access_token"]

        response = client.post(
            f"/api/v1/alerts/{alert_id}/read",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 403


class TestWatchlistTargets:
    def test_target_is_stored_and_returned(self, client, auth_headers):
        item = watch(client, auth_headers, target=140.0, direction="above")
        assert item["target_price"] == 140.0
        assert item["target_direction"] == "above"

    def test_an_unknown_direction_is_rejected(self, client, auth_headers):
        response = client.post(
            "/api/v1/watchlist/",
            json={"ticker": "AAPL", "target_price": 100.0, "target_direction": "sideways"},
            headers=auth_headers,
        )
        assert response.status_code == 422

    def test_a_negative_target_is_rejected(self, client, auth_headers):
        response = client.post(
            "/api/v1/watchlist/",
            json={"ticker": "AAPL", "target_price": -5.0, "target_direction": "above"},
            headers=auth_headers,
        )
        assert response.status_code == 422

    def test_updating_notes_leaves_the_target_alone(self, client, auth_headers):
        """A partial update must not silently clear a price target."""
        item = watch(client, auth_headers, target=140.0, direction="above")

        updated = client.patch(
            f"/api/v1/watchlist/{item['id']}", json={"notes": "still watching"},
            headers=auth_headers,
        ).json()
        assert updated["notes"] == "still watching"
        assert updated["target_price"] == 140.0
