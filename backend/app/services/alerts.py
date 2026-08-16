"""
Watchlist Alert Evaluation
==========================
Turns a saved watchlist into something that does work between visits.

Two things are worth telling a user about without them re-running an analysis
by hand: a price target being reached, and the model changing its mind about a
holding since the last time it looked.

Evaluation is idempotent — running it twice in a row produces one alert, not
two — because it is driven both by a periodic task and by an explicit request.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session

from ..core.market_data import TTL_QUOTE, client, fmp_get
from ..models.alert import (
    KIND_PRICE_TARGET,
    KIND_RECOMMENDATION_CHANGE,
    Alert,
)
from ..models.analysis_snapshot import AnalysisSnapshot
from ..models.watchlist import WatchlistItem

logger = logging.getLogger("stock_analyzer.services.alerts")

# An alert of the same kind for the same ticker inside this window is treated
# as already delivered, so a price hovering on a target does not spam.
DEDUPE_HOURS = 24


def _recently_alerted(db: Session, user_id: int, ticker: str, kind: str) -> bool:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=DEDUPE_HOURS)
    return (
        db.query(Alert)
        .filter(
            Alert.user_id == user_id,
            Alert.ticker == ticker,
            Alert.kind == kind,
            Alert.created_at >= cutoff,
        )
        .first()
        is not None
    )


def _latest_prices(tickers: list[str]) -> dict[str, Optional[float]]:
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


def _check_price_targets(
    db: Session, items: list[WatchlistItem], prices: dict[str, Optional[float]]
) -> list[Alert]:
    alerts: list[Alert] = []

    for item in items:
        if not item.target_price or not item.target_direction:
            continue
        price = prices.get(item.ticker)
        if price is None:
            continue

        crossed = (
            price >= item.target_price
            if item.target_direction == "above"
            else price <= item.target_price
        )
        if not crossed or _recently_alerted(db, item.user_id, item.ticker, KIND_PRICE_TARGET):
            continue

        alerts.append(
            Alert(
                user_id=item.user_id,
                ticker=item.ticker,
                kind=KIND_PRICE_TARGET,
                triggered_value=price,
                message=(
                    f"{item.ticker} is at ${price:,.2f}, "
                    f"{'at or above' if item.target_direction == 'above' else 'at or below'} "
                    f"your ${item.target_price:,.2f} target."
                ),
            )
        )

    return alerts


def _check_recommendation_changes(db: Session, items: list[WatchlistItem]) -> list[Alert]:
    """Alert when the two most recent analyses of a watched ticker disagree."""
    alerts: list[Alert] = []

    for item in items:
        snapshots = (
            db.query(AnalysisSnapshot)
            .filter(
                AnalysisSnapshot.user_id == item.user_id,
                AnalysisSnapshot.ticker == item.ticker,
            )
            .order_by(AnalysisSnapshot.created_at.desc())
            .limit(2)
            .all()
        )
        if len(snapshots) < 2:
            continue

        latest, previous = snapshots
        if not latest.recommendation or latest.recommendation == previous.recommendation:
            continue
        if _recently_alerted(db, item.user_id, item.ticker, KIND_RECOMMENDATION_CHANGE):
            continue

        alerts.append(
            Alert(
                user_id=item.user_id,
                ticker=item.ticker,
                kind=KIND_RECOMMENDATION_CHANGE,
                triggered_value=latest.composite_score,
                message=(
                    f"{item.ticker} moved from {previous.recommendation.upper()} to "
                    f"{latest.recommendation.upper()} in the latest analysis."
                ),
            )
        )

    return alerts


def evaluate_alerts(db: Session, user_id: Optional[int] = None) -> list[Alert]:
    """
    Evaluate every watchlist (or one user's) and persist any new alerts.

    Returns the alerts created by this run — an empty list when nothing has
    changed, which is the normal case.
    """
    query = db.query(WatchlistItem)
    if user_id is not None:
        query = query.filter(WatchlistItem.user_id == user_id)
    items = query.all()
    if not items:
        return []

    # One quote per distinct ticker, however many users watch it.
    tickers = sorted({item.ticker for item in items if item.target_price})
    prices = _latest_prices(tickers)

    new_alerts = _check_price_targets(db, items, prices) + _check_recommendation_changes(db, items)

    if new_alerts:
        db.add_all(new_alerts)
        db.commit()
        for alert in new_alerts:
            db.refresh(alert)
        logger.info("Raised %d watchlist alert(s)", len(new_alerts))

    return new_alerts
