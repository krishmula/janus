from __future__ import annotations

from unittest.mock import patch

import pytest


class TestInteractEndpoint:
    @pytest.mark.asyncio
    async def test_interact_returns_200(self, app_client):
        with patch("app.main.executor.run") as mock_run:
            mock_run.return_value = ([], None)
            response = app_client.post("/api/interact", json={"prompt": "test"})

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_response_has_run_id(self, app_client):
        with patch("app.main.executor.run") as mock_run:
            mock_run.return_value = ([], None)
            response = app_client.post("/api/interact", json={"prompt": "test"})

        data = response.json()
        assert "run_id" in data
        assert len(data["run_id"]) > 0

    @pytest.mark.asyncio
    async def test_goal_preserved_in_response(self, app_client):
        with patch("app.main.executor.run") as mock_run:
            mock_run.return_value = ([], None)
            response = app_client.post(
                "/api/interact", json={"prompt": "get the top post"}
            )

        data = response.json()
        assert data["goal"] == "get the top post"

    @pytest.mark.asyncio
    async def test_steps_in_response(self, app_client):
        fake_steps = [
            {
                "action_type": "goto",
                "action_data": {"type": "goto", "url": "https://example.com"},
                "status": "success",
                "error": None,
                "latency_ms": 10.0,
                "screenshot_path": None,
            }
        ]
        with patch("app.main.executor.run") as mock_run:
            mock_run.return_value = (fake_steps, None)
            response = app_client.post("/api/interact", json={"prompt": "test"})

        data = response.json()
        assert data["steps"] == fake_steps
        assert data["total_steps"] == 1

    @pytest.mark.asyncio
    async def test_total_steps_matches_steps_length(self, app_client):
        with patch("app.main.executor.run") as mock_run:
            mock_run.return_value = ([], None)
            response = app_client.post("/api/interact", json={"prompt": "test"})

        data = response.json()
        assert data["total_steps"] == len(data["steps"])

    @pytest.mark.asyncio
    async def test_final_result_in_response(self, app_client):
        fake_result = {
            "summary": "completed",
            "url": "https://example.com",
            "title": "Example",
            "screenshot_path": "artifacts/screenshots/final.png",
        }
        with patch("app.main.executor.run") as mock_run:
            mock_run.return_value = ([], fake_result)
            response = app_client.post("/api/interact", json={"prompt": "test"})

        data = response.json()
        assert data["final_result"] == fake_result

    @pytest.mark.asyncio
    async def test_final_screenshot_when_result_present(self, app_client):
        fake_result = {
            "summary": "done",
            "url": "https://example.com",
            "title": "Example",
            "screenshot_path": "artifacts/screenshots/final.png",
        }
        with patch("app.main.executor.run") as mock_run:
            mock_run.return_value = ([], fake_result)
            response = app_client.post("/api/interact", json={"prompt": "test"})

        data = response.json()
        assert data["final_screenshot"] == "artifacts/screenshots/final.png"

    @pytest.mark.asyncio
    async def test_final_screenshot_null_when_no_result(self, app_client):
        with patch("app.main.executor.run") as mock_run:
            mock_run.return_value = ([], None)
            response = app_client.post("/api/interact", json={"prompt": "test"})

        data = response.json()
        assert data["final_screenshot"] is None


class TestHealthEndpoint:
    def test_health_returns_200(self, app_client):
        response = app_client.get("/health")
        assert response.status_code == 200

    def test_health_returns_status_healthy(self, app_client):
        response = app_client.get("/health")
        assert response.json() == {"status": "healthy"}


class TestExtractEndpoint:
    def test_extract_returns_200(self, app_client):
        response = app_client.post(
            "/api/extract", json={"run_id": "abc-123"}
        )
        assert response.status_code == 200

    def test_extract_has_run_id(self, app_client):
        response = app_client.post(
            "/api/extract", json={"run_id": "abc-123"}
        )
        data = response.json()
        assert data["run_id"] == "abc-123"
        assert data["schema_name"] == "default"
