import logging
from typing import Any, Optional

import httpx

from ..core.config import settings

logger = logging.getLogger("stock_analyzer.agents.data_gathering")

# Shared timeout for all external API calls
HTTP_TIMEOUT = httpx.Timeout(30.0)


class DataGatheringAgent:
    """Gathers raw financial data from external APIs for a given ticker."""

    def __init__(self) -> None:
        self.fmp_api_key = settings.FINANCIAL_MODELING_PREP_API_KEY
        self.news_api_key = settings.NEWS_API_KEY
        self.fmp_base_url = "https://financialmodelingprep.com/api/v3"

    def _fmp_get(self, endpoint: str) -> Any:
        """Make a GET request to the Financial Modeling Prep API."""
        url = f"{self.fmp_base_url}/{endpoint}"
        separator = "&" if "?" in endpoint else "?"
        url = f"{url}{separator}apikey={self.fmp_api_key}"
        try:
            response = httpx.get(url, timeout=HTTP_TIMEOUT)
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
        return {
            "income_statement": self._fmp_get(f"income-statement/{ticker}") or [],
            "balance_sheet": self._fmp_get(f"balance-sheet-statement/{ticker}") or [],
            "cash_flow": self._fmp_get(f"cash-flow-statement/{ticker}") or [],
        }

    def get_stock_price_history(self, ticker: str) -> list[dict]:
        """Fetch historical daily stock prices."""
        logger.info("Fetching price history for %s", ticker)
        data = self._fmp_get(f"historical-price-full/{ticker}")
        if data and isinstance(data, dict):
            return data.get("historical", [])
        return []

    def get_company_profile(self, ticker: str) -> Optional[dict]:
        """Fetch the company profile (includes beta, market cap, etc.)."""
        logger.info("Fetching company profile for %s", ticker)
        data = self._fmp_get(f"profile/{ticker}")
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
