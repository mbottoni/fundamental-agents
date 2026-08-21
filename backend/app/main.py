"""
Stock Analyzer AI — Application Entry Point
=============================================
Sets up FastAPI with middleware (CORS, rate limiting, security headers),
Sentry monitoring, database initialization, and all API routers.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from .api.v1 import (
    endpoints_alerts,
    endpoints_analysis,
    endpoints_auth,
    endpoints_chart,
    endpoints_compare,
    endpoints_dashboard,
    endpoints_history,
    endpoints_market,
    endpoints_reports,
    endpoints_screener,
    endpoints_stripe,
    endpoints_watchlist,
)
from .core.config import logger, settings
from .core.db import engine
from .core.rate_limit import RateLimitMiddleware
from .db.base import Base


# ── Sentry (optional) ─────────────────────────────────────────

if settings.SENTRY_DSN:
    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration

        sentry_sdk.init(
            dsn=settings.SENTRY_DSN,
            integrations=[FastApiIntegration(), SqlalchemyIntegration()],
            traces_sample_rate=0.1,
            send_default_pii=False,
        )
        logger.info("Sentry initialized.")
    except Exception as e:
        logger.warning("Sentry init failed (non-fatal): %s", e)


# ── Security Headers Middleware ───────────────────────────────

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add standard security headers to every response."""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        # HSTS only in production (when not localhost)
        if "localhost" not in settings.FRONTEND_URL:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response


# ── Database Startup Migration ────────────────────────────────

def _run_auto_migrations() -> None:
    """
    Lightweight auto-migration for columns added after initial schema.
    For a real production system, use `alembic upgrade head` instead.
    """
    from sqlalchemy import text, inspect as sa_inspect

    with engine.connect() as conn:
        inspector = sa_inspect(engine)

        # reports.chart_data
        report_cols = [c["name"] for c in inspector.get_columns("reports")]
        if "chart_data" not in report_cols:
            conn.execute(text("ALTER TABLE reports ADD COLUMN chart_data TEXT"))
            logger.info("Migration: added chart_data column to reports.")

        # users.is_verified
        user_cols = [c["name"] for c in inspector.get_columns("users")]
        if "is_verified" not in user_cols:
            conn.execute(text("ALTER TABLE users ADD COLUMN is_verified BOOLEAN NOT NULL DEFAULT false"))
            logger.info("Migration: added is_verified column to users.")

        # analysissnapshots is created by create_all(); nothing to patch here.

        # analysisjobs.error_message
        job_cols = [c["name"] for c in inspector.get_columns("analysisjobs")]
        if "error_message" not in job_cols:
            conn.execute(text("ALTER TABLE analysisjobs ADD COLUMN error_message TEXT"))
            logger.info("Migration: added error_message column to analysisjobs.")

        conn.commit()


def _reap_interrupted_jobs() -> None:
    """
    Fail jobs left running by a previous process.

    Analyses run as in-process background tasks, so anything mid-flight when
    the server stopped is gone — without this the frontend polls those jobs
    forever.
    """
    from .core.db import SessionLocal
    from .crud import fail_stale_jobs

    db = SessionLocal()
    try:
        fail_stale_jobs(
            db,
            "This analysis was interrupted by a server restart and did not finish. "
            "Please run it again.",
        )
    except Exception as e:
        logger.warning("Could not reap interrupted jobs (non-fatal): %s", e)
    finally:
        db.close()


async def _watchlist_sweep() -> None:
    """
    Evaluate every watchlist on a timer.

    Analyses run in-process and there is no scheduler, so this is a plain
    asyncio task. It runs the blocking evaluation in a worker thread to keep
    the event loop free, and never lets an error end the loop.
    """
    import asyncio

    interval = settings.ALERT_SWEEP_MINUTES * 60
    if interval <= 0:
        logger.info("Watchlist alert sweep disabled (ALERT_SWEEP_MINUTES=0).")
        return

    from .core.db import SessionLocal
    from .services.alerts import evaluate_alerts

    def sweep() -> int:
        db = SessionLocal()
        try:
            return len(evaluate_alerts(db))
        finally:
            db.close()

    logger.info("Watchlist alert sweep every %d minute(s).", settings.ALERT_SWEEP_MINUTES)
    while True:
        try:
            await asyncio.sleep(interval)
            created = await asyncio.to_thread(sweep)
            if created:
                logger.info("Watchlist sweep raised %d alert(s).", created)
        except asyncio.CancelledError:
            raise
        except Exception as e:  # noqa: BLE001 - a bad sweep must not stop the rest
            logger.error("Watchlist sweep failed: %s", e, exc_info=True)


# ── Lifespan ──────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Stock Analyzer AI...")
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables verified.")
    _run_auto_migrations()
    _reap_interrupted_jobs()

    import asyncio

    sweep_task = asyncio.create_task(_watchlist_sweep())

    yield

    logger.info("Shutting down Stock Analyzer AI...")
    sweep_task.cancel()
    engine.dispose()
    logger.info("Database connections closed.")


# ── App Factory ───────────────────────────────────────────────

app = FastAPI(
    title="Stock Analyzer AI",
    description="Multi-agent AI platform for fundamental stock analysis.",
    version="2.0.0",
    lifespan=lifespan,
)

# Rate limiting. See app/core/rate_limit.py — the previous slowapi wiring
# never counted a single request.
app.add_middleware(RateLimitMiddleware)

# Security headers
app.add_middleware(SecurityHeadersMiddleware)

# CORS
allowed_origins = [
    settings.FRONTEND_URL,
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────

app.include_router(endpoints_auth.router, prefix="/api/v1/auth", tags=["Authentication"])
app.include_router(endpoints_analysis.router, prefix="/api/v1/analysis", tags=["Analysis"])
app.include_router(endpoints_reports.router, prefix="/api/v1/reports", tags=["Reports"])
app.include_router(endpoints_stripe.router, prefix="/api/v1/stripe", tags=["Stripe"])
app.include_router(endpoints_dashboard.router, prefix="/api/v1/dashboard", tags=["Dashboard"])
app.include_router(endpoints_watchlist.router, prefix="/api/v1/watchlist", tags=["Watchlist"])
app.include_router(endpoints_compare.router, prefix="/api/v1/compare", tags=["Compare"])
app.include_router(endpoints_screener.router, prefix="/api/v1/screener", tags=["Screener"])
app.include_router(endpoints_chart.router, prefix="/api/v1/chart", tags=["Chart"])
app.include_router(endpoints_market.router, prefix="/api/v1/market", tags=["Market"])
app.include_router(endpoints_history.router, prefix="/api/v1/history", tags=["History"])
app.include_router(endpoints_alerts.router, prefix="/api/v1/alerts", tags=["Alerts"])


# ── Root & Health ─────────────────────────────────────────────

@app.get("/", tags=["Health"])
def root():
    return {"name": "Stock Analyzer AI", "version": "2.0.0", "docs": "/docs"}


@app.get("/health", tags=["Health"])
def health_check():
    return {"status": "healthy"}
