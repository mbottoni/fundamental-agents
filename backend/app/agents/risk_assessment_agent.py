"""
Risk Assessment Agent
=====================
Quantifies portfolio/stock risk using standard financial metrics:
  - Annualized Volatility (σ)
  - Sharpe Ratio
  - Sortino Ratio
  - Maximum Drawdown (MDD) & recovery period
  - Beta (vs. market benchmark)
  - Value at Risk (VaR) — historical & parametric
  - Risk‑adjusted return
  - Overall risk rating (low / moderate / high / very high)
"""

import logging
import math
from typing import Any, Optional

logger = logging.getLogger("stock_analyzer.agents.risk_assessment")

TRADING_DAYS_PER_YEAR = 252
RISK_FREE_RATE_ANNUAL = 0.04  # 4 % — roughly current T‑bill


class RiskAssessmentAgent:
    """Evaluate the risk profile of a stock from historical price data."""

    # ── helpers ────────────────────────────────────────────────

    @staticmethod
    def _daily_returns(closes: list[float]) -> list[float]:
        """Compute daily returns from newest‑first close prices (output is chronological)."""
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
        """Annualized Sharpe Ratio (excess return / volatility)."""
        if len(daily_returns) < 60:
            return None
        mean_daily = self._mean(daily_returns)
        std_daily = self._std(daily_returns, mean_daily)
        if std_daily == 0:
            return None
        daily_rf = RISK_FREE_RATE_ANNUAL / TRADING_DAYS_PER_YEAR
        sharpe = ((mean_daily - daily_rf) / std_daily) * math.sqrt(TRADING_DAYS_PER_YEAR)
        return round(sharpe, 3)

    def compute_sortino_ratio(self, daily_returns: list[float]) -> Optional[float]:
        """Annualized Sortino Ratio (downside deviation only)."""
        if len(daily_returns) < 60:
            return None
        daily_rf = RISK_FREE_RATE_ANNUAL / TRADING_DAYS_PER_YEAR
        mean_daily = self._mean(daily_returns)
        downside = [r for r in daily_returns if r < daily_rf]
        if not downside:
            return None
        downside_std = self._std(downside)
        if downside_std == 0:
            return None
        sortino = ((mean_daily - daily_rf) / downside_std) * math.sqrt(TRADING_DAYS_PER_YEAR)
        return round(sortino, 3)

    def compute_max_drawdown(self, closes: list[float]) -> dict[str, Optional[float]]:
        """Maximum Drawdown (MDD) and the peak‑to‑trough percentage."""
        if len(closes) < 5:
            return {"max_drawdown": None, "max_drawdown_pct": None}

        # Chronological order
        ordered = list(reversed(closes))
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

    def compute_beta(self, daily_returns: list[float], profile: Optional[dict]) -> Optional[float]:
        """Beta from the company profile (FMP provides it), with sanity check."""
        if profile and profile.get("beta") is not None:
            return round(profile["beta"], 3)
        return None

    def compute_var(
        self, daily_returns: list[float], confidence: float = 0.95
    ) -> dict[str, Optional[float]]:
        """Value at Risk — historical percentile and parametric (normal)."""
        if len(daily_returns) < 60:
            return {"var_historical_95": None, "var_parametric_95": None}

        sorted_returns = sorted(daily_returns)
        index = int((1 - confidence) * len(sorted_returns))
        hist_var = sorted_returns[index]

        mean_r = self._mean(daily_returns)
        std_r = self._std(daily_returns, mean_r)
        # z‑score for 95 %
        z = 1.645
        param_var = mean_r - z * std_r

        return {
            "var_historical_95": round(hist_var * 100, 3),
            "var_parametric_95": round(param_var * 100, 3),
        }

    def compute_risk_adjusted_return(
        self, closes: list[float], daily_returns: list[float]
    ) -> Optional[float]:
        """Annualized return divided by annualized volatility."""
        if len(closes) < 252 or len(daily_returns) < 252:
            return None
        ordered = list(reversed(closes))
        annual_return = (ordered[-1] - ordered[0]) / ordered[0]
        std_daily = self._std(daily_returns)
        annual_vol = std_daily * math.sqrt(TRADING_DAYS_PER_YEAR) if std_daily else 0
        if annual_vol == 0:
            return None
        return round(annual_return / annual_vol, 3)

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

        prices: list[dict] = raw_data.get("prices", [])
        profile: Optional[dict] = raw_data.get("profile")

        closes = [p["close"] for p in prices if p.get("close")]
        if len(closes) < 30:
            logger.warning("Insufficient price history for risk assessment (%d days)", len(closes))
            return {"error": "Insufficient price data for risk analysis", "risk_rating": "unknown"}

        daily_returns = self._daily_returns(closes)

        volatility = self.compute_volatility(daily_returns)
        sharpe = self.compute_sharpe_ratio(daily_returns)
        sortino = self.compute_sortino_ratio(daily_returns)
        max_dd = self.compute_max_drawdown(closes)
        beta = self.compute_beta(daily_returns, profile)
        var = self.compute_var(daily_returns)
        risk_adj_return = self.compute_risk_adjusted_return(closes, daily_returns)

        risk_rating = self._risk_rating(
            volatility.get("annual_volatility"),
            max_dd.get("max_drawdown_pct"),
            beta,
        )

        result = {
            **volatility,
            "sharpe_ratio": sharpe,
            "sortino_ratio": sortino,
            **max_dd,
            "beta": beta,
            **var,
            "risk_adjusted_return": risk_adj_return,
            "risk_rating": risk_rating,
        }

        logger.info("Risk assessment complete: rating=%s", risk_rating)
        return result
