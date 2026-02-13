"""
Stock Screener Endpoint
=======================
Proxy to FMP's stock screener with structured filters.
"""

import logging
from typing import Optional

import httpx
from fastapi import APIRouter, HTTPException, Query, status

from app.core.config import settings

logger = logging.getLogger("stock_analyzer.api.screener")
router = APIRouter()

FMP_BASE = "https://financialmodelingprep.com/stable"
HTTP_TIMEOUT = httpx.Timeout(20.0)


@router.get("/")
def screen_stocks(
    sector: Optional[str] = Query(None, description="Sector filter (e.g. Technology, Healthcare)"),
    industry: Optional[str] = Query(None, description="Industry filter"),
    market_cap_min: Optional[float] = Query(None, alias="marketCapMin", description="Minimum market cap"),
    market_cap_max: Optional[float] = Query(None, alias="marketCapMax", description="Maximum market cap"),
    price_min: Optional[float] = Query(None, alias="priceMin", description="Minimum price"),
    price_max: Optional[float] = Query(None, alias="priceMax", description="Maximum price"),
    dividend_min: Optional[float] = Query(None, alias="dividendMin", description="Minimum dividend yield"),
    volume_min: Optional[float] = Query(None, alias="volumeMin", description="Minimum average volume"),
    beta_min: Optional[float] = Query(None, alias="betaMin"),
    beta_max: Optional[float] = Query(None, alias="betaMax"),
    country: Optional[str] = Query(None, description="Country (e.g. US, GB)"),
    exchange: Optional[str] = Query(None, description="Exchange (e.g. NASDAQ, NYSE)"),
    limit: int = Query(50, ge=1, le=200, description="Max results"),
):
    """
    Screen stocks using FMP's screener API with various filters.
    Returns a list of matching stocks with key metrics.
    """
    params: dict = {
        "apikey": settings.FINANCIAL_MODELING_PREP_API_KEY,
        "limit": str(limit),
    }

    if sector:
        params["sector"] = sector
    if industry:
        params["industry"] = industry
    if market_cap_min is not None:
        params["marketCapMoreThan"] = str(int(market_cap_min))
    if market_cap_max is not None:
        params["marketCapLowerThan"] = str(int(market_cap_max))
    if price_min is not None:
        params["priceMoreThan"] = str(price_min)
    if price_max is not None:
        params["priceLowerThan"] = str(price_max)
    if dividend_min is not None:
        params["dividendMoreThan"] = str(dividend_min)
    if volume_min is not None:
        params["volumeMoreThan"] = str(int(volume_min))
    if beta_min is not None:
        params["betaMoreThan"] = str(beta_min)
    if beta_max is not None:
        params["betaLowerThan"] = str(beta_max)
    if country:
        params["country"] = country.upper()
    if exchange:
        params["exchange"] = exchange.upper()

    try:
        resp = httpx.get(
            f"{FMP_BASE}/stock-screener",
            params=params,
            timeout=HTTP_TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPStatusError as e:
        logger.error("FMP screener HTTP error: %s", e)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Screener request failed.")
    except httpx.RequestError as e:
        logger.error("FMP screener request error: %s", e)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Market data provider unreachable.")


@router.get("/sectors")
def list_sectors():
    """Return available sectors for the screener filter."""
    return [
        "Technology", "Healthcare", "Financial Services", "Consumer Cyclical",
        "Industrials", "Communication Services", "Consumer Defensive",
        "Energy", "Real Estate", "Utilities", "Basic Materials",
    ]


@router.get("/exchanges")
def list_exchanges():
    """Return available exchanges for the screener filter."""
    return ["NASDAQ", "NYSE", "AMEX", "TSX", "LSE", "EURONEXT"]
