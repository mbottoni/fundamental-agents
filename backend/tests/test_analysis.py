"""Tests for analysis endpoints (job management, not the actual pipeline)."""

from fastapi.testclient import TestClient


class TestAnalysisEndpoints:
    def test_start_analysis_requires_auth(self, client: TestClient):
        resp = client.post("/api/v1/analysis/", json={"ticker": "AAPL"})
        assert resp.status_code == 401

    def test_start_analysis_creates_job(self, client: TestClient, auth_headers):
        resp = client.post(
            "/api/v1/analysis/",
            json={"ticker": "AAPL"},
            headers=auth_headers,
        )
        assert resp.status_code == 202
        data = resp.json()
        assert data["ticker"] == "AAPL"
        assert data["status"] == "pending"
        assert "id" in data

    def test_list_jobs(self, client: TestClient, auth_headers):
        # Create a job
        client.post("/api/v1/analysis/", json={"ticker": "MSFT"}, headers=auth_headers)

        resp = client.get("/api/v1/analysis/", headers=auth_headers)
        assert resp.status_code == 200
        jobs = resp.json()
        assert len(jobs) >= 1
        assert any(j["ticker"] == "MSFT" for j in jobs)

    def test_get_job_status(self, client: TestClient, auth_headers):
        create_resp = client.post(
            "/api/v1/analysis/", json={"ticker": "GOOG"}, headers=auth_headers,
        )
        job_id = create_resp.json()["id"]

        resp = client.get(f"/api/v1/analysis/{job_id}", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["id"] == job_id

    def test_get_nonexistent_job(self, client: TestClient, auth_headers):
        resp = client.get("/api/v1/analysis/99999", headers=auth_headers)
        assert resp.status_code == 404


class TestFreeTierLimits:
    def test_free_tier_limit_enforced(self, client: TestClient, auth_headers):
        """Free users should be limited to the configured daily cap."""
        # Create jobs up to the limit (default is 3)
        for i in range(3):
            resp = client.post(
                "/api/v1/analysis/",
                json={"ticker": f"T{i}"},
                headers=auth_headers,
            )
            assert resp.status_code == 202, f"Job {i} should succeed"

        # The 4th should be rejected
        resp = client.post(
            "/api/v1/analysis/",
            json={"ticker": "FAIL"},
            headers=auth_headers,
        )
        assert resp.status_code == 429
        assert "limit" in resp.json()["detail"].lower()
