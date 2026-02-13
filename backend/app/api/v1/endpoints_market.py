"""
Market Overview & Stock Lists Endpoints
========================================
Provides market-wide data:
  - Market movers (gainers / losers / most active)
  - Sector performance
  - Curated stock lists / themes
"""

import logging
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException, Query, status

from app.core.config import settings

logger = logging.getLogger("stock_analyzer.api.market")
router = APIRouter()

FMP_BASE = "https://financialmodelingprep.com/stable"
HTTP_TIMEOUT = httpx.Timeout(20.0)


def _fmp(endpoint: str, params: dict | None = None) -> Any:
    p = params or {}
    p["apikey"] = settings.FINANCIAL_MODELING_PREP_API_KEY
    try:
        r = httpx.get(f"{FMP_BASE}/{endpoint}", params=p, timeout=HTTP_TIMEOUT)
        r.raise_for_status()
        return r.json()
    except (httpx.HTTPStatusError, httpx.RequestError) as e:
        logger.error("FMP market error %s: %s", endpoint, e)
        return None


# ── Market Movers ─────────────────────────────────────────────

@router.get("/gainers")
def top_gainers():
    data = _fmp("gainers")
    if not data:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Could not fetch gainers.")
    return data[:20] if isinstance(data, list) else data


@router.get("/losers")
def top_losers():
    data = _fmp("losers")
    if not data:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Could not fetch losers.")
    return data[:20] if isinstance(data, list) else data


@router.get("/most-active")
def most_active():
    data = _fmp("actives")
    if not data:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Could not fetch active stocks.")
    return data[:20] if isinstance(data, list) else data


# ── Sector Performance ────────────────────────────────────────

@router.get("/sector-performance")
def sector_performance():
    data = _fmp("sector-performance")
    if not data:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Could not fetch sector performance.")
    return data


# ── Curated Stock Lists (Themes) ─────────────────────────────

STOCK_THEMES = {
    "magnificent-7": {
        "name": "Magnificent 7",
        "description": "The seven mega-cap tech companies driving market returns",
        "tickers": ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA"],
    },
    "dividend-aristocrats": {
        "name": "Dividend Aristocrats",
        "description": "Companies that have increased dividends for 25+ consecutive years",
        "tickers": ["JNJ", "PG", "KO", "PEP", "MMM", "ABT", "ABBV", "T", "XOM", "CVX"],
    },
    "ai-leaders": {
        "name": "AI & Machine Learning",
        "description": "Companies at the forefront of artificial intelligence",
        "tickers": ["NVDA", "MSFT", "GOOGL", "AMD", "PLTR", "CRM", "SNOW", "AI", "PATH", "DDOG"],
    },
    "clean-energy": {
        "name": "Clean Energy",
        "description": "Renewable energy and sustainable technology companies",
        "tickers": ["ENPH", "SEDG", "FSLR", "NEE", "BEP", "PLUG", "RUN", "NOVA", "CSIQ", "DQ"],
    },
    "healthcare-innovation": {
        "name": "Healthcare Innovation",
        "description": "Biotech and healthcare disruptors",
        "tickers": ["LLY", "NVO", "MRNA", "ISRG", "DXCM", "VEEV", "HIMS", "DOCS", "TDOC", "ALGN"],
    },
    "fintech": {
        "name": "Fintech Leaders",
        "description": "Financial technology companies reshaping finance",
        "tickers": ["SQ", "PYPL", "COIN", "SOFI", "AFRM", "HOOD", "NU", "MELI", "ADYEN", "FIS"],
    },
    "semiconductors": {
        "name": "Semiconductors",
        "description": "Chip makers powering the global economy",
        "tickers": ["NVDA", "AMD", "INTC", "TSM", "ASML", "AVGO", "QCOM", "MRVL", "MU", "LRCX"],
    },
    "value-stocks": {
        "name": "Value Stocks",
        "description": "Established companies trading at attractive valuations",
        "tickers": ["BRK.B", "JPM", "BAC", "WFC", "C", "UNH", "CVS", "GM", "F", "VALE"],
    },
}


@router.get("/lists")
def get_stock_lists():
    """Return all available curated stock lists with metadata."""
    return [
        {"id": k, "name": v["name"], "description": v["description"], "count": len(v["tickers"])}
        for k, v in STOCK_THEMES.items()
    ]


@router.get("/lists/{list_id}")
def get_stock_list_detail(list_id: str):
    """Return a curated stock list with live quotes for each ticker."""
    theme = STOCK_THEMES.get(list_id)
    if not theme:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"List '{list_id}' not found.")

    # Fetch batch quotes
    symbols = ",".join(theme["tickers"])
    quotes = _fmp("batch-quote", {"symbols": symbols}) or []

    # Map quotes by symbol for easy lookup
    quote_map = {}
    if isinstance(quotes, list):
        for q in quotes:
            sym = q.get("symbol", "")
            quote_map[sym] = q

    stocks = []
    for t in theme["tickers"]:
        q = quote_map.get(t, {})
        stocks.append({
            "ticker": t,
            "name": q.get("name", t),
            "price": q.get("price"),
            "change": q.get("change"),
            "change_pct": q.get("changesPercentage"),
            "market_cap": q.get("marketCap"),
            "volume": q.get("volume"),
        })

    return {
        "id": list_id,
        "name": theme["name"],
        "description": theme["description"],
        "stocks": stocks,
    }
