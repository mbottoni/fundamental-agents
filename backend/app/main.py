"""
Stock Analyzer AI — Application Entry Point
=============================================
Sets up FastAPI with middleware (CORS, rate limiting, security headers),
Sentry monitoring, database initialization, and all API routers.
"""

from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
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
from .core.db import engine, get_db
from .core.rate_limit import RateLimitMiddleware
from .db import base as _models  # noqa: F401 - registers every model
from .services import health
from .db.migrate import current_revision, head_revision, upgrade_to_head


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
        if settings.is_production:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response


def _recover_interrupted_jobs() -> None:
    """
    Put jobs stranded by a previous process back on the queue.

    This used to fail everything in flight, because an analysis running as an
    in-process background task really was gone once that process died. Now that
    jobs are claimed under a lease, a stranded one can simply be run again —
    which is strictly better for the user, who was charged a daily analysis when
    the job was created and would otherwise be told to spend another.

    Leases are checked rather than assumed expired: another worker may be
    perfectly healthy and midway through the job this process can see.
    """
    from .core.db import SessionLocal
    from .services.job_queue import reclaim_expired_jobs

    db = SessionLocal()
    try:
        reclaim_expired_jobs(db)
    except Exception as e:
        logger.warning("Could not recover interrupted jobs (non-fatal): %s", e)
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
    # Alembic is the only thing that changes the schema; a deploy migrates
    # itself here. A failure is fatal on purpose: serving requests against a
    # schema the code was not written for corrupts data quietly.
    state = upgrade_to_head(engine)
    if state == "ahead":
        logger.warning(
            "The database is at revision %s, newer than this code (%s). Running "
            "as a rollback: no migration was applied.",
            current_revision(engine), head_revision(),
        )
    else:
        logger.info("Database schema is at revision %s.", head_revision())
    _recover_interrupted_jobs()

    import asyncio

    sweep_task = asyncio.create_task(_watchlist_sweep())

    # The worker runs in-process for local development so `make up` still needs
    # one container. Production sets ANALYSIS_WORKER_INLINE=false and runs
    # `python -m app.worker` as its own service, so deploying the API does not
    # interrupt an analysis.
    worker = None
    worker_thread = None
    if settings.ANALYSIS_WORKER_INLINE:
        import threading

        from .worker import Worker

        worker = Worker()
        worker_thread = threading.Thread(
            target=worker.run_forever, name="inline-analysis-worker", daemon=True
        )
        worker_thread.start()
        app.state.inline_worker_thread = worker_thread
        logger.info("Inline analysis worker started.")
    else:
        logger.info("Inline worker disabled; expecting a standalone worker process.")

    yield

    logger.info("Shutting down Stock Analyzer AI...")
    sweep_task.cancel()
    if worker is not None:
        worker.stop()
        # Give an in-flight analysis a moment to release its lease. Anything
        # still running is reclaimed once its lease expires, so this is a
        # courtesy rather than a correctness requirement.
        if worker_thread is not None:
            worker_thread.join(timeout=5)
    engine.dispose()
    logger.info("Database connections closed.")


# ── App Factory ───────────────────────────────────────────────

app = FastAPI(
    title="Stock Analyzer AI",
    description="Multi-agent AI platform for fundamental stock analysis.",
    version="2.0.0",
    lifespan=lifespan,
    # The interactive docs describe every endpoint to anyone who asks. Caddy
    # already keeps them off the public hostname; this keeps them off in
    # production however the app is reached.
    docs_url=None if settings.is_production else "/docs",
    redoc_url=None if settings.is_production else "/redoc",
    openapi_url=None if settings.is_production else "/openapi.json",
)

# Rate limiting. See app/core/rate_limit.py — the previous slowapi wiring
# never counted a single request.
app.add_middleware(RateLimitMiddleware)

# Security headers
app.add_middleware(SecurityHeadersMiddleware)

# CORS
# In production the site and the API share one origin (see the Caddyfile), so
# no cross-origin request is expected at all. The local development origins
# are allowed in development only.
allowed_origins = [settings.FRONTEND_URL]
if not settings.is_production:
    allowed_origins += ["http://localhost:3000", "http://127.0.0.1:3000"]
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


@app.get("/healthz", tags=["Health"])
def healthz(request: Request, db: Session = Depends(get_db)):
    """
    Whether the site can do its job: database reachable, schema at the
    revision this code expects, a worker alive to run analyses.

    Always 200, with `status` either "ok" or "degraded" and the reason in the
    other fields, so a failing probe says what is wrong. Consumers check
    `status`, not the status code.
    """
    return health.check(db, inline_thread=getattr(request.app.state, "inline_worker_thread", None))
