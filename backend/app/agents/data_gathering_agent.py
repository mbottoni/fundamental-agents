import requests
from ..core.config import settings

class DataGatheringAgent:
    def __init__(self):
        self.fmp_api_key = settings.FINANCIAL_MODELING_PREP_API_KEY
        self.news_api_key = settings.NEWS_API_KEY
        self.fmp_base_url = "https://financialmodelingprep.com/api/v3"

    def get_financial_statements(self, ticker: str):
        """
        Fetches income statement, balance sheet, and cash flow statement for a given ticker.
        """
        income_statement = requests.get(f"{self.fmp_base_url}/income-statement/{ticker}?apikey={self.fmp_api_key}").json()
        balance_sheet = requests.get(f"{self.fmp_base_url}/balance-sheet-statement/{ticker}?apikey={self.fmp_api_key}").json()
        cash_flow = requests.get(f"{self.fmp_base_url}/cash-flow-statement/{ticker}?apikey={self.fmp_api_key}").json()
        
        return {
            "income_statement": income_statement,
            "balance_sheet": balance_sheet,
            "cash_flow": cash_flow
        }

    def get_stock_price_history(self, ticker: str):
        """
        Fetches historical daily stock prices for a given ticker.
        """
        prices = requests.get(f"{self.fmp_base_url}/historical-price-full/{ticker}?apikey={self.fmp_api_key}").json()
        return prices.get('historical', [])

    def get_company_profile(self, ticker: str):
        """
        Fetches the company profile for a given ticker, which includes beta.
        """
        profile = requests.get(f"{self.fmp_base_url}/profile/{ticker}?apikey={self.fmp_api_key}").json()
        return profile[0] if profile else None

    def get_news(self, ticker: str):
        """
        Fetches recent news articles for a given ticker from NewsAPI.
        """
        # Note: NewsAPI may require a more specific query than just the ticker for best results
        news_url = f"https://newsapi.org/v2/everything?q={ticker}&apiKey={self.news_api_key}"
        news = requests.get(news_url).json()
        return news.get('articles', [])

    def run(self, ticker: str):
        """
        Runs all data gathering tasks for a given ticker.
        """
        financials = self.get_financial_statements(ticker)
        prices = self.get_stock_price_history(ticker)
        profile = self.get_company_profile(ticker)
        news = self.get_news(ticker)

        return {
            "ticker": ticker,
            "financials": financials,
            "prices": prices,
            "profile": profile,
            "news": news
        }
