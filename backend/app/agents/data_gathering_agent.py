import logging
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

    def get_stock_price_history(self, ticker: str) -> list[dict]:
        """Fetch historical daily stock prices."""
        logger.info("Fetching price history for %s", ticker)
        # The /stable API returns a flat list of price records directly.
        data = self._fmp_get("historical-price-eod/full", {"symbol": ticker})
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

    def run(self, ticker: str) -> dict[str, Any]:
        """Run all data gathering tasks for a given ticker."""
        logger.info("Starting data gathering for %s", ticker)

        financials = self.get_financial_statements(ticker)
        prices = self.get_stock_price_history(ticker)
        profile = self.get_company_profile(ticker)
        news = self.get_news(ticker)

        logger.info(
            "Data gathering complete for %s: profile=%s, prices=%d, news=%d",
            ticker,
            "found" if profile else "missing",
            len(prices),
            len(news),
        )

        return {
            "ticker": ticker,
            "financials": financials,
            "prices": prices,
            "profile": profile,
            "news": news,
        }
