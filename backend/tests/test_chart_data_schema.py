"""
The chart payload schema must describe what the pipeline actually emits.

`_build_chart_data` used to return a bare dict whose shape was mirrored by hand
in the frontend's TypeScript. Nothing enforced the mirror and nothing failed
when it drifted — the chart just rendered empty.

Now that the shape is declared, a wrong field name is worse than useless: it
would be *dropped* on serialization, so these tests assert that validating a
real payload preserves every value in it.
"""

from typing import Any

import pytest

from app.agents.orchestrator import Orchestrator
from app.schemas.chart_data import ChartData


def _assert_preserved(source: Any, result: Any, path: str = "") -> None:
    """Every key and value in `source` must survive into `result` unchanged."""
    if isinstance(source, dict):
        assert isinstance(result, dict), f"{path}: expected a dict, got {type(result)}"
        for key, value in source.items():
            assert key in result, f"{path}.{key} was dropped by the schema"
            _assert_preserved(value, result[key], f"{path}.{key}")
    elif isinstance(source, list):
        assert isinstance(result, list), f"{path}: expected a list"
        assert len(source) == len(result), f"{path}: length changed"
        for i, item in enumerate(source):
            _assert_preserved(item, result[i], f"{path}[{i}]")
    else:
        assert source == result, f"{path}: {source!r} became {result!r}"


@pytest.fixture
def built_payload() -> dict:
    """What the orchestrator emits for a company with complete data."""
    orchestrator = Orchestrator("AAPL")
    return orchestrator._build_chart_data(
        raw_data={
            "profile": {"companyName": "Apple Inc."},
            "prices": [
                {"date": "2026-03-02", "close": 190.5, "high": 191.0, "low": 188.0, "volume": 5_000_000},
                {"date": "2026-03-01", "close": 188.0, "high": 189.0, "low": 187.0, "volume": 4_000_000},
            ],
            "revenue_segments": {
                "product": [{"date": "2025-09-30", "iPhone": 200_000, "Mac": 40_000}],
                "geographic": [{"date": "2025-09-30", "Americas": 150_000}],
            },
            "dividend_history": [{"date": "2026-02-10", "dividend": 0.25}],
        },
        metrics={
            "groups": {
                "profitability": {
                    "gross_margin": 0.45, "operating_margin": 0.30, "net_margin": 0.25,
                    "roe": 1.5, "roa": 0.28, "roic": 0.55,
                },
                "valuation": {
                    "pe_ratio": 30.1, "pb_ratio": 45.0, "ps_ratio": 7.5,
                    "ev_ebitda": 22.0, "peg_ratio": 2.4,
                },
                "growth": {"revenue_growth": 0.08, "net_income_growth": 0.11, "eps_growth": 0.13},
                "liquidity": {"current_ratio": 1.1, "quick_ratio": 0.9},
                "leverage": {"de_ratio": 1.8, "interest_coverage": 25.0},
            },
        },
        technical={
            "rsi": 58.2,
            "atr": 3.4,
            "moving_averages": {"sma_20": 189.0, "sma_50": 185.0, "sma_200": 175.0},
            "bollinger_bands": {"upper": 195.0, "lower": 180.0, "middle": 187.5},
            "macd": {"macd_line": 1.2, "signal_line": 0.9, "macd_histogram": 0.3},
            "volume_profile": {"avg_volume": 4_500_000, "relative_volume": 1.1},
            "momentum": {
                "price_momentum_1m": 0.04,
                "price_momentum_3m": 0.09,
                "price_momentum_6m": 0.15,
            },
            "trend_signals": ["Golden cross", "Above 200-day"],
            "support_resistance": {"support": 180.0, "resistance": 196.0},
        },
        risk={
            "risk_rating": "Moderate",
            "annual_volatility": 0.27,
            "sharpe_ratio": 1.1,
            "sortino_ratio": 1.4,
            "max_drawdown_pct": -18.2,
            "beta": 1.15,
            "var_historical_95": -0.031,
            "annualized_return": 0.19,
            "window_start": "2025-03-01",
            "window_end": "2026-03-01",
        },
        sentiment={
            "positive_articles_count": 7,
            "neutral_articles_count": 3,
            "negative_articles_count": 2,
            "average_sentiment_compound": 0.31,
        },
        valuation={
            "dcf_intrinsic_value_per_share": 205.0,
            "wacc": 0.085,
            "sensitivity": {"low": 170.0, "high": 250.0},
            "net_debt": -50_000,
            "status": "ok",
            "error": None,
        },
        assessment={
            "recommendation": "BUY",
            "composite_score": 71.5,
            "confidence": 80,
            "rationale": "Quality compounder at a fair price.",
            "coverage": 0.9,
            "factors": [
                {
                    "key": "valuation",
                    "label": "Valuation",
                    "weight": 0.3,
                    "score": 62.0,
                    "drivers": ["DCF suggests 8% upside"],
                },
            ],
        },
        peers={
            "peer_count": 3,
            "peers": [{"symbol": "MSFT", "name": "Microsoft", "market_cap": 3.1e12}],
            "comparisons": [
                {
                    "key": "pe_ratio",
                    "label": "P/E",
                    "company": 30.1,
                    "peer_median": 27.0,
                    "premium_discount": 0.115,
                    "percentile": 0.66,
                    "lower_is_better": True,
                    "verdict": "12% above the peer median",
                },
            ],
            "sector": {
                "sector": "Technology",
                "industry": "Consumer Electronics",
                "sector_pe": 28.0,
                "industry_pe": 26.0,
                "vs_sector_pe": 0.075,
                "vs_industry_pe": 0.157,
                "as_of": "2026-03-01",
            },
            "relative_valuation_score": 58.0,
            "summary": "Slightly expensive against peers.",
        },
        earnings={
            "available": True,
            "next_date": "2026-04-28",
            "days_until": 57,
            "is_imminent": False,
            "eps_estimate": 1.55,
            "beat_rate": 0.75,
            "reports_assessed": 4,
            "recent_surprises": [
                {
                    "date": "2026-01-30",
                    "eps_actual": 2.4,
                    "eps_estimated": 2.35,
                    "surprise_pct": 0.021,
                },
            ],
        },
    )


class TestSchemaMatchesProducer:
    def test_a_complete_payload_validates(self, built_payload):
        ChartData.model_validate(built_payload)

    def test_no_field_is_dropped(self, built_payload):
        """
        The failure this guards against: a field named wrongly in the schema is
        silently discarded on serialization, and the chart renders empty.
        """
        result = ChartData.model_validate(built_payload).model_dump()
        _assert_preserved(built_payload, result)


class TestSchemaToleratesThinData:
    """
    The pipeline already copes with partial provider data. Declaring a shape
    must not turn a thin report into a failed analysis.
    """

    def test_a_minimal_payload_validates(self):
        orchestrator = Orchestrator("XYZ")
        payload = orchestrator._build_chart_data(
            raw_data={}, metrics={}, technical={}, risk={}, sentiment={},
            valuation={}, assessment={}, peers={}, earnings={},
        )
        ChartData.model_validate(payload)

    def test_an_out_of_plan_earnings_section_validates(self):
        """EarningsAgent returns just {available, note} when data is missing."""
        ChartData.model_validate(
            {"ticker": "XYZ", "earnings": {"available": False, "note": "No data."}}
        )

    def test_unknown_extra_keys_do_not_raise(self):
        """A new field added upstream must not break existing deployments."""
        ChartData.model_validate({"ticker": "XYZ", "something_new": 1})
