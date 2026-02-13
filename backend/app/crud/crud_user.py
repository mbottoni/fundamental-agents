from datetime import date, datetime, timezone
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from ..core.config import logger
from ..core.security import get_password_hash
from ..models.user import User
from ..models.analysis_job import AnalysisJob
from ..schemas.user import UserCreate


def get_user_by_email(db: Session, email: str) -> Optional[User]:
    """Retrieve a user by their email address."""
    return db.query(User).filter(User.email == email).first()


def get_user_by_id(db: Session, user_id: int) -> Optional[User]:
    """Retrieve a user by their ID."""
    return db.query(User).filter(User.id == user_id).first()


def get_user_by_stripe_customer_id(db: Session, stripe_customer_id: str) -> Optional[User]:
    """Retrieve a user by their Stripe customer ID."""
    return db.query(User).filter(User.stripe_customer_id == stripe_customer_id).first()


def create_user(db: Session, user: UserCreate) -> User:
    """Create a new user with a hashed password."""
    hashed_password = get_password_hash(user.password)
    db_user = User(email=user.email, hashed_password=hashed_password)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    logger.info("Created new user: %s", user.email)
    return db_user


def verify_user_email(db: Session, email: str) -> Optional[User]:
    """Mark a user's email as verified."""
    user = get_user_by_email(db, email)
    if not user:
        return None
    user.is_verified = True
    db.commit()
    db.refresh(user)
    logger.info("Email verified for user: %s", email)
    return user


def reset_user_password(db: Session, email: str, new_hashed_password: str) -> Optional[User]:
    """Reset a user's password."""
    user = get_user_by_email(db, email)
    if not user:
        return None
    user.hashed_password = new_hashed_password
    db.commit()
    db.refresh(user)
    logger.info("Password reset for user: %s", email)
    return user


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


def deactivate_subscription_by_stripe_id(db: Session, stripe_customer_id: str) -> Optional[User]:
    """Deactivate a subscription by Stripe customer ID."""
    user = get_user_by_stripe_customer_id(db, stripe_customer_id)
    if not user:
        logger.warning("Cannot deactivate: no user with stripe_customer_id %s", stripe_customer_id)
        return None
    user.subscription_status = "cancelled"
    db.commit()
    db.refresh(user)
    logger.info("Subscription deactivated for user %d (stripe: %s)", user.id, stripe_customer_id)
    return user


def count_user_analyses_today(db: Session, user_id: int) -> int:
    """Count the number of analysis jobs a user has created today."""
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    return (
        db.query(func.count(AnalysisJob.id))
        .filter(AnalysisJob.user_id == user_id, AnalysisJob.created_at >= today_start)
        .scalar()
        or 0
    )
