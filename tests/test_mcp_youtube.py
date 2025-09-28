import pytest
from fastapi.testclient import TestClient


def test_health():
    from mcp.youtube_researcher_server import app

    client = TestClient(app)
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_call_mock_mode(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("YOUTUBE_TEST_MODE", "1")
    from mcp.youtube_researcher_server import app

    client: TestClient = TestClient(app)
    r = client.post("/call", json={"id": "t1", "query": "energy", "max_results": 2})
    assert r.status_code == 200
    j = r.json()
    assert j["id"] == "t1"
    assert isinstance(j["response"], list)
    assert len(j["response"]) == 2


def test_quota_propagation(monkeypatch: pytest.MonkeyPatch):
    # Patch YouTubeResearcher.search to raise QuotaExceeded
    from agents.youtube_researcher import QuotaExceeded

    def raise_quota(*a, **k):
        raise QuotaExceeded(retry_after=30)

    import mcp.youtube_researcher_server as srv

    monkeypatch.setattr(
        "agents.youtube_researcher.YouTubeResearcher.search", raise_quota
    )
    client: TestClient = TestClient(srv.app)
    r = client.post("/call", json={"id": "t2", "query": "x", "max_results": 1})
    assert r.status_code == 429
    assert "Retry-After" in r.headers
    assert r.json().get("retry_after") == 30
