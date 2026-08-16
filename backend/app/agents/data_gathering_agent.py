"""
Data Gathering Agent
====================
Fetches everything the analysis pipeline needs from Financial Modeling Prep
and NewsAPI.

Two things matter here beyond the raw fetching:

* **Concurrency.** An analysis needs eleven separate responses. Issued serially
  they dominate the runtime of the whole pipeline, so they are fanned out
  across a small thread pool.
* **Shared transport.** Retries, backoff and caching live in
  `app/core/market_data.py`, so the pipeline and the interactive endpoints
  behave identically against the provider's quota.
"""

import logging
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from typing import Any, Callable, Optional

from ..core.config import settings
from ..core.market_data import (
    _MISS,
    TTL_NEWS,
    TTL_PRICES,
    TTL_PROFILE,
    TTL_STATEMENTS,
    MarketDataClient,
    cache_key,
)

logger = logging.getLogger("stock_analyzer.agents.data_gathering")

# Retained as module-level names so existing callers and tests keep working.
STATEMENT_TTL = TTL_STATEMENTS
PROFILE_TTL = TTL_PROFILE
PRICE_TTL = TTL_PRICES
NEWS_TTL = TTL_NEWS


class DataGatheringAgent:
    """Gathers raw financial data from external APIs for a given ticker."""

    # Three years covers the longest window any agent needs (200-day SMA,
    # 52-week range, 1-year risk statistics) without pulling decades of bars.
    PRICE_HISTORY_YEARS = 3
    # Market proxy used to regress beta.
    BENCHMARK_TICKER = "SPY"

    MAX_WORKERS = 8

    # Peer ratios cost one request each, so the list is capped. Peers overlap
    # heavily between companies, so the cache absorbs most of the repeat cost.
    MAX_PEERS = 5
    # Sector snapshots are only published for trading days; how many days back
    # to look before giving up.
    MAX_TRADING_DAY_LOOKBACK = 5

    def __init__(self, use_cache: bool = True) -> None:
        self.news_api_key = settings.NEWS_API_KEY
        self.use_cache = use_cache
        self.client = MarketDataClient(use_cache=use_cache)

    # ── HTTP ──────────────────────────────────────────────────

    def _fmp_get(
        self, endpoint: str, params: Optional[dict[str, str]] = None, ttl: float = STATEMENT_TTL,
    ) -> Any:
        """GET from the Financial Modeling Prep /stable API, via the cache."""
        return self.client.get(endpoint, params, ttl)

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

        # NewsAPI is not an FMP endpoint, so it is cached by hand against the
        # same backend rather than going through MarketDataClient.get.
        key = cache_key("newsapi", {"q": query})
        if self.use_cache:
            cached = self.client.cache.get(key)
            if cached is not _MISS:
                return cached

        articles = self.client.request(
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
            self.client.cache.set(key, result, NEWS_TTL)
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

    def get_peers(self, ticker: str) -> list[dict]:
        """
        Fetch comparable companies.

        A multiple only means something next to the multiples of similar
        businesses, so this is what makes the relative valuation possible.
        """
        data = self._fmp_get("stock-peers", {"symbol": ticker}, ttl=PROFILE_TTL)
        if not isinstance(data, list):
            return []
        peers = [p for p in data if isinstance(p, dict) and p.get("symbol")]
        return peers[: self.MAX_PEERS]

    def get_peer_ratios(self, symbols: list[str]) -> dict[str, dict]:
        """
        Fetch TTM ratios for each peer, concurrently.

        The company itself is measured with the same endpoint, so the
        comparison is like for like rather than provider-computed figures set
        against ones we derived ourselves.
        """
        if not symbols:
            return {}

        ratios: dict[str, dict] = {}
        with ThreadPoolExecutor(max_workers=min(len(symbols), self.MAX_WORKERS)) as pool:
            futures = {
                symbol: pool.submit(self._fmp_get, "ratios-ttm", {"symbol": symbol}, PROFILE_TTL)
                for symbol in symbols
            }
            for symbol, future in futures.items():
                try:
                    payload = future.result()
                except Exception as e:
                    logger.warning("Peer ratios failed for %s: %s", symbol, e)
                    continue
                if isinstance(payload, list) and payload:
                    ratios[symbol] = payload[0]
        return ratios

    def get_sector_valuation(
        self, sector: Optional[str], industry: Optional[str], exchange: Optional[str]
    ) -> dict[str, Any]:
        """
        Fetch sector and industry P/E snapshots.

        Snapshots exist only for trading days, so recent dates are tried in
        turn — asking for a Sunday returns an empty list.
        """
        if not exchange or not (sector or industry):
            return {}

        result: dict[str, Any] = {"sector": sector, "industry": industry}
        day = date.today()
        for _ in range(self.MAX_TRADING_DAY_LOOKBACK):
            params = {"date": day.isoformat(), "exchange": exchange}
            sector_rows = (
                self._fmp_get("sector-pe-snapshot", {**params, "sector": sector}, ttl=PROFILE_TTL)
                if sector
                else None
            )
            industry_rows = (
                self._fmp_get(
                    "industry-pe-snapshot", {**params, "industry": industry}, ttl=PROFILE_TTL
                )
                if industry
                else None
            )

            sector_pe = self._first_pe(sector_rows)
            industry_pe = self._first_pe(industry_rows)
            if sector_pe is not None or industry_pe is not None:
                result.update(
                    {"sector_pe": sector_pe, "industry_pe": industry_pe, "date": day.isoformat()}
                )
                return result
            day -= timedelta(days=1)

        logger.info("No sector or industry P/E snapshot found for %s", exchange)
        return result

    @staticmethod
    def _first_pe(rows: Any) -> Optional[float]:
        if isinstance(rows, list) and rows and isinstance(rows[0], dict):
            try:
                pe = rows[0].get("pe")
                return float(pe) if pe is not None else None
            except (TypeError, ValueError):
                return None
        return None

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
            "peers": lambda: self.get_peers(ticker),
            "sector_valuation": lambda: self.get_sector_valuation(
                (profile or {}).get("sector"),
                (profile or {}).get("industry"),
                (profile or {}).get("exchange"),
            ),
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

        # Second wave: peer ratios can only be requested once the peer list is
        # known. Still concurrent, just necessarily after the list arrives.
        peers = results.get("peers") or []
        peer_ratios = self.get_peer_ratios([p["symbol"] for p in peers])

        logger.info(
            "Data gathering complete for %s in %.1fs: profile=%s, prices=%d, benchmark=%d, "
            "news=%d, divs=%d, peers=%d",
            ticker,
            time.monotonic() - started,
            "found" if profile else "missing",
            len(prices),
            len(results.get("benchmark_prices") or []),
            len(news),
            len(dividends),
            len(peer_ratios),
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
            "peers": {"companies": peers, "ratios": peer_ratios},
            "sector_valuation": results.get("sector_valuation") or {},
        }
