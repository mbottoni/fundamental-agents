"""
Tests for the data gathering agent: caching, retries, and concurrent fetching.

All HTTP is stubbed — these assert on how the agent calls the network, not on
what the providers return.
"""

import httpx
import pytest

from app.agents import data_gathering_agent as module
from app.agents.data_gathering_agent import DataGatheringAgent


@pytest.fixture(autouse=True)
def clear_cache():
    """The response cache is process-wide; isolate every test from the last."""
    module._CACHE.clear()
    yield
    module._CACHE.clear()


@pytest.fixture(autouse=True)
def no_backoff_sleep(monkeypatch):
    """Keep retry backoff out of the test runtime without patching time itself."""
    monkeypatch.setattr(DataGatheringAgent, "BACKOFF_BASE_SECONDS", 0)


class FakeHTTP:
    """Records requests and replays queued responses."""

    def __init__(self, default=None):
        self.calls: list[tuple[str, dict]] = []
        self.default = default if default is not None else []
        self.queues: dict[str, list] = {}

    def queue(self, url_fragment: str, responses: list):
        self.queues[url_fragment] = list(responses)

    def __call__(self, url, params=None, timeout=None):
        self.calls.append((url, dict(params or {})))
        request = httpx.Request("GET", url)
        for fragment, queued in self.queues.items():
            if fragment in url and queued:
                item = queued.pop(0)
                if isinstance(item, int):
                    return httpx.Response(item, json={}, request=request)
                return httpx.Response(200, json=item, request=request)
        return httpx.Response(200, json=self.default, request=request)

    def urls_containing(self, fragment: str) -> list[str]:
        return [url for url, _ in self.calls if fragment in url]


@pytest.fixture
def http(monkeypatch) -> FakeHTTP:
    fake = FakeHTTP()
    monkeypatch.setattr(module.httpx, "get", fake)
    return fake


class TestCaching:
    def test_repeated_requests_hit_the_network_once(self, http):
        agent = DataGatheringAgent()
        agent.get_company_profile("AAPL")
        agent.get_company_profile("AAPL")
        agent.get_company_profile("AAPL")
        assert len(http.urls_containing("profile")) == 1

    def test_different_tickers_are_cached_separately(self, http):
        agent = DataGatheringAgent()
        agent.get_company_profile("AAPL")
        agent.get_company_profile("MSFT")
        assert len(http.urls_containing("profile")) == 2

    def test_cache_can_be_disabled(self, http):
        agent = DataGatheringAgent(use_cache=False)
        agent.get_company_profile("AAPL")
        agent.get_company_profile("AAPL")
        assert len(http.urls_containing("profile")) == 2

    def test_failed_responses_are_not_cached(self, http):
        """A transient outage must not be frozen in for the whole TTL."""
        http.queue("profile", [500, 500, 500, [{"companyName": "Apple"}]])
        agent = DataGatheringAgent()

        assert agent.get_company_profile("AAPL") is None
        assert agent.get_company_profile("AAPL") == {"companyName": "Apple"}

    def test_expired_entries_are_refetched(self, http, monkeypatch):
        agent = DataGatheringAgent()
        agent.get_company_profile("AAPL")

        # Jump past the profile TTL.
        real_monotonic = module.time.monotonic
        monkeypatch.setattr(
            module.time, "monotonic", lambda: real_monotonic() + module.PROFILE_TTL + 1
        )
        agent.get_company_profile("AAPL")
        assert len(http.urls_containing("profile")) == 2


class TestRetries:
    def test_throttling_is_retried(self, http):
        http.queue("profile", [429, 429, [{"companyName": "Apple"}]])
        agent = DataGatheringAgent()

        assert agent.get_company_profile("AAPL") == {"companyName": "Apple"}
        assert len(http.urls_containing("profile")) == 3

    def test_server_errors_are_retried(self, http):
        http.queue("profile", [503, [{"companyName": "Apple"}]])
        agent = DataGatheringAgent()

        assert agent.get_company_profile("AAPL") == {"companyName": "Apple"}

    def test_client_errors_fail_fast(self, http):
        """A bad symbol or revoked key will not fix itself on retry."""
        http.queue("profile", [404, 404, 404])
        agent = DataGatheringAgent()

        assert agent.get_company_profile("BADTICKER") is None
        assert len(http.urls_containing("profile")) == 1

    def test_retries_are_bounded(self, http):
        http.queue("profile", [500] * 10)
        agent = DataGatheringAgent()

        assert agent.get_company_profile("AAPL") is None
        assert len(http.urls_containing("profile")) == agent.MAX_RETRIES

    def test_connection_errors_are_retried(self, monkeypatch):
        attempts = {"count": 0}

        def flaky(url, params=None, timeout=None):
            attempts["count"] += 1
            if attempts["count"] < 3:
                raise httpx.ConnectError("boom")
            return httpx.Response(200, json=[{"companyName": "Apple"}], request=httpx.Request("GET", url))

        monkeypatch.setattr(module.httpx, "get", flaky)
        assert DataGatheringAgent().get_company_profile("AAPL") == {"companyName": "Apple"}
        assert attempts["count"] == 3


class TestRun:
    def test_payload_has_every_dataset(self, http):
        http.queue("profile", [[{"companyName": "Apple Inc."}]])
        result = DataGatheringAgent().run("AAPL")

        for key in (
            "ticker", "financials", "prices", "benchmark_prices",
            "profile", "news", "revenue_segments", "dividend_history",
        ):
            assert key in result
        for key in ("income_statement", "balance_sheet", "cash_flow"):
            assert key in result["financials"]

    def test_price_requests_are_date_bounded(self, http):
        DataGatheringAgent().run("AAPL")
        price_calls = [
            params for url, params in http.calls if "historical-price-eod/full" in url
        ]
        assert price_calls
        assert all("from" in params and "to" in params for params in price_calls)

    def test_benchmark_prices_are_fetched(self, http):
        DataGatheringAgent().run("AAPL")
        symbols = {
            params.get("symbol")
            for url, params in http.calls
            if "historical-price-eod/full" in url
        }
        assert DataGatheringAgent.BENCHMARK_TICKER in symbols

    def test_news_query_uses_the_company_name(self, http):
        http.queue("profile", [[{"companyName": "Ford Motor Company"}]])
        DataGatheringAgent().run("F")

        news_params = [params for url, params in http.calls if "newsapi" in url]
        assert news_params
        assert "Ford Motor Company" in news_params[0]["q"]

    def test_news_falls_back_to_the_ticker_alone(self, http):
        http.queue("profile", [[]])
        DataGatheringAgent().run("AAPL")

        news_params = [params for url, params in http.calls if "newsapi" in url]
        assert news_params[0]["q"] == "AAPL"

    def test_one_failing_dataset_does_not_sink_the_run(self, monkeypatch, http):
        def explode(*args, **kwargs):
            raise RuntimeError("dividend service is down")

        monkeypatch.setattr(DataGatheringAgent, "get_dividend_history", explode)
        result = DataGatheringAgent().run("AAPL")

        assert result["dividend_history"] == []
        assert "financials" in result

    def test_datasets_are_fetched_concurrently(self, monkeypatch):
        """The nine requests should overlap rather than run end to end."""
        import threading

        in_flight = {"current": 0, "peak": 0}
        lock = threading.Lock()
        barrier_delay = 0.05

        def slow_get(url, params=None, timeout=None):
            with lock:
                in_flight["current"] += 1
                in_flight["peak"] = max(in_flight["peak"], in_flight["current"])
            import time as real_time
            real_time.sleep(barrier_delay)
            with lock:
                in_flight["current"] -= 1
            return httpx.Response(200, json=[], request=httpx.Request("GET", url))

        monkeypatch.setattr(module.httpx, "get", slow_get)
        DataGatheringAgent(use_cache=False).run("AAPL")

        assert in_flight["peak"] > 1
