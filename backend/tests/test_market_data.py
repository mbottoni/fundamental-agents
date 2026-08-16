"""
Tests for the shared market data client: caching, retries, and concurrency.
"""

import httpx
import pytest

from app.core import market_data
from app.core.market_data import MarketDataClient, TTLCache, cache_key


@pytest.fixture(autouse=True)
def clear_cache():
    market_data.CACHE.clear()
    yield
    market_data.CACHE.clear()


@pytest.fixture(autouse=True)
def no_backoff(monkeypatch):
    monkeypatch.setattr(market_data, "BACKOFF_BASE_SECONDS", 0)


class Recorder:
    def __init__(self, responses=None):
        self.calls = []
        self.responses = list(responses or [])

    def __call__(self, url, params=None, timeout=None):
        self.calls.append((url, dict(params or {})))
        request = httpx.Request("GET", url)
        if self.responses:
            item = self.responses.pop(0)
            if isinstance(item, int):
                return httpx.Response(item, json={}, request=request)
            return httpx.Response(200, json=item, request=request)
        return httpx.Response(200, json=[{"ok": True}], request=request)


@pytest.fixture
def http(monkeypatch) -> Recorder:
    recorder = Recorder()
    monkeypatch.setattr(market_data.httpx, "get", recorder)
    return recorder


class TestCacheKey:
    def test_api_key_is_never_part_of_the_key(self):
        """Cache keys can end up in logs or Redis; the credential must not."""
        key = cache_key("quote", {"symbol": "AAPL", "apikey": "secret-value"})
        assert "secret-value" not in key
        assert "AAPL" in key

    def test_parameter_order_does_not_matter(self):
        assert cache_key("q", {"a": 1, "b": 2}) == cache_key("q", {"b": 2, "a": 1})

    def test_different_parameters_produce_different_keys(self):
        assert cache_key("quote", {"symbol": "AAPL"}) != cache_key("quote", {"symbol": "MSFT"})


class TestTTLCache:
    def test_entries_expire(self, monkeypatch):
        cache = TTLCache()
        cache.set("k", "v", ttl=10)
        assert cache.get("k") == "v"

        real = market_data.time.monotonic
        monkeypatch.setattr(market_data.time, "monotonic", lambda: real() + 11)
        assert cache.get("k") is market_data._MISS

    def test_eviction_keeps_the_cache_bounded(self):
        cache = TTLCache(maxsize=3)
        for i in range(10):
            cache.set(f"k{i}", i, ttl=60)
        assert len(cache._entries) <= 3

    def test_missing_key_is_a_miss_not_none(self):
        """None is a legitimate cached value, so misses need their own sentinel."""
        cache = TTLCache()
        cache.set("present", None, ttl=60)
        assert cache.get("present") is None
        assert cache.get("absent") is market_data._MISS


class TestClient:
    def test_responses_are_cached(self, http):
        client = MarketDataClient()
        client.get("quote", {"symbol": "AAPL"}, ttl=60)
        client.get("quote", {"symbol": "AAPL"}, ttl=60)
        assert len(http.calls) == 1

    def test_the_api_key_is_sent_but_not_cached(self, http):
        client = MarketDataClient()
        client.get("quote", {"symbol": "AAPL"}, ttl=60)
        assert "apikey" in http.calls[0][1]

    def test_failures_are_not_cached(self, http):
        http.responses = [500, 500, 500, [{"ok": True}]]
        client = MarketDataClient()
        assert client.get("quote", {"symbol": "AAPL"}, ttl=60) is None
        assert client.get("quote", {"symbol": "AAPL"}, ttl=60) == [{"ok": True}]

    def test_throttling_is_retried(self, http):
        http.responses = [429, [{"ok": True}]]
        assert MarketDataClient().get("quote", {}) == [{"ok": True}]
        assert len(http.calls) == 2

    def test_client_errors_fail_fast(self, http):
        http.responses = [404, 404, 404]
        assert MarketDataClient().get("quote", {}) is None
        assert len(http.calls) == 1

    def test_get_many_runs_concurrently(self, monkeypatch):
        import threading
        import time as real_time

        state = {"current": 0, "peak": 0}
        lock = threading.Lock()

        def slow(url, params=None, timeout=None):
            with lock:
                state["current"] += 1
                state["peak"] = max(state["peak"], state["current"])
            real_time.sleep(0.05)
            with lock:
                state["current"] -= 1
            return httpx.Response(200, json=[], request=httpx.Request("GET", url))

        monkeypatch.setattr(market_data.httpx, "get", slow)
        client = MarketDataClient(use_cache=False)
        results = client.get_many(
            {s: (lambda sym=s: client.get("quote", {"symbol": sym})) for s in "ABCDEF"}
        )
        assert len(results) == 6
        assert state["peak"] > 1

    def test_get_many_isolates_failures(self):
        def boom():
            raise RuntimeError("upstream died")

        results = MarketDataClient(use_cache=False).get_many({"ok": lambda: 1, "bad": boom})
        assert results["ok"] == 1
        assert results["bad"] is None
