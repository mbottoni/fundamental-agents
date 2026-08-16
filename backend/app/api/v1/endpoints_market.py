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

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app import models
from app.api.deps import get_current_user
from app.core.market_data import TTL_MARKET, fmp_get

logger = logging.getLogger("stock_analyzer.api.market")
router = APIRouter()


def _fmp(endpoint: str, params: dict | None = None) -> Any:
    """Market-wide data is identical for every user, so it caches well."""
    return fmp_get(endpoint, params or {}, ttl=TTL_MARKET)


# ── Market Movers ─────────────────────────────────────────────

@router.get("/gainers")
def top_gainers(current_user: models.User = Depends(get_current_user)):
    data = _fmp("gainers")
    if not data:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Could not fetch gainers.")
    return data[:20] if isinstance(data, list) else data


@router.get("/losers")
def top_losers(current_user: models.User = Depends(get_current_user)):
    data = _fmp("losers")
    if not data:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Could not fetch losers.")
    return data[:20] if isinstance(data, list) else data


@router.get("/most-active")
def most_active(current_user: models.User = Depends(get_current_user)):
    data = _fmp("actives")
    if not data:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Could not fetch active stocks.")
    return data[:20] if isinstance(data, list) else data


# ── Sector Performance ────────────────────────────────────────

@router.get("/sector-performance")
def sector_performance(current_user: models.User = Depends(get_current_user)):
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
def get_stock_lists(current_user: models.User = Depends(get_current_user)):
    """Return all available curated stock lists with metadata."""
    return [
        {"id": k, "name": v["name"], "description": v["description"], "count": len(v["tickers"])}
        for k, v in STOCK_THEMES.items()
    ]


@router.get("/lists/{list_id}")
def get_stock_list_detail(list_id: str, current_user: models.User = Depends(get_current_user)):
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
