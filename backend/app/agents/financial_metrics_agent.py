"""
Financial Metrics Agent
=======================
Calculates a comprehensive set of fundamental financial metrics:

Valuation:        P/E, P/B, P/S, EV/EBITDA, PEG (estimated)
Profitability:    Gross Margin, Operating Margin, Net Margin, ROE, ROA, ROIC
Liquidity:        Current Ratio, Quick Ratio
Leverage:         D/E Ratio, Interest Coverage
Efficiency:       Asset Turnover, Inventory Turnover
Growth:           Revenue Growth, Net Income Growth, EPS Growth
Cash Flow:        FCF Yield, FCF per Share, Operating CF / Net Income
Dividends:        Dividend Yield, Payout Ratio
"""

import logging
from typing import Any, Optional

logger = logging.getLogger("stock_analyzer.agents.financial_metrics")


class FinancialMetricsAgent:
    """Calculates key financial metrics from raw financial data."""

    # ── helpers ────────────────────────────────────────────────

    def _safe_divide(self, numerator: Any, denominator: Any) -> Optional[float]:
        """Safely divide two numbers, returning None on failure."""
        try:
            if numerator is None or denominator is None or denominator == 0:
                return None
            return float(numerator) / float(denominator)
        except (TypeError, ValueError):
            return None

    def _growth_rate(self, current: Any, previous: Any) -> Optional[float]:
        """YoY growth rate. Returns decimal (0.10 = 10 %)."""
        try:
            if current is None or previous is None or previous == 0:
                return None
            return (float(current) - float(previous)) / abs(float(previous))
        except (TypeError, ValueError):
            return None

    def _get_latest(self, data: list[dict], key: str) -> Any:
        """Get key from the most recent statement."""
        try:
            return data[0].get(key)
        except (IndexError, AttributeError):
            return None

    def _get_prev(self, data: list[dict], key: str, offset: int = 1) -> Any:
        """Get key from a prior period."""
        try:
            return data[offset].get(key)
        except (IndexError, AttributeError):
            return None

    # ── valuation ─────────────────────────────────────────────

    def _valuation_metrics(
        self,
        prices: list[dict],
        income: list[dict],
        balance: list[dict],
        profile: Optional[dict],
    ) -> dict[str, Optional[float]]:
        """P/E, P/B, P/S, EV/EBITDA, estimated PEG."""
        current_price = prices[0].get("close") if prices else None

        pe = self._safe_divide(current_price, self._get_latest(income, "eps"))

        # Book value per share
        equity = self._get_latest(balance, "totalStockholdersEquity")
        shares = self._get_latest(income, "weightedAverageShsOut")
        bvps = self._safe_divide(equity, shares)
        pb = self._safe_divide(current_price, bvps)

        # Price to Sales
        revenue = self._get_latest(income, "revenue")
        rps = self._safe_divide(revenue, shares)
        ps = self._safe_divide(current_price, rps)

        # EV / EBITDA
        market_cap = (profile or {}).get("marketCap")
        total_debt = self._get_latest(balance, "totalDebt") or 0
        cash = self._get_latest(balance, "cashAndCashEquivalents") or 0
        ev = (market_cap or 0) + total_debt - cash if market_cap else None
        ebitda = self._get_latest(income, "ebitda")
        ev_ebitda = self._safe_divide(ev, ebitda)

        # Estimated PEG (using EPS growth)
        eps_current = self._get_latest(income, "eps")
        eps_prev = self._get_prev(income, "eps")
        eps_growth = self._growth_rate(eps_current, eps_prev)
        peg = self._safe_divide(pe, (eps_growth * 100) if eps_growth else None)

        return {
            "pe_ratio": round(pe, 2) if pe else None,
            "pb_ratio": round(pb, 2) if pb else None,
            "ps_ratio": round(ps, 2) if ps else None,
            "ev_ebitda": round(ev_ebitda, 2) if ev_ebitda else None,
            "peg_ratio": round(peg, 2) if peg else None,
        }

    # ── profitability ─────────────────────────────────────────

    def _profitability_metrics(
        self, income: list[dict], balance: list[dict]
    ) -> dict[str, Optional[float]]:
        revenue = self._get_latest(income, "revenue")
        gross_profit = self._get_latest(income, "grossProfit")
        operating_income = self._get_latest(income, "operatingIncome")
        net_income = self._get_latest(income, "netIncome")
        total_assets = self._get_latest(balance, "totalAssets")
        equity = self._get_latest(balance, "totalStockholdersEquity")
        total_debt = self._get_latest(balance, "totalDebt") or 0
        cash = self._get_latest(balance, "cashAndCashEquivalents") or 0
        tax_expense = self._get_latest(income, "incomeTaxExpense") or 0

        # ROIC = NOPAT / Invested Capital
        nopat = None
        if operating_income is not None:
            # Approximate effective tax rate
            income_before_tax = self._get_latest(income, "incomeBeforeTax")
            eff_tax = self._safe_divide(tax_expense, income_before_tax) if income_before_tax else 0.21
            nopat = operating_income * (1 - (eff_tax or 0.21))
        invested_capital = (equity or 0) + total_debt - cash if equity else None
        roic = self._safe_divide(nopat, invested_capital)

        return {
            "gross_margin": self._safe_divide(gross_profit, revenue),
            "operating_margin": self._safe_divide(operating_income, revenue),
            "net_margin": self._safe_divide(net_income, revenue),
            "roe": self._safe_divide(net_income, equity),
            "roa": self._safe_divide(net_income, total_assets),
            "roic": round(roic, 4) if roic else None,
        }

    # ── liquidity ─────────────────────────────────────────────

    def _liquidity_metrics(self, balance: list[dict]) -> dict[str, Optional[float]]:
        current_assets = self._get_latest(balance, "totalCurrentAssets")
        current_liabilities = self._get_latest(balance, "totalCurrentLiabilities")
        inventory = self._get_latest(balance, "inventory") or 0

        quick_assets = (current_assets or 0) - inventory if current_assets else None

        return {
            "current_ratio": self._safe_divide(current_assets, current_liabilities),
            "quick_ratio": self._safe_divide(quick_assets, current_liabilities),
        }

    # ── leverage ──────────────────────────────────────────────

    def _leverage_metrics(
        self, balance: list[dict], income: list[dict]
    ) -> dict[str, Optional[float]]:
        total_debt = self._get_latest(balance, "totalDebt")
        equity = self._get_latest(balance, "totalEquity")
        interest_expense = self._get_latest(income, "interestExpense") or 0
        operating_income = self._get_latest(income, "operatingIncome")

        return {
            "de_ratio": self._safe_divide(total_debt, equity),
            "interest_coverage": self._safe_divide(operating_income, interest_expense) if interest_expense else None,
        }

    # ── efficiency ────────────────────────────────────────────

    def _efficiency_metrics(
        self, income: list[dict], balance: list[dict]
    ) -> dict[str, Optional[float]]:
        revenue = self._get_latest(income, "revenue")
        total_assets = self._get_latest(balance, "totalAssets")
        cost_of_revenue = self._get_latest(income, "costOfRevenue")
        inventory = self._get_latest(balance, "inventory")

        return {
            "asset_turnover": self._safe_divide(revenue, total_assets),
            "inventory_turnover": self._safe_divide(cost_of_revenue, inventory),
        }

    # ── growth ────────────────────────────────────────────────

    def _growth_metrics(self, income: list[dict]) -> dict[str, Optional[float]]:
        return {
            "revenue_growth": self._growth_rate(
                self._get_latest(income, "revenue"),
                self._get_prev(income, "revenue"),
            ),
            "net_income_growth": self._growth_rate(
                self._get_latest(income, "netIncome"),
                self._get_prev(income, "netIncome"),
            ),
            "eps_growth": self._growth_rate(
                self._get_latest(income, "eps"),
                self._get_prev(income, "eps"),
            ),
        }

    # ── cash flow ─────────────────────────────────────────────

    def _cashflow_metrics(
        self,
        cash_flow: list[dict],
        income: list[dict],
        profile: Optional[dict],
    ) -> dict[str, Optional[float]]:
        fcf = self._get_latest(cash_flow, "freeCashFlow")
        operating_cf = self._get_latest(cash_flow, "operatingCashFlow")
        net_income = self._get_latest(income, "netIncome")
        shares = self._get_latest(income, "weightedAverageShsOut")
        market_cap = (profile or {}).get("marketCap")

        return {
            "fcf_yield": self._safe_divide(fcf, market_cap),
            "fcf_per_share": self._safe_divide(fcf, shares),
            "ocf_to_net_income": self._safe_divide(operating_cf, net_income),
        }

    # ── dividends ─────────────────────────────────────────────

    def _dividend_metrics(
        self, cash_flow: list[dict], income: list[dict], profile: Optional[dict]
    ) -> dict[str, Optional[float]]:
        dividends_paid = abs(self._get_latest(cash_flow, "commonDividendsPaid") or 0)
        net_income = self._get_latest(income, "netIncome")
        last_dividend = (profile or {}).get("lastDividend")
        current_price = (profile or {}).get("price")

        payout_ratio = self._safe_divide(dividends_paid, net_income) if dividends_paid else None
        dividend_yield = self._safe_divide(last_dividend, current_price) if last_dividend else None

        return {
            "dividend_yield": dividend_yield,
            "payout_ratio": payout_ratio,
        }

    # ── main entry point ──────────────────────────────────────

    def run(self, raw_data: dict) -> dict[str, Any]:
        """Calculate all financial metrics from raw data."""
        logger.info("Calculating financial metrics")

        financials = raw_data.get("financials", {})
        prices = raw_data.get("prices", [])
        profile = raw_data.get("profile")

        income = financials.get("income_statement", [])
        balance = financials.get("balance_sheet", [])
        cash_flow = financials.get("cash_flow", [])

        metrics: dict[str, Any] = {}

        # Collect all metric groups
        metrics["valuation"] = self._valuation_metrics(prices, income, balance, profile)
        metrics["profitability"] = self._profitability_metrics(income, balance)
        metrics["liquidity"] = self._liquidity_metrics(balance)
        metrics["leverage"] = self._leverage_metrics(balance, income)
        metrics["efficiency"] = self._efficiency_metrics(income, balance)
        metrics["growth"] = self._growth_metrics(income)
        metrics["cash_flow"] = self._cashflow_metrics(cash_flow, income, profile)
        metrics["dividends"] = self._dividend_metrics(cash_flow, income, profile)

        # Flatten for backward‑compat (the report agent can use either)
        flat: dict[str, Optional[float]] = {}
        for group in metrics.values():
            if isinstance(group, dict):
                flat.update(group)

        computed = sum(1 for v in flat.values() if v is not None)
        logger.info("Computed %d/%d financial metrics", computed, len(flat))

        return {"groups": metrics, **flat}
