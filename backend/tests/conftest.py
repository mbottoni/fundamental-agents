"""
Shared fixtures for pytest.
Creates an in-memory SQLite database and a test client
so tests don't touch the real PostgreSQL instance.
"""

import os

# Override env vars BEFORE importing anything from the app
os.environ.setdefault("SECRET_KEY", "test-secret-key-that-is-at-least-32-characters-long-ok")
os.environ.setdefault("DATABASE_URL", "sqlite:///./test.db")
os.environ.setdefault("FINANCIAL_MODELING_PREP_API_KEY", "test_key")
os.environ.setdefault("NEWS_API_KEY", "test_key")
os.environ.setdefault("STRIPE_SECRET_KEY", "sk_test_fake")
os.environ.setdefault("STRIPE_WEBHOOK_SECRET", "whsec_fake")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

from app.db.base_class import Base
from app.core.db import get_db
from app.main import app

# ── In-memory SQLite for tests ────────────────────────────────

TEST_ENGINE = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=TEST_ENGINE)


def override_get_db():
    db = TestSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(autouse=True)
def setup_db():
    """Create all tables before each test, drop them after."""
    # Import all models so Base.metadata is fully populated
    import app.db.base  # noqa: F401

    Base.metadata.create_all(bind=TEST_ENGINE)
    yield
    Base.metadata.drop_all(bind=TEST_ENGINE)


@pytest.fixture
def db() -> Session:
    """Provide a test database session."""
    session = TestSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client() -> TestClient:
    """Provide a FastAPI test client."""
    return TestClient(app)


@pytest.fixture
def test_user(client: TestClient) -> dict:
    """Create a test user and return their credentials."""
    user_data = {"email": "test@example.com", "password": "TestPass123"}
    client.post("/api/v1/auth/register", json=user_data)
    return user_data


@pytest.fixture
def auth_headers(client: TestClient, test_user: dict) -> dict:
    """Authenticate and return headers with the access token."""
    resp = client.post(
        "/api/v1/auth/login",
        data={"username": test_user["email"], "password": test_user["password"]},
    )
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
