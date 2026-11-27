"""
Production must refuse to start on a setting left at its development value.

Each of these fails silently otherwise: the app runs, and the mistake surfaces
later as a password-reset link to localhost, or a payment that was never real.
"""

import pytest
from pydantic import ValidationError

from app.core.config import Settings

GOOD = dict(
    ENVIRONMENT="production",
    SECRET_KEY="k9Jq2vX7mNp4sT8wZ1cF6hL3bR5yD0aGeUiOxVnMqWtYzAsBdCf",
    DATABASE_URL="postgresql://app:pw@db:5432/app",
    FINANCIAL_MODELING_PREP_API_KEY="k",
    NEWS_API_KEY="k",
    STRIPE_SECRET_KEY="sk_test_abc",
    STRIPE_WEBHOOK_SECRET="whsec_abc",
    FRONTEND_URL="https://example.com",
)


def build(**overrides) -> Settings:
    # _env_file=None: the developer's own .env must not leak into the test.
    return Settings(_env_file=None, **{**GOOD, **overrides})


def refusal(**overrides) -> str:
    with pytest.raises(ValidationError) as refused:
        build(**overrides)
    return str(refused.value)


def test_a_correct_production_configuration_starts():
    assert build().is_production


def test_development_accepts_what_production_refuses():
    settings = build(
        ENVIRONMENT="development",
        FRONTEND_URL="http://localhost:3000",
        SECRET_KEY="changeme_generate_a_secure_key_at_least_32_characters",
        DATABASE_URL="sqlite:///./dev.db",
    )
    assert not settings.is_production


def test_the_default_environment_is_development():
    assert Settings.model_fields["ENVIRONMENT"].default == "development"


@pytest.mark.parametrize("url", ["http://localhost:3000", "http://example.com", "example.com", ""])
def test_frontend_url_must_be_the_https_origin(url):
    """Left at its default, every emailed link and Stripe return URL points at localhost."""
    assert "FRONTEND_URL" in refusal(FRONTEND_URL=url)


@pytest.mark.parametrize(
    "key",
    [
        # .env.example's value: long enough to pass the length check.
        "changeme_generate_a_secure_key_at_least_32_characters",
        # CI's and the test suite's.
        "test-secret-key-that-is-at-least-32-characters-long-ok",
    ],
)
def test_a_placeholder_secret_key_is_refused(key):
    assert "SECRET_KEY" in refusal(SECRET_KEY=key)


def test_sqlite_is_refused():
    assert "PostgreSQL" in refusal(DATABASE_URL="sqlite:///./app.db")


def test_a_live_stripe_key_needs_the_switch():
    """A live key must not slip in unannounced."""
    assert "STRIPE_LIVE" in refusal(STRIPE_SECRET_KEY="sk_live_abc")


def test_the_switch_needs_a_live_key():
    """Believing payments are live while on test keys is the worse mistake."""
    assert "not a live key" in refusal(STRIPE_LIVE=True)


def test_live_key_and_switch_together_start():
    assert build(STRIPE_SECRET_KEY="sk_live_abc", STRIPE_LIVE=True).STRIPE_LIVE


def test_every_problem_is_reported_at_once():
    """Fixing a deployment one restart at a time is how a step gets skipped."""
    message = refusal(FRONTEND_URL="http://localhost:3000", DATABASE_URL="sqlite:///./app.db")
    assert "FRONTEND_URL" in message and "PostgreSQL" in message


def test_a_refusal_does_not_print_the_secrets_it_was_given():
    """Pydantic's errors echo their input by default; here that is every secret."""
    message = refusal(FRONTEND_URL="http://localhost:3000")
    assert GOOD["SECRET_KEY"][:8] not in message
    assert "whsec_" not in message


def test_an_unknown_environment_is_refused():
    with pytest.raises(ValidationError):
        build(ENVIRONMENT="staging")


# ── What production turns off ─────────────────────────────────────────────


def _import_app(environment: str) -> str:
    """Import the app in a fresh interpreter and report how it was built."""
    import os
    import pathlib
    import subprocess
    import sys

    env = {
        **os.environ,
        **{k: str(v) for k, v in GOOD.items()},
        "ENVIRONMENT": environment,
        "FRONTEND_URL": "https://example.com",
    }
    script = (
        "from app.main import app, allowed_origins;"
        "print(app.docs_url, app.redoc_url, app.openapi_url, len(allowed_origins))"
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=pathlib.Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr[-2000:]
    return result.stdout.strip().splitlines()[-1]


def test_production_serves_no_api_docs_and_allows_no_localhost_origin():
    assert _import_app("production") == "None None None 1"


def test_development_serves_the_docs():
    assert _import_app("development") == "/docs /redoc /openapi.json 3"


def test_an_unsent_email_is_not_written_to_the_log_in_production(monkeypatch, caplog):
    """The body carries a working reset or verification link."""
    import logging

    from app.core import email
    from app.core.config import settings

    monkeypatch.setattr(settings, "SMTP_HOST", "")
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    with caplog.at_level(logging.INFO):
        email.send_password_reset_email("someone@example.com", "the-secret-token")
    assert "the-secret-token" not in caplog.text
    assert "Email not sent" in caplog.text

    caplog.clear()
    monkeypatch.setattr(settings, "ENVIRONMENT", "development")
    with caplog.at_level(logging.INFO):
        email.send_password_reset_email("someone@example.com", "the-secret-token")
    assert "the-secret-token" in caplog.text  # development still prints the link


def test_an_operator_can_verify_an_account_without_email(client, db, monkeypatch, capsys):
    from sqlalchemy.orm import sessionmaker

    from app import crud, manage

    client.post("/api/v1/auth/register", json={"email": "owner@example.com", "password": "TestPass123"})
    monkeypatch.setattr(manage, "SessionLocal", sessionmaker(bind=db.get_bind()))

    assert manage.main(["verify", "nobody@example.com"]) == 1
    assert manage.main(["verify", "owner@example.com"]) == 0
    db.expire_all()
    assert crud.get_user_by_email(db, email="owner@example.com").is_verified is True
    assert manage.main(["verify", "owner@example.com"]) == 0  # idempotent
    assert manage.main(["users"]) == 0
    assert "owner@example.com\tverified" in capsys.readouterr().out
    assert manage.main([]) == 2
