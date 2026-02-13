"""
Financial Metrics Agent
=======================
Computes 30+ fundamental financial metrics grouped by category.
Returns a structured dict with a flat ``groups`` key for easy charting.
"""

import logging
from typing import Any, Optional

logger = logging.getLogger("stock_analyzer.agents.financial_metrics")


class FinancialMetricsAgent:
    """Calculates comprehensive financial metrics from raw data."""

    # ── helpers ────────────────────────────────────────────────

    @staticmethod
    def _safe_divide(numerator: Any, denominator: Any) -> Optional[float]:
        try:
            if numerator is None or denominator is None or float(denominator) == 0:
                return None
            return float(numerator) / float(denominator)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _growth(current: Any, previous: Any) -> Optional[float]:
        try:
            if current is None or previous is None or float(previous) == 0:
                return None
            return (float(current) - float(previous)) / abs(float(previous))
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _get(stmt: list[dict], key: str, idx: int = 0) -> Any:
        try:
            return stmt[idx].get(key)
        except (IndexError, AttributeError):
            return None

    # ── metric groups ──────────────────────────────────────────

    def _valuation(self, price: float, income: list[dict], bs: list[dict], profile: dict) -> dict:
        eps = self._get(income, "eps")
        bvps = self._safe_divide(self._get(bs, "totalEquity"), self._get(income, "weightedAverageShsOut"))
        revenue = self._get(income, "revenue")
        shares = self._get(income, "weightedAverageShsOut")
        revenue_ps = self._safe_divide(revenue, shares) if revenue and shares else None
        ebitda = self._get(income, "ebitda")
        total_debt = self._get(bs, "totalDebt") or self._get(bs, "longTermDebt") or 0
        cash = self._get(bs, "cashAndCashEquivalents") or 0
        market_cap = profile.get("marketCap") or profile.get("mktCap")
        ev = (float(market_cap) + float(total_debt) - float(cash)) if market_cap else None

        pe = self._safe_divide(price, eps)
        # PEG = PE / EPS growth rate
        eps_prev = self._get(income, "eps", 1)
        eps_growth_pct = None
        if eps and eps_prev:
            g = self._growth(eps, eps_prev)
            if g is not None:
                eps_growth_pct = g * 100  # percentage

        return {
            "pe_ratio": round(pe, 2) if pe else None,
            "pb_ratio": round(self._safe_divide(price, bvps), 2) if bvps else None,
            "ps_ratio": round(self._safe_divide(price, revenue_ps), 2) if revenue_ps else None,
            "ev_ebitda": round(self._safe_divide(ev, ebitda), 2) if ev and ebitda else None,
            "peg_ratio": round(self._safe_divide(pe, eps_growth_pct), 2) if pe and eps_growth_pct and eps_growth_pct > 0 else None,
        }

    def _profitability(self, income: list[dict], bs: list[dict]) -> dict:
        revenue = self._get(income, "revenue")
        gross_profit = self._get(income, "grossProfit")
        op_income = self._get(income, "operatingIncome")
        net_income = self._get(income, "netIncome")
        equity = self._get(bs, "totalEquity")
        total_assets = self._get(bs, "totalAssets")
        invested_capital = (float(equity or 0)) + float(self._get(bs, "totalDebt") or self._get(bs, "longTermDebt") or 0)

        return {
            "gross_margin": round(float(self._safe_divide(gross_profit, revenue)), 4) if self._safe_divide(gross_profit, revenue) else None,
            "operating_margin": round(float(self._safe_divide(op_income, revenue)), 4) if self._safe_divide(op_income, revenue) else None,
            "net_margin": round(float(self._safe_divide(net_income, revenue)), 4) if self._safe_divide(net_income, revenue) else None,
            "roe": round(float(self._safe_divide(net_income, equity)), 4) if self._safe_divide(net_income, equity) else None,
            "roa": round(float(self._safe_divide(net_income, total_assets)), 4) if self._safe_divide(net_income, total_assets) else None,
            "roic": round(float(self._safe_divide(op_income, invested_capital)), 4) if invested_capital and self._safe_divide(op_income, invested_capital) else None,
        }

    def _liquidity(self, bs: list[dict]) -> dict:
        ca = self._get(bs, "totalCurrentAssets")
        cl = self._get(bs, "totalCurrentLiabilities")
        inventory = self._get(bs, "inventory") or 0
        quick_assets = (float(ca) - float(inventory)) if ca else None

        return {
            "current_ratio": round(float(self._safe_divide(ca, cl)), 2) if self._safe_divide(ca, cl) else None,
            "quick_ratio": round(float(self._safe_divide(quick_assets, cl)), 2) if quick_assets and self._safe_divide(quick_assets, cl) else None,
        }

    def _leverage(self, bs: list[dict], income: list[dict]) -> dict:
        total_debt = self._get(bs, "totalDebt") or self._get(bs, "longTermDebt")
        equity = self._get(bs, "totalEquity")
        op_income = self._get(income, "operatingIncome")
        interest_expense = self._get(income, "interestExpense")

        return {
            "de_ratio": round(float(self._safe_divide(total_debt, equity)), 2) if self._safe_divide(total_debt, equity) else None,
            "interest_coverage": round(float(self._safe_divide(op_income, interest_expense)), 2) if self._safe_divide(op_income, interest_expense) else None,
        }

    def _efficiency(self, income: list[dict], bs: list[dict]) -> dict:
        revenue = self._get(income, "revenue")
        total_assets = self._get(bs, "totalAssets")
        cogs = self._get(income, "costOfRevenue")
        inventory = self._get(bs, "inventory")

        return {
            "asset_turnover": round(float(self._safe_divide(revenue, total_assets)), 2) if self._safe_divide(revenue, total_assets) else None,
            "inventory_turnover": round(float(self._safe_divide(cogs, inventory)), 2) if self._safe_divide(cogs, inventory) else None,
        }

    def _growth_metrics(self, income: list[dict]) -> dict:
        return {
            "revenue_growth": round(float(self._growth(self._get(income, "revenue", 0), self._get(income, "revenue", 1))), 4) if self._growth(self._get(income, "revenue", 0), self._get(income, "revenue", 1)) else None,
            "net_income_growth": round(float(self._growth(self._get(income, "netIncome", 0), self._get(income, "netIncome", 1))), 4) if self._growth(self._get(income, "netIncome", 0), self._get(income, "netIncome", 1)) else None,
            "eps_growth": round(float(self._growth(self._get(income, "eps", 0), self._get(income, "eps", 1))), 4) if self._growth(self._get(income, "eps", 0), self._get(income, "eps", 1)) else None,
        }

    def _cash_flow(self, cf: list[dict], income: list[dict], price: float) -> dict:
        ocf = self._get(cf, "operatingCashFlow")
        capex = self._get(cf, "capitalExpenditure")
        shares = self._get(income, "weightedAverageShsOut")
        net_income = self._get(income, "netIncome")

        fcf = (float(ocf) - abs(float(capex or 0))) if ocf else None
        fcf_ps = self._safe_divide(fcf, shares) if fcf and shares else None

        return {
            "fcf_yield": round(float(self._safe_divide(fcf_ps, price)), 4) if fcf_ps and price else None,
            "fcf_per_share": round(float(fcf_ps), 2) if fcf_ps else None,
            "ocf_to_net_income": round(float(self._safe_divide(ocf, net_income)), 2) if self._safe_divide(ocf, net_income) else None,
        }

    def _dividends(self, cf: list[dict], income: list[dict], price: float) -> dict:
        dividends_paid = self._get(cf, "dividendsPaid")
        shares = self._get(income, "weightedAverageShsOut")
        net_income = self._get(income, "netIncome")

        dps = self._safe_divide(abs(float(dividends_paid or 0)), shares) if dividends_paid and shares else None

        return {
            "dividend_yield": round(float(self._safe_divide(dps, price)), 4) if dps and price else None,
            "payout_ratio": round(float(self._safe_divide(abs(float(dividends_paid or 0)), net_income)), 2) if dividends_paid and net_income and self._safe_divide(abs(float(dividends_paid or 0)), net_income) else None,
        }

    # ── main entry point ──────────────────────────────────────

    def run(self, raw_data: dict) -> dict[str, Any]:
        """Calculate all financial metrics from raw data."""
        logger.info("Calculating financial metrics")

        financials = raw_data.get("financials", {})
        prices = raw_data.get("prices", [])
        profile = raw_data.get("profile") or {}

        income = financials.get("income_statement", [])
        balance_sheet = financials.get("balance_sheet", [])
        cash_flow = financials.get("cash_flow", [])

        current_price = prices[0].get("close") if prices else 0

        groups = {
            "valuation": self._valuation(current_price, income, balance_sheet, profile),
            "profitability": self._profitability(income, balance_sheet),
            "liquidity": self._liquidity(balance_sheet),
            "leverage": self._leverage(balance_sheet, income),
            "efficiency": self._efficiency(income, balance_sheet),
            "growth": self._growth_metrics(income),
            "cash_flow": self._cash_flow(cash_flow, income, current_price),
            "dividends": self._dividends(cash_flow, income, current_price),
        }

        # Count how many non-None values we computed
        total = sum(len(g) for g in groups.values())
        computed = sum(1 for g in groups.values() for v in g.values() if v is not None)
        logger.info("Computed %d/%d financial metrics across %d groups", computed, total, len(groups))

        # Also keep flat top-level aliases for backward compat
        return {
            "groups": groups,
            "pe_ratio": groups["valuation"].get("pe_ratio"),
            "de_ratio": groups["leverage"].get("de_ratio"),
            "roe": groups["profitability"].get("roe"),
            "current_ratio": groups["liquidity"].get("current_ratio"),
        }
