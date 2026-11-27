import logging
from typing import Literal, Optional

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings


# Fragments that mark a SECRET_KEY copied from an example or a test file. Any
# of them is long enough to pass the length check.
PLACEHOLDER_SECRET_MARKERS = ("changeme", "test-secret-key", "your-secret", "placeholder")


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # --- Security ---
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # --- Database ---
    DATABASE_URL: str

    # --- External APIs ---
    FINANCIAL_MODELING_PREP_API_KEY: str
    NEWS_API_KEY: str

    # --- Stripe ---
    STRIPE_SECRET_KEY: str
    STRIPE_WEBHOOK_SECRET: str
    STRIPE_PREMIUM_PRICE_ID: str = ""
    # Whether this deployment is meant to take real money. In production the
    # key has to agree with it, so running on test keys is a decision someone
    # made rather than a leftover, and a live key cannot slip in unannounced.
    STRIPE_LIVE: bool = False

    # --- Application ---
    # "production" turns on the start-up checks below and turns off everything
    # that exists for development: the interactive API docs, the localhost
    # CORS origins, and writing unsent emails (with their tokens) to the log.
    # The production compose file sets it.
    ENVIRONMENT: Literal["development", "production"] = "development"
    FRONTEND_URL: str = "http://localhost:3000"
    # The commit this build was made from; the image sets it. Reported by
    # /healthz so a deploy can be seen to have taken effect.
    APP_VERSION: str = "dev"
    LOG_LEVEL: str = "INFO"

    # Comma-separated addresses that always get premium, once verified. Empty
    # by default on purpose: a default address here is published with the
    # source, and granted premium on every deployment that forgets to set it.
    PREMIUM_EMAILS: str = ""

    # --- Rate Limiting ---
    # Requests per minute per caller. Authenticated callers are counted per
    # user; anonymous ones per client address.
    RATE_LIMIT_PER_MINUTE: int = 30
    # Off only where a test needs to make many calls in quick succession.
    RATE_LIMIT_ENABLED: bool = True
    # Who may create an account.
    #   open    anyone
    #   invite  only the addresses in REGISTRATION_ALLOWLIST (comma-separated)
    #   closed  nobody
    # The market-data plan allows 250 requests a day and an analysis costs about
    # eleven, so a handful of new free accounts can spend the day's quota for
    # everyone, paying users included. A new deployment should start on invite.
    REGISTRATION_MODE: Literal["open", "invite", "closed"] = "open"
    REGISTRATION_ALLOWLIST: str = ""
    FREE_TIER_DAILY_ANALYSES: int = 3
    # A repeat analysis of the same ticker within this window returns the
    # existing report instead of re-running the pipeline.
    ANALYSIS_REUSE_HOURS: int = 12
    # How often the watchlist sweep runs, in minutes. 0 disables it, which is
    # what you want if alerts are driven by an external scheduler instead.
    ALERT_SWEEP_MINUTES: int = 60

    # --- Email (optional - logs tokens to console when unset) ---
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    EMAILS_FROM_NAME: str = "StockAnalyzer AI"
    EMAILS_FROM_ADDRESS: str = "noreply@stockanalyzer.ai"

    # --- Analysis queue ---
    # How many analyses one worker runs at once. Each fans out ~11 provider
    # requests, so this is the main defence against walking into the provider's
    # rate limit; raise it only alongside the quota.
    ANALYSIS_WORKER_CONCURRENCY: int = 2
    # How long a claimed job may go without a heartbeat before another worker
    # treats it as abandoned and takes it over.
    ANALYSIS_LEASE_SECONDS: int = 300
    # How often an idle worker looks for new work.
    ANALYSIS_POLL_SECONDS: int = 5
    # Total attempts per job, including the first. Most pipeline failures are
    # provider timeouts, which usually succeed on a retry.
    ANALYSIS_MAX_ATTEMPTS: int = 3
    # Run the worker inside the API process. Convenient for local development,
    # where it keeps `make up` to one container; production runs the worker as
    # its own service so an API deploy does not interrupt it.
    ANALYSIS_WORKER_INLINE: bool = True
    # A standalone worker records that it is alive this often, and /healthz
    # reports "degraded" once the newest record is older than the second value:
    # with no worker, every analysis stays pending forever.
    WORKER_HEARTBEAT_SECONDS: int = 15
    WORKER_HEARTBEAT_STALE_SECONDS: int = 90

    # --- Caching (optional) ---
    # Set to share the market-data cache across gunicorn workers; without it
    # each worker keeps its own in-process cache.
    REDIS_URL: str = ""

    # --- Narrative summaries (optional) ---
    # Unset disables the feature; reports are generated without a written
    # summary and nothing else in the pipeline changes.
    ANTHROPIC_API_KEY: str = ""

    # --- Monitoring (optional) ---
    SENTRY_DSN: str = ""

    @field_validator("SECRET_KEY")
    @classmethod
    def secret_key_must_be_strong(cls, v: str) -> str:
        if len(v) < 32:
            raise ValueError(
                "SECRET_KEY must be at least 32 characters. "
                'Generate one with: python -c "import secrets; print(secrets.token_urlsafe(64))"'
            )
        return v

    @field_validator("DATABASE_URL")
    @classmethod
    def database_url_must_be_set(cls, v: str) -> str:
        if not v or v == "changeme":
            raise ValueError("DATABASE_URL must be properly configured.")
        return v

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"

    @model_validator(mode="after")
    def production_settings_must_be_real(self) -> "Settings":
        """
        Refuse to start in production on a setting left at its development
        value. Each of these fails silently otherwise: the app runs, and the
        mistake shows up later as a reset link to localhost or a payment that
        was never real.
        """
        if not self.is_production:
            return self

        problems = []
        if not self.FRONTEND_URL.startswith("https://"):
            problems.append(
                f"FRONTEND_URL is {self.FRONTEND_URL!r}. It must be the site's https:// "
                "origin: links in emails and Stripe return URLs are built from it."
            )
        if any(marker in self.SECRET_KEY.lower() for marker in PLACEHOLDER_SECRET_MARKERS):
            problems.append(
                "SECRET_KEY is a placeholder from an example file. Generate one with: "
                'python3 -c "import secrets; print(secrets.token_urlsafe(64))"'
            )
        if self.DATABASE_URL.startswith("sqlite"):
            problems.append("DATABASE_URL points at SQLite. Production runs on PostgreSQL.")
        live_key = self.STRIPE_SECRET_KEY.startswith(("sk_live_", "rk_live_"))
        if live_key and not self.STRIPE_LIVE:
            problems.append(
                "STRIPE_SECRET_KEY is a live key but STRIPE_LIVE is not set. Set "
                "STRIPE_LIVE=true once the go-live checklist is done, or use a test key."
            )
        if self.STRIPE_LIVE and not live_key:
            problems.append(
                "STRIPE_LIVE is set but STRIPE_SECRET_KEY is not a live key."
            )
        if problems:
            raise ValueError(
                "Refusing to start with ENVIRONMENT=production:\n- " + "\n- ".join(problems)
            )
        return self

    model_config = {
        # A validation error otherwise prints the start of what it was given,
        # which here is the secrets themselves, straight into the log.
        "hide_input_in_errors": True,
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
