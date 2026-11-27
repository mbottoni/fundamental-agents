"""
PREMIUM_EMAILS grants premium to listed addresses on every request.

Two ways that went wrong: the setting had a real address as its default, so
any deployment that forgot the variable granted premium to whoever held that
address there; and "held" meant only "registered it first", because nothing
checked the address had been verified.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app import crud
from app.core.config import Settings, settings

EMAIL = "owner@example.com"
PASSWORD = "TestPass123"


def _sign_up(client: TestClient, email: str = EMAIL) -> dict:
    client.post("/api/v1/auth/register", json={"email": email, "password": PASSWORD})
    resp = client.post("/api/v1/auth/login", data={"username": email, "password": PASSWORD})
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _status_after_a_request(client: TestClient, db: Session, headers: dict, email: str = EMAIL) -> str:
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 200
    db.expire_all()
    return crud.get_user_by_email(db, email=email).subscription_status


def _verify(db: Session, email: str = EMAIL) -> None:
    user = crud.get_user_by_email(db, email=email)
    user.is_verified = True
    db.commit()


def test_the_setting_has_no_default_address():
    """A default here is published with the source and applies wherever the variable is unset."""
    assert Settings.model_fields["PREMIUM_EMAILS"].default == ""


def test_nobody_is_upgraded_when_the_list_is_empty(client, db, monkeypatch):
    monkeypatch.setattr(settings, "PREMIUM_EMAILS", "")
    headers = _sign_up(client)
    _verify(db)
    assert _status_after_a_request(client, db, headers) != "active"


def test_a_listed_address_is_not_upgraded_until_it_is_verified(client, db, monkeypatch):
    """Typing a listed address into the sign-up form must not be enough."""
    monkeypatch.setattr(settings, "PREMIUM_EMAILS", EMAIL)
    headers = _sign_up(client)
    assert _status_after_a_request(client, db, headers) != "active"


def test_a_listed_and_verified_address_is_upgraded(client, db, monkeypatch):
    monkeypatch.setattr(settings, "PREMIUM_EMAILS", f"someone@example.com, {EMAIL}")
    headers = _sign_up(client)
    _verify(db)
    assert _status_after_a_request(client, db, headers) == "active"


def test_the_list_is_matched_without_regard_to_case(client, db, monkeypatch):
    monkeypatch.setattr(settings, "PREMIUM_EMAILS", "Owner@Example.COM")
    headers = _sign_up(client)
    _verify(db)
    assert _status_after_a_request(client, db, headers) == "active"


def test_an_unlisted_verified_address_is_not_upgraded(client, db, monkeypatch):
    monkeypatch.setattr(settings, "PREMIUM_EMAILS", EMAIL)
    headers = _sign_up(client, "visitor@example.com")
    _verify(db, "visitor@example.com")
    assert _status_after_a_request(client, db, headers, "visitor@example.com") != "active"
