import logging
from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # --- Security ---
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # --- Database ---
    DATABASE_URL: str

    # --- External APIs ---
    FINANCIAL_MODELING_PREP_API_KEY: str
    NEWS_API_KEY: str

    # --- Stripe ---
    STRIPE_SECRET_KEY: str
    STRIPE_WEBHOOK_SECRET: str
    STRIPE_PREMIUM_PRICE_ID: str = ""

    # --- Application ---
    FRONTEND_URL: str = "http://localhost:3000"
    LOG_LEVEL: str = "INFO"

    # Comma-separated list of emails that always get premium features.
    PREMIUM_EMAILS: str = "maruanbakriottoni@gmail.com"

    @field_validator("SECRET_KEY")
    @classmethod
    def secret_key_must_be_strong(cls, v: str) -> str:
        if len(v) < 32:
            raise ValueError(
                "SECRET_KEY must be at least 32 characters. "
                "Generate one with: python -c \"import secrets; print(secrets.token_urlsafe(64))\""
            )
        return v

    @field_validator("DATABASE_URL")
    @classmethod
    def database_url_must_be_set(cls, v: str) -> str:
        if not v or v == "changeme":
            raise ValueError("DATABASE_URL must be properly configured.")
        return v

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
    }


settings = Settings()


def setup_logging() -> logging.Logger:
    """Configure structured logging for the application."""
    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)

    logging.basicConfig(
        level=log_level,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Suppress noisy third-party loggers
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

    return logging.getLogger("stock_analyzer")


logger = setup_logging()
