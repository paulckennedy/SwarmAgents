from fastapi.testclient import TestClient

from mcp.twitter_researcher_server import app
from agents.twitter_researcher import RateLimitExceeded


def test_mcp_twitter_call_test_mode():
    client = TestClient(app)
    resp = client.post("/call", json={"query": "__TEST__"})
    assert resp.status_code == 200
    data = resp.json()
    assert "results" in data
    assert isinstance(data["results"], list)


def test_mcp_twitter_call_rate_limit(monkeypatch):
    # Simulate RateLimitExceeded from the researcher
    def fake_search(self, q):
        raise RateLimitExceeded(30)

    monkeypatch.setattr("agents.twitter_researcher.TwitterResearcher.search", fake_search)
    client = TestClient(app)
    resp = client.post("/call", json={"query": "anything"})
    assert resp.status_code == 429
    assert resp.headers.get("Retry-After") == "30"
