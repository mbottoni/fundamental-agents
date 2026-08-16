import logging
from datetime import date, timedelta
from typing import Any, Optional

import httpx

from ..core.config import settings

logger = logging.getLogger("stock_analyzer.agents.data_gathering")

# Shared timeout for all external API calls
HTTP_TIMEOUT = httpx.Timeout(30.0)


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

    def __init__(self) -> None:
        self.fmp_api_key = settings.FINANCIAL_MODELING_PREP_API_KEY
        self.news_api_key = settings.NEWS_API_KEY

    def _fmp_get(self, endpoint: str, params: Optional[dict[str, str]] = None) -> Any:
        """Make a GET request to the Financial Modeling Prep /stable API."""
        url = f"{self.FMP_BASE_URL}/{endpoint}"
        query_params = params or {}
        query_params["apikey"] = self.fmp_api_key
        try:
            response = httpx.get(url, params=query_params, timeout=HTTP_TIMEOUT)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error("FMP API HTTP error for %s: %s", endpoint, e)
            return None
        except httpx.RequestError as e:
            logger.error("FMP API request error for %s: %s", endpoint, e)
            return None

    def get_financial_statements(self, ticker: str) -> dict[str, Any]:
        """Fetch income statement, balance sheet, and cash flow statement."""
        logger.info("Fetching financial statements for %s", ticker)
        params = {"symbol": ticker}
        return {
            "income_statement": self._fmp_get("income-statement", params) or [],
            "balance_sheet": self._fmp_get("balance-sheet-statement", params) or [],
            "cash_flow": self._fmp_get("cash-flow-statement", params) or [],
        }

    def _price_window(self) -> dict[str, str]:
        """Date range parameters for the price history request."""
        today = date.today()
        start = today - timedelta(days=365 * self.PRICE_HISTORY_YEARS)
        return {"from": start.isoformat(), "to": today.isoformat()}

    def get_stock_price_history(self, ticker: str) -> list[dict]:
        """Fetch historical daily stock prices over the analysis window."""
        logger.info("Fetching price history for %s", ticker)
        # The /stable API returns a flat list of price records directly.
        data = self._fmp_get(
            "historical-price-eod/full", {"symbol": ticker, **self._price_window()},
        )
        if data and isinstance(data, list):
            return data
        return []

    def get_benchmark_prices(self) -> list[dict]:
        """Fetch price history for the market benchmark, used to regress beta."""
        logger.info("Fetching benchmark price history (%s)", self.BENCHMARK_TICKER)
        data = self._fmp_get(
            "historical-price-eod/full",
            {"symbol": self.BENCHMARK_TICKER, **self._price_window()},
        )
        if data and isinstance(data, list):
            return data
        return []

    def get_company_profile(self, ticker: str) -> Optional[dict]:
        """Fetch the company profile (includes beta, market cap, etc.)."""
        logger.info("Fetching company profile for %s", ticker)
        data = self._fmp_get("profile", {"symbol": ticker})
        if data and isinstance(data, list) and len(data) > 0:
            return data[0]
        return None

    def get_news(self, ticker: str) -> list[dict]:
        """Fetch recent news articles from NewsAPI."""
        logger.info("Fetching news for %s", ticker)
        url = f"https://newsapi.org/v2/everything?q={ticker}&apiKey={self.news_api_key}&sortBy=publishedAt&pageSize=20"
        try:
            response = httpx.get(url, timeout=HTTP_TIMEOUT)
            response.raise_for_status()
            return response.json().get("articles", [])
        except (httpx.HTTPStatusError, httpx.RequestError) as e:
            logger.error("NewsAPI error for %s: %s", ticker, e)
            return []

    def get_revenue_segments(self, ticker: str) -> dict[str, Any]:
        """Fetch revenue segmentation (by product/geography) from FMP."""
        logger.info("Fetching revenue segments for %s", ticker)
        product = self._fmp_get("revenue-product-segmentation", {"symbol": ticker, "period": "annual"}) or []
        geo = self._fmp_get("revenue-geographic-segmentation", {"symbol": ticker, "period": "annual"}) or []
        return {"product": product, "geographic": geo}

    def get_dividend_history(self, ticker: str) -> list[dict]:
        """Fetch historical dividend payouts."""
        logger.info("Fetching dividend history for %s", ticker)
        data = self._fmp_get("historical-price-eod/dividend", {"symbol": ticker})
        if data and isinstance(data, list):
            return data[:20]  # last 20 dividends
        return []

    def run(self, ticker: str) -> dict[str, Any]:
        """Run all data gathering tasks for a given ticker."""
        logger.info("Starting data gathering for %s", ticker)

        financials = self.get_financial_statements(ticker)
        prices = self.get_stock_price_history(ticker)
        benchmark_prices = self.get_benchmark_prices()
        profile = self.get_company_profile(ticker)
        news = self.get_news(ticker)
        revenue_segments = self.get_revenue_segments(ticker)
        dividend_history = self.get_dividend_history(ticker)

        logger.info(
            "Data gathering complete for %s: profile=%s, prices=%d, benchmark=%d, news=%d, divs=%d",
            ticker,
            "found" if profile else "missing",
            len(prices),
            len(benchmark_prices),
            len(news),
            len(dividend_history),
        )

        return {
            "ticker": ticker,
            "financials": financials,
            "prices": prices,
            "benchmark_prices": benchmark_prices,
            "profile": profile,
            "news": news,
            "revenue_segments": revenue_segments,
            "dividend_history": dividend_history,
        }
