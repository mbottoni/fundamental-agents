from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.v1 import endpoints_analysis, endpoints_auth, endpoints_reports, endpoints_stripe
from .core.config import logger, settings
from .core.db import engine
from .db.base import Base


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events for the application."""
    logger.info("Starting Stock Analyzer AI...")
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables verified.")
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
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
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


# --- Health Check ---
@app.get("/health", tags=["Health"])
def health_check():
    """Health check endpoint for load balancers and monitoring."""
    return {"status": "healthy"}
