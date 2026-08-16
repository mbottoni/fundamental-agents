"""
Tests for the financial metrics agent: TTM overlay, growth rates, dividend
yield, and the equity figure used for leverage.
"""

from datetime import date, timedelta

import pytest

from app.agents.financial_metrics_agent import FinancialMetricsAgent


def raw_data(
    *,
    income: list[dict] | None = None,
    balance: list[dict] | None = None,
    cash_flow: list[dict] | None = None,
    profile: dict | None = None,
    dividend_history: list[dict] | None = None,
    ttm: dict | None = None,
) -> dict:
    return {
        "ticker": "TEST",
        "prices": [{"date": "2026-08-14", "close": 100.0}],
        "profile": profile if profile is not None else {"marketCap": 1_000_000_000, "price": 100.0},
        "financials": {
            "income_statement": income if income is not None else [
                {"revenue": 1_000_000_000, "netIncome": 100_000_000, "eps": 10.0,
                 "weightedAverageShsOut": 10_000_000, "ebitda": 200_000_000,
                 "operatingIncome": 150_000_000, "grossProfit": 500_000_000,
                 "incomeBeforeTax": 130_000_000, "incomeTaxExpense": 30_000_000,
                 "interestExpense": 10_000_000, "costOfRevenue": 500_000_000},
            ],
            "balance_sheet": balance if balance is not None else [
                {"totalDebt": 400_000_000, "totalStockholdersEquity": 500_000_000,
                 "totalEquity": 600_000_000, "totalAssets": 2_000_000_000,
                 "totalCurrentAssets": 600_000_000, "totalCurrentLiabilities": 300_000_000,
                 "inventory": 100_000_000, "cashAndCashEquivalents": 200_000_000},
            ],
            "cash_flow": cash_flow if cash_flow is not None else [
                {"freeCashFlow": 90_000_000, "operatingCashFlow": 120_000_000,
                 "commonDividendsPaid": -20_000_000},
            ],
        },
        "dividend_history": dividend_history or [],
        "ttm": ttm or {},
    }


def income_series(revenues: list[float]) -> list[dict]:
    """Newest-first income statements with the given revenues."""
    return [
        {
            "revenue": revenue,
            "netIncome": revenue * 0.1,
            "eps": revenue / 100_000_000,
            "weightedAverageShsOut": 10_000_000,
        }
        for revenue in revenues
    ]


class TestTTMOverlay:
    def test_ttm_ratios_replace_annual_ones(self):
        """Annual filings can be fifteen months stale by the time they are latest."""
        result = FinancialMetricsAgent().run(
            raw_data(ttm={"ratios": {"priceToEarningsRatioTTM": 34.92,
                                     "netProfitMarginTTM": 0.276}})
        )
        assert result["groups"]["valuation"]["pe_ratio"] == 34.92
        assert result["groups"]["profitability"]["net_margin"] == 0.276
        assert "pe_ratio" in result["ttm_metrics"]

    def test_key_metrics_overlay_is_applied(self):
        result = FinancialMetricsAgent().run(
            raw_data(ttm={"key_metrics": {"returnOnInvestedCapitalTTM": 0.52,
                                          "evToEBITDATTM": 26.9}})
        )
        assert result["groups"]["profitability"]["roic"] == 0.52
        assert result["groups"]["valuation"]["ev_ebitda"] == 26.9

    def test_annual_values_survive_without_ttm_data(self):
        computed = FinancialMetricsAgent().run(raw_data())
        assert computed["groups"]["valuation"]["pe_ratio"] == 10.0  # 100 / 10 EPS
        assert computed["ttm_metrics"] == []

    def test_malformed_ttm_payload_is_ignored(self):
        result = FinancialMetricsAgent().run(
            raw_data(ttm={"ratios": {"priceToEarningsRatioTTM": "not a number"},
                          "key_metrics": None})
        )
        assert result["groups"]["valuation"]["pe_ratio"] == 10.0

    def test_ttm_values_are_rounded_like_computed_ones(self):
        result = FinancialMetricsAgent().run(
            raw_data(ttm={"ratios": {"priceToEarningsRatioTTM": 34.9235159817}})
        )
        assert result["groups"]["valuation"]["pe_ratio"] == 34.92


class TestLeverage:
    def test_debt_to_equity_uses_shareholders_equity(self):
        """
        Book value and ROE use totalStockholdersEquity; leverage read
        totalEquity, which differs whenever there are minority interests.
        """
        result = FinancialMetricsAgent().run(raw_data())
        # 400M debt / 500M shareholders' equity, not / 600M total equity.
        assert result["groups"]["leverage"]["de_ratio"] == 0.8

    def test_falls_back_to_total_equity(self):
        balance = [{"totalDebt": 400_000_000, "totalEquity": 800_000_000}]
        result = FinancialMetricsAgent().run(raw_data(balance=balance))
        assert result["groups"]["leverage"]["de_ratio"] == 0.5


class TestGrowth:
    def test_three_year_cagr_is_computed(self):
        # Newest first: 1331, 1210, 1100, 1000 → 10% a year.
        result = FinancialMetricsAgent().run(
            raw_data(income=income_series([1331.0, 1210.0, 1100.0, 1000.0]))
        )
        assert result["groups"]["growth"]["revenue_cagr_3y"] == pytest.approx(0.10, abs=1e-6)

    def test_cagr_is_none_without_enough_history(self):
        result = FinancialMetricsAgent().run(raw_data(income=income_series([1100.0, 1000.0])))
        assert result["groups"]["growth"]["revenue_cagr_3y"] is None

    def test_cagr_is_none_across_a_sign_change(self):
        """A compound rate through zero is meaningless."""
        agent = FinancialMetricsAgent()
        statements = [
            {"netIncome": 100.0}, {"netIncome": 50.0}, {"netIncome": -10.0}, {"netIncome": -80.0},
        ]
        assert agent._cagr(statements, "netIncome") is None

    def test_year_over_year_growth_still_reported(self):
        result = FinancialMetricsAgent().run(
            raw_data(income=income_series([1100.0, 1000.0, 900.0, 800.0]))
        )
        assert result["groups"]["growth"]["revenue_growth"] == pytest.approx(0.10)


class TestDividends:
    def test_yield_uses_trailing_twelve_months_of_payments(self):
        """A quarterly payer's yield must not be one quarter's dividend."""
        recent = date.today()
        history = [
            {"date": (recent - timedelta(days=days)).isoformat(), "dividend": 0.25}
            for days in (10, 100, 190, 280)
        ]
        result = FinancialMetricsAgent().run(
            raw_data(dividend_history=history, profile={"price": 100.0, "lastDividend": 0.25})
        )
        # Four quarterly payments of 0.25 at a price of 100 is 1%.
        assert result["groups"]["dividends"]["dividend_yield"] == pytest.approx(0.01)

    def test_payments_older_than_a_year_are_excluded(self):
        history = [
            {"date": (date.today() - timedelta(days=days)).isoformat(), "dividend": 0.25}
            for days in (10, 400, 800)
        ]
        result = FinancialMetricsAgent().run(
            raw_data(dividend_history=history, profile={"price": 100.0})
        )
        assert result["groups"]["dividends"]["dividend_yield"] == pytest.approx(0.0025)

    def test_falls_back_to_last_declared_dividend(self):
        result = FinancialMetricsAgent().run(
            raw_data(dividend_history=[], profile={"price": 100.0, "lastDividend": 2.0})
        )
        assert result["groups"]["dividends"]["dividend_yield"] == pytest.approx(0.02)

    def test_non_payer_has_no_yield(self):
        result = FinancialMetricsAgent().run(raw_data(profile={"price": 100.0}))
        assert result["groups"]["dividends"]["dividend_yield"] is None


class TestPayload:
    def test_flattened_keys_remain_available(self):
        result = FinancialMetricsAgent().run(raw_data())
        for key in ("pe_ratio", "roe", "current_ratio", "de_ratio", "revenue_growth"):
            assert key in result
            assert result[key] == result["groups"][
                next(g for g, values in result["groups"].items() if key in values)
            ][key]

    def test_empty_input_does_not_raise(self):
        result = FinancialMetricsAgent().run({})
        assert "groups" in result
        assert result["groups"]["valuation"]["pe_ratio"] is None
