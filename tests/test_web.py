import pytest
from fastapi.testclient import TestClient
from pathlib import Path
from unittest.mock import patch
from web.app import create_app


@pytest.fixture
def client(temp_workspace):
    app = create_app(temp_workspace)
    return TestClient(app)


def test_dashboard_returns_html(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


def test_api_status_returns_json(client):
    response = client.get("/api/status")
    assert response.status_code == 200
    data = response.json()
    assert "workspace" in data
    assert "status" in data


def test_api_memory_returns_json(client):
    response = client.get("/api/memory")
    assert response.status_code == 200
    data = response.json()
    assert "project" in data
    assert "fix_history" in data