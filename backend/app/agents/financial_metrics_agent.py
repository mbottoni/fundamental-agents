import logging
from typing import Any, Optional

logger = logging.getLogger("stock_analyzer.agents.financial_metrics")


class FinancialMetricsAgent:
    """Calculates key financial metrics from raw financial data."""

    def _safe_divide(self, numerator: Any, denominator: Any) -> Optional[float]:
        """Safely divide two numbers, returning None on failure."""
        try:
            if numerator is None or denominator is None or denominator == 0:
                return None
            return float(numerator) / float(denominator)
        except (TypeError, ValueError):
            return None

    def calculate_pe_ratio(
        self, price_data: list[dict], earnings_data: list[dict]
    ) -> Optional[float]:
        """Calculate the Price-to-Earnings (P/E) ratio."""
        try:
            latest_price = price_data[0]["close"]
            latest_eps = earnings_data[0]["eps"]
            return self._safe_divide(latest_price, latest_eps)
        except (IndexError, TypeError, KeyError) as e:
            logger.warning("Could not calculate P/E ratio: %s", e)
            return None

    def calculate_de_ratio(self, balance_sheet_data: list[dict]) -> Optional[float]:
        """Calculate the Debt-to-Equity (D/E) ratio."""
        try:
            latest = balance_sheet_data[0]
            return self._safe_divide(latest.get("totalDebt"), latest.get("totalEquity"))
        except (IndexError, TypeError) as e:
            logger.warning("Could not calculate D/E ratio: %s", e)
            return None

    def calculate_roe(self, income_data: list[dict], balance_sheet_data: list[dict]) -> Optional[float]:
        """Calculate Return on Equity (ROE)."""
        try:
            net_income = income_data[0].get("netIncome")
            equity = balance_sheet_data[0].get("totalEquity")
            return self._safe_divide(net_income, equity)
        except (IndexError, TypeError) as e:
            logger.warning("Could not calculate ROE: %s", e)
            return None

    def calculate_current_ratio(self, balance_sheet_data: list[dict]) -> Optional[float]:
        """Calculate the Current Ratio."""
        try:
            latest = balance_sheet_data[0]
            return self._safe_divide(
                latest.get("totalCurrentAssets"),
                latest.get("totalCurrentLiabilities"),
            )
        except (IndexError, TypeError) as e:
            logger.warning("Could not calculate Current Ratio: %s", e)
            return None

    def run(self, raw_data: dict) -> dict[str, Optional[float]]:
        """Calculate all financial metrics from raw data."""
        logger.info("Calculating financial metrics")

        financials = raw_data.get("financials", {})
        prices = raw_data.get("prices", [])

        income_statement = financials.get("income_statement", [])
        balance_sheet = financials.get("balance_sheet", [])

        metrics = {
            "pe_ratio": self.calculate_pe_ratio(prices, income_statement),
            "de_ratio": self.calculate_de_ratio(balance_sheet),
            "roe": self.calculate_roe(income_statement, balance_sheet),
            "current_ratio": self.calculate_current_ratio(balance_sheet),
        }

        computed_count = sum(1 for v in metrics.values() if v is not None)
        logger.info("Computed %d/%d financial metrics", computed_count, len(metrics))

        return metrics
