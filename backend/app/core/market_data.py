"""
Market Data Client
==================
One way in to Financial Modeling Prep, shared by the analysis pipeline and the
interactive endpoints.

Before this existed, five endpoint modules each carried a private `_fmp()`
helper with no retries and no caching, so the throttling and caching work done
for the pipeline benefited nothing else. Market movers and sector performance
are identical for every user and were re-fetched on every page view against a
250-call daily quota.

The cache is process-local. With several gunicorn workers each keeps its own
copy, which is a fraction of the benefit of a shared store but needs no extra
infrastructure; `RedisCache` swaps in when `REDIS_URL` is configured.
"""

import json
import logging
import threading
import time
from typing import Any, Callable, Optional, Protocol

import httpx

from .config import settings

logger = logging.getLogger("stock_analyzer.market_data")

FMP_BASE_URL = "https://financialmodelingprep.com/stable"
DEFAULT_TIMEOUT = httpx.Timeout(30.0, connect=10.0)

MAX_RETRIES = 3
BACKOFF_BASE_SECONDS = 0.5

# Cache lifetimes in seconds, by how often each dataset actually moves.
TTL_STATEMENTS = 24 * 60 * 60
TTL_PROFILE = 6 * 60 * 60
TTL_PRICES = 60 * 60
TTL_QUOTE = 60
TTL_MARKET = 5 * 60
TTL_NEWS = 30 * 60
TTL_SEARCH = 60 * 60

_MISS = object()


class _PlanRestricted:
    """
    Sentinel for an endpoint the provider subscription does not include.

    FMP answers those with HTTP 200 and a plain-text body, so without this they
    look like a successful empty response and the feature silently renders "no
    results" instead of explaining that it needs a different plan.
    """

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return "<PLAN_RESTRICTED>"

    def __bool__(self) -> bool:
        return False


PLAN_RESTRICTED = _PlanRestricted()
RESTRICTED_MARKER = "Restricted Endpoint"


class CacheBackend(Protocol):
    def get(self, key: str) -> Any: ...
    def set(self, key: str, value: Any, ttl: float) -> None: ...
    def clear(self) -> None: ...


class TTLCache:
    """A small thread-safe in-process cache with per-entry expiry."""

    def __init__(self, maxsize: int = 1024) -> None:
        self._maxsize = maxsize
        self._entries: dict[str, tuple[float, Any]] = {}
        self._lock = threading.Lock()

    def get(self, key: str) -> Any:
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                return _MISS
            expires_at, value = entry
            if expires_at < time.monotonic():
                self._entries.pop(key, None)
                return _MISS
            return value

    def set(self, key: str, value: Any, ttl: float) -> None:
        with self._lock:
            if len(self._entries) >= self._maxsize:
                # Cheap eviction: drop whatever expires soonest.
                oldest = min(self._entries, key=lambda k: self._entries[k][0])
                self._entries.pop(oldest, None)
            self._entries[key] = (time.monotonic() + ttl, value)

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()


class RedisCache:
    """
    Shared cache for multi-worker deployments.

    Falls back to behaving like a permanent miss if Redis is unreachable, so a
    cache outage degrades to the uncached behaviour rather than failing
    requests.
    """

    def __init__(self, url: str) -> None:
        import redis  # imported lazily so redis stays an optional dependency

        self._client = redis.Redis.from_url(url, socket_timeout=2, socket_connect_timeout=2)

    def get(self, key: str) -> Any:
        try:
            raw = self._client.get(key)
        except Exception as e:  # noqa: BLE001 - any client error means "no cache"
            logger.warning("Redis get failed (%s); treating as a miss", e)
            return _MISS
        if raw is None:
            return _MISS
        try:
            return json.loads(raw)
        except (TypeError, ValueError):
            return _MISS

    def set(self, key: str, value: Any, ttl: float) -> None:
        try:
            self._client.setex(key, int(ttl), json.dumps(value))
        except Exception as e:  # noqa: BLE001
            logger.warning("Redis set failed (%s); continuing without caching", e)

    def clear(self) -> None:
        try:
            self._client.flushdb()
        except Exception as e:  # noqa: BLE001
            logger.warning("Redis flush failed: %s", e)


def _build_cache() -> CacheBackend:
    url = getattr(settings, "REDIS_URL", "") or ""
    if url:
        try:
            cache = RedisCache(url)
            logger.info("Market data cache: Redis at %s", url.split("@")[-1])
            return cache
        except Exception as e:  # noqa: BLE001 - never let cache setup break boot
            logger.warning("Redis unavailable (%s); using the in-process cache", e)
    return TTLCache()


CACHE: CacheBackend = _build_cache()


def cache_key(endpoint: str, params: dict[str, Any]) -> str:
    """A stable key for an endpoint and its parameters, minus the API key."""
    scrubbed = {k: v for k, v in params.items() if k != "apikey"}
    return "fmp:" + endpoint + ":" + json.dumps(scrubbed, sort_keys=True, default=str)


class MarketDataClient:
    """Fetches from FMP with retries and caching."""

    def __init__(self, cache: Optional[CacheBackend] = None, use_cache: bool = True) -> None:
        self.cache = cache if cache is not None else CACHE
        self.use_cache = use_cache

    # ── HTTP ──────────────────────────────────────────────────

    def request(self, url: str, params: dict[str, Any], label: str) -> Any:
        """
        GET with retries on throttling and server errors.

        Client errors other than 429 are permanent for this request (a bad
        symbol, a revoked key), so they fail fast rather than burning retries.
        """
        for attempt in range(MAX_RETRIES):
            try:
                response = httpx.get(url, params=params, timeout=DEFAULT_TIMEOUT)
                response.raise_for_status()
                if RESTRICTED_MARKER in response.text[:200]:
                    logger.error("%s: not included in the current provider plan", label)
                    return PLAN_RESTRICTED
                try:
                    return response.json()
                except ValueError:
                    # A 200 that is not JSON is a provider-side problem, and
                    # retrying an unparseable body will not fix it.
                    logger.error("%s: response was not valid JSON", label)
                    return None
            except httpx.HTTPStatusError as e:
                status_code = e.response.status_code
                retryable = status_code == 429 or status_code >= 500
                if not retryable or attempt == MAX_RETRIES - 1:
                    logger.error("%s: HTTP %d (giving up)", label, status_code)
                    return None
                delay = BACKOFF_BASE_SECONDS * (2 ** attempt)
                logger.warning("%s: HTTP %d, retrying in %.1fs", label, status_code, delay)
                time.sleep(delay)
            except httpx.RequestError as e:
                if attempt == MAX_RETRIES - 1:
                    logger.error("%s: request failed (giving up): %s", label, e)
                    return None
                delay = BACKOFF_BASE_SECONDS * (2 ** attempt)
                logger.warning("%s: request error, retrying in %.1fs: %s", label, delay, e)
                time.sleep(delay)
        return None

    def get(
        self,
        endpoint: str,
        params: Optional[dict[str, Any]] = None,
        ttl: float = TTL_STATEMENTS,
    ) -> Any:
        """GET from the FMP /stable API, via the cache."""
        query = dict(params or {})
        key = cache_key(endpoint, query)

        if self.use_cache:
            cached = self.cache.get(key)
            if cached is not _MISS:
                logger.debug("Cache hit for %s", key)
                return cached

        query["apikey"] = settings.FINANCIAL_MODELING_PREP_API_KEY
        data = self.request(f"{FMP_BASE_URL}/{endpoint}", query, f"FMP {endpoint}")

        # Only successful responses are cached, so a transient outage does not
        # get frozen in for hours. A plan restriction is not transient, but it
        # is not serialisable either, so it is left uncached.
        if self.use_cache and data is not None and data is not PLAN_RESTRICTED:
            self.cache.set(key, data, ttl)
        return data

    def get_many(
        self,
        calls: dict[str, Callable[[], Any]],
        max_workers: int = 8,
    ) -> dict[str, Any]:
        """
        Run several fetches concurrently, returning what succeeded.

        A failing call yields None for its key rather than sinking the batch.
        """
        from concurrent.futures import ThreadPoolExecutor

        if not calls:
            return {}

        results: dict[str, Any] = {}
        with ThreadPoolExecutor(max_workers=min(len(calls), max_workers)) as pool:
            futures = {key: pool.submit(call) for key, call in calls.items()}
            for key, future in futures.items():
                try:
                    results[key] = future.result()
                except Exception as e:  # noqa: BLE001
                    logger.error("Concurrent fetch '%s' failed: %s", key, e, exc_info=True)
                    results[key] = None
        return results


# Module-level client for endpoint modules, which have no state of their own.
client = MarketDataClient()


def fmp_get(endpoint: str, params: Optional[dict[str, Any]] = None, ttl: float = TTL_MARKET) -> Any:
    """Convenience wrapper around the shared client."""
    return client.get(endpoint, params, ttl)
