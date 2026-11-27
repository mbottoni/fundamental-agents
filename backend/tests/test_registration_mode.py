"""
Who may create an account.

The market-data plan allows 250 requests a day and an analysis costs about
eleven, so a handful of strangers' free accounts can spend the day's quota for
everyone. A deployment has to be able to say "not yet".
"""

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings, settings

PASSWORD = "TestPass123"


def register(client: TestClient, email: str):
    return client.post("/api/v1/auth/register", json={"email": email, "password": PASSWORD})


def test_registration_is_open_unless_configured_otherwise():
    assert Settings.model_fields["REGISTRATION_MODE"].default == "open"


def test_open_lets_anyone_register(client, monkeypatch):
    monkeypatch.setattr(settings, "REGISTRATION_MODE", "open")
    assert register(client, "anyone@example.com").status_code == 201
    assert client.get("/api/v1/auth/registration").json() == {"mode": "open"}


def test_closed_lets_nobody_register(client, monkeypatch):
    monkeypatch.setattr(settings, "REGISTRATION_MODE", "closed")
    monkeypatch.setattr(settings, "REGISTRATION_ALLOWLIST", "listed@example.com")

    for email in ("anyone@example.com", "listed@example.com"):
        resp = register(client, email)
        assert resp.status_code == 403
        assert "closed" in resp.json()["detail"]
    assert client.get("/api/v1/auth/registration").json() == {"mode": "closed"}


def test_invite_lets_only_listed_addresses_register(client, monkeypatch):
    monkeypatch.setattr(settings, "REGISTRATION_MODE", "invite")
    monkeypatch.setattr(settings, "REGISTRATION_ALLOWLIST", "first@example.com, Second@Example.com")

    refused = register(client, "stranger@example.com")
    assert refused.status_code == 403
    assert "invitation" in refused.json()["detail"]

    assert register(client, "first@example.com").status_code == 201
    # Matched without regard to case, in either direction.
    assert register(client, "SECOND@example.com").status_code == 201


def test_invite_with_an_empty_list_lets_nobody_in(client, monkeypatch):
    monkeypatch.setattr(settings, "REGISTRATION_MODE", "invite")
    monkeypatch.setattr(settings, "REGISTRATION_ALLOWLIST", "")
    assert register(client, "anyone@example.com").status_code == 403


@pytest.mark.parametrize("mode", ["invite", "closed"])
def test_existing_accounts_can_still_sign_in(client, monkeypatch, mode):
    """Closing registration must not lock out the people already in."""
    assert register(client, "member@example.com").status_code == 201
    monkeypatch.setattr(settings, "REGISTRATION_MODE", mode)
    resp = client.post(
        "/api/v1/auth/login", data={"username": "member@example.com", "password": PASSWORD}
    )
    assert resp.status_code == 200


def test_the_status_endpoint_needs_no_sign_in(client):
    """The sign-up page asks before anyone has an account."""
    assert client.get("/api/v1/auth/registration").status_code == 200


def test_an_unknown_mode_is_refused():
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            SECRET_KEY="k9Jq2vX7mNp4sT8wZ1cF6hL3bR5yD0aGeUiOxVnMqWtYzAsBdCf",
            DATABASE_URL="sqlite://",
            FINANCIAL_MODELING_PREP_API_KEY="k",
            NEWS_API_KEY="k",
            STRIPE_SECRET_KEY="sk_test_abc",
            STRIPE_WEBHOOK_SECRET="whsec_abc",
            REGISTRATION_MODE="friends",
        )
