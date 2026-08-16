"""
Tests for the Stripe integration — the money path, previously untested.

Signature verification is stubbed (that is Stripe's code, not ours); what is
tested is what the app does with an event once it is trusted.
"""

import pytest
import stripe
from fastapi.testclient import TestClient

from app import crud
from app.api.v1 import endpoints_stripe


@pytest.fixture
def deliver(client: TestClient, monkeypatch):
    """Deliver a webhook event as though Stripe had signed it."""

    def _deliver(event_type: str, obj: dict):
        monkeypatch.setattr(
            endpoints_stripe.stripe.Webhook,
            "construct_event",
            lambda payload, sig_header, secret: {"type": event_type, "data": {"object": obj}},
        )
        return client.post(
            "/api/v1/stripe/webhook",
            json={},
            headers={"stripe-signature": "test-signature"},
        )

    return _deliver


class TestWebhookSecurity:
    def test_missing_signature_is_rejected(self, client: TestClient):
        assert client.post("/api/v1/stripe/webhook", json={}).status_code == 400

    def test_invalid_signature_is_rejected(self, client: TestClient, monkeypatch):
        def raise_signature_error(payload, sig_header, secret):
            raise stripe.error.SignatureVerificationError("bad", sig_header)

        monkeypatch.setattr(
            endpoints_stripe.stripe.Webhook, "construct_event", raise_signature_error
        )
        response = client.post(
            "/api/v1/stripe/webhook", json={}, headers={"stripe-signature": "forged"}
        )
        assert response.status_code == 400

    def test_malformed_payload_is_rejected(self, client: TestClient, monkeypatch):
        def raise_value_error(payload, sig_header, secret):
            raise ValueError("not json")

        monkeypatch.setattr(
            endpoints_stripe.stripe.Webhook, "construct_event", raise_value_error
        )
        response = client.post(
            "/api/v1/stripe/webhook", json={}, headers={"stripe-signature": "sig"}
        )
        assert response.status_code == 400


class TestCheckoutCompleted:
    def test_subscription_is_activated(self, deliver, db, test_user):
        user = crud.get_user_by_email(db, test_user["email"])
        assert user.subscription_status == "free"

        response = deliver(
            "checkout.session.completed",
            {"client_reference_id": str(user.id), "customer": "cus_123"},
        )
        assert response.status_code == 200

        db.refresh(user)
        assert user.subscription_status == "active"
        assert user.stripe_customer_id == "cus_123"

    def test_a_non_numeric_reference_does_not_500(self, deliver, test_user):
        """
        A 500 makes Stripe retry the delivery indefinitely, so bad input has to
        be acknowledged rather than raised.
        """
        response = deliver(
            "checkout.session.completed",
            {"client_reference_id": "not-a-number", "customer": "cus_123"},
        )
        assert response.status_code == 200
        assert response.json()["status"] == "ignored"

    def test_an_unknown_user_is_ignored(self, deliver, test_user):
        response = deliver(
            "checkout.session.completed",
            {"client_reference_id": "999999", "customer": "cus_123"},
        )
        assert response.status_code == 200
        assert response.json()["status"] == "ignored"

    def test_missing_customer_is_ignored(self, deliver, db, test_user):
        user = crud.get_user_by_email(db, test_user["email"])
        response = deliver(
            "checkout.session.completed", {"client_reference_id": str(user.id)}
        )
        assert response.status_code == 200
        db.refresh(user)
        assert user.subscription_status == "free"


class TestSubscriptionLifecycle:
    def _activate(self, deliver, db, test_user) -> object:
        user = crud.get_user_by_email(db, test_user["email"])
        deliver(
            "checkout.session.completed",
            {"client_reference_id": str(user.id), "customer": "cus_123"},
        )
        db.refresh(user)
        return user

    def test_cancellation_deactivates(self, deliver, db, test_user):
        user = self._activate(deliver, db, test_user)

        deliver("customer.subscription.deleted", {"customer": "cus_123"})
        db.refresh(user)
        assert user.subscription_status != "active"

    def test_failed_payment_suspends_access(self, deliver, db, test_user):
        """
        A failed payment used to only write a log line, leaving premium access
        in place indefinitely.
        """
        user = self._activate(deliver, db, test_user)

        deliver("invoice.payment_failed", {"customer": "cus_123"})
        db.refresh(user)
        assert user.subscription_status == "past_due"

    def test_recovered_payment_restores_access(self, deliver, db, test_user):
        user = self._activate(deliver, db, test_user)
        deliver("invoice.payment_failed", {"customer": "cus_123"})

        deliver("invoice.payment_succeeded", {"customer": "cus_123"})
        db.refresh(user)
        assert user.subscription_status == "active"

    def test_events_for_unknown_customers_are_harmless(self, deliver, test_user):
        assert deliver("invoice.payment_failed", {"customer": "cus_nobody"}).status_code == 200
        assert deliver("customer.subscription.deleted", {"customer": "cus_nobody"}).status_code == 200

    def test_unhandled_event_types_are_acknowledged(self, deliver):
        assert deliver("customer.updated", {"customer": "cus_123"}).status_code == 200


class TestCheckoutSession:
    def test_requires_authentication(self, client: TestClient):
        assert client.post("/api/v1/stripe/create-checkout-session").status_code == 401

    def test_unconfigured_price_id_is_reported(self, client: TestClient, auth_headers, monkeypatch):
        monkeypatch.setattr(endpoints_stripe.settings, "STRIPE_PREMIUM_PRICE_ID", "")
        response = client.post("/api/v1/stripe/create-checkout-session", headers=auth_headers)
        assert response.status_code == 503

    def test_session_id_is_returned(self, client: TestClient, auth_headers, monkeypatch):
        monkeypatch.setattr(endpoints_stripe.settings, "STRIPE_PREMIUM_PRICE_ID", "price_123")
        monkeypatch.setattr(
            endpoints_stripe.stripe.checkout.Session,
            "create",
            classmethod(lambda cls, **kwargs: type("S", (), {"id": "cs_test_123"})()),
        )
        response = client.post("/api/v1/stripe/create-checkout-session", headers=auth_headers)
        assert response.status_code == 200
        assert response.json()["sessionId"] == "cs_test_123"

    def test_provider_errors_are_not_leaked(self, client: TestClient, auth_headers, monkeypatch):
        monkeypatch.setattr(endpoints_stripe.settings, "STRIPE_PREMIUM_PRICE_ID", "price_123")

        def explode(cls, **kwargs):
            raise stripe.error.StripeError("card declined: internal detail")

        monkeypatch.setattr(
            endpoints_stripe.stripe.checkout.Session, "create", classmethod(explode)
        )
        response = client.post("/api/v1/stripe/create-checkout-session", headers=auth_headers)
        assert response.status_code == 502
        assert "internal detail" not in response.json()["detail"]


class TestCancelSubscription:
    def test_requires_authentication(self, client: TestClient):
        assert client.post("/api/v1/stripe/cancel-subscription").status_code == 401

    def test_without_a_customer_id_it_reports_no_subscription(self, client: TestClient, auth_headers):
        response = client.post("/api/v1/stripe/cancel-subscription", headers=auth_headers)
        assert response.status_code == 400
