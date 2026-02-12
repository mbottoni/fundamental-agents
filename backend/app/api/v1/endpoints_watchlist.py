from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app import crud, models, schemas
from app.api.deps import get_current_user
from app.core.db import get_db

router = APIRouter()


@router.get("/", response_model=list[schemas.WatchlistItem])
def list_watchlist(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Return the current user's watchlist."""
    return crud.get_user_watchlist(db, user_id=current_user.id)


@router.post("/", response_model=schemas.WatchlistItem, status_code=status.HTTP_201_CREATED)
def add_watchlist_item(
    item: schemas.WatchlistItemCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Add a ticker to the user's watchlist."""
    existing = crud.get_watchlist_item_by_ticker(db, user_id=current_user.id, ticker=item.ticker)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"{item.ticker} is already in your watchlist.",
        )
    return crud.add_to_watchlist(db, item=item, user_id=current_user.id)


@router.patch("/{item_id}", response_model=schemas.WatchlistItem)
def update_watchlist_item(
    item_id: int,
    update: schemas.WatchlistItemUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Update notes on a watchlist item."""
    db_item = crud.get_watchlist_item(db, item_id)
    if not db_item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found.")
    if db_item.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your item.")
    return crud.update_watchlist_item(db, item_id=item_id, notes=update.notes)


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_watchlist_item(
    item_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Remove a ticker from the user's watchlist."""
    db_item = crud.get_watchlist_item(db, item_id)
    if not db_item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found.")
    if db_item.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your item.")
    crud.remove_from_watchlist(db, item_id=item_id)
