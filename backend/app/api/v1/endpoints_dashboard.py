"""
Dashboard & Market Data Endpoints
==================================
Provides quick‑access data for the frontend dashboard:
  - Real‑time stock quote
  - User dashboard stats (analyses count, watchlist size, etc.)
"""

import logging

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app import crud, models
from app.api.deps import get_current_user
from app.core.config import settings
from app.core.db import get_db

logger = logging.getLogger("stock_analyzer.api.dashboard")

router = APIRouter()

FMP_BASE = "https://financialmodelingprep.com/stable"
HTTP_TIMEOUT = httpx.Timeout(15.0)


# ── Quick Quote ───────────────────────────────────────────────

@router.get("/quote/{ticker}")
def get_quick_quote(ticker: str):
    """
    Return a real‑time quote for a single ticker from FMP.
    No authentication required — public endpoint.
    """
    ticker = ticker.strip().upper()
    try:
        resp = httpx.get(
            f"{FMP_BASE}/quote",
            params={"symbol": ticker, "apikey": settings.FINANCIAL_MODELING_PREP_API_KEY},
            timeout=HTTP_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
        if not data or (isinstance(data, list) and len(data) == 0):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"No quote found for {ticker}")
        return data[0] if isinstance(data, list) else data
    except httpx.HTTPStatusError as e:
        logger.error("FMP quote error for %s: %s", ticker, e)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Could not fetch quote from market data provider.")
    except httpx.RequestError as e:
        logger.error("FMP quote request error: %s", e)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Market data provider unreachable.")


@router.get("/quote-batch")
def get_batch_quotes(symbols: str = Query(..., description="Comma-separated ticker symbols")):
    """
    Return real‑time quotes for multiple tickers in one call.
    No authentication required.
    """
    symbols = symbols.strip().upper()
    try:
        resp = httpx.get(
            f"{FMP_BASE}/batch-quote",
            params={"symbols": symbols, "apikey": settings.FINANCIAL_MODELING_PREP_API_KEY},
            timeout=HTTP_TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json()
    except (httpx.HTTPStatusError, httpx.RequestError) as e:
        logger.error("FMP batch quote error: %s", e)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Could not fetch quotes.")


# ── Dashboard Stats ───────────────────────────────────────────

@router.get("/stats")
def get_dashboard_stats(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    Aggregated stats for the authenticated user's dashboard.
    """
    jobs = crud.get_user_jobs(db, user_id=current_user.id)
    watchlist = crud.get_user_watchlist(db, user_id=current_user.id)

    completed = [j for j in jobs if j.status == "complete"]
    failed = [j for j in jobs if j.status == "failed"]
    pending = [j for j in jobs if j.status in ("pending", "gathering_data", "analyzing", "generating_report")]

    # Unique tickers analyzed
    tickers_analyzed = list({j.ticker for j in completed})

    return {
        "total_analyses": len(jobs),
        "completed_analyses": len(completed),
        "failed_analyses": len(failed),
        "pending_analyses": len(pending),
        "tickers_analyzed": tickers_analyzed,
        "watchlist_count": len(watchlist),
        "subscription_status": current_user.subscription_status,
        "is_premium": current_user.subscription_status == "active",
    }


# ── Search ────────────────────────────────────────────────────

@router.get("/search")
def search_ticker(q: str = Query(..., min_length=1, description="Search query")):
    """
    Search for stock tickers/companies by name or symbol.
    No authentication required.
    """
    try:
        resp = httpx.get(
            f"{FMP_BASE}/search-symbol",
            params={"query": q.strip(), "apikey": settings.FINANCIAL_MODELING_PREP_API_KEY, "limit": "10"},
            timeout=HTTP_TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json()
    except (httpx.HTTPStatusError, httpx.RequestError) as e:
        logger.error("FMP search error: %s", e)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Search failed.")
