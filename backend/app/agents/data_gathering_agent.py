"""
Data Gathering Agent
====================
Fetches everything the analysis pipeline needs from Financial Modeling Prep
and NewsAPI.

Three things matter here beyond the raw fetching:

* **Concurrency.** An analysis needs nine separate responses. Issued serially
  they dominate the runtime of the whole pipeline, so they are fanned out
  across a small thread pool.
* **Retries.** FMP rate-limits aggressively; a single 429 used to fail an
  entire analysis. Throttled and server-error responses are retried with
  exponential backoff.
* **Caching.** Fundamentals change quarterly but were re-fetched on every run,
  so two users analysing the same ticker burned two full quotas. Responses are
  cached in-process with a per-endpoint TTL. The cache is per worker, which is
  the pragmatic step short of introducing Redis.
"""

import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from typing import Any, Callable, Optional

import httpx

from ..core.config import settings

logger = logging.getLogger("stock_analyzer.agents.data_gathering")

# Shared timeout for all external API calls
HTTP_TIMEOUT = httpx.Timeout(30.0, connect=10.0)

# ── Response cache ────────────────────────────────────────────

_MISS = object()


class TTLCache:
    """A small thread-safe cache with per-entry expiry."""

    def __init__(self, maxsize: int = 512) -> None:
        self._maxsize = maxsize
        self._entries: dict[Any, tuple[float, Any]] = {}
        self._lock = threading.Lock()

    def get(self, key: Any) -> Any:
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                return _MISS
            expires_at, value = entry
            if expires_at < time.monotonic():
                self._entries.pop(key, None)
                return _MISS
            return value

    def set(self, key: Any, value: Any, ttl: float) -> None:
        with self._lock:
            if len(self._entries) >= self._maxsize:
                # Cheap eviction: drop whatever expires soonest.
                oldest = min(self._entries, key=lambda k: self._entries[k][0])
                self._entries.pop(oldest, None)
            self._entries[key] = (time.monotonic() + ttl, value)

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()


_CACHE = TTLCache()

# Cache lifetimes, in seconds, chosen by how often each dataset actually moves.
STATEMENT_TTL = 24 * 60 * 60
PROFILE_TTL = 6 * 60 * 60
PRICE_TTL = 60 * 60
NEWS_TTL = 30 * 60


class DataGatheringAgent:
    """Gathers raw financial data from external APIs for a given ticker."""

    # FMP migrated from /api/v3 (legacy) to /stable endpoints in Aug 2025.
    # The new API uses query parameters (?symbol=X) instead of path params (/X).
    FMP_BASE_URL = "https://financialmodelingprep.com/stable"

    # Three years covers the longest window any agent needs (200-day SMA,
    # 52-week range, 1-year risk statistics) without pulling decades of bars.
    PRICE_HISTORY_YEARS = 3
    # Market proxy used to regress beta.
    BENCHMARK_TICKER = "SPY"

    MAX_RETRIES = 3
    BACKOFF_BASE_SECONDS = 0.5
    MAX_WORKERS = 8

    def __init__(self, use_cache: bool = True) -> None:
        self.fmp_api_key = settings.FINANCIAL_MODELING_PREP_API_KEY
        self.news_api_key = settings.NEWS_API_KEY
        self.use_cache = use_cache

    # ── HTTP ──────────────────────────────────────────────────

    def _request(self, url: str, params: dict[str, str], label: str) -> Any:
        """
        GET with retries on throttling and server errors.

        Client errors other than 429 are permanent for this request (a bad
        symbol, a revoked key), so they fail fast rather than burning retries.
        """
        for attempt in range(self.MAX_RETRIES):
            try:
                response = httpx.get(url, params=params, timeout=HTTP_TIMEOUT)
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                status = e.response.status_code
                retryable = status == 429 or status >= 500
                if not retryable or attempt == self.MAX_RETRIES - 1:
                    logger.error("%s: HTTP %d (giving up)", label, status)
                    return None
                delay = self.BACKOFF_BASE_SECONDS * (2 ** attempt)
                logger.warning("%s: HTTP %d, retrying in %.1fs", label, status, delay)
                time.sleep(delay)
            except httpx.RequestError as e:
                if attempt == self.MAX_RETRIES - 1:
                    logger.error("%s: request failed (giving up): %s", label, e)
                    return None
                delay = self.BACKOFF_BASE_SECONDS * (2 ** attempt)
                logger.warning("%s: request error, retrying in %.1fs: %s", label, delay, e)
                time.sleep(delay)
        return None

    def _fmp_get(
        self, endpoint: str, params: Optional[dict[str, str]] = None, ttl: float = STATEMENT_TTL,
    ) -> Any:
        """GET from the Financial Modeling Prep /stable API, via the cache."""
        query_params = dict(params or {})
        cache_key = ("fmp", endpoint, tuple(sorted(query_params.items())))

        if self.use_cache:
            cached = _CACHE.get(cache_key)
            if cached is not _MISS:
                logger.debug("Cache hit for %s %s", endpoint, query_params)
                return cached

        query_params["apikey"] = self.fmp_api_key
        data = self._request(f"{self.FMP_BASE_URL}/{endpoint}", query_params, f"FMP {endpoint}")

        # Only successful responses are cached, so a transient outage does not
        # get frozen in for hours.
        if self.use_cache and data is not None:
            _CACHE.set(cache_key, data, ttl)
        return data

    # ── individual datasets ───────────────────────────────────

    def _price_window(self) -> dict[str, str]:
        """Date range parameters for the price history request."""
        today = date.today()
        start = today - timedelta(days=365 * self.PRICE_HISTORY_YEARS)
        return {"from": start.isoformat(), "to": today.isoformat()}

    def get_financial_statements(self, ticker: str) -> dict[str, Any]:
        """Fetch income statement, balance sheet, and cash flow statement."""
        params = {"symbol": ticker}
        return {
            "income_statement": self._fmp_get("income-statement", params) or [],
            "balance_sheet": self._fmp_get("balance-sheet-statement", params) or [],
            "cash_flow": self._fmp_get("cash-flow-statement", params) or [],
        }

    def get_stock_price_history(self, ticker: str) -> list[dict]:
        """Fetch historical daily stock prices over the analysis window."""
        # The /stable API returns a flat list of price records directly.
        data = self._fmp_get(
            "historical-price-eod/full",
            {"symbol": ticker, **self._price_window()},
            ttl=PRICE_TTL,
        )
        return data if isinstance(data, list) else []

    def get_benchmark_prices(self) -> list[dict]:
        """Fetch price history for the market benchmark, used to regress beta."""
        return self.get_stock_price_history(self.BENCHMARK_TICKER)

    def get_company_profile(self, ticker: str) -> Optional[dict]:
        """Fetch the company profile (includes beta, market cap, etc.)."""
        data = self._fmp_get("profile", {"symbol": ticker}, ttl=PROFILE_TTL)
        if data and isinstance(data, list):
            return data[0]
        return None

    def get_news(self, ticker: str, company_name: Optional[str] = None) -> list[dict]:
        """
        Fetch recent news articles from NewsAPI.

        Querying the bare ticker returns mostly unrelated articles for short
        symbols (F, A, IT), so the company name is included when known.
        """
        if company_name:
            query = f'"{company_name}" OR "{ticker}"'
        else:
            query = ticker

        cache_key = ("news", query)
        if self.use_cache:
            cached = _CACHE.get(cache_key)
            if cached is not _MISS:
                return cached

        articles = self._request(
            "https://newsapi.org/v2/everything",
            {
                "q": query,
                "apiKey": self.news_api_key,
                "sortBy": "publishedAt",
                "pageSize": "20",
                "language": "en",
            },
            "NewsAPI",
        )
        result = (articles or {}).get("articles", []) if isinstance(articles, dict) else []

        if self.use_cache and result:
            _CACHE.set(cache_key, result, NEWS_TTL)
        return result

    def get_revenue_segments(self, ticker: str) -> dict[str, Any]:
        """Fetch revenue segmentation (by product/geography) from FMP."""
        params = {"symbol": ticker, "period": "annual"}
        return {
            "product": self._fmp_get("revenue-product-segmentation", params) or [],
            "geographic": self._fmp_get("revenue-geographic-segmentation", params) or [],
        }

    def get_ttm_metrics(self, ticker: str) -> dict[str, Any]:
        """
        Fetch trailing-twelve-month ratios and key metrics.

        Annual statements can be fifteen months stale by the time they are the
        latest filing, which makes a P/E computed from them describe a company
        that no longer exists.
        """
        params = {"symbol": ticker}
        ratios = self._fmp_get("ratios-ttm", params, ttl=PROFILE_TTL)
        key_metrics = self._fmp_get("key-metrics-ttm", params, ttl=PROFILE_TTL)
        return {
            "ratios": ratios[0] if isinstance(ratios, list) and ratios else {},
            "key_metrics": key_metrics[0] if isinstance(key_metrics, list) and key_metrics else {},
        }

    def get_dividend_history(self, ticker: str) -> list[dict]:
        """Fetch historical dividend payouts."""
        # The /stable API serves these from `dividends`; the old
        # historical-price-eod/dividend path 404s.
        data = self._fmp_get("dividends", {"symbol": ticker})
        if isinstance(data, list):
            return data[:20]  # last 20 dividends
        return []

    # ── main entry point ──────────────────────────────────────

    def run(self, ticker: str) -> dict[str, Any]:
        """
        Run all data gathering tasks for a ticker, concurrently.

        The profile is fetched first because the news query is materially
        better with the company name in it.
        """
        logger.info("Starting data gathering for %s", ticker)
        started = time.monotonic()

        profile = self.get_company_profile(ticker)
        company_name = (profile or {}).get("companyName")

        params = {"symbol": ticker}
        segment_params = {"symbol": ticker, "period": "annual"}
        tasks: dict[str, Callable[[], Any]] = {
            "income_statement": lambda: self._fmp_get("income-statement", params),
            "balance_sheet": lambda: self._fmp_get("balance-sheet-statement", params),
            "cash_flow": lambda: self._fmp_get("cash-flow-statement", params),
            "prices": lambda: self.get_stock_price_history(ticker),
            "benchmark_prices": self.get_benchmark_prices,
            "news": lambda: self.get_news(ticker, company_name),
            "revenue_product": lambda: self._fmp_get("revenue-product-segmentation", segment_params),
            "revenue_geographic": lambda: self._fmp_get(
                "revenue-geographic-segmentation", segment_params
            ),
            "dividend_history": lambda: self.get_dividend_history(ticker),
            "ttm": lambda: self.get_ttm_metrics(ticker),
        }

        results: dict[str, Any] = {}
        with ThreadPoolExecutor(max_workers=self.MAX_WORKERS) as pool:
            futures = {key: pool.submit(task) for key, task in tasks.items()}
            for key, future in futures.items():
                try:
                    results[key] = future.result()
                except Exception as e:  # a single dataset must not sink the run
                    logger.error("Data gathering task '%s' failed: %s", key, e, exc_info=True)
                    results[key] = None

        prices = results.get("prices") or []
        news = results.get("news") or []
        dividends = results.get("dividend_history") or []

        logger.info(
            "Data gathering complete for %s in %.1fs: profile=%s, prices=%d, benchmark=%d, "
            "news=%d, divs=%d",
            ticker,
            time.monotonic() - started,
            "found" if profile else "missing",
            len(prices),
            len(results.get("benchmark_prices") or []),
            len(news),
            len(dividends),
        )

        return {
            "ticker": ticker,
            "financials": {
                "income_statement": results.get("income_statement") or [],
                "balance_sheet": results.get("balance_sheet") or [],
                "cash_flow": results.get("cash_flow") or [],
            },
            "prices": prices,
            "benchmark_prices": results.get("benchmark_prices") or [],
            "profile": profile,
            "news": news,
            "revenue_segments": {
                "product": results.get("revenue_product") or [],
                "geographic": results.get("revenue_geographic") or [],
            },
            "dividend_history": dividends,
            "ttm": results.get("ttm") or {},
        }
