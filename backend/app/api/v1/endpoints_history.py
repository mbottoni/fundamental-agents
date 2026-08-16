"""
Analysis History & Call Performance
===================================
Two questions the stored reports could not answer on their own:

  * How has the model's view of this ticker changed between runs?
  * Were the earlier calls any good?

Both are served from `analysissnapshots`, which records the recommendation,
the score and the price at the moment of each analysis.
"""

import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app import crud, models
from app.api.deps import get_current_user
from app.core.db import get_db
from app.core.market_data import TTL_QUOTE, client, fmp_get

logger = logging.getLogger("stock_analyzer.api.history")
router = APIRouter()

# Calls are grouped into "expected up" and "expected down" for scoring.
BULLISH = {"strong buy", "buy"}
BEARISH = {"strong sell", "sell"}


def _snapshot_dict(snapshot: models.AnalysisSnapshot) -> dict[str, Any]:
    return {
        "id": snapshot.id,
        "job_id": snapshot.job_id,
        "ticker": snapshot.ticker,
        "recommendation": snapshot.recommendation,
        "composite_score": snapshot.composite_score,
        "confidence": snapshot.confidence,
        "price": snapshot.price,
        "dcf_value": snapshot.dcf_value,
        "risk_rating": snapshot.risk_rating,
        "created_at": snapshot.created_at,
    }


def _current_prices(tickers: list[str]) -> dict[str, Optional[float]]:
    """Latest price per ticker, fetched concurrently and cached."""
    if not tickers:
        return {}

    results = client.get_many(
        {t: (lambda sym=t: fmp_get("quote", {"symbol": sym}, ttl=TTL_QUOTE)) for t in tickers}
    )

    prices: dict[str, Optional[float]] = {}
    for ticker, payload in results.items():
        quote = payload[0] if isinstance(payload, list) and payload else payload
        prices[ticker] = (quote or {}).get("price") if isinstance(quote, dict) else None
    return prices


@router.get("/{ticker}")
def ticker_history(
    ticker: str,
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    Every analysis this user has run on a ticker, oldest first, with the change
    since the previous run.
    """
    snapshots = crud.get_ticker_history(db, current_user.id, ticker, limit=limit)
    if not snapshots:
        return {"ticker": ticker.upper(), "snapshots": [], "latest_change": None}

    entries = [_snapshot_dict(s) for s in snapshots]

    # Deltas against the preceding run, so the reader sees movement rather than
    # a column of absolute numbers.
    for previous, current in zip(entries, entries[1:]):
        if previous["composite_score"] is not None and current["composite_score"] is not None:
            current["score_change"] = round(
                current["composite_score"] - previous["composite_score"], 3
            )
        if previous["price"] and current["price"]:
            current["price_change_pct"] = round(
                (current["price"] - previous["price"]) / previous["price"], 4
            )
        current["recommendation_changed"] = (
            previous["recommendation"] != current["recommendation"]
        )

    latest_change = entries[-1] if len(entries) > 1 else None
    return {
        "ticker": ticker.upper(),
        "snapshots": entries,
        "latest_change": {
            "score_change": (latest_change or {}).get("score_change"),
            "recommendation_changed": (latest_change or {}).get("recommendation_changed"),
            "previous_recommendation": entries[-2]["recommendation"] if len(entries) > 1 else None,
        }
        if latest_change
        else None,
    }


@router.get("/")
def call_performance(
    min_age_days: int = Query(
        7, ge=0, le=365, description="Ignore calls younger than this, which have not played out"
    ),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    How the user's past recommendations have fared against the market since.

    This is deliberately descriptive rather than a claim of skill: a handful of
    calls over a few weeks says almost nothing, so the response carries the
    sample size and the window alongside the numbers.
    """
    from datetime import datetime, timedelta, timezone

    snapshots = crud.get_user_snapshots(db, current_user.id)
    cutoff = datetime.now(timezone.utc) - timedelta(days=min_age_days)

    matured = []
    for snapshot in snapshots:
        if not snapshot.price or not snapshot.recommendation:
            continue
        created = snapshot.created_at
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        if created <= cutoff:
            matured.append(snapshot)

    if not matured:
        return {
            "sample_size": 0,
            "note": (
                "No calls are old enough to assess yet. Recommendations are included "
                f"once they are at least {min_age_days} days old."
            ),
            "calls": [],
            "by_recommendation": {},
        }

    prices = _current_prices(sorted({s.ticker for s in matured}))

    calls = []
    for snapshot in matured:
        current_price = prices.get(snapshot.ticker)
        if not current_price:
            continue
        change = (current_price - snapshot.price) / snapshot.price
        expected_up = snapshot.recommendation in BULLISH
        expected_down = snapshot.recommendation in BEARISH
        calls.append(
            {
                "ticker": snapshot.ticker,
                "recommendation": snapshot.recommendation,
                "composite_score": snapshot.composite_score,
                "confidence": snapshot.confidence,
                "price_at_call": snapshot.price,
                "current_price": current_price,
                "change_pct": round(change, 4),
                # A hold has no directional claim, so it is never scored.
                "directionally_right": (
                    None
                    if not (expected_up or expected_down)
                    else (change > 0 if expected_up else change < 0)
                ),
                "called_at": snapshot.created_at,
            }
        )

    by_recommendation: dict[str, Any] = {}
    for call in calls:
        bucket = by_recommendation.setdefault(
            call["recommendation"], {"count": 0, "total_change": 0.0, "right": 0, "scored": 0}
        )
        bucket["count"] += 1
        bucket["total_change"] += call["change_pct"]
        if call["directionally_right"] is not None:
            bucket["scored"] += 1
            bucket["right"] += 1 if call["directionally_right"] else 0

    for bucket in by_recommendation.values():
        bucket["average_change_pct"] = round(bucket["total_change"] / bucket["count"], 4)
        bucket["hit_rate"] = (
            round(bucket["right"] / bucket["scored"], 3) if bucket["scored"] else None
        )
        del bucket["total_change"]

    scored = [c for c in calls if c["directionally_right"] is not None]
    return {
        "sample_size": len(calls),
        "min_age_days": min_age_days,
        "overall_hit_rate": (
            round(sum(1 for c in scored if c["directionally_right"]) / len(scored), 3)
            if scored
            else None
        ),
        "note": (
            "Descriptive only. A small number of calls over a short window is not "
            "evidence of skill."
        ),
        "by_recommendation": by_recommendation,
        "calls": sorted(calls, key=lambda c: c["called_at"], reverse=True),
    }
