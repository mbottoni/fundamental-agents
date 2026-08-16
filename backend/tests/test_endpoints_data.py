"""
Tests for the market-data endpoints: chart, market, screener, compare and
watchlist. All provider traffic is stubbed.
"""

import httpx
import pytest
from fastapi.testclient import TestClient

from app.core import market_data


def price_history(days: int = 400, start: float = 100.0) -> list[dict]:
    """Newest-first daily bars, as FMP returns them."""
    from datetime import date, timedelta

    today = date.today()
    return [
        {
            "date": (today - timedelta(days=i)).isoformat(),
            "open": start + i * 0.1,
            "high": start + i * 0.1 + 1,
            "low": start + i * 0.1 - 1,
            "close": start + i * 0.1,
            "volume": 1_000_000 + i,
        }
        for i in range(days)
    ]


class Provider:
    """Serves canned responses keyed by URL fragment."""

    def __init__(self):
        self.calls: list[tuple[str, dict]] = []
        self.routes: dict[str, object] = {
            "historical-price-eod/full": price_history(),
            "profile": [{"symbol": "AAPL", "companyName": "Apple Inc.", "sector": "Technology",
                         "industry": "Consumer Electronics", "exchange": "NASDAQ",
                         "marketCap": 3e12, "beta": 1.2, "price": 200.0}],
            "quote": [{"symbol": "AAPL", "price": 200.0, "marketCap": 3e12, "volume": 5e7}],
            "ratios": [{"priceToEarningsRatioTTM": 30.0, "netProfitMarginTTM": 0.25}],
            "key-metrics": [{"returnOnEquityTTM": 0.4}],
            "financial-growth": [{"revenueGrowth": 0.1}],
            "gainers": [{"symbol": "AAA", "name": "AAA Corp", "changesPercentage": 12.0}],
            "losers": [{"symbol": "BBB", "name": "BBB Corp", "changesPercentage": -9.0}],
            "actives": [{"symbol": "CCC", "name": "CCC Corp", "volume": 9e7}],
            "most-active": [{"symbol": "CCC", "name": "CCC Corp", "volume": 9e7}],
            "sector-performance": [{"sector": "Technology", "changesPercentage": "1.2%"}],
            "company-screener": [{"symbol": "DDD", "companyName": "DDD Corp", "marketCap": 5e9}],
            "search-symbol": [{"symbol": "AAPL", "name": "Apple Inc."}],
        }

    def __call__(self, url, params=None, timeout=None):
        self.calls.append((url, dict(params or {})))
        request = httpx.Request("GET", url)
        for fragment, payload in self.routes.items():
            if fragment in url:
                return httpx.Response(200, json=payload, request=request)
        return httpx.Response(200, json=[], request=request)

    def params_for(self, fragment: str) -> list[dict]:
        return [p for url, p in self.calls if fragment in url]


@pytest.fixture(autouse=True)
def provider(monkeypatch) -> Provider:
    market_data.CACHE.clear()
    stub = Provider()
    monkeypatch.setattr(market_data.httpx, "get", stub)
    yield stub
    market_data.CACHE.clear()


class TestChart:
    def test_returns_prices_and_indicators(self, client: TestClient, auth_headers):
        response = client.get("/api/v1/chart/AAPL?indicators=sma,rsi", headers=auth_headers)
        assert response.status_code == 200
        body = response.json()
        assert body.get("ohlcv")
        assert "indicators" in body

    def test_request_is_bounded_by_timeframe(self, client, auth_headers, provider):
        """A one-month chart must not download the full history."""
        client.get("/api/v1/chart/AAPL?timeframe=1m", headers=auth_headers)
        params = provider.params_for("historical-price-eod/full")
        assert params
        assert "from" in params[0] and "to" in params[0]

    def test_max_timeframe_asks_for_everything(self, client, auth_headers, provider):
        client.get("/api/v1/chart/AAPL?timeframe=max", headers=auth_headers)
        params = provider.params_for("historical-price-eod/full")
        assert "from" not in params[0]

    def test_shorter_timeframes_return_fewer_bars(self, client, auth_headers):
        short = client.get("/api/v1/chart/AAPL?timeframe=1m", headers=auth_headers).json()
        long = client.get("/api/v1/chart/AAPL?timeframe=1y", headers=auth_headers).json()
        assert len(short["ohlcv"]) <= len(long["ohlcv"])

    def test_unknown_ticker_is_a_404(self, client, auth_headers, provider):
        provider.routes["historical-price-eod/full"] = []
        response = client.get("/api/v1/chart/NOPE", headers=auth_headers)
        assert response.status_code == 404

    def test_repeat_requests_are_cached(self, client, auth_headers, provider):
        client.get("/api/v1/chart/AAPL", headers=auth_headers)
        first = len(provider.params_for("historical-price-eod/full"))
        client.get("/api/v1/chart/AAPL", headers=auth_headers)
        assert len(provider.params_for("historical-price-eod/full")) == first


class TestMarket:
    @pytest.mark.parametrize(
        "path", ["/api/v1/market/gainers", "/api/v1/market/losers", "/api/v1/market/most-active"],
    )
    def test_movers_are_served(self, client: TestClient, auth_headers, path):
        response = client.get(path, headers=auth_headers)
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_sector_performance_is_served(self, client: TestClient, auth_headers):
        assert client.get("/api/v1/market/sector-performance", headers=auth_headers).status_code == 200

    def test_curated_lists_are_served(self, client: TestClient, auth_headers):
        assert client.get("/api/v1/market/lists", headers=auth_headers).status_code == 200

    def test_market_data_is_cached_across_users(self, client, auth_headers, provider):
        """Movers are identical for everyone, so the second caller costs nothing."""
        client.get("/api/v1/market/gainers", headers=auth_headers)
        calls = len(provider.params_for("gainers"))
        client.get("/api/v1/market/gainers", headers=auth_headers)
        assert len(provider.params_for("gainers")) == calls

    def test_provider_failure_is_a_502(self, client, auth_headers, monkeypatch):
        monkeypatch.setattr(
            market_data.httpx,
            "get",
            lambda url, params=None, timeout=None: httpx.Response(
                500, json={}, request=httpx.Request("GET", url)
            ),
        )
        monkeypatch.setattr(market_data, "BACKOFF_BASE_SECONDS", 0)
        assert client.get("/api/v1/market/gainers", headers=auth_headers).status_code == 502


class TestScreener:
    def test_filters_are_passed_through(self, client, auth_headers, provider):
        client.get(
            "/api/v1/screener/?sector=Technology&marketCapMin=1000000000&limit=10",
            headers=auth_headers,
        )
        params = provider.params_for("company-screener")
        assert params
        assert params[0].get("sector") == "Technology"

    def test_limit_is_bounded(self, client: TestClient, auth_headers):
        assert client.get("/api/v1/screener/?limit=5000", headers=auth_headers).status_code == 422

    def test_sector_and_exchange_lists_are_served(self, client: TestClient, auth_headers):
        assert client.get("/api/v1/screener/sectors", headers=auth_headers).status_code == 200
        assert client.get("/api/v1/screener/exchanges", headers=auth_headers).status_code == 200

    def test_a_restricted_plan_is_explained_not_shown_as_no_results(
        self, client: TestClient, auth_headers, monkeypatch
    ):
        """
        FMP answers an out-of-plan endpoint with HTTP 200 and a plain-text
        body, which otherwise reads as "nothing matched your filters".
        """
        monkeypatch.setattr(
            market_data.httpx,
            "get",
            lambda url, params=None, timeout=None: httpx.Response(
                200,
                text="Restricted Endpoint: This endpoint is not available under your plan",
                request=httpx.Request("GET", url),
            ),
        )
        response = client.get("/api/v1/screener/?sector=Technology", headers=auth_headers)
        assert response.status_code == 503
        assert "plan" in response.json()["detail"].lower()


class TestCompare:
    def test_two_tickers_are_compared(self, client: TestClient, auth_headers):
        response = client.get(
            "/api/v1/compare/?ticker1=AAPL&ticker2=MSFT", headers=auth_headers
        )
        assert response.status_code == 200

    def test_identical_tickers_are_rejected(self, client: TestClient, auth_headers):
        response = client.get(
            "/api/v1/compare/?ticker1=AAPL&ticker2=AAPL", headers=auth_headers
        )
        assert response.status_code == 400


class TestDashboardStats:
    def test_quota_is_reported_so_the_frontend_need_not_hardcode_it(
        self, client: TestClient, auth_headers
    ):
        response = client.get("/api/v1/dashboard/stats", headers=auth_headers)
        assert response.status_code == 200
        body = response.json()
        assert body["free_tier_daily_limit"] == 3
        assert body["analyses_today"] == 0

    def test_usage_reflects_started_analyses(self, client: TestClient, auth_headers):
        client.post("/api/v1/analysis/", json={"ticker": "AAPL"}, headers=auth_headers)
        body = client.get("/api/v1/dashboard/stats", headers=auth_headers).json()
        assert body["analyses_today"] == 1

    def test_premium_users_have_no_limit(self, client: TestClient, auth_headers, db):
        from app import crud

        user = crud.get_user_by_email(db, "test@example.com")
        user.subscription_status = "active"
        db.commit()

        body = client.get("/api/v1/dashboard/stats", headers=auth_headers).json()
        assert body["free_tier_daily_limit"] is None
        assert body["is_premium"] is True


class TestWatchlist:
    def test_add_list_and_remove(self, client: TestClient, auth_headers):
        created = client.post(
            "/api/v1/watchlist/", json={"ticker": "AAPL", "notes": "watching"},
            headers=auth_headers,
        )
        assert created.status_code == 201
        item_id = created.json()["id"]

        listed = client.get("/api/v1/watchlist/", headers=auth_headers)
        assert any(i["ticker"] == "AAPL" for i in listed.json())

        patched = client.patch(
            f"/api/v1/watchlist/{item_id}", json={"notes": "updated"}, headers=auth_headers
        )
        assert patched.status_code == 200
        assert patched.json()["notes"] == "updated"

        assert client.delete(f"/api/v1/watchlist/{item_id}", headers=auth_headers).status_code == 204
        assert client.get("/api/v1/watchlist/", headers=auth_headers).json() == []

    def test_another_users_item_is_not_reachable(self, client: TestClient, auth_headers):
        created = client.post(
            "/api/v1/watchlist/", json={"ticker": "AAPL"}, headers=auth_headers
        )
        item_id = created.json()["id"]

        client.post(
            "/api/v1/auth/register",
            json={"email": "other@example.com", "password": "OtherPass123"},
        )
        token = client.post(
            "/api/v1/auth/login",
            data={"username": "other@example.com", "password": "OtherPass123"},
        ).json()["access_token"]
        other = {"Authorization": f"Bearer {token}"}

        assert client.delete(f"/api/v1/watchlist/{item_id}", headers=other).status_code in (403, 404)
