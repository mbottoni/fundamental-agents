from typing import Optional

from sqlalchemy.orm import Session

from ..core.config import logger
from ..core.security import get_password_hash
from ..models.user import User
from ..schemas.user import UserCreate


def get_user_by_email(db: Session, email: str) -> Optional[User]:
    """Retrieve a user by their email address."""
    return db.query(User).filter(User.email == email).first()


def get_user_by_id(db: Session, user_id: int) -> Optional[User]:
    """Retrieve a user by their ID."""
    return db.query(User).filter(User.id == user_id).first()


def create_user(db: Session, user: UserCreate) -> User:
    """Create a new user with a hashed password."""
    hashed_password = get_password_hash(user.password)
    db_user = User(email=user.email, hashed_password=hashed_password)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    logger.info("Created new user: %s", user.email)
    return db_user


def update_user_subscription(
    db: Session, user_id: int, stripe_customer_id: str, status: str
) -> Optional[User]:
    """Update a user's Stripe subscription details."""
    user = get_user_by_id(db, user_id)
    if not user:
        logger.warning("Cannot update subscription: user %d not found", user_id)
        return None
    user.stripe_customer_id = stripe_customer_id
    user.subscription_status = status
    db.commit()
    db.refresh(user)
    logger.info("Updated subscription for user %d: status=%s", user_id, status)
    return user
