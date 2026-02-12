from typing import Optional

from sqlalchemy.orm import Session

from ..core.config import logger
from ..models.watchlist import WatchlistItem
from ..schemas.watchlist import WatchlistItemCreate


def get_user_watchlist(db: Session, user_id: int) -> list[WatchlistItem]:
    """Return all watchlist items for a user, newest first."""
    return (
        db.query(WatchlistItem)
        .filter(WatchlistItem.user_id == user_id)
        .order_by(WatchlistItem.created_at.desc())
        .all()
    )


def get_watchlist_item(db: Session, item_id: int) -> Optional[WatchlistItem]:
    """Get a single watchlist item by ID."""
    return db.query(WatchlistItem).filter(WatchlistItem.id == item_id).first()


def get_watchlist_item_by_ticker(
    db: Session, user_id: int, ticker: str
) -> Optional[WatchlistItem]:
    """Check if a ticker is already in the user's watchlist."""
    return (
        db.query(WatchlistItem)
        .filter(WatchlistItem.user_id == user_id, WatchlistItem.ticker == ticker.upper())
        .first()
    )


def add_to_watchlist(
    db: Session, item: WatchlistItemCreate, user_id: int
) -> WatchlistItem:
    """Add a ticker to the user's watchlist."""
    db_item = WatchlistItem(
        user_id=user_id,
        ticker=item.ticker.upper(),
        notes=item.notes,
    )
    db.add(db_item)
    db.commit()
    db.refresh(db_item)
    logger.info("User %d added %s to watchlist", user_id, item.ticker)
    return db_item


def update_watchlist_item(
    db: Session, item_id: int, notes: Optional[str]
) -> Optional[WatchlistItem]:
    """Update notes on a watchlist item."""
    db_item = get_watchlist_item(db, item_id)
    if not db_item:
        return None
    db_item.notes = notes
    db.commit()
    db.refresh(db_item)
    return db_item


def remove_from_watchlist(db: Session, item_id: int) -> bool:
    """Remove an item from the watchlist. Returns True if deleted."""
    db_item = get_watchlist_item(db, item_id)
    if not db_item:
        return False
    db.delete(db_item)
    db.commit()
    logger.info("Watchlist item %d removed", item_id)
    return True
