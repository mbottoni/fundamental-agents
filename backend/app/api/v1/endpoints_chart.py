"""
Interactive Chart Endpoint
==========================
Returns historical price data and computed technical indicators
for the interactive chart page.
"""

import logging
import math
from typing import Any, Optional

import httpx
from fastapi import APIRouter, HTTPException, Query, status

from app.core.config import settings

logger = logging.getLogger("stock_analyzer.api.chart")
router = APIRouter()

FMP_BASE = "https://financialmodelingprep.com/stable"
HTTP_TIMEOUT = httpx.Timeout(20.0)


def _fmp(endpoint: str, params: dict) -> Any:
    params["apikey"] = settings.FINANCIAL_MODELING_PREP_API_KEY
    try:
        r = httpx.get(f"{FMP_BASE}/{endpoint}", params=params, timeout=HTTP_TIMEOUT)
        r.raise_for_status()
        return r.json()
    except (httpx.HTTPStatusError, httpx.RequestError) as e:
        logger.error("FMP chart error %s: %s", endpoint, e)
        return None


def _sma(prices: list[float], period: int) -> list[Optional[float]]:
    result: list[Optional[float]] = [None] * len(prices)
    for i in range(period - 1, len(prices)):
        result[i] = round(sum(prices[i - period + 1: i + 1]) / period, 2)
    return result


def _ema(prices: list[float], period: int) -> list[Optional[float]]:
    result: list[Optional[float]] = [None] * len(prices)
    if len(prices) < period:
        return result
    k = 2 / (period + 1)
    result[period - 1] = sum(prices[:period]) / period
    for i in range(period, len(prices)):
        result[i] = round(prices[i] * k + (result[i - 1] or 0) * (1 - k), 2)
    return result


def _rsi(prices: list[float], period: int = 14) -> list[Optional[float]]:
    result: list[Optional[float]] = [None] * len(prices)
    if len(prices) < period + 1:
        return result
    gains, losses = [], []
    for i in range(1, period + 1):
        diff = prices[i] - prices[i - 1]
        gains.append(max(diff, 0))
        losses.append(max(-diff, 0))
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    if avg_loss == 0:
        result[period] = 100.0
    else:
        rs = avg_gain / avg_loss
        result[period] = round(100 - 100 / (1 + rs), 2)
    for i in range(period + 1, len(prices)):
        diff = prices[i] - prices[i - 1]
        avg_gain = (avg_gain * (period - 1) + max(diff, 0)) / period
        avg_loss = (avg_loss * (period - 1) + max(-diff, 0)) / period
        if avg_loss == 0:
            result[i] = 100.0
        else:
            rs = avg_gain / avg_loss
            result[i] = round(100 - 100 / (1 + rs), 2)
    return result


def _macd(prices: list[float]) -> dict[str, list[Optional[float]]]:
    ema12 = _ema(prices, 12)
    ema26 = _ema(prices, 26)
    macd_line: list[Optional[float]] = [None] * len(prices)
    for i in range(len(prices)):
        if ema12[i] is not None and ema26[i] is not None:
            macd_line[i] = round(ema12[i] - ema26[i], 4)
    valid = [v for v in macd_line if v is not None]
    signal: list[Optional[float]] = [None] * len(prices)
    if len(valid) >= 9:
        k = 2 / 10
        first_valid_idx = next(i for i, v in enumerate(macd_line) if v is not None)
        sig_start = first_valid_idx + 8
        if sig_start < len(prices):
            signal[sig_start] = round(sum(valid[:9]) / 9, 4)
            for i in range(sig_start + 1, len(prices)):
                if macd_line[i] is not None and signal[i - 1] is not None:
                    signal[i] = round(macd_line[i] * k + signal[i - 1] * (1 - k), 4)
    histogram: list[Optional[float]] = [None] * len(prices)
    for i in range(len(prices)):
        if macd_line[i] is not None and signal[i] is not None:
            histogram[i] = round(macd_line[i] - signal[i], 4)
    return {"macd": macd_line, "signal": signal, "histogram": histogram}


def _bollinger(prices: list[float], period: int = 20, std_mult: float = 2.0) -> dict:
    sma = _sma(prices, period)
    upper: list[Optional[float]] = [None] * len(prices)
    lower: list[Optional[float]] = [None] * len(prices)
    for i in range(period - 1, len(prices)):
        window = prices[i - period + 1: i + 1]
        mean = sum(window) / period
        std = math.sqrt(sum((x - mean) ** 2 for x in window) / period)
        upper[i] = round(mean + std_mult * std, 2)
        lower[i] = round(mean - std_mult * std, 2)
    return {"sma": sma, "upper": upper, "lower": lower}


@router.get("/{ticker}")
def get_chart_data(
    ticker: str,
    timeframe: str = Query("1y", description="1m, 3m, 6m, 1y, 2y, 5y, max"),
    indicators: str = Query("sma", description="Comma-separated: sma,ema,rsi,macd,bollinger"),
):
    """
    Return historical OHLCV data + computed technical indicators for a ticker.
    """
    ticker = ticker.strip().upper()

    raw = _fmp("historical-price-eod/full", {"symbol": ticker})
    if not raw or not isinstance(raw, list):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"No price data for {ticker}")

    # Sort chronologically (oldest first)
    raw.sort(key=lambda x: x.get("date", ""))

    # Trim by timeframe
    tf_map = {"1m": 21, "3m": 63, "6m": 126, "1y": 252, "2y": 504, "5y": 1260, "max": len(raw)}
    limit = tf_map.get(timeframe, 252)
    raw = raw[-limit:]

    closes = [float(r.get("close", 0)) for r in raw]
    dates = [r.get("date", "") for r in raw]

    # Base OHLCV
    ohlcv = []
    for r in raw:
        ohlcv.append({
            "date": r.get("date"),
            "open": r.get("open"),
            "high": r.get("high"),
            "low": r.get("low"),
            "close": r.get("close"),
            "volume": r.get("volume"),
        })

    ind_set = {s.strip().lower() for s in indicators.split(",")} if indicators else set()
    computed: dict[str, Any] = {}

    if "sma" in ind_set:
        computed["sma20"] = _sma(closes, 20)
        computed["sma50"] = _sma(closes, 50)
        computed["sma200"] = _sma(closes, 200)

    if "ema" in ind_set:
        computed["ema12"] = _ema(closes, 12)
        computed["ema26"] = _ema(closes, 26)

    if "rsi" in ind_set:
        computed["rsi"] = _rsi(closes)

    if "macd" in ind_set:
        computed["macd"] = _macd(closes)

    if "bollinger" in ind_set:
        computed["bollinger"] = _bollinger(closes)

    # Also get profile for meta-info
    profile_raw = _fmp("profile", {"symbol": ticker})
    profile = profile_raw[0] if isinstance(profile_raw, list) and profile_raw else {}

    return {
        "ticker": ticker,
        "name": profile.get("companyName", ticker),
        "dates": dates,
        "ohlcv": ohlcv,
        "indicators": computed,
    }
