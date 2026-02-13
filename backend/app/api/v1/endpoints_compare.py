"""
Stock Comparison Endpoint
=========================
Fetches key financial data for two tickers from FMP and returns
a structured side-by-side comparison without running the full analysis pipeline.
"""

import logging
from typing import Any, Optional

import httpx
from fastapi import APIRouter, HTTPException, Query, status

from app.core.config import settings

logger = logging.getLogger("stock_analyzer.api.compare")
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
        logger.error("FMP error %s: %s", endpoint, e)
        return None


def _safe(v: Any) -> Optional[float]:
    if v is None:
        return None
    try:
        return round(float(v), 4)
    except (TypeError, ValueError):
        return None


def _get_stock_data(ticker: str) -> dict:
    """Fetch profile, key metrics, ratios, and quote for one ticker."""
    profile_raw = _fmp("profile", {"symbol": ticker})
    profile = profile_raw[0] if isinstance(profile_raw, list) and profile_raw else {}

    ratios_raw = _fmp("ratios", {"symbol": ticker, "limit": "1"})
    ratios = ratios_raw[0] if isinstance(ratios_raw, list) and ratios_raw else {}

    metrics_raw = _fmp("key-metrics", {"symbol": ticker, "limit": "1"})
    metrics = metrics_raw[0] if isinstance(metrics_raw, list) and metrics_raw else {}

    quote_raw = _fmp("quote", {"symbol": ticker})
    quote = quote_raw[0] if isinstance(quote_raw, list) and quote_raw else {}

    growth_raw = _fmp("financial-growth", {"symbol": ticker, "limit": "1"})
    growth = growth_raw[0] if isinstance(growth_raw, list) and growth_raw else {}

    return {
        "ticker": ticker,
        "name": profile.get("companyName", ticker),
        "sector": profile.get("sector", "N/A"),
        "industry": profile.get("industry", "N/A"),
        "description": profile.get("description", "")[:300],
        "price": _safe(quote.get("price")),
        "market_cap": _safe(profile.get("mktCap") or profile.get("marketCap")),
        "change_pct": _safe(quote.get("changesPercentage")),
        # Valuation
        "pe_ratio": _safe(ratios.get("priceEarningsRatio")),
        "pb_ratio": _safe(ratios.get("priceBookValueRatio") or ratios.get("priceToBookRatio")),
        "ps_ratio": _safe(ratios.get("priceToSalesRatio")),
        "ev_ebitda": _safe(metrics.get("enterpriseValueOverEBITDA")),
        "peg_ratio": _safe(ratios.get("priceEarningsToGrowthRatio")),
        # Profitability
        "gross_margin": _safe(ratios.get("grossProfitMargin")),
        "operating_margin": _safe(ratios.get("operatingProfitMargin")),
        "net_margin": _safe(ratios.get("netProfitMargin")),
        "roe": _safe(ratios.get("returnOnEquity")),
        "roa": _safe(ratios.get("returnOnAssets")),
        "roic": _safe(ratios.get("returnOnCapitalEmployed")),
        # Growth
        "revenue_growth": _safe(growth.get("revenueGrowth")),
        "net_income_growth": _safe(growth.get("netIncomeGrowth")),
        "eps_growth": _safe(growth.get("epsgrowth") or growth.get("epsGrowth")),
        # Financial Health
        "current_ratio": _safe(ratios.get("currentRatio")),
        "debt_equity": _safe(ratios.get("debtEquityRatio")),
        "interest_coverage": _safe(ratios.get("interestCoverage")),
        # Dividends
        "dividend_yield": _safe(ratios.get("dividendYield")),
        "payout_ratio": _safe(ratios.get("payoutRatio")),
        # Other
        "beta": _safe(profile.get("beta")),
        "avg_volume": _safe(quote.get("avgVolume")),
    }


@router.get("/")
def compare_stocks(
    ticker1: str = Query(..., description="First ticker symbol"),
    ticker2: str = Query(..., description="Second ticker symbol"),
):
    """Compare two stocks side-by-side across valuation, profitability, growth, and health."""
    t1 = ticker1.strip().upper()
    t2 = ticker2.strip().upper()

    if t1 == t2:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Please provide two different tickers.")

    data1 = _get_stock_data(t1)
    data2 = _get_stock_data(t2)

    if not data1.get("price") and not data2.get("price"):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Could not fetch data for either ticker.")

    return {"stock1": data1, "stock2": data2}
