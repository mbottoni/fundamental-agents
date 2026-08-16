"""
Risk Assessment Agent
=====================
Quantifies stock risk from historical prices:
  - Annualized volatility (σ)
  - Sharpe ratio
  - Sortino ratio (downside deviation below the minimum acceptable return)
  - Maximum drawdown
  - Beta, regressed against a market benchmark when its prices are available
  - Value at Risk (VaR) — historical & parametric
  - Annualized return and return / volatility
  - Overall risk rating (low / moderate / high / very high)

Every return-based statistic is computed over a fixed trailing window rather
than the whole price history FMP happens to return. Without that, a 20-year
series makes "maximum drawdown" mean "2008 happened" and turns multi-year
cumulative return into a number labelled as annual.
"""

import logging
import math
from typing import Any, Optional

logger = logging.getLogger("stock_analyzer.agents.risk_assessment")

TRADING_DAYS_PER_YEAR = 252
RISK_FREE_RATE_ANNUAL = 0.04  # 4 % — roughly current T‑bill


class RiskAssessmentAgent:
    """Evaluate the risk profile of a stock from historical price data."""

    # Trailing window for all return-based statistics.
    DEFAULT_LOOKBACK_DAYS = TRADING_DAYS_PER_YEAR
    MIN_OBSERVATIONS = 60
    # Summed squared deviation below this means the benchmark is effectively
    # flat and any beta regressed against it would be numerical noise.
    MIN_MARKET_VARIANCE = 1e-8

    def __init__(self, lookback_days: int = DEFAULT_LOOKBACK_DAYS) -> None:
        self.lookback_days = lookback_days

    # ── helpers ────────────────────────────────────────────────

    @staticmethod
    def _daily_returns(closes: list[float]) -> list[float]:
        """Daily returns from newest‑first closes (output is chronological)."""
        ordered = list(reversed(closes))
        return [
            (ordered[i] - ordered[i - 1]) / ordered[i - 1]
            for i in range(1, len(ordered))
            if ordered[i - 1] != 0
        ]

    @staticmethod
    def _mean(values: list[float]) -> float:
        return sum(values) / len(values) if values else 0.0

    @staticmethod
    def _std(values: list[float], mean_val: Optional[float] = None) -> float:
        if len(values) < 2:
            return 0.0
        m = mean_val if mean_val is not None else sum(values) / len(values)
        return math.sqrt(sum((x - m) ** 2 for x in values) / (len(values) - 1))

    # ── indicators ────────────────────────────────────────────

    def compute_volatility(self, daily_returns: list[float]) -> dict[str, Optional[float]]:
        """Annualized volatility from daily returns."""
        if len(daily_returns) < 20:
            return {"daily_volatility": None, "annual_volatility": None}

        daily_vol = self._std(daily_returns)
        annual_vol = daily_vol * math.sqrt(TRADING_DAYS_PER_YEAR)
        return {
            "daily_volatility": round(daily_vol, 6),
            "annual_volatility": round(annual_vol, 4),
        }

    def compute_sharpe_ratio(self, daily_returns: list[float]) -> Optional[float]:
        """Annualized Sharpe ratio (excess return / total volatility)."""
        if len(daily_returns) < self.MIN_OBSERVATIONS:
            return None
        mean_daily = self._mean(daily_returns)
        std_daily = self._std(daily_returns, mean_daily)
        if std_daily == 0:
            return None
        daily_rf = RISK_FREE_RATE_ANNUAL / TRADING_DAYS_PER_YEAR
        sharpe = ((mean_daily - daily_rf) / std_daily) * math.sqrt(TRADING_DAYS_PER_YEAR)
        return round(sharpe, 3)

    def compute_sortino_ratio(self, daily_returns: list[float]) -> Optional[float]:
        """
        Annualized Sortino ratio.

        Downside deviation is the root mean square of shortfalls below the
        minimum acceptable return, averaged over *all* observations — not the
        standard deviation of the downside subset about its own mean, which
        measures dispersion among bad days rather than how bad they are.
        """
        if len(daily_returns) < self.MIN_OBSERVATIONS:
            return None

        daily_rf = RISK_FREE_RATE_ANNUAL / TRADING_DAYS_PER_YEAR
        mean_daily = self._mean(daily_returns)

        squared_shortfalls = [min(0.0, r - daily_rf) ** 2 for r in daily_returns]
        downside_deviation = math.sqrt(sum(squared_shortfalls) / len(daily_returns))
        if downside_deviation == 0:
            return None

        sortino = ((mean_daily - daily_rf) / downside_deviation) * math.sqrt(TRADING_DAYS_PER_YEAR)
        return round(sortino, 3)

    def compute_max_drawdown(self, closes: list[float]) -> dict[str, Optional[float]]:
        """Maximum peak‑to‑trough decline over the window."""
        if len(closes) < 5:
            return {"max_drawdown": None, "max_drawdown_pct": None}

        ordered = list(reversed(closes))  # chronological
        peak = ordered[0]
        max_dd = 0.0
        for price in ordered[1:]:
            if price > peak:
                peak = price
            dd = (peak - price) / peak
            if dd > max_dd:
                max_dd = dd

        return {
            "max_drawdown": round(max_dd, 4),
            "max_drawdown_pct": round(max_dd * 100, 2),
        }

    def compute_beta(
        self,
        prices: list[dict],
        benchmark_prices: Optional[list[dict]],
        profile: Optional[dict],
    ) -> tuple[Optional[float], str]:
        """
        Beta against the market benchmark, regressed on date‑aligned daily
        returns. Falls back to the beta reported on the company profile.

        Returns (beta, source).
        """
        aligned = self._aligned_returns(prices, benchmark_prices or [])
        if aligned:
            stock_returns, market_returns = aligned
            market_mean = self._mean(market_returns)
            stock_mean = self._mean(stock_returns)
            market_variance = sum((m - market_mean) ** 2 for m in market_returns)
            # A benchmark that barely moves makes the regression numerically
            # meaningless, so fall back rather than divide by noise.
            if market_variance > self.MIN_MARKET_VARIANCE:
                covariance = sum(
                    (s - stock_mean) * (m - market_mean)
                    for s, m in zip(stock_returns, market_returns)
                )
                return round(covariance / market_variance, 3), "regressed vs benchmark"

        profile_beta = (profile or {}).get("beta")
        if profile_beta is not None:
            try:
                return round(float(profile_beta), 3), "company profile"
            except (TypeError, ValueError):
                pass
        return None, "unavailable"

    def _aligned_returns(
        self, prices: list[dict], benchmark_prices: list[dict]
    ) -> Optional[tuple[list[float], list[float]]]:
        """Date‑aligned daily return series for the stock and the benchmark."""
        if not prices or not benchmark_prices:
            return None

        stock_by_date = {p["date"]: p["close"] for p in prices if p.get("date") and p.get("close")}
        market_by_date = {
            p["date"]: p["close"] for p in benchmark_prices if p.get("date") and p.get("close")
        }
        shared = sorted(set(stock_by_date) & set(market_by_date))[-self.lookback_days:]
        if len(shared) < self.MIN_OBSERVATIONS:
            return None

        stock_returns: list[float] = []
        market_returns: list[float] = []
        for i in range(1, len(shared)):
            prev_stock, prev_market = stock_by_date[shared[i - 1]], market_by_date[shared[i - 1]]
            if prev_stock == 0 or prev_market == 0:
                continue
            stock_returns.append((stock_by_date[shared[i]] - prev_stock) / prev_stock)
            market_returns.append((market_by_date[shared[i]] - prev_market) / prev_market)

        if len(stock_returns) < self.MIN_OBSERVATIONS:
            return None
        return stock_returns, market_returns

    def compute_var(
        self, daily_returns: list[float], confidence: float = 0.95
    ) -> dict[str, Optional[float]]:
        """Value at Risk — historical percentile and parametric (normal)."""
        if len(daily_returns) < self.MIN_OBSERVATIONS:
            return {"var_historical_95": None, "var_parametric_95": None}

        sorted_returns = sorted(daily_returns)
        index = int((1 - confidence) * len(sorted_returns))
        hist_var = sorted_returns[index]

        mean_r = self._mean(daily_returns)
        std_r = self._std(daily_returns, mean_r)
        z = 1.645  # 95 % one‑tailed

        return {
            "var_historical_95": round(hist_var * 100, 3),
            "var_parametric_95": round((mean_r - z * std_r) * 100, 3),
        }

    def compute_annualized_return(self, closes: list[float]) -> Optional[float]:
        """
        Annualized (compound) return over the window.

        The window is rarely exactly one year, so the total return is scaled by
        the number of trading days it actually spans.
        """
        if len(closes) < self.MIN_OBSERVATIONS:
            return None
        ordered = list(reversed(closes))
        start, end = ordered[0], ordered[-1]
        if start <= 0 or end <= 0:
            return None
        periods = len(ordered) - 1
        annualized = (end / start) ** (TRADING_DAYS_PER_YEAR / periods) - 1
        return round(annualized, 4)

    def compute_risk_adjusted_return(
        self, annualized_return: Optional[float], annual_volatility: Optional[float]
    ) -> Optional[float]:
        """Annualized return per unit of annualized volatility."""
        if annualized_return is None or not annual_volatility:
            return None
        return round(annualized_return / annual_volatility, 3)

    def _risk_rating(
        self,
        annual_vol: Optional[float],
        max_dd_pct: Optional[float],
        beta: Optional[float],
    ) -> str:
        """Derive an overall risk rating from key metrics."""
        score = 0  # higher = riskier
        if annual_vol is not None:
            if annual_vol > 0.50:
                score += 3
            elif annual_vol > 0.30:
                score += 2
            elif annual_vol > 0.15:
                score += 1

        if max_dd_pct is not None:
            if max_dd_pct > 50:
                score += 3
            elif max_dd_pct > 30:
                score += 2
            elif max_dd_pct > 15:
                score += 1

        if beta is not None:
            if beta > 1.5:
                score += 2
            elif beta > 1.0:
                score += 1

        if score >= 6:
            return "very_high"
        elif score >= 4:
            return "high"
        elif score >= 2:
            return "moderate"
        return "low"

    # ── main entry point ──────────────────────────────────────

    def run(self, raw_data: dict) -> dict[str, Any]:
        """Run full risk assessment on raw data."""
        logger.info("Starting risk assessment")

        prices: list[dict] = raw_data.get("prices") or []
        benchmark_prices: list[dict] = raw_data.get("benchmark_prices") or []
        profile: Optional[dict] = raw_data.get("profile")

        # Newest-first, trimmed to the trailing window. One extra close is kept
        # so the window yields `lookback_days` returns.
        window = [p for p in prices if p.get("close")][: self.lookback_days + 1]
        closes = [p["close"] for p in window]
        if len(closes) < 30:
            logger.warning("Insufficient price history for risk assessment (%d days)", len(closes))
            return {
                "error": "Insufficient price data for risk analysis",
                "risk_rating": "unknown",
                "observations": len(closes),
            }

        daily_returns = self._daily_returns(closes)

        volatility = self.compute_volatility(daily_returns)
        annualized_return = self.compute_annualized_return(closes)
        beta, beta_source = self.compute_beta(prices, benchmark_prices, profile)
        max_dd = self.compute_max_drawdown(closes)

        risk_rating = self._risk_rating(
            volatility.get("annual_volatility"), max_dd.get("max_drawdown_pct"), beta,
        )

        result = {
            **volatility,
            "sharpe_ratio": self.compute_sharpe_ratio(daily_returns),
            "sortino_ratio": self.compute_sortino_ratio(daily_returns),
            **max_dd,
            "beta": beta,
            "beta_source": beta_source,
            **self.compute_var(daily_returns),
            "annualized_return": annualized_return,
            "risk_adjusted_return": self.compute_risk_adjusted_return(
                annualized_return, volatility.get("annual_volatility"),
            ),
            "risk_rating": risk_rating,
            "observations": len(daily_returns),
            "window_start": window[-1].get("date"),
            "window_end": window[0].get("date"),
        }

        logger.info(
            "Risk assessment complete: rating=%s over %d sessions (%s → %s)",
            risk_rating, len(daily_returns), result["window_start"], result["window_end"],
        )
        return result
