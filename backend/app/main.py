from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .api.v1 import endpoints_analysis, endpoints_auth, endpoints_reports, endpoints_stripe
from .core.db import engine
from .db import base

base.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Stock Analyzer AI")

# Set up CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

app.include_router(endpoints_analysis.router, prefix="/api/v1/analysis", tags=["analysis"])
app.include_router(endpoints_auth.router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(endpoints_reports.router, prefix="/api/v1/reports", tags=["reports"])
app.include_router(endpoints_stripe.router, prefix="/api/v1/stripe", tags=["stripe"])

@app.get("/")
def read_root():
    return {"Hello": "World"}
