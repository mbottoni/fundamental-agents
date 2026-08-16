"""
Every endpoint that spends the provider quota must require a login.

Without this the deployment is an open proxy to a paid market-data key: anyone
who finds the URL can drain the daily quota — which then breaks analyses for
real users — and the whole product works without signing up.
"""

import httpx
import pytest
from fastapi.testclient import TestClient

from app.core import market_data

# (method, path) for everything that reaches the market data provider.
PROVIDER_BACKED_ROUTES = [
    ("get", "/api/v1/dashboard/quote/AAPL"),
    ("get", "/api/v1/dashboard/quote-batch?symbols=AAPL,MSFT"),
    ("get", "/api/v1/dashboard/search?q=apple"),
    ("get", "/api/v1/dashboard/stats"),
    ("get", "/api/v1/chart/AAPL"),
    ("get", "/api/v1/market/gainers"),
    ("get", "/api/v1/market/losers"),
    ("get", "/api/v1/market/most-active"),
    ("get", "/api/v1/market/sector-performance"),
    ("get", "/api/v1/market/lists"),
    ("get", "/api/v1/market/lists/tech"),
    ("get", "/api/v1/screener/"),
    ("get", "/api/v1/screener/sectors"),
    ("get", "/api/v1/screener/exchanges"),
    ("get", "/api/v1/compare/?ticker1=AAPL&ticker2=MSFT"),
    ("get", "/api/v1/watchlist/"),
    ("get", "/api/v1/analysis/"),
]


@pytest.fixture(autouse=True)
def stub_provider(monkeypatch):
    """No test here should reach the network."""
    market_data.CACHE.clear()

    def stub(url, params=None, timeout=None):
        return httpx.Response(
            200, json=[{"symbol": "AAPL", "price": 100.0}], request=httpx.Request("GET", url)
        )

    monkeypatch.setattr(market_data.httpx, "get", stub)
    yield
    market_data.CACHE.clear()


@pytest.mark.parametrize("method,path", PROVIDER_BACKED_ROUTES)
def test_requires_authentication(client: TestClient, method: str, path: str):
    response = getattr(client, method)(path)
    assert response.status_code == 401, f"{path} is reachable without a token"


@pytest.mark.parametrize("method,path", PROVIDER_BACKED_ROUTES)
def test_rejects_a_bogus_token(client: TestClient, method: str, path: str):
    response = getattr(client, method)(path, headers={"Authorization": "Bearer not-a-token"})
    assert response.status_code == 401


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/dashboard/quote/AAPL",
        "/api/v1/dashboard/search?q=apple",
        "/api/v1/market/gainers",
        "/api/v1/screener/sectors",
    ],
)
def test_authenticated_requests_are_served(client: TestClient, auth_headers, path: str):
    response = client.get(path, headers=auth_headers)
    assert response.status_code == 200


class TestPublicRoutes:
    """Health and auth must stay reachable."""

    @pytest.mark.parametrize("path", ["/health", "/"])
    def test_health_is_public(self, client: TestClient, path: str):
        assert client.get(path).status_code == 200

    def test_registration_is_public(self, client: TestClient):
        response = client.post(
            "/api/v1/auth/register",
            json={"email": "public@example.com", "password": "TestPass123"},
        )
        assert response.status_code == 201


class TestBatchQuotes:
    def test_batch_is_bounded(self, client: TestClient, auth_headers):
        """An unbounded batch turns the deployment into a bulk data feed."""
        symbols = ",".join(f"SYM{i}" for i in range(50))
        response = client.get(
            f"/api/v1/dashboard/quote-batch?symbols={symbols}", headers=auth_headers
        )
        assert response.status_code == 400

    def test_empty_batch_is_rejected(self, client: TestClient, auth_headers):
        response = client.get("/api/v1/dashboard/quote-batch?symbols=,,", headers=auth_headers)
        assert response.status_code == 400

    def test_batch_returns_a_quote_per_symbol(self, client: TestClient, auth_headers):
        response = client.get(
            "/api/v1/dashboard/quote-batch?symbols=AAPL,MSFT", headers=auth_headers
        )
        assert response.status_code == 200
        assert len(response.json()) == 2

    def test_duplicate_symbols_are_collapsed(self, client: TestClient, auth_headers):
        response = client.get(
            "/api/v1/dashboard/quote-batch?symbols=AAPL,AAPL,AAPL", headers=auth_headers
        )
        assert len(response.json()) == 1
