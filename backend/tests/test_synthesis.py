"""
End-to-end tests for report generation.

These render a full report from agent output so that a broken reference in any
section builder fails here rather than in a background job.
"""

import pytest

from app.agents.recommendation import RecommendationEngine
from app.agents.synthesis_reporting_agent import SynthesisReportingAgent
from tests.test_recommendation import metrics_payload, sentiment_payload, technical_payload


@pytest.fixture
def raw_data() -> dict:
    return {
        "ticker": "TEST",
        "profile": {
            "companyName": "Test Co",
            "industry": "Software",
            "sector": "Technology",
            "exchangeFullName": "NASDAQ",
        },
        "prices": [{"date": "2026-08-14", "close": 100.0}],
    }


@pytest.fixture
def valuation() -> dict:
    return {
        "dcf_intrinsic_value_per_share": 120.0,
        "status": "ok",
        "method": "two-stage FCFF DCF with net-debt bridge",
        "wacc": 0.085,
        "terminal_growth_rate": 0.025,
        "fcf_growth_rate": 0.06,
        "fcf_growth_basis": "CAGR of historical unlevered FCF",
        "latest_fcf": 100_000_000,
        "latest_fcff": 107_900_000,
        "enterprise_value": 1_500_000_000,
        "equity_value": 1_200_000_000,
        "net_debt": 300_000_000,
        "total_debt": 400_000_000,
        "cash": 100_000_000,
        "shares_outstanding": 10_000_000,
        "terminal_value_share": 0.78,
        "sensitivity": {
            "wacc_values": [0.075, 0.085, 0.095],
            "terminal_growth_values": [0.02, 0.025, 0.03],
            "grid": [[130.0, 140.0, 155.0], [110.0, 120.0, 132.0], [95.0, 103.0, 112.0]],
            "low": 95.0,
            "high": 155.0,
        },
        "warnings": [],
    }


@pytest.fixture
def risk() -> dict:
    return {
        "risk_rating": "moderate",
        "annual_volatility": 0.28,
        "daily_volatility": 0.0176,
        "beta": 1.15,
        "beta_source": "regressed vs benchmark",
        "max_drawdown_pct": 22.4,
        "sharpe_ratio": 0.85,
        "sortino_ratio": 1.12,
        "annualized_return": 0.14,
        "risk_adjusted_return": 0.5,
        "var_historical_95": -2.8,
        "var_parametric_95": -2.6,
        "observations": 251,
        "window_start": "2025-08-15",
        "window_end": "2026-08-14",
    }


def render(raw_data, valuation, risk, **overrides) -> str:
    payload = {
        "metrics": metrics_payload(),
        "sentiment": sentiment_payload(),
        "technical": technical_payload(),
    }
    payload.update(overrides)
    return SynthesisReportingAgent().run(
        raw_data=raw_data, valuation=valuation, risk=risk, **payload
    )


class TestReportStructure:
    def test_all_sections_render(self, raw_data, valuation, risk):
        report = render(raw_data, valuation, risk)
        for heading in (
            "# Financial Analysis Report: Test Co (TEST)",
            "## Executive Summary",
            "## Recommendation Scorecard",
            "## Valuation Analysis",
            "## Financial Health",
            "## Growth & Cash Flow",
            "## Technical Analysis",
            "## Risk Assessment",
            "## Market Sentiment",
            "## Investment Thesis",
        ):
            assert heading in report

    def test_scorecard_lists_every_factor(self, raw_data, valuation, risk):
        report = render(raw_data, valuation, risk)
        for label in (
            "Valuation", "Profitability & Quality", "Financial Health",
            "Growth", "Price Momentum", "News Sentiment",
        ):
            assert label in report

    def test_equity_bridge_and_sensitivity_are_shown(self, raw_data, valuation, risk):
        report = render(raw_data, valuation, risk)
        assert "Enterprise → Equity Bridge" in report
        assert "Sensitivity — Value per Share" in report
        assert "Range Across Assumptions" in report

    def test_risk_window_is_stated(self, raw_data, valuation, risk):
        report = render(raw_data, valuation, risk)
        assert "2025-08-15 → 2026-08-14" in report
        assert "251 trading sessions" in report

    def test_supplied_assessment_is_used(self, raw_data, valuation, risk):
        assessment = RecommendationEngine().evaluate(
            metrics=metrics_payload(), valuation=valuation, technical=technical_payload(),
            risk=risk, sentiment=sentiment_payload(), current_price=100.0,
        )
        report = SynthesisReportingAgent().run(
            raw_data=raw_data, metrics=metrics_payload(), sentiment=sentiment_payload(),
            valuation=valuation, technical=technical_payload(), risk=risk,
            assessment=assessment,
        )
        assert assessment["recommendation"].upper() in report


class TestDegradedInputs:
    def test_renders_without_any_agent_output(self, raw_data):
        report = SynthesisReportingAgent().run(
            raw_data=raw_data, metrics={}, sentiment={}, valuation={}, technical={}, risk={},
        )
        assert "## Investment Thesis" in report
        assert "HOLD" in report

    def test_failed_dcf_is_explained_not_hidden(self, raw_data, risk):
        failed = {
            "dcf_intrinsic_value_per_share": None,
            "status": "unavailable",
            "error": "Latest unlevered free cash flow is negative.",
        }
        report = render(raw_data, failed, risk)
        assert "DCF unavailable" in report
        assert "negative" in report

    def test_missing_prices_do_not_break_rendering(self, valuation, risk):
        report = render({"ticker": "TEST", "profile": {}, "prices": []}, valuation, risk)
        assert "## Executive Summary" in report
