import json
import time
from unittest import mock

import fakeredis
import pytest

from worker.worker import process_job, run_once
from agents.youtube_researcher import QuotaExceeded


def test_worker_defers_job_on_quota(monkeypatch):
    # Prepare fake redis server
    fake_redis = fakeredis.FakeRedis()

    # Create a sample job that will trigger YouTubeResearcher quota
    job = {'id': 'job-123', 'payload': {'prompt_id': 'pr-007', 'query': 'foo'}}
    raw = json.dumps(job)

    # Monkeypatch redis.Redis to return our fake redis
    monkeypatch.setattr('worker.worker.redis.Redis', lambda *a, **k: fake_redis)

    # Push the job into 'tasks' (the worker will blpop it)
    fake_redis.rpush('tasks', raw)

    # Create a fake researcher factory that raises QuotaExceeded when search() is invoked
    class FakeResearcher:
        def search(self, *a, **k):
            raise QuotaExceeded(retry_after=2)

    def fake_factory():
        return FakeResearcher()

    processed = run_once(r=fake_redis, blpop_timeout=1, researcher_factory=fake_factory)
    assert processed is True

    # After run_once the job should be in delayed_jobs
    members = fake_redis.zrangebyscore('delayed_jobs', 0, time.time() + 10)
    assert any(json.dumps(job).encode() == m for m in members)
