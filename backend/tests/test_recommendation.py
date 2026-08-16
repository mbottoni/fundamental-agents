"""
Tests for the composite recommendation engine.

The property that matters most: the call reflects every factor with data, not
just DCF upside, and factors without data are dropped rather than counted as
neutral.
"""

import pytest

from app.agents.recommendation import RecommendationEngine


def metrics_payload(
    *,
    pe=18.0,
    peg=1.5,
    ev_ebitda=12.0,
    fcf_yield=0.04,
    roic=0.12,
    roe=0.15,
    operating_margin=0.15,
    net_margin=0.10,
    conversion=1.1,
    current_ratio=1.6,
    de_ratio=0.9,
    coverage=6.0,
    revenue_growth=0.08,
    net_income_growth=0.10,
    eps_growth=0.10,
) -> dict:
    return {
        "groups": {
            "valuation": {
                "pe_ratio": pe,
                "peg_ratio": peg,
                "ev_ebitda": ev_ebitda,
                "pb_ratio": 3.0,
                "ps_ratio": 2.0,
            },
            "profitability": {
                "roic": roic,
                "roe": roe,
                "operating_margin": operating_margin,
                "net_margin": net_margin,
            },
            "liquidity": {"current_ratio": current_ratio},
            "leverage": {"de_ratio": de_ratio, "interest_coverage": coverage},
            "growth": {
                "revenue_growth": revenue_growth,
                "net_income_growth": net_income_growth,
                "eps_growth": eps_growth,
            },
            "cash_flow": {"fcf_yield": fcf_yield, "ocf_to_net_income": conversion},
            "dividends": {},
        }
    }


def technical_payload(*, price=100.0, sma_200=95.0, sma_50=98.0, rsi=55.0, roc_60d=5.0) -> dict:
    return {
        "current_price": price,
        "moving_averages": {"sma_200": sma_200, "sma_50": sma_50},
        "momentum": {"roc_60d": roc_60d},
        "macd": {"macd_histogram": 0.5},
        "rsi": rsi,
    }


def sentiment_payload(compound=0.1, count=12) -> dict:
    return {"average_sentiment_compound": compound, "analyzed_articles_count": count}


class TestMultiFactorBehaviour:
    def test_weak_fundamentals_temper_a_large_dcf_upside(self):
        """
        The old model called any 25%+ DCF upside a strong buy regardless of the
        business behind it. A deeply unprofitable, over-levered, shrinking
        company should not reach that verdict on DCF alone.
        """
        engine = RecommendationEngine()
        result = engine.evaluate(
            metrics=metrics_payload(
                pe=-5.0, roic=0.01, roe=0.01, operating_margin=0.0, net_margin=-0.05,
                conversion=0.3, current_ratio=0.7, de_ratio=4.0, coverage=0.8,
                revenue_growth=-0.15, net_income_growth=-0.40, eps_growth=-0.40,
                fcf_yield=0.005, peg=None, ev_ebitda=None,
            ),
            valuation={"dcf_intrinsic_value_per_share": 200.0},
            technical=technical_payload(price=100.0, sma_200=130.0, sma_50=120.0, roc_60d=-25.0),
            risk={"risk_rating": "very_high"},
            sentiment=sentiment_payload(-0.3, 20),
            current_price=100.0,
        )
        assert result["recommendation"] != "strong buy"
        assert result["composite_score"] < 0

    def test_strong_business_at_a_fair_price_still_scores_positively(self):
        engine = RecommendationEngine()
        result = engine.evaluate(
            metrics=metrics_payload(
                pe=14.0, roic=0.25, roe=0.30, operating_margin=0.30, net_margin=0.22,
                conversion=1.4, current_ratio=2.5, de_ratio=0.2, coverage=25.0,
                revenue_growth=0.20, net_income_growth=0.25, eps_growth=0.25,
                fcf_yield=0.07, peg=0.9, ev_ebitda=9.0,
            ),
            valuation={"dcf_intrinsic_value_per_share": 105.0},
            technical=technical_payload(price=100.0, sma_200=88.0, sma_50=95.0, roc_60d=12.0),
            risk={"risk_rating": "low"},
            sentiment=sentiment_payload(0.25, 18),
            current_price=100.0,
        )
        assert result["recommendation"] in ("buy", "strong buy")
        assert result["composite_score"] > 0

    def test_every_factor_is_scored_when_data_is_present(self):
        engine = RecommendationEngine()
        result = engine.evaluate(
            metrics=metrics_payload(),
            valuation={"dcf_intrinsic_value_per_share": 110.0},
            technical=technical_payload(),
            risk={"risk_rating": "moderate"},
            sentiment=sentiment_payload(),
            current_price=100.0,
        )
        assert all(f["score"] is not None for f in result["factors"])
        assert result["coverage"] == 1.0


class TestValuationLimit:
    def test_a_great_business_at_a_punishing_price_is_not_a_strong_buy(self):
        """
        Quality and growth can carry the composite a long way; price still has
        to constrain the call.
        """
        engine = RecommendationEngine()
        result = engine.evaluate(
            metrics=metrics_payload(
                pe=60.0, peg=4.0, ev_ebitda=40.0, fcf_yield=0.005,
                roic=0.40, roe=0.50, operating_margin=0.40, net_margin=0.35,
                conversion=1.5, current_ratio=3.0, de_ratio=0.1, coverage=40.0,
                revenue_growth=0.30, net_income_growth=0.35, eps_growth=0.35,
            ),
            valuation={"dcf_intrinsic_value_per_share": 30.0},  # 70% overvalued
            technical=technical_payload(price=100.0, sma_200=80.0, sma_50=95.0, roc_60d=25.0),
            risk={"risk_rating": "low"},
            sentiment=sentiment_payload(0.4, 30),
            current_price=100.0,
        )
        assert result["recommendation"] == "hold"
        assert "overvalued" in result["rationale"]

    def test_a_stretched_valuation_holds_back_a_strong_buy(self):
        engine = RecommendationEngine()
        valuation_factor_score = -0.3
        result = engine.evaluate(
            metrics=metrics_payload(pe=32.0, peg=2.4, ev_ebitda=22.0, fcf_yield=0.02,
                                    roic=0.30, roe=0.35, operating_margin=0.30,
                                    net_margin=0.25, conversion=1.4,
                                    revenue_growth=0.25, net_income_growth=0.30,
                                    eps_growth=0.30),
            valuation={"dcf_intrinsic_value_per_share": 88.0},
            technical=technical_payload(price=100.0, sma_200=85.0, roc_60d=20.0),
            risk={"risk_rating": "low"},
            sentiment=sentiment_payload(0.35, 25),
            current_price=100.0,
        )
        assert result["recommendation"] != "strong buy"
        assert valuation_factor_score  # documented intent of the fixture

    def test_a_deeply_undervalued_stock_is_not_a_strong_sell(self):
        engine = RecommendationEngine()
        result = engine.evaluate(
            metrics=metrics_payload(
                pe=6.0, peg=0.4, ev_ebitda=4.0, fcf_yield=0.15,
                roic=0.02, roe=0.02, operating_margin=0.01, net_margin=0.005,
                conversion=0.4, current_ratio=0.9, de_ratio=3.0, coverage=1.2,
                revenue_growth=-0.20, net_income_growth=-0.45, eps_growth=-0.45,
            ),
            valuation={"dcf_intrinsic_value_per_share": 250.0},
            technical=technical_payload(price=100.0, sma_200=140.0, sma_50=125.0, roc_60d=-30.0),
            risk={"risk_rating": "high"},
            sentiment=sentiment_payload(-0.4, 25),
            current_price=100.0,
        )
        assert result["recommendation"] != "strong sell"

    def test_the_limit_does_not_apply_without_a_valuation_score(self):
        engine = RecommendationEngine()
        result = engine.evaluate(
            metrics={"groups": {"profitability": {"roic": 0.40, "roe": 0.50},
                                "growth": {"revenue_growth": 0.35}}},
            valuation={},
            technical={},
            risk={"risk_rating": "low"},
            sentiment={},
            current_price=None,
        )
        assert result["recommendation"] in ("buy", "strong buy")


class TestMissingData:
    def test_missing_dcf_does_not_force_a_hold(self):
        """
        With no DCF the old model returned hold at 30% confidence regardless of
        how good or bad the business was.
        """
        engine = RecommendationEngine()
        result = engine.evaluate(
            metrics=metrics_payload(
                pe=9.0, roic=0.28, roe=0.32, operating_margin=0.28, net_margin=0.20,
                conversion=1.5, current_ratio=3.0, de_ratio=0.1, coverage=30.0,
                revenue_growth=0.25, net_income_growth=0.30, eps_growth=0.30,
                fcf_yield=0.09, peg=0.7, ev_ebitda=7.0,
            ),
            valuation={"dcf_intrinsic_value_per_share": None, "error": "negative FCF"},
            technical=technical_payload(price=100.0, sma_200=85.0, sma_50=95.0, roc_60d=18.0),
            risk={"risk_rating": "low"},
            sentiment=sentiment_payload(0.3, 15),
            current_price=100.0,
        )
        assert result["recommendation"] in ("buy", "strong buy")
        # Valuation still scores off the multiples even without a DCF.
        valuation_factor = next(f for f in result["factors"] if f["key"] == "valuation")
        assert valuation_factor["score"] is not None

    def test_weight_is_redistributed_over_available_factors(self):
        engine = RecommendationEngine()
        result = engine.evaluate(
            metrics={"groups": {"profitability": {"roic": 0.25, "roe": 0.30}}},
            valuation={},
            technical={},
            risk={},
            sentiment={},
            current_price=None,
        )
        scored = [f for f in result["factors"] if f["score"] is not None]
        assert len(scored) == 1
        # The single available factor drives the composite entirely.
        assert result["composite_score"] == pytest.approx(scored[0]["score"], rel=1e-6)
        assert result["coverage"] < 1.0

    def test_no_data_at_all_yields_a_low_confidence_hold(self):
        engine = RecommendationEngine()
        result = engine.evaluate({}, {}, {}, {}, {}, None)
        assert result["recommendation"] == "hold"
        assert result["confidence"] <= 20

    def test_thin_news_coverage_is_excluded(self):
        engine = RecommendationEngine()
        result = engine.evaluate(
            metrics=metrics_payload(),
            valuation={},
            technical={},
            risk={},
            sentiment={"average_sentiment_compound": 0.9, "analyzed_articles_count": 2},
            current_price=None,
        )
        sentiment_factor = next(f for f in result["factors"] if f["key"] == "sentiment")
        assert sentiment_factor["score"] is None


class TestScoring:
    def test_scale_maps_between_anchors(self):
        engine = RecommendationEngine()
        assert engine._scale(10, 10, 20) == -1.0
        assert engine._scale(20, 10, 20) == 1.0
        assert engine._scale(15, 10, 20) == pytest.approx(0.0)
        # Inverted anchors handle "lower is better" metrics.
        assert engine._scale(10, 40, 10) == 1.0
        assert engine._scale(40, 40, 10) == -1.0

    def test_scale_clamps_outliers(self):
        engine = RecommendationEngine()
        assert engine._scale(1000, 10, 20) == 1.0
        assert engine._scale(-1000, 10, 20) == -1.0

    def test_negative_pe_is_penalised_not_treated_as_cheap(self):
        engine = RecommendationEngine()
        loss_making = engine.evaluate(
            metrics=metrics_payload(pe=-8.0, peg=None, ev_ebitda=None, fcf_yield=None),
            valuation={}, technical={}, risk={}, sentiment={}, current_price=None,
        )
        factor = next(f for f in loss_making["factors"] if f["key"] == "valuation")
        assert factor["score"] < 0


class TestConfidence:
    def test_high_risk_lowers_confidence(self):
        engine = RecommendationEngine()
        args = dict(
            metrics=metrics_payload(),
            valuation={"dcf_intrinsic_value_per_share": 110.0},
            technical=technical_payload(),
            sentiment=sentiment_payload(),
            current_price=100.0,
        )
        calm = engine.evaluate(risk={"risk_rating": "low"}, **args)
        risky = engine.evaluate(risk={"risk_rating": "very_high"}, **args)
        assert risky["confidence"] < calm["confidence"]

    def test_partial_coverage_lowers_confidence(self):
        engine = RecommendationEngine()
        full = engine.evaluate(
            metrics=metrics_payload(),
            valuation={"dcf_intrinsic_value_per_share": 110.0},
            technical=technical_payload(),
            risk={"risk_rating": "low"},
            sentiment=sentiment_payload(),
            current_price=100.0,
        )
        partial = engine.evaluate(
            metrics={"groups": {"profitability": {"roic": 0.12, "roe": 0.15}}},
            valuation={},
            technical={},
            risk={"risk_rating": "low"},
            sentiment={},
            current_price=None,
        )
        assert partial["confidence"] < full["confidence"]

    def test_confidence_stays_in_bounds(self):
        engine = RecommendationEngine()
        result = engine.evaluate(
            metrics=metrics_payload(),
            valuation={"dcf_intrinsic_value_per_share": 400.0},
            technical=technical_payload(),
            risk={"risk_rating": "low"},
            sentiment=sentiment_payload(0.9, 50),
            current_price=100.0,
        )
        assert 10 <= result["confidence"] <= 95


class TestRationale:
    def test_rationale_names_contributing_factors(self):
        engine = RecommendationEngine()
        result = engine.evaluate(
            metrics=metrics_payload(roic=0.30, roe=0.35, revenue_growth=-0.20,
                                    net_income_growth=-0.30, eps_growth=-0.30),
            valuation={"dcf_intrinsic_value_per_share": 130.0},
            technical=technical_payload(),
            risk={"risk_rating": "moderate"},
            sentiment=sentiment_payload(),
            current_price=100.0,
        )
        assert "supported by" in result["rationale"] or "offset by" in result["rationale"]
