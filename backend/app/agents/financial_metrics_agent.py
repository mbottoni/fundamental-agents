"""
Financial Metrics Agent
=======================
Calculates a comprehensive set of fundamental financial metrics:

Valuation:        P/E, P/B, P/S, EV/EBITDA, PEG (estimated)
Profitability:    Gross Margin, Operating Margin, Net Margin, ROE, ROA, ROIC
Liquidity:        Current Ratio, Quick Ratio
Leverage:         D/E Ratio, Interest Coverage
Efficiency:       Asset Turnover, Inventory Turnover
Growth:           Revenue Growth, Net Income Growth, EPS Growth, 3y CAGRs
Cash Flow:        FCF Yield, FCF per Share, Operating CF / Net Income
Dividends:        Dividend Yield, Payout Ratio

Everything is computed from the annual statements, then overlaid with
trailing-twelve-month figures wherever the provider supplies them. The latest
annual filing can be fifteen months old, which is long enough for a P/E built
on it to describe a company that no longer exists.
"""

import logging
from typing import Any, Optional

logger = logging.getLogger("stock_analyzer.agents.financial_metrics")


# (metric group, metric key) → field on the TTM payload it can be replaced by.
TTM_RATIO_OVERLAY: dict[tuple[str, str], str] = {
    ("valuation", "pe_ratio"): "priceToEarningsRatioTTM",
    ("valuation", "pb_ratio"): "priceToBookRatioTTM",
    ("valuation", "ps_ratio"): "priceToSalesRatioTTM",
    ("valuation", "peg_ratio"): "priceToEarningsGrowthRatioTTM",
    ("profitability", "gross_margin"): "grossProfitMarginTTM",
    ("profitability", "operating_margin"): "operatingProfitMarginTTM",
    ("profitability", "net_margin"): "netProfitMarginTTM",
    ("liquidity", "current_ratio"): "currentRatioTTM",
    ("liquidity", "quick_ratio"): "quickRatioTTM",
    ("leverage", "de_ratio"): "debtToEquityRatioTTM",
    ("leverage", "interest_coverage"): "interestCoverageRatioTTM",
    ("efficiency", "asset_turnover"): "assetTurnoverTTM",
    ("efficiency", "inventory_turnover"): "inventoryTurnoverTTM",
    ("dividends", "dividend_yield"): "dividendYieldTTM",
    ("dividends", "payout_ratio"): "dividendPayoutRatioTTM",
}

TTM_KEY_METRIC_OVERLAY: dict[tuple[str, str], str] = {
    ("valuation", "ev_ebitda"): "evToEBITDATTM",
    ("profitability", "roe"): "returnOnEquityTTM",
    ("profitability", "roa"): "returnOnAssetsTTM",
    ("profitability", "roic"): "returnOnInvestedCapitalTTM",
    ("cash_flow", "fcf_yield"): "freeCashFlowYieldTTM",
}


class FinancialMetricsAgent:
    """Calculates comprehensive financial metrics from raw data."""

    # ── helpers ────────────────────────────────────────────────

    def _safe_divide(self, numerator: Any, denominator: Any) -> Optional[float]:
        """Safely divide two numbers, returning None on failure."""
        try:
            if numerator is None or denominator is None or float(denominator) == 0:
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

        # Rounding happens after the TTM overlay in run(); returning raw values
        # also avoids the `if value` idiom discarding a legitimate zero.
        return {
            "pe_ratio": pe,
            "pb_ratio": pb,
            "ps_ratio": ps,
            "ev_ebitda": ev_ebitda,
            "peg_ratio": peg,
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
            "roic": roic,
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
        # Every other calculation uses totalStockholdersEquity; using
        # totalEquity here made debt-to-equity inconsistent with book value and
        # ROE for any company with minority interests.
        equity = self._get_latest(balance, "totalStockholdersEquity")
        if equity is None:
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

    def _cagr(self, income: list[dict], key: str, years: int = 3) -> Optional[float]:
        """
        Compound annual growth over `years`, which says far more about a
        business than a single year-over-year figure that one weak quarter or
        one-off charge can dominate.
        """
        latest = self._get_latest(income, key)
        earliest = self._get_prev(income, key, offset=years)
        try:
            if latest is None or earliest is None:
                return None
            latest, earliest = float(latest), float(earliest)
            # A sign change makes a compound rate meaningless.
            if earliest <= 0 or latest <= 0:
                return None
            return (latest / earliest) ** (1 / years) - 1
        except (TypeError, ValueError, ZeroDivisionError):
            return None

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
            "revenue_cagr_3y": self._cagr(income, "revenue"),
            "net_income_cagr_3y": self._cagr(income, "netIncome"),
            "eps_cagr_3y": self._cagr(income, "eps"),
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

    @staticmethod
    def _trailing_dividends(dividend_history: list[dict]) -> Optional[float]:
        """
        Sum the dividends actually paid over the last twelve months.

        The profile's `lastDividend` is a single declared payment, so dividing
        it by the price understates the yield of any quarterly payer.
        """
        if not dividend_history:
            return None
        from datetime import date, timedelta

        cutoff = (date.today() - timedelta(days=365)).isoformat()
        total = 0.0
        found = False
        for payment in dividend_history:
            payment_date = payment.get("date")
            amount = payment.get("dividend")
            if not payment_date or amount is None or str(payment_date) < cutoff:
                continue
            try:
                total += float(amount)
                found = True
            except (TypeError, ValueError):
                continue
        return total if found else None

    def _dividend_metrics(
        self,
        cash_flow: list[dict],
        income: list[dict],
        profile: Optional[dict],
        dividend_history: Optional[list[dict]] = None,
    ) -> dict[str, Optional[float]]:
        dividends_paid = abs(self._get_latest(cash_flow, "commonDividendsPaid") or 0)
        net_income = self._get_latest(income, "netIncome")
        current_price = (profile or {}).get("price")

        trailing = self._trailing_dividends(dividend_history or [])
        annual_dividend = trailing if trailing is not None else (profile or {}).get("lastDividend")

        payout_ratio = self._safe_divide(dividends_paid, net_income) if dividends_paid else None
        dividend_yield = (
            self._safe_divide(annual_dividend, current_price) if annual_dividend else None
        )

        return {
            "dividend_yield": dividend_yield,
            "payout_ratio": payout_ratio,
        }

    # ── trailing twelve months ────────────────────────────────

    def _apply_ttm_overlay(self, groups: dict[str, dict], ttm: dict) -> list[str]:
        """
        Replace annual figures with trailing-twelve-month ones where available.

        Returns the metric keys that came from TTM data, so the report can say
        which basis it is quoting instead of implying everything is current.
        """
        sources = (
            (ttm.get("ratios") or {}, TTM_RATIO_OVERLAY),
            (ttm.get("key_metrics") or {}, TTM_KEY_METRIC_OVERLAY),
        )

        applied: list[str] = []
        for payload, overlay in sources:
            if not isinstance(payload, dict):
                continue
            for (group_name, metric_key), source_key in overlay.items():
                value = payload.get(source_key)
                if value is None or group_name not in groups:
                    continue
                try:
                    groups[group_name][metric_key] = float(value)
                    applied.append(metric_key)
                except (TypeError, ValueError):
                    continue
        return applied

    # ── main entry point ──────────────────────────────────────

    def run(self, raw_data: dict) -> dict[str, Any]:
        """Calculate all financial metrics from raw data."""
        logger.info("Calculating financial metrics")

        financials = raw_data.get("financials", {})
        prices = raw_data.get("prices", [])
        profile = raw_data.get("profile")
        dividend_history = raw_data.get("dividend_history") or []
        ttm = raw_data.get("ttm") or {}

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
        metrics["dividends"] = self._dividend_metrics(
            cash_flow, income, profile, dividend_history,
        )

        ttm_applied = self._apply_ttm_overlay(metrics, ttm)

        # Round the ratio groups only after the overlay, so TTM values get the
        # same treatment as computed ones.
        for group_name in ("valuation", "leverage", "efficiency", "liquidity"):
            for key, value in metrics[group_name].items():
                if isinstance(value, (int, float)):
                    metrics[group_name][key] = round(value, 2)

        # Flatten for backward‑compat (the report agent can use either)
        flat: dict[str, Optional[float]] = {}
        for group in metrics.values():
            if isinstance(group, dict):
                flat.update(group)

        computed = sum(1 for v in flat.values() if v is not None)
        logger.info(
            "Computed %d/%d financial metrics (%d from TTM data)",
            computed, len(flat), len(ttm_applied),
        )

        return {
            "groups": metrics,
            "ttm_metrics": sorted(set(ttm_applied)),
            "basis": "trailing twelve months where available, otherwise latest fiscal year",
            **flat,
        }
