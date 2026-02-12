from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app import crud, models, schemas
from app.core.config import settings
from app.core.db import get_db
from app.core.security import decode_access_token

reusable_oauth2 = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

# Pre-compute the set of emails that always get premium access.
_PREMIUM_EMAILS: set[str] = {
    e.strip().lower() for e in settings.PREMIUM_EMAILS.split(",") if e.strip()
}


def get_current_user(
    db: Session = Depends(get_db),
    token: str = Depends(reusable_oauth2),
) -> models.User:
    """Dependency that extracts and validates the current user from the JWT token."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_access_token(token)
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
        token_data = schemas.TokenData(email=email)
    except (JWTError, ValidationError):
        raise credentials_exception

    user = crud.get_user_by_email(db, email=token_data.email)
    if user is None:
        raise credentials_exception

    # Grant permanent premium access to configured emails.
    if user.email.lower() in _PREMIUM_EMAILS and user.subscription_status != "active":
        user.subscription_status = "active"
        db.commit()
        db.refresh(user)

    return user
