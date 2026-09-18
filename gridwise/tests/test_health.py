"""Tests for GridWise /health endpoint."""

import pytest
from fastapi.testclient import TestClient
from gridwise.app.main import app


class TestHealth:
    """Health check tests."""

    def test_health_returns_ok(self):
        """GET /health should return 200 with {\"status\": \"ok\"}."""
        client = TestClient(app)
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data == {"status": "ok"}

    def test_health_no_llm(self):
        """Health should work without LLM configured."""
        client = TestClient(app)
        response = client.get("/health")
        assert response.status_code == 200