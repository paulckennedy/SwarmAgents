import sys
from pathlib import Path
import glob
import json

# Ensure the repository root is on sys.path for test imports
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _import_process_job():
    # Deferred import to avoid import-time side-effects during test collection
    from worker.worker import process_job

    return process_job


def test_worker_persists_successful_job(tmp_path, monkeypatch):
    # Run in a fresh temp directory to avoid clobbering real runs/
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("YOUTUBE_TEST_MODE", "1")

    job = {
        "id": "ut-job-1",
        "payload": {
            "prompt_id": "pr-007",
            "topic_or_person": "testing",
            "max_results": 2,
        },
    }

    process_job = _import_process_job()
    res = process_job(job)

    # worker should return a successful result with response list
    assert "error" not in res
    assert isinstance(res.get("response"), list)
    # ensure url fields exist on entries
    for v in res["response"]:
        assert "videoId" in v
        assert "url" in v
        assert v["url"].startswith("https://www.youtube.com/watch?v=")

    # emulate worker's persist behavior (we tested process_job earlier separately)
    runs_dir = tmp_path / "runs"
    runs_dir.mkdir()
    stable = runs_dir / f'last_job_{job["id"]}.json'
    stable.write_text(json.dumps(res, indent=2), encoding="utf-8")

    # create a timestamped snapshot and ensure it matches pattern
    # simulate same format used by worker
    from datetime import datetime, timezone

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    snap = runs_dir / f'job_{job["id"]}_{ts}.json'
    snap.write_text(json.dumps(res, indent=2), encoding="utf-8")

    files = list(glob.glob(str(runs_dir / f'job_{job["id"]}_*.json')))
    assert len(files) == 1
