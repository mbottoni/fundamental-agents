from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.v1 import (
    endpoints_analysis,
    endpoints_auth,
    endpoints_dashboard,
    endpoints_reports,
    endpoints_stripe,
    endpoints_watchlist,
)
from .core.config import logger, settings
from .core.db import engine
from .db.base import Base


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events for the application."""
    logger.info("Starting Stock Analyzer AI...")
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables verified.")

    # Auto-migrate: add chart_data column if it doesn't exist yet
    from sqlalchemy import text, inspect as sa_inspect
    with engine.connect() as conn:
        inspector = sa_inspect(engine)
        columns = [c["name"] for c in inspector.get_columns("reports")]
        if "chart_data" not in columns:
            conn.execute(text("ALTER TABLE reports ADD COLUMN chart_data TEXT"))
            conn.commit()
            logger.info("Migration: added chart_data column to reports table.")

    yield
    logger.info("Shutting down Stock Analyzer AI...")
    engine.dispose()
    logger.info("Database connections closed.")


app = FastAPI(
    title="Stock Analyzer AI",
    description="Multi-agent AI platform for fundamental stock analysis.",
    version="1.0.0",
    lifespan=lifespan,
)

# --- Middleware ---
# In development, the frontend may reach the backend from different origins
# (localhost, Docker internal network, etc.)
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

# --- Routers ---
app.include_router(
    endpoints_auth.router,
    prefix="/api/v1/auth",
    tags=["Authentication"],
)
app.include_router(
    endpoints_analysis.router,
    prefix="/api/v1/analysis",
    tags=["Analysis"],
)
app.include_router(
    endpoints_reports.router,
    prefix="/api/v1/reports",
    tags=["Reports"],
)
app.include_router(
    endpoints_stripe.router,
    prefix="/api/v1/stripe",
    tags=["Stripe"],
)
app.include_router(
    endpoints_watchlist.router,
    prefix="/api/v1/watchlist",
    tags=["Watchlist"],
)
app.include_router(
    endpoints_dashboard.router,
    prefix="/api/v1/dashboard",
    tags=["Dashboard"],
)


# --- Root & Health ---
@app.get("/", tags=["Health"])
def root():
    """Root endpoint."""
    return {"name": "Stock Analyzer AI", "version": "1.0.0", "docs": "/docs"}


@app.get("/health", tags=["Health"])
def health_check():
    """Health check endpoint for load balancers and monitoring."""
    return {"status": "healthy"}
