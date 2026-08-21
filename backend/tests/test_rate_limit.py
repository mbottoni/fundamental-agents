"""
Tests for rate limiting.

Two failures are covered here, both of which shipped:

1. Nothing was ever counted. `RATE_LIMIT_PER_MINUTE` was handed to slowapi as
   a default limit, but default limits only apply from SlowAPIMiddleware,
   which was never installed — and would not have worked anyway, since
   slowapi cannot resolve routes nested in this Starlette version's
   `_IncludedRouter` entries and treats an unresolved route as exempt.
2. The key was the client address, which behind the production reverse proxy
   is the proxy's own address — one bucket for every user in the world.

The limiter is disabled for the rest of the suite (see conftest); these tests
turn it back on and reset its storage so each starts from a clean count.
"""

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.config import settings
from app.core.rate_limit import client_key, limiter
from app.core.security import create_access_token, create_refresh_token


@pytest.fixture
def limited():
    """Enable the limiter for one test, with an empty count, then restore it."""
    previous = limiter.enabled
    limiter.enabled = True
    limiter.reset()
    yield limiter
    limiter.reset()
    limiter.enabled = previous


class _FakeRequest:
    """The pieces of a Request the key function actually reads."""

    def __init__(self, auth: str | None = None, host: str = "203.0.113.7"):
        self.headers = {"Authorization": auth} if auth else {}

        class _Client:
            def __init__(self, h):
                self.host = h

        self.client = _Client(host)


def _limit() -> int:
    return settings.RATE_LIMIT_PER_MINUTE


# ── The key function ──────────────────────────────────────────

class TestClientKey:
    def test_authenticated_request_keys_on_the_user(self):
        token = create_access_token({"sub": "someone@example.com"})
        assert client_key(_FakeRequest(f"Bearer {token}")) == "user:someone@example.com"

    def test_two_users_behind_one_address_get_different_keys(self):
        """The bug: one proxy address meant one shared bucket."""
        a = create_access_token({"sub": "a@example.com"})
        b = create_access_token({"sub": "b@example.com"})
        host = "10.0.0.1"  # the same proxy for both
        assert client_key(_FakeRequest(f"Bearer {a}", host)) != client_key(
            _FakeRequest(f"Bearer {b}", host)
        )

    def test_anonymous_request_falls_back_to_address(self):
        assert client_key(_FakeRequest(None, "198.51.100.4")) == "ip:198.51.100.4"

    def test_email_case_does_not_open_a_second_bucket(self):
        lower = create_access_token({"sub": "user@example.com"})
        upper = create_access_token({"sub": "USER@example.com"})
        assert client_key(_FakeRequest(f"Bearer {lower}")) == client_key(
            _FakeRequest(f"Bearer {upper}")
        )

    @pytest.mark.parametrize(
        "header",
        [
            "Bearer not-a-jwt",
            "Bearer ",
            "Basic dXNlcjpwYXNz",
            "garbage",
            "",
        ],
    )
    def test_unusable_authorization_headers_fall_back_rather_than_raise(self, header):
        """A key function that raises would turn every request into a 500."""
        assert client_key(_FakeRequest(header, "192.0.2.9")) == "ip:192.0.2.9"

    def test_refresh_token_does_not_open_a_second_bucket(self):
        """Only access tokens identify a caller; a refresh token is not a key."""
        refresh = create_refresh_token({"sub": "user@example.com"})
        assert client_key(_FakeRequest(f"Bearer {refresh}", "192.0.2.9")) == "ip:192.0.2.9"


# ── Enforcement ───────────────────────────────────────────────

class TestEnforcement:
    def test_limit_is_actually_enforced(self, client: TestClient, limited):
        """
        Regression: without SlowAPIMiddleware the limiter counted nothing, and
        this loop returned 200 every time.
        """
        codes = [
            client.get("/api/v1/dashboard/stats").status_code
            for _ in range(settings.RATE_LIMIT_PER_MINUTE + 5)
        ]
        assert 429 in codes, "requests past the limit were not rejected"

    def test_one_user_cannot_exhaust_anothers_budget(
        self, client: TestClient, limited, auth_headers: dict
    ):
        """
        The point of user keying: both users arrive from the same test client
        address, so under address keying the second would inherit the first's
        exhausted bucket.
        """
        for _ in range(settings.RATE_LIMIT_PER_MINUTE + 5):
            client.get("/api/v1/dashboard/stats", headers=auth_headers)

        other = {"email": "second@example.com", "password": "TestPass123"}
        client.post("/api/v1/auth/register", json=other)
        login = client.post(
            "/api/v1/auth/login",
            data={"username": other["email"], "password": other["password"]},
        )
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

        assert client.get("/api/v1/dashboard/stats", headers=headers).status_code != 429

    def test_health_check_is_exempt(self, client: TestClient, limited):
        """
        A monitor polling /health must not lock users out from its address.

        Exhausts a normal route first, so this cannot pass merely because
        nothing is being enforced — the limiter is demonstrably active by the
        time /health is polled.
        """
        codes = [
            client.get("/api/v1/dashboard/stats").status_code
            for _ in range(settings.RATE_LIMIT_PER_MINUTE + 5)
        ]
        assert 429 in codes, "precondition: the limiter must be active"

        health = [
            client.get("/health").status_code
            for _ in range(settings.RATE_LIMIT_PER_MINUTE + 10)
        ]
        assert set(health) == {200}
