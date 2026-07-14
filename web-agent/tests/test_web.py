import pytest
from fastapi.testclient import TestClient
from web.app import create_app


@pytest.fixture
def client():
    app = create_app()
    return TestClient(app)


def test_create_session_returns_id(client):
    response = client.post("/api/session", json={"api_key": "sk-test"})
    assert response.status_code == 200
    data = response.json()
    assert "session_id" in data
    assert len(data["session_id"]) == 32


def test_create_session_rejects_empty_key(client):
    response = client.post("/api/session", json={"api_key": ""})
    assert response.status_code == 400


def test_stream_requires_valid_session(client):
    response = client.get("/api/session/nonexistent/stream", params={"task": "test"})
    assert response.status_code == 404


def test_destroy_session(client):
    resp = client.post("/api/session", json={"api_key": "sk-test"})
    sid = resp.json()["session_id"]
    response = client.delete(f"/api/session/{sid}")
    assert response.status_code == 200


def test_status_endpoint(client):
    response = client.get("/api/status")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "running"
    assert "active_sessions" in data


def test_index_page_returns_html(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]