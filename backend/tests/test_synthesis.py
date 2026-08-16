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


class TestPeerSection:
    @pytest.fixture
    def peers(self) -> dict:
        return {
            "peer_count": 3,
            "peers": [
                {"symbol": "AAA", "name": "AAA Corp", "market_cap": 1e11},
                {"symbol": "BBB", "name": "BBB Corp", "market_cap": 2e11},
                {"symbol": "CCC", "name": "CCC Corp", "market_cap": 3e11},
            ],
            "comparisons": [
                {"key": "pe_ratio", "label": "P/E", "company": 35.0, "peer_median": 40.0,
                 "premium_discount": -0.125, "percentile": 66.7, "lower_is_better": True,
                 "verdict": "13% below the peer median"},
                {"key": "operating_margin", "label": "Operating Margin", "company": 0.28,
                 "peer_median": 0.30, "premium_discount": -0.067, "percentile": 33.3,
                 "lower_is_better": False, "verdict": "in line with peers"},
            ],
            "sector": {"sector": "Technology", "industry": "Software", "sector_pe": 46.6,
                       "industry_pe": 35.0, "vs_sector_pe": -0.25, "vs_industry_pe": 0.0,
                       "as_of": "2026-08-14"},
            "relative_valuation_score": 0.31,
            "summary": "Against 3 peers the company trades at a discount to its peer group.",
        }

    def test_peer_table_and_benchmarks_render(self, raw_data, valuation, risk, peers):
        report = SynthesisReportingAgent().run(
            raw_data=raw_data, metrics=metrics_payload(), sentiment=sentiment_payload(),
            valuation=valuation, technical=technical_payload(), risk=risk, peers=peers,
        )
        assert "## Peer & Sector Comparison" in report
        assert "AAA" in report and "BBB" in report
        assert "Peer Median" in report
        assert "Technology sector P/E" in report
        assert "2026-08-14" in report

    def test_sector_comparison_states_which_way_it_runs(self, raw_data, valuation, risk, peers):
        report = SynthesisReportingAgent().run(
            raw_data=raw_data, metrics=metrics_payload(), sentiment=sentiment_payload(),
            valuation=valuation, technical=technical_payload(), risk=risk, peers=peers,
        )
        # vs_sector_pe of -0.25 means the company is below the sector.
        assert "the company trades 25% below" in report
        # vs_industry_pe of 0.0 is in line.
        assert "the company trades in line" in report

    def test_margins_render_as_percentages(self, raw_data, valuation, risk, peers):
        report = SynthesisReportingAgent().run(
            raw_data=raw_data, metrics=metrics_payload(), sentiment=sentiment_payload(),
            valuation=valuation, technical=technical_payload(), risk=risk, peers=peers,
        )
        assert "28.00%" in report

    def test_missing_peers_are_explained(self, raw_data, valuation, risk):
        report = SynthesisReportingAgent().run(
            raw_data=raw_data, metrics=metrics_payload(), sentiment=sentiment_payload(),
            valuation=valuation, technical=technical_payload(), risk=risk,
            peers={"error": "No comparable companies were available for this ticker."},
        )
        assert "No comparable companies" in report

    def test_report_renders_without_peer_data_at_all(self, raw_data, valuation, risk):
        report = render(raw_data, valuation, risk)
        assert "## Peer & Sector Comparison" in report


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
