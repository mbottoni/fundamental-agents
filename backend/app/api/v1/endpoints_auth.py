import logging

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from jose import JWTError
from sqlalchemy.orm import Session

from app import crud, models, schemas
from app.core import security, email as email_service
from app.core.db import get_db
from app.api.deps import get_current_user

logger = logging.getLogger("stock_analyzer.api.auth")

router = APIRouter()


# ── Registration ──────────────────────────────────────────────

@router.post("/register", response_model=schemas.User, status_code=status.HTTP_201_CREATED)
def register(user: schemas.UserCreate, db: Session = Depends(get_db)):
    """Register a new user account and send a verification email."""
    existing_user = crud.get_user_by_email(db, email=user.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )
    new_user = crud.create_user(db=db, user=user)

    # Send verification email
    token = security.generate_timed_token(user.email, "email_verify", expires_minutes=1440)
    email_service.send_email_verification(user.email, token)

    return new_user


# ── Login ─────────────────────────────────────────────────────

@router.post("/login", response_model=schemas.Token)
def login(
    db: Session = Depends(get_db),
    form_data: OAuth2PasswordRequestForm = Depends(),
):
    """Authenticate a user and return access + refresh tokens."""
    user = crud.get_user_by_email(db, email=form_data.username)
    if not user or not security.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = security.create_access_token(data={"sub": user.email})
    refresh_token = security.create_refresh_token(data={"sub": user.email})
    return schemas.Token(access_token=access_token, refresh_token=refresh_token)


# ── Refresh Token ─────────────────────────────────────────────

@router.post("/refresh", response_model=schemas.Token)
def refresh_token(body: schemas.RefreshTokenRequest, db: Session = Depends(get_db)):
    """Exchange a valid refresh token for a new access + refresh token pair."""
    try:
        payload = security.decode_access_token(body.refresh_token)
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type.")
        email = payload.get("sub")
        if not email:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token.")
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired or invalid.")

    user = crud.get_user_by_email(db, email=email)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found.")

    new_access = security.create_access_token(data={"sub": user.email})
    new_refresh = security.create_refresh_token(data={"sub": user.email})
    return schemas.Token(access_token=new_access, refresh_token=new_refresh)


# ── Current User ──────────────────────────────────────────────

@router.get("/me", response_model=schemas.User)
def read_current_user(current_user: models.User = Depends(get_current_user)):
    """Return the currently authenticated user's profile."""
    return current_user


# ── Email Verification ────────────────────────────────────────

@router.post("/verify-email")
def verify_email(body: schemas.EmailVerifyRequest, db: Session = Depends(get_db)):
    """Verify a user's email with a signed token."""
    email = security.verify_timed_token(body.token, "email_verify")
    if not email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired verification link.")

    user = crud.verify_user_email(db, email)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    return {"message": "Email verified successfully."}


@router.post("/resend-verification")
def resend_verification(current_user: models.User = Depends(get_current_user)):
    """Resend the email verification link."""
    if current_user.is_verified:
        return {"message": "Email is already verified."}

    token = security.generate_timed_token(current_user.email, "email_verify", expires_minutes=1440)
    email_service.send_email_verification(current_user.email, token)
    return {"message": "Verification email sent."}


# ── Password Reset ────────────────────────────────────────────

@router.post("/forgot-password")
def forgot_password(body: schemas.PasswordResetRequest, db: Session = Depends(get_db)):
    """Send a password reset link. Always returns 200 to prevent email enumeration."""
    user = crud.get_user_by_email(db, email=body.email)
    if user:
        token = security.generate_timed_token(user.email, "password_reset", expires_minutes=60)
        email_service.send_password_reset_email(user.email, token)
        logger.info("Password reset requested for %s", body.email)
    # Always return success to prevent email enumeration
    return {"message": "If an account exists with this email, a reset link has been sent."}


@router.post("/reset-password")
def reset_password(body: schemas.PasswordResetConfirm, db: Session = Depends(get_db)):
    """Reset a user's password using a signed token."""
    email = security.verify_timed_token(body.token, "password_reset")
    if not email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired reset link.")

    hashed = security.get_password_hash(body.new_password)
    user = crud.reset_user_password(db, email, hashed)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    return {"message": "Password reset successfully. You can now log in with your new password."}
