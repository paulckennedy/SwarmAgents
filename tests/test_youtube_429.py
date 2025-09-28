import json
import os
import time

import pytest

from agents.youtube_researcher import (
    QuotaExceeded,
    YouTubeResearcher,
    _load_state,
    _save_state,
)


def make_resp(status=200, headers=None, json_data=None):
    class Resp:
        def __init__(self, status, headers, json_data):
            self.status_code = status
            self.headers = headers or {}
            self._json = json_data or {}

        def json(self):
            return self._json

    return Resp(status, headers or {}, json_data or {})


def test_429_sets_blocked_state(tmp_path, monkeypatch):
    # use a temp HOME for state file
    tmp_home = str(tmp_path)
    monkeypatch.setenv("HOME", tmp_home)
    # ensure no prior state
    state_file = os.path.join(tmp_home, ".swarmagents", "youtube_state.json")
    if os.path.exists(state_file):
        os.remove(state_file)

    r = YouTubeResearcher(api_key="fake-key")

    # first call returns 429 with Retry-After=10
    resp1 = make_resp(status=429, headers={"Retry-After": "10"}, json_data={})
    # second call would be normal search payload (not needed here)

    monkeypatch.setattr("requests.get", lambda *a, **k: resp1)

    with pytest.raises(QuotaExceeded):
        r.search("anything", max_results=1, depth=1)

    # blocked_until should be set in state file
    st = _load_state(r._state_file)
    assert "blocked_until" in st
    assert st["blocked_until"] > time.time()


def test_block_prevents_calls(tmp_path, monkeypatch):
    tmp_home = str(tmp_path)
    monkeypatch.setenv("HOME", tmp_home)
    r = YouTubeResearcher(api_key="fake-key")
    # set blocked_until in the past -> should be allowed
    _save_state(r._state_file, {"blocked_until": time.time() - 5})

    # mock a successful response for actual calls
    good = make_resp(status=200, json_data={"items": []})
    monkeypatch.setattr("requests.get", lambda *a, **k: good)

    res = r.search("ok", max_results=1, depth=1)
    assert isinstance(res, list)


def test_integration_worker_and_429(tmp_path, monkeypatch):
    # Use same temp home
    tmp_home = str(tmp_path)
    monkeypatch.setenv("HOME", tmp_home)

    # fake redis
    import fakeredis

    fake_redis = fakeredis.FakeRedis()

    # prepare job
    job = {"id": "job-xyz", "payload": {"prompt_id": "pr-007", "query": "bar"}}
    raw = json.dumps(job)
    fake_redis.rpush("tasks", raw)

    # fake researcher factory that raises QuotaExceeded
    from agents.youtube_researcher import QuotaExceeded

    class FakeResearcher:
        def search(self, *a, **k):
            raise QuotaExceeded(retry_after=3)

    def fake_factory():
        return FakeResearcher()

    # run a single worker iteration
    from worker.worker import run_once

    ran = run_once(r=fake_redis, blpop_timeout=1, researcher_factory=fake_factory)
    assert ran is True

    members = fake_redis.zrangebyscore("delayed_jobs", 0, time.time() + 10)
    assert any(json.dumps(job).encode() == m for m in members)


def test_429_retry_after_http_date_sets_blocked_state(tmp_path, monkeypatch):
    # use a temp HOME for state file
    tmp_home = str(tmp_path)
    monkeypatch.setenv("HOME", tmp_home)

    r = YouTubeResearcher(api_key="fake-key")

    # craft an HTTP-date in the near future
    from datetime import datetime, timedelta
    from email.utils import format_datetime

    future_dt = datetime.utcnow() + timedelta(seconds=30)
    http_date = format_datetime(future_dt)

    resp1 = make_resp(status=429, headers={"Retry-After": http_date}, json_data={})
    monkeypatch.setattr("requests.get", lambda *a, **k: resp1)

    with pytest.raises(QuotaExceeded):
        r.search("anything", max_results=1, depth=1)

    # blocked_until should be set and be roughly in the future (> now)
    st = _load_state(r._state_file)
    assert "blocked_until" in st
    assert st["blocked_until"] > time.time()


def test_429_malformed_retry_after_uses_conservative_block(tmp_path, monkeypatch):
    tmp_home = str(tmp_path)
    monkeypatch.setenv("HOME", tmp_home)

    r = YouTubeResearcher(api_key="fake-key")

    # malformed Retry-After header should fall back to conservative block (>= ~60s)
    resp1 = make_resp(
        status=429, headers={"Retry-After": "not-a-valid-header"}, json_data={}
    )
    monkeypatch.setattr("requests.get", lambda *a, **k: resp1)

    with pytest.raises(QuotaExceeded):
        r.search("anything", max_results=1, depth=1)

    st = _load_state(r._state_file)
    assert "blocked_until" in st
    # block should be at least ~60 seconds from now (the conservative default in code)
    assert st["blocked_until"] - time.time() >= 59
