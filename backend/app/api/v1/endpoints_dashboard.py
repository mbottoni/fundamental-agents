"""
Dashboard & Market Data Endpoints
==================================
Provides quick‑access data for the frontend dashboard:
  - Real‑time stock quote
  - User dashboard stats (analyses count, watchlist size, etc.)
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app import crud, models
from app.api.deps import get_current_user
from app.core.config import settings
from app.core.db import get_db
from app.core.market_data import TTL_QUOTE, TTL_SEARCH, client, fmp_get

logger = logging.getLogger("stock_analyzer.api.dashboard")

router = APIRouter()

# A batch request larger than this is either a mistake or an attempt to use the
# deployment as a bulk market-data feed.
MAX_BATCH_SYMBOLS = 25


# ── Quick Quote ───────────────────────────────────────────────

@router.get("/quote/{ticker}")
def get_quick_quote(
    ticker: str,
    current_user: models.User = Depends(get_current_user),
):
    """Return a quote for a single ticker."""
    ticker = ticker.strip().upper()
    data = fmp_get("quote", {"symbol": ticker}, ttl=TTL_QUOTE)

    if data is None:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not fetch a quote from the market data provider.",
        )
    if isinstance(data, list):
        if not data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=f"No quote found for {ticker}."
            )
        return data[0]
    return data


@router.get("/quote-batch")
def get_batch_quotes(
    symbols: str = Query(..., description="Comma-separated ticker symbols"),
    current_user: models.User = Depends(get_current_user),
):
    """
    Return quotes for several tickers.

    FMP's own batch-quote endpoint is not available on the current plan — it
    answers every request with "Restricted Endpoint", so this used to fail
    100% of the time. Single quotes are issued concurrently instead, and the
    per-symbol cache means a repeated watchlist refresh mostly costs nothing.
    """
    requested = [s.strip().upper() for s in symbols.split(",") if s.strip()]
    if not requested:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="No ticker symbols supplied."
        )
    if len(requested) > MAX_BATCH_SYMBOLS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"At most {MAX_BATCH_SYMBOLS} symbols can be requested at once.",
        )

    # Deduplicate while preserving the caller's order.
    unique = list(dict.fromkeys(requested))
    results = client.get_many(
        {
            symbol: (lambda s=symbol: fmp_get("quote", {"symbol": s}, ttl=TTL_QUOTE))
            for symbol in unique
        }
    )

    quotes = []
    for symbol in unique:
        payload = results.get(symbol)
        if isinstance(payload, list) and payload:
            quotes.append(payload[0])
        elif isinstance(payload, dict):
            quotes.append(payload)
    return quotes


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

    is_premium = current_user.subscription_status == "active"

    return {
        "total_analyses": len(jobs),
        "completed_analyses": len(completed),
        "failed_analyses": len(failed),
        "pending_analyses": len(pending),
        "tickers_analyzed": tickers_analyzed,
        "watchlist_count": len(watchlist),
        "subscription_status": current_user.subscription_status,
        "is_premium": is_premium,
        # The frontend used to hardcode the cap, so the two could disagree
        # after a config change. None means "no limit applies".
        "analyses_today": crud.count_user_analyses_today(db, current_user.id),
        "free_tier_daily_limit": None if is_premium else settings.FREE_TIER_DAILY_ANALYSES,
    }


# ── Search ────────────────────────────────────────────────────

@router.get("/search")
def search_ticker(
    q: str = Query(..., min_length=1, description="Search query"),
    current_user: models.User = Depends(get_current_user),
):
    """Search for stock tickers or companies by name or symbol."""
    data = fmp_get("search-symbol", {"query": q.strip(), "limit": "10"}, ttl=TTL_SEARCH)
    if data is None:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Search failed.")
    return data
