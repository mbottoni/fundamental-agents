"""
Recommendation Engine
=====================
Turns the output of every analysis agent into a single buy/hold/sell call.

The recommendation used to be derived entirely from DCF upside, with the other
agents only nudging a confidence number — so a report that claimed to combine
valuation, quality, growth, technicals and sentiment was in practice a
one-input model wrapped in prose.

Here each factor is scored on a common [-1, +1] scale, weighted, and combined.
Factors whose inputs are missing are dropped and their weight redistributed
across the rest, so a company with no DCF is still assessed on everything else
rather than defaulting to "hold". Every factor reports the drivers behind its
score, which the report renders as a scorecard.
"""

import logging
from typing import Any, Optional

logger = logging.getLogger("stock_analyzer.agents.recommendation")

Number = float


class Factor:
    """One scored dimension of the investment case."""

    def __init__(self, key: str, label: str, weight: float) -> None:
        self.key = key
        self.label = label
        self.weight = weight
        self.score: Optional[float] = None
        self.drivers: list[str] = []

    @property
    def available(self) -> bool:
        return self.score is not None

    def as_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "label": self.label,
            "weight": self.weight,
            "score": round(self.score, 3) if self.score is not None else None,
            "drivers": self.drivers,
        }


class RecommendationEngine:
    """Scores an investment case across weighted factors."""

    # ── factor weights (renormalised over whatever is available) ──
    WEIGHTS = {
        "valuation": 0.30,
        "quality": 0.20,
        "financial_health": 0.15,
        "growth": 0.15,
        "momentum": 0.10,
        "sentiment": 0.10,
    }

    # ── composite score → recommendation ──────────────────────
    STRONG_BUY_THRESHOLD = 0.35
    BUY_THRESHOLD = 0.12
    SELL_THRESHOLD = -0.12
    STRONG_SELL_THRESHOLD = -0.35

    # A sentiment read on a handful of articles is noise.
    MIN_ARTICLES_FOR_SENTIMENT = 5

    # However good a business is, price still constrains the call: no "strong
    # buy" on something the valuation work says is badly overpriced, and no
    # "strong sell" on something it says is deeply discounted.
    VALUATION_VETO_THRESHOLD = -0.50
    VALUATION_CAUTION_THRESHOLD = -0.25
    RANK = ["strong sell", "sell", "hold", "buy", "strong buy"]

    # ── scoring helpers ───────────────────────────────────────

    @staticmethod
    def _scale(value: Optional[Number], bad: Number, good: Number) -> Optional[float]:
        """
        Map a metric onto [-1, +1] by linear interpolation between a `bad` and
        a `good` anchor. Works in either direction: pass bad > good for metrics
        where lower is better (P/E, debt-to-equity).
        """
        if value is None or bad == good:
            return None
        try:
            position = (float(value) - bad) / (good - bad)
        except (TypeError, ValueError, ZeroDivisionError):
            return None
        return max(-1.0, min(1.0, position * 2 - 1))

    @staticmethod
    def _blend(components: list[tuple[float, float]]) -> Optional[float]:
        """Weighted mean of (score, weight) pairs, ignoring missing components."""
        usable = [(s, w) for s, w in components if s is not None]
        if not usable:
            return None
        total_weight = sum(w for _, w in usable)
        if total_weight == 0:
            return None
        return sum(s * w for s, w in usable) / total_weight

    @staticmethod
    def _describe(score: float) -> str:
        if score >= 0.5:
            return "strong"
        if score >= 0.15:
            return "favourable"
        if score > -0.15:
            return "neutral"
        if score > -0.5:
            return "weak"
        return "poor"

    # ── individual factors ────────────────────────────────────

    def _score_valuation(
        self, factor: Factor, metrics: dict, valuation: dict, current_price: Optional[Number]
    ) -> None:
        groups = metrics.get("groups", {})
        multiples = groups.get("valuation", {})
        cash_flow = groups.get("cash_flow", {})
        components: list[tuple[Optional[float], float]] = []

        # DCF upside carries the most weight within the factor, but no longer
        # decides the recommendation on its own.
        dcf = valuation.get("dcf_intrinsic_value_per_share")
        if dcf is not None and current_price:
            upside = (dcf - current_price) / current_price
            components.append((self._scale(upside, -0.30, 0.30), 0.40))
            factor.drivers.append(f"DCF implies {upside:+.0%} vs. the current price")

        pe = multiples.get("pe_ratio")
        if pe is not None:
            # A negative P/E means the company is loss-making, which the linear
            # scale would otherwise read as extremely cheap.
            score = -0.6 if pe < 0 else self._scale(pe, 40, 10)
            components.append((score, 0.20))
            factor.drivers.append(f"P/E of {pe:.1f}" if pe >= 0 else "negative earnings")

        peg = multiples.get("peg_ratio")
        if peg is not None and peg > 0:
            components.append((self._scale(peg, 3.0, 1.0), 0.10))
            factor.drivers.append(f"PEG of {peg:.2f}")

        ev_ebitda = multiples.get("ev_ebitda")
        if ev_ebitda is not None and ev_ebitda > 0:
            components.append((self._scale(ev_ebitda, 25, 8), 0.15))
            factor.drivers.append(f"EV/EBITDA of {ev_ebitda:.1f}")

        fcf_yield = cash_flow.get("fcf_yield")
        if fcf_yield is not None:
            components.append((self._scale(fcf_yield, 0.005, 0.07), 0.15))
            factor.drivers.append(f"FCF yield of {fcf_yield:.1%}")

        factor.score = self._blend(components)

    def _score_quality(self, factor: Factor, metrics: dict) -> None:
        groups = metrics.get("groups", {})
        profitability = groups.get("profitability", {})
        cash_flow = groups.get("cash_flow", {})

        roic = profitability.get("roic")
        roe = profitability.get("roe")
        net_margin = profitability.get("net_margin")
        operating_margin = profitability.get("operating_margin")
        conversion = cash_flow.get("ocf_to_net_income")

        components = [
            (self._scale(roic, 0.04, 0.16), 0.30),
            (self._scale(roe, 0.05, 0.20), 0.25),
            (self._scale(operating_margin, 0.03, 0.20), 0.20),
            (self._scale(net_margin, 0.02, 0.15), 0.15),
            (self._scale(conversion, 0.60, 1.30), 0.10),
        ]

        if roic is not None:
            factor.drivers.append(f"ROIC of {roic:.1%}")
        if roe is not None:
            factor.drivers.append(f"ROE of {roe:.1%}")
        if operating_margin is not None:
            factor.drivers.append(f"operating margin of {operating_margin:.1%}")
        if conversion is not None:
            factor.drivers.append(f"cash conversion of {conversion:.2f}x")

        factor.score = self._blend(components)

    def _score_financial_health(self, factor: Factor, metrics: dict) -> None:
        groups = metrics.get("groups", {})
        liquidity = groups.get("liquidity", {})
        leverage = groups.get("leverage", {})

        current_ratio = liquidity.get("current_ratio")
        de_ratio = leverage.get("de_ratio")
        coverage = leverage.get("interest_coverage")

        components = [
            (self._scale(current_ratio, 0.8, 2.2), 0.35),
            (self._scale(de_ratio, 2.5, 0.4), 0.35),
            (self._scale(coverage, 2.0, 10.0), 0.30),
        ]

        if current_ratio is not None:
            factor.drivers.append(f"current ratio of {current_ratio:.2f}")
        if de_ratio is not None:
            factor.drivers.append(f"debt-to-equity of {de_ratio:.2f}")
        if coverage is not None:
            factor.drivers.append(f"interest coverage of {coverage:.1f}x")

        factor.score = self._blend(components)

    def _score_growth(self, factor: Factor, metrics: dict) -> None:
        growth = metrics.get("groups", {}).get("growth", {})

        revenue_growth = growth.get("revenue_growth")
        net_income_growth = growth.get("net_income_growth")
        eps_growth = growth.get("eps_growth")

        components = [
            (self._scale(revenue_growth, -0.05, 0.18), 0.45),
            # Bottom-line growth is noisier than revenue, so it carries less.
            (self._scale(net_income_growth, -0.10, 0.25), 0.30),
            (self._scale(eps_growth, -0.10, 0.25), 0.25),
        ]

        if revenue_growth is not None:
            factor.drivers.append(f"revenue growth of {revenue_growth:+.1%}")
        if net_income_growth is not None:
            factor.drivers.append(f"net income growth of {net_income_growth:+.1%}")

        factor.score = self._blend(components)

    def _score_momentum(self, factor: Factor, technical: dict) -> None:
        moving_averages = technical.get("moving_averages") or {}
        momentum = technical.get("momentum") or {}
        macd = technical.get("macd") or {}

        current_price = technical.get("current_price")
        sma_200 = moving_averages.get("sma_200")
        sma_50 = moving_averages.get("sma_50")
        rsi = technical.get("rsi")

        components: list[tuple[Optional[float], float]] = []

        if current_price and sma_200:
            distance = current_price / sma_200 - 1
            components.append((self._scale(distance, -0.12, 0.12), 0.35))
            factor.drivers.append(f"{distance:+.1%} vs. the 200-day average")

        if sma_50 and sma_200:
            golden = sma_50 > sma_200
            components.append((0.6 if golden else -0.6, 0.20))
            factor.drivers.append("golden cross" if golden else "death cross")

        roc_60d = momentum.get("roc_60d")
        if roc_60d is not None:
            components.append((self._scale(roc_60d, -15.0, 15.0), 0.25))
            factor.drivers.append(f"{roc_60d:+.1f}% over 60 sessions")

        histogram = macd.get("macd_histogram")
        if histogram is not None:
            components.append((0.5 if histogram > 0 else -0.5, 0.10))

        if rsi is not None:
            # Extremes are treated as mean-reversion signals, not trend.
            if rsi > 70:
                components.append((-0.4, 0.10))
                factor.drivers.append(f"RSI {rsi:.0f} (overbought)")
            elif rsi < 30:
                components.append((0.4, 0.10))
                factor.drivers.append(f"RSI {rsi:.0f} (oversold)")
            else:
                components.append((0.0, 0.10))

        factor.score = self._blend(components)

    def _score_sentiment(self, factor: Factor, sentiment: dict) -> None:
        analyzed = sentiment.get("analyzed_articles_count") or 0
        if analyzed < self.MIN_ARTICLES_FOR_SENTIMENT:
            factor.drivers.append(f"only {analyzed} article(s) — excluded as too thin")
            return

        compound = sentiment.get("average_sentiment_compound")
        # Wide anchors: a full mark should take uniformly strong coverage, not
        # a couple of upbeat headlines.
        factor.score = self._scale(compound, -0.35, 0.35)
        if compound is not None:
            factor.drivers.append(
                f"average sentiment {compound:+.2f} across {analyzed} articles"
            )

    # ── aggregation ───────────────────────────────────────────

    def _confidence(
        self, factors: list[Factor], composite: float, coverage: float, risk_rating: str
    ) -> int:
        """
        Confidence reflects how much of the picture was actually measurable and
        how much the measurable parts agree — not how extreme the answer is.
        """
        confidence = 40.0

        # How much of the intended weight had data behind it.
        confidence += 25 * coverage

        # Agreement between factors: a case where everything points the same
        # way deserves more confidence than one built on offsetting extremes.
        scored = [f.score for f in factors if f.available]
        if len(scored) > 1:
            mean = sum(scored) / len(scored)
            dispersion = (sum((s - mean) ** 2 for s in scored) / len(scored)) ** 0.5
            confidence += 15 * max(0.0, 1 - dispersion / 0.6)

        # A decisive composite is worth a little more than a borderline one.
        confidence += 10 * min(1.0, abs(composite) / 0.5)

        if risk_rating == "very_high":
            confidence -= 15
        elif risk_rating == "high":
            confidence -= 8
        elif risk_rating == "unknown":
            confidence -= 5

        return int(max(10, min(confidence, 95)))

    def _classify(self, composite: float) -> str:
        if composite >= self.STRONG_BUY_THRESHOLD:
            return "strong buy"
        if composite >= self.BUY_THRESHOLD:
            return "buy"
        if composite <= self.STRONG_SELL_THRESHOLD:
            return "strong sell"
        if composite <= self.SELL_THRESHOLD:
            return "sell"
        return "hold"

    def _apply_valuation_limit(
        self, recommendation: str, valuation: Factor
    ) -> tuple[str, Optional[str]]:
        """
        Constrain the call by what the stock costs.

        Quality and growth can carry a composite score a long way, but a
        wonderful business at a punishing price is not a strong buy — and a
        struggling one trading far below its intrinsic value is not a strong
        sell. Returns the (possibly capped) call and a note explaining any cap.
        """
        if not valuation.available:
            return recommendation, None

        score = valuation.score
        current = self.RANK.index(recommendation)

        if score <= self.VALUATION_VETO_THRESHOLD:
            ceiling = self.RANK.index("hold")
            if current > ceiling:
                return "hold", "capped at hold because the stock looks materially overvalued"
        elif score <= self.VALUATION_CAUTION_THRESHOLD:
            ceiling = self.RANK.index("buy")
            if current > ceiling:
                return "buy", "held back from strong buy by a stretched valuation"

        if score >= -self.VALUATION_VETO_THRESHOLD:
            floor = self.RANK.index("hold")
            if current < floor:
                return "hold", "lifted to hold because the stock looks materially undervalued"

        return recommendation, None

    def _rationale(self, factors: list[Factor], composite: float) -> str:
        """Name the factors that actually moved the result."""
        contributions = [
            (f, f.score * f.weight) for f in factors if f.available
        ]
        if not contributions:
            return "no factor had sufficient data to support a view"

        positive = sorted([c for c in contributions if c[1] > 0.02], key=lambda c: -c[1])
        negative = sorted([c for c in contributions if c[1] < -0.02], key=lambda c: c[1])

        parts: list[str] = []
        if positive:
            parts.append(
                "supported by "
                + " and ".join(f"{self._describe(f.score)} {f.label.lower()}" for f, _ in positive[:2])
            )
        if negative:
            parts.append(
                "offset by "
                + " and ".join(f"{self._describe(f.score)} {f.label.lower()}" for f, _ in negative[:2])
            )
        if not parts:
            return "every factor scored close to neutral"
        return ", ".join(parts)

    # ── main entry point ──────────────────────────────────────

    def evaluate(
        self,
        metrics: dict,
        valuation: dict,
        technical: dict,
        risk: dict,
        sentiment: dict,
        current_price: Optional[Number],
    ) -> dict[str, Any]:
        """
        Score every factor and combine them into a recommendation.

        Returns the recommendation, the composite score, a confidence figure,
        and the per-factor scorecard behind them.
        """
        metrics = metrics or {}
        valuation = valuation or {}
        technical = technical or {}
        risk = risk or {}
        sentiment = sentiment or {}

        factors = [
            Factor("valuation", "Valuation", self.WEIGHTS["valuation"]),
            Factor("quality", "Profitability & Quality", self.WEIGHTS["quality"]),
            Factor("financial_health", "Financial Health", self.WEIGHTS["financial_health"]),
            Factor("growth", "Growth", self.WEIGHTS["growth"]),
            Factor("momentum", "Price Momentum", self.WEIGHTS["momentum"]),
            Factor("sentiment", "News Sentiment", self.WEIGHTS["sentiment"]),
        ]
        by_key = {f.key: f for f in factors}

        self._score_valuation(by_key["valuation"], metrics, valuation, current_price)
        self._score_quality(by_key["quality"], metrics)
        self._score_financial_health(by_key["financial_health"], metrics)
        self._score_growth(by_key["growth"], metrics)
        self._score_momentum(by_key["momentum"], technical)
        self._score_sentiment(by_key["sentiment"], sentiment)

        available = [f for f in factors if f.available]
        available_weight = sum(f.weight for f in available)
        if not available or available_weight == 0:
            logger.warning("No factors could be scored; defaulting to hold")
            return {
                "recommendation": "hold",
                "composite_score": 0.0,
                "confidence": 15,
                "rationale": "insufficient data to score any factor",
                "coverage": 0.0,
                "factors": [f.as_dict() for f in factors],
            }

        # Missing factors have their weight redistributed rather than counted
        # as neutral, which would drag every score toward hold.
        composite = sum(f.score * f.weight for f in available) / available_weight
        coverage = available_weight / sum(self.WEIGHTS.values())

        recommendation = self._classify(composite)
        recommendation, limit_note = self._apply_valuation_limit(
            recommendation, by_key["valuation"],
        )
        confidence = self._confidence(
            factors, composite, coverage, risk.get("risk_rating", "unknown"),
        )
        rationale = self._rationale(available, composite)
        if limit_note:
            rationale = f"{rationale}; {limit_note}"

        logger.info(
            "Recommendation: %s (score %.3f, confidence %d%%, coverage %.0f%%)%s",
            recommendation, composite, confidence, coverage * 100,
            f" [{limit_note}]" if limit_note else "",
        )

        return {
            "recommendation": recommendation,
            "composite_score": round(composite, 3),
            "confidence": confidence,
            "rationale": rationale,
            "coverage": round(coverage, 3),
            "factors": [f.as_dict() for f in factors],
        }
