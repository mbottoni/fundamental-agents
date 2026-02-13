"""Tests for authentication endpoints."""

from fastapi.testclient import TestClient


class TestRegister:
    def test_register_success(self, client: TestClient):
        resp = client.post(
            "/api/v1/auth/register",
            json={"email": "new@example.com", "password": "StrongPass1"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["email"] == "new@example.com"
        assert data["is_verified"] is False
        assert "id" in data

    def test_register_duplicate_email(self, client: TestClient, test_user):
        resp = client.post(
            "/api/v1/auth/register",
            json={"email": test_user["email"], "password": "AnotherPass1"},
        )
        assert resp.status_code == 409

    def test_register_weak_password(self, client: TestClient):
        resp = client.post(
            "/api/v1/auth/register",
            json={"email": "weak@example.com", "password": "short"},
        )
        assert resp.status_code == 422

    def test_register_invalid_email(self, client: TestClient):
        resp = client.post(
            "/api/v1/auth/register",
            json={"email": "not-an-email", "password": "StrongPass1"},
        )
        assert resp.status_code == 422


class TestLogin:
    def test_login_success(self, client: TestClient, test_user):
        resp = client.post(
            "/api/v1/auth/login",
            data={"username": test_user["email"], "password": test_user["password"]},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"

    def test_login_wrong_password(self, client: TestClient, test_user):
        resp = client.post(
            "/api/v1/auth/login",
            data={"username": test_user["email"], "password": "WrongPassword1"},
        )
        assert resp.status_code == 401

    def test_login_nonexistent_user(self, client: TestClient):
        resp = client.post(
            "/api/v1/auth/login",
            data={"username": "nobody@example.com", "password": "Whatever1"},
        )
        assert resp.status_code == 401


class TestRefreshToken:
    def test_refresh_success(self, client: TestClient, test_user):
        # Login first
        login_resp = client.post(
            "/api/v1/auth/login",
            data={"username": test_user["email"], "password": test_user["password"]},
        )
        refresh_token = login_resp.json()["refresh_token"]

        # Refresh
        resp = client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data

    def test_refresh_invalid_token(self, client: TestClient):
        resp = client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": "invalid.token.here"},
        )
        assert resp.status_code == 401


class TestMe:
    def test_get_current_user(self, client: TestClient, auth_headers):
        resp = client.get("/api/v1/auth/me", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["email"] == "test@example.com"

    def test_get_current_user_no_token(self, client: TestClient):
        resp = client.get("/api/v1/auth/me")
        assert resp.status_code == 401


class TestPasswordReset:
    def test_forgot_password_always_200(self, client: TestClient):
        # Should return 200 even for non-existent email (prevent enumeration)
        resp = client.post(
            "/api/v1/auth/forgot-password",
            json={"email": "nobody@example.com"},
        )
        assert resp.status_code == 200

    def test_reset_password_invalid_token(self, client: TestClient):
        resp = client.post(
            "/api/v1/auth/reset-password",
            json={"token": "bad-token", "new_password": "NewPass123"},
        )
        assert resp.status_code == 400


class TestEmailVerification:
    def test_verify_email_invalid_token(self, client: TestClient):
        resp = client.post(
            "/api/v1/auth/verify-email",
            json={"token": "bad-token"},
        )
        assert resp.status_code == 400
