"""
Tests for the earnings agent and its effect on confidence.
"""

from datetime import date, timedelta

import pytest

from app.agents.earnings_agent import EarningsAgent
from app.agents.recommendation import RecommendationEngine
from tests.test_recommendation import metrics_payload, sentiment_payload, technical_payload


TODAY = date(2026, 8, 16)


def entry(day: date, actual=None, estimated=None) -> dict:
    return {
        "symbol": "AAPL",
        "date": day.isoformat(),
        "epsActual": actual,
        "epsEstimated": estimated,
        "revenueEstimated": 1.1e11,
    }


class TestNextReport:
    def test_the_soonest_upcoming_date_is_chosen(self):
        raw = {
            "earnings": [
                entry(TODAY + timedelta(days=60), estimated=2.1),
                entry(TODAY + timedelta(days=5), estimated=1.98),
                entry(TODAY - timedelta(days=30), actual=2.02, estimated=1.95),
            ]
        }
        result = EarningsAgent().run(raw, today=TODAY)
        assert result["next_date"] == (TODAY + timedelta(days=5)).isoformat()
        assert result["days_until"] == 5
        assert result["is_imminent"] is True

    def test_a_distant_report_is_not_imminent(self):
        raw = {"earnings": [entry(TODAY + timedelta(days=70), estimated=2.0)]}
        result = EarningsAgent().run(raw, today=TODAY)
        assert result["is_imminent"] is False

    def test_reported_quarters_are_not_treated_as_upcoming(self):
        """A row with an actual EPS has already happened."""
        raw = {"earnings": [entry(TODAY - timedelta(days=2), actual=2.0, estimated=1.9)]}
        result = EarningsAgent().run(raw, today=TODAY)
        assert result["next_date"] is None
        assert result["is_imminent"] is False

    def test_missing_data_is_reported_not_guessed(self):
        result = EarningsAgent().run({}, today=TODAY)
        assert result["available"] is False


class TestSurpriseRecord:
    def test_beat_rate_counts_only_scoreable_reports(self):
        raw = {
            "earnings": [
                entry(TODAY - timedelta(days=30), actual=2.0, estimated=1.8),   # beat
                entry(TODAY - timedelta(days=120), actual=1.5, estimated=1.6),  # miss
                entry(TODAY - timedelta(days=210), actual=1.4, estimated=None), # unscoreable
            ]
        }
        result = EarningsAgent().run(raw, today=TODAY)
        assert result["reports_assessed"] == 2
        assert result["beat_rate"] == 0.5

    def test_surprise_percentage_is_relative_to_the_estimate(self):
        raw = {"earnings": [entry(TODAY - timedelta(days=30), actual=2.2, estimated=2.0)]}
        surprise = EarningsAgent().run(raw, today=TODAY)["recent_surprises"][0]
        assert surprise["surprise_pct"] == pytest.approx(0.10)

    def test_history_is_newest_first(self):
        raw = {
            "earnings": [
                entry(TODAY - timedelta(days=200), actual=1.0, estimated=1.0),
                entry(TODAY - timedelta(days=20), actual=2.0, estimated=1.8),
            ]
        }
        dates = [s["date"] for s in EarningsAgent().run(raw, today=TODAY)["recent_surprises"]]
        assert dates == sorted(dates, reverse=True)

    def test_malformed_rows_are_skipped(self):
        raw = {"earnings": [{"date": "not-a-date"}, "junk", entry(TODAY + timedelta(days=3), estimated=1.0)]}
        result = EarningsAgent().run(raw, today=TODAY)
        assert result["days_until"] == 3


class TestConfidenceEffect:
    def _evaluate(self, earnings):
        return RecommendationEngine().evaluate(
            metrics=metrics_payload(),
            valuation={"dcf_intrinsic_value_per_share": 110.0},
            technical=technical_payload(),
            risk={"risk_rating": "low"},
            sentiment=sentiment_payload(),
            current_price=100.0,
            earnings=earnings,
        )

    def test_imminent_results_lower_confidence(self):
        """
        A call made days before results rests on numbers about to be replaced.
        """
        quiet = self._evaluate({"is_imminent": False, "days_until": 60})
        imminent = self._evaluate({"is_imminent": True, "days_until": 3})
        assert imminent["confidence"] < quiet["confidence"]

    def test_the_reason_is_stated_in_the_rationale(self):
        result = self._evaluate({"is_imminent": True, "days_until": 3})
        assert "earnings due in 3 days" in result["rationale"]

    def test_absent_earnings_data_changes_nothing(self):
        assert self._evaluate(None) == self._evaluate({})
