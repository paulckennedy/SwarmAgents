import json
import time

import fakeredis

from worker.worker import run_once


def test_worker_schedules_delayed_job_on_rate_limit(monkeypatch):
    # Prepare a fake redis instance
    r = fakeredis.FakeRedis()

    # Prepare a job payload that the worker will process as a twitter job
    job = {
        "id": "test-job-1",
        "payload": {"agent": "twitter_researcher", "query": "anything"},
    }
    r.rpush("tasks", json.dumps(job))

    # Monkeypatch TwitterResearcher.search to raise RateLimitExceeded
    from agents.twitter_researcher import RateLimitExceeded

    def fake_process(job_dict):
        raise RateLimitExceeded(5)

    # Run one iteration which should pick the job and schedule it in delayed_jobs
    run_once(r, blpop_timeout=1, process_job_fn=fake_process)

    # Check that delayed_jobs contains one member
    items = r.zrangebyscore("delayed_jobs", 0, time.time() + 1000)
    assert len(items) == 1
    # The member should be the original job JSON
    member = items[0]
    if isinstance(member, bytes):
        member = member.decode()
    j = json.loads(member)
    assert j.get("id") == "test-job-1"
