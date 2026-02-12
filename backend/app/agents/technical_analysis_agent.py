"""
Technical Analysis Agent
========================
Computes standard technical indicators from historical price data:
  - Simple & Exponential Moving Averages (SMA/EMA)
  - RSI (Relative Strength Index)
  - MACD (Moving Average Convergence Divergence)
  - Bollinger Bands
  - Average True Range (ATR)
  - Volume profile (average, trend)
  - Support / Resistance levels (recent high/low)
  - Price momentum (rate of change)
"""

import logging
import math
from typing import Any, Optional

logger = logging.getLogger("stock_analyzer.agents.technical_analysis")


class TechnicalAnalysisAgent:
    """Calculates technical indicators from historical price data."""

    # ── helpers ────────────────────────────────────────────────

    @staticmethod
    def _sma(values: list[float], period: int) -> Optional[float]:
        """Simple Moving Average over the most recent *period* values."""
        if len(values) < period:
            return None
        return sum(values[:period]) / period

    @staticmethod
    def _ema(values: list[float], period: int) -> Optional[float]:
        """Exponential Moving Average (most‑recent first)."""
        if len(values) < period:
            return None
        # Reverse so oldest is first for iterative EMA calc
        ordered = list(reversed(values[:max(period * 3, len(values))]))
        multiplier = 2 / (period + 1)
        ema = sum(ordered[:period]) / period
        for price in ordered[period:]:
            ema = (price - ema) * multiplier + ema
        return ema

    # ── indicators ────────────────────────────────────────────

    def compute_moving_averages(self, closes: list[float]) -> dict[str, Optional[float]]:
        """SMA and EMA for standard windows."""
        return {
            "sma_20": self._sma(closes, 20),
            "sma_50": self._sma(closes, 50),
            "sma_200": self._sma(closes, 200),
            "ema_12": self._ema(closes, 12),
            "ema_26": self._ema(closes, 26),
            "ema_50": self._ema(closes, 50),
        }

    def compute_rsi(self, closes: list[float], period: int = 14) -> Optional[float]:
        """Relative Strength Index (Wilder smoothing)."""
        if len(closes) < period + 1:
            return None

        # Most recent first → reverse for chronological order
        ordered = list(reversed(closes[: period * 3 + 1]))
        gains, losses = [], []
        for i in range(1, len(ordered)):
            delta = ordered[i] - ordered[i - 1]
            gains.append(max(delta, 0))
            losses.append(max(-delta, 0))

        if len(gains) < period:
            return None

        avg_gain = sum(gains[:period]) / period
        avg_loss = sum(losses[:period]) / period

        for i in range(period, len(gains)):
            avg_gain = (avg_gain * (period - 1) + gains[i]) / period
            avg_loss = (avg_loss * (period - 1) + losses[i]) / period

        if avg_loss == 0:
            return 100.0
        rs = avg_gain / avg_loss
        return round(100 - (100 / (1 + rs)), 2)

    def compute_macd(
        self, closes: list[float]
    ) -> dict[str, Optional[float]]:
        """MACD line, signal line, and histogram."""
        ema_12 = self._ema(closes, 12)
        ema_26 = self._ema(closes, 26)
        if ema_12 is None or ema_26 is None:
            return {"macd_line": None, "signal_line": None, "macd_histogram": None}

        macd_line = ema_12 - ema_26

        # Approximate signal line from recent MACD series
        # Build a short MACD series for the signal EMA
        macd_series: list[float] = []
        for i in range(min(35, len(closes) - 26)):
            e12 = self._ema(closes[i:], 12)
            e26 = self._ema(closes[i:], 26)
            if e12 is not None and e26 is not None:
                macd_series.append(e12 - e26)

        if len(macd_series) >= 9:
            signal_line = self._ema(macd_series, 9)
        else:
            signal_line = None

        histogram = (macd_line - signal_line) if signal_line is not None else None

        return {
            "macd_line": round(macd_line, 4) if macd_line else None,
            "signal_line": round(signal_line, 4) if signal_line else None,
            "macd_histogram": round(histogram, 4) if histogram else None,
        }

    def compute_bollinger_bands(
        self, closes: list[float], period: int = 20, num_std: float = 2.0
    ) -> dict[str, Optional[float]]:
        """Bollinger Bands (middle, upper, lower, bandwidth)."""
        if len(closes) < period:
            return {"bb_upper": None, "bb_middle": None, "bb_lower": None, "bb_bandwidth": None}

        window = closes[:period]
        middle = sum(window) / period
        variance = sum((x - middle) ** 2 for x in window) / period
        std_dev = math.sqrt(variance)

        upper = middle + num_std * std_dev
        lower = middle - num_std * std_dev
        bandwidth = ((upper - lower) / middle) * 100 if middle else None

        return {
            "bb_upper": round(upper, 2),
            "bb_middle": round(middle, 2),
            "bb_lower": round(lower, 2),
            "bb_bandwidth": round(bandwidth, 2) if bandwidth else None,
        }

    def compute_atr(self, prices: list[dict], period: int = 14) -> Optional[float]:
        """Average True Range using high/low/close data."""
        if len(prices) < period + 1:
            return None

        # prices are newest-first, reverse to chronological
        ordered = list(reversed(prices[: period * 2 + 1]))
        true_ranges: list[float] = []
        for i in range(1, len(ordered)):
            high = ordered[i].get("high", 0)
            low = ordered[i].get("low", 0)
            prev_close = ordered[i - 1].get("close", 0)
            tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
            true_ranges.append(tr)

        if len(true_ranges) < period:
            return None

        atr = sum(true_ranges[:period]) / period
        for tr in true_ranges[period:]:
            atr = (atr * (period - 1) + tr) / period

        return round(atr, 2)

    def compute_volume_profile(self, prices: list[dict]) -> dict[str, Any]:
        """Volume analysis: averages and short-vs-long trend."""
        volumes = [p.get("volume", 0) for p in prices if p.get("volume")]
        if not volumes:
            return {"avg_volume_20": None, "avg_volume_50": None, "volume_trend": "unknown"}

        avg_20 = sum(volumes[:20]) / min(len(volumes), 20) if len(volumes) >= 1 else None
        avg_50 = sum(volumes[:50]) / min(len(volumes), 50) if len(volumes) >= 20 else None

        if avg_20 and avg_50:
            ratio = avg_20 / avg_50
            if ratio > 1.2:
                trend = "increasing"
            elif ratio < 0.8:
                trend = "decreasing"
            else:
                trend = "stable"
        else:
            trend = "insufficient_data"

        return {
            "avg_volume_20": int(avg_20) if avg_20 else None,
            "avg_volume_50": int(avg_50) if avg_50 else None,
            "volume_trend": trend,
        }

    def compute_support_resistance(self, prices: list[dict]) -> dict[str, Optional[float]]:
        """Recent support and resistance from 52‑week high/low."""
        if not prices:
            return {"resistance_52w": None, "support_52w": None, "resistance_20d": None, "support_20d": None}

        highs_252 = [p.get("high", 0) for p in prices[:252] if p.get("high")]
        lows_252 = [p.get("low", 0) for p in prices[:252] if p.get("low")]
        highs_20 = [p.get("high", 0) for p in prices[:20] if p.get("high")]
        lows_20 = [p.get("low", 0) for p in prices[:20] if p.get("low")]

        return {
            "resistance_52w": max(highs_252) if highs_252 else None,
            "support_52w": min(lows_252) if lows_252 else None,
            "resistance_20d": max(highs_20) if highs_20 else None,
            "support_20d": min(lows_20) if lows_20 else None,
        }

    def compute_momentum(self, closes: list[float]) -> dict[str, Optional[float]]:
        """Rate of Change (ROC) over multiple windows."""
        result: dict[str, Optional[float]] = {}
        for label, period in [("roc_5d", 5), ("roc_20d", 20), ("roc_60d", 60)]:
            if len(closes) > period and closes[period] != 0:
                result[label] = round(((closes[0] - closes[period]) / closes[period]) * 100, 2)
            else:
                result[label] = None
        return result

    # ── main entry point ──────────────────────────────────────

    def run(self, raw_data: dict) -> dict[str, Any]:
        """Run all technical analysis on raw price data."""
        logger.info("Starting technical analysis")

        prices: list[dict] = raw_data.get("prices", [])
        if not prices:
            logger.warning("No price data available for technical analysis")
            return {"error": "No price data available"}

        closes = [p["close"] for p in prices if p.get("close")]

        current_price = closes[0] if closes else None

        moving_averages = self.compute_moving_averages(closes)
        rsi = self.compute_rsi(closes)
        macd = self.compute_macd(closes)
        bollinger = self.compute_bollinger_bands(closes)
        atr = self.compute_atr(prices)
        volume = self.compute_volume_profile(prices)
        support_resistance = self.compute_support_resistance(prices)
        momentum = self.compute_momentum(closes)

        # ── Trend & signal summary ──
        trend_signals: list[str] = []
        if moving_averages.get("sma_50") and moving_averages.get("sma_200"):
            if moving_averages["sma_50"] > moving_averages["sma_200"]:
                trend_signals.append("Golden Cross (SMA50 > SMA200) — bullish")
            else:
                trend_signals.append("Death Cross (SMA50 < SMA200) — bearish")

        if current_price and moving_averages.get("sma_200"):
            if current_price > moving_averages["sma_200"]:
                trend_signals.append("Price above 200‑day SMA — bullish")
            else:
                trend_signals.append("Price below 200‑day SMA — bearish")

        if rsi is not None:
            if rsi > 70:
                trend_signals.append(f"RSI {rsi} — overbought")
            elif rsi < 30:
                trend_signals.append(f"RSI {rsi} — oversold")
            else:
                trend_signals.append(f"RSI {rsi} — neutral")

        if macd.get("macd_histogram") is not None:
            if macd["macd_histogram"] > 0:
                trend_signals.append("MACD histogram positive — bullish momentum")
            else:
                trend_signals.append("MACD histogram negative — bearish momentum")

        result = {
            "current_price": current_price,
            "moving_averages": moving_averages,
            "rsi": rsi,
            "macd": macd,
            "bollinger_bands": bollinger,
            "atr": atr,
            "volume_profile": volume,
            "support_resistance": support_resistance,
            "momentum": momentum,
            "trend_signals": trend_signals,
        }

        logger.info("Technical analysis complete: %d signals generated", len(trend_signals))
        return result
