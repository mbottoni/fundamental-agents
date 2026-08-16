"""
Tests for the risk assessment agent.

Price series are synthesised so the expected statistics can be derived
analytically rather than eyeballed.
"""

import math
from datetime import date, timedelta

import pytest

from app.agents.risk_assessment_agent import (
    RISK_FREE_RATE_ANNUAL,
    TRADING_DAYS_PER_YEAR,
    RiskAssessmentAgent,
)


def price_series(closes: list[float], start: date | None = None) -> list[dict]:
    """Build a newest-first price series with sequential dates."""
    start = start or date(2020, 1, 1)
    records = [
        {
            "date": (start + timedelta(days=i)).isoformat(),
            "close": close,
            "high": close * 1.01,
            "low": close * 0.99,
            "volume": 1_000_000,
        }
        for i, close in enumerate(closes)
    ]
    return list(reversed(records))  # newest first, as FMP returns it


def compounding_series(days: int, daily_rate: float, start_price: float = 100.0) -> list[float]:
    """Chronological closes compounding at a fixed daily rate."""
    return [start_price * ((1 + daily_rate) ** i) for i in range(days)]


# A repeating pattern of daily moves, so the series has genuine variance to
# regress against rather than a single constant return.
MARKET_PATTERN = (0.012, -0.006, 0.004, -0.009, 0.007, 0.002, -0.011)


def varying_market(days: int, start_price: float = 100.0) -> list[float]:
    """Chronological benchmark closes with realistic day-to-day variation."""
    closes = [start_price]
    for i in range(1, days):
        closes.append(closes[-1] * (1 + MARKET_PATTERN[i % len(MARKET_PATTERN)]))
    return closes


def levered_to_market(market: list[float], multiple: float) -> list[float]:
    """A stock whose daily return is exactly `multiple` times the market's."""
    stock = [100.0]
    for i in range(1, len(market)):
        market_return = (market[i] - market[i - 1]) / market[i - 1]
        stock.append(stock[-1] * (1 + multiple * market_return))
    return stock


class TestWindowing:
    def test_statistics_use_only_the_trailing_window(self):
        """
        A crash far in the past must not define the reported drawdown — the old
        implementation measured over whatever history the API returned.
        """
        agent = RiskAssessmentAgent(lookback_days=252)
        crash = [100.0] * 100 + [30.0] + [100.0] * 100  # -70% early on
        recent = compounding_series(300, 0.0005, start_price=100.0)
        raw = {"prices": price_series(crash + recent)}

        result = agent.run(raw)
        assert result["max_drawdown_pct"] < 5.0
        assert result["observations"] <= 252

    def test_window_bounds_are_reported(self):
        agent = RiskAssessmentAgent(lookback_days=100)
        result = agent.run({"prices": price_series(compounding_series(400, 0.0003))})
        assert result["window_start"] < result["window_end"]
        assert result["observations"] == 100

    def test_insufficient_history_is_reported(self):
        result = RiskAssessmentAgent().run({"prices": price_series([100.0] * 10)})
        assert result["risk_rating"] == "unknown"
        assert "error" in result


class TestAnnualizedReturn:
    def test_multi_year_history_is_annualized_not_summed(self):
        """
        Ten percent a year for three years is a 10% annualized return, not 33%.
        The previous implementation returned the cumulative figure.
        """
        agent = RiskAssessmentAgent(lookback_days=756)
        daily = (1.10) ** (1 / TRADING_DAYS_PER_YEAR) - 1
        result = agent.run({"prices": price_series(compounding_series(757, daily))})
        assert result["annualized_return"] == pytest.approx(0.10, abs=0.005)

    def test_flat_prices_give_zero_return(self):
        agent = RiskAssessmentAgent()
        result = agent.run({"prices": price_series([100.0] * 300)})
        assert result["annualized_return"] == pytest.approx(0.0, abs=1e-9)

    def test_risk_adjusted_return_needs_volatility(self):
        agent = RiskAssessmentAgent()
        assert agent.compute_risk_adjusted_return(0.12, 0.0) is None
        assert agent.compute_risk_adjusted_return(None, 0.2) is None
        assert agent.compute_risk_adjusted_return(0.12, 0.24) == pytest.approx(0.5)


class TestSortino:
    def test_downside_deviation_is_measured_against_the_target(self):
        """
        Two series with identically-sized losses: the one whose losses are more
        tightly clustered must not look safer. Measuring the standard deviation
        of the downside subset (the old behaviour) made clustered losses appear
        to have near-zero downside risk.
        """
        agent = RiskAssessmentAgent()
        clustered = [0.01, -0.02] * 60
        expected_dd = math.sqrt(
            sum(min(0.0, r - RISK_FREE_RATE_ANNUAL / TRADING_DAYS_PER_YEAR) ** 2 for r in clustered)
            / len(clustered)
        )
        sortino = agent.compute_sortino_ratio(clustered)

        mean = sum(clustered) / len(clustered)
        daily_rf = RISK_FREE_RATE_ANNUAL / TRADING_DAYS_PER_YEAR
        expected = ((mean - daily_rf) / expected_dd) * math.sqrt(TRADING_DAYS_PER_YEAR)
        assert sortino == pytest.approx(round(expected, 3))

    def test_no_downside_returns_none(self):
        agent = RiskAssessmentAgent()
        assert agent.compute_sortino_ratio([0.01] * 100) is None

    def test_short_series_returns_none(self):
        agent = RiskAssessmentAgent()
        assert agent.compute_sortino_ratio([0.01, -0.01] * 5) is None


class TestBeta:
    def test_beta_is_regressed_against_the_benchmark(self):
        """A stock that moves exactly twice the benchmark has a beta of 2."""
        agent = RiskAssessmentAgent()
        market = varying_market(300)
        stock = levered_to_market(market, 2.0)

        beta, source = agent.compute_beta(
            price_series(stock), price_series(market), {"beta": 0.5},
        )
        assert beta == pytest.approx(2.0, abs=0.01)
        assert source == "regressed vs benchmark"

    def test_flat_benchmark_falls_back_instead_of_dividing_by_noise(self):
        agent = RiskAssessmentAgent()
        flat_market = price_series([100.0] * 300)
        beta, source = agent.compute_beta(
            price_series(compounding_series(300, 0.001)), flat_market, {"beta": 0.9},
        )
        assert beta == 0.9
        assert source == "company profile"

    def test_falls_back_to_profile_beta(self):
        agent = RiskAssessmentAgent()
        beta, source = agent.compute_beta(price_series([100.0] * 300), [], {"beta": 1.23})
        assert beta == 1.23
        assert source == "company profile"

    def test_unavailable_when_no_source(self):
        agent = RiskAssessmentAgent()
        beta, source = agent.compute_beta(price_series([100.0] * 300), [], {})
        assert beta is None
        assert source == "unavailable"

    def test_misaligned_dates_do_not_corrupt_the_regression(self):
        """Only dates present in both series should be paired."""
        agent = RiskAssessmentAgent()
        market = varying_market(300)
        stock = levered_to_market(market, 2.0)

        market_prices = price_series(market)
        # Drop a scattering of benchmark sessions, as a holiday mismatch would.
        thinned = [p for i, p in enumerate(market_prices) if i % 7]

        beta, source = agent.compute_beta(price_series(stock), thinned, None)
        assert source == "regressed vs benchmark"
        assert beta == pytest.approx(2.0, abs=0.05)


class TestPayload:
    def test_keys_consumed_downstream_are_present(self):
        agent = RiskAssessmentAgent()
        result = agent.run({"prices": price_series(compounding_series(300, 0.0004))})
        for key in (
            "risk_rating", "annual_volatility", "sharpe_ratio", "sortino_ratio",
            "max_drawdown_pct", "beta", "var_historical_95",
        ):
            assert key in result

    def test_risk_rating_escalates_with_volatility(self):
        agent = RiskAssessmentAgent()
        calm = agent._risk_rating(0.10, 5.0, 0.8)
        wild = agent._risk_rating(0.65, 60.0, 2.0)
        assert calm == "low"
        assert wild == "very_high"
