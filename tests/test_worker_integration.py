import sys
import types


class DummyResearcher:
    def __init__(self, *a, **k):
        pass

    def search(self, topic_or_person, max_results=25, depth_of_search=1, filters=None):
        return [
            {
                "videoId": "vid1",
                "title": "T1",
                "description": "d1",
                "channelTitle": "C1",
                "publishedAt": "2020-01-01T00:00:00Z",
                "duration": 60,
                "viewCount": 100,
            }
        ]


def test_worker_processes_youtube_job(monkeypatch):
    # Provide a minimal dummy redis module so the worker module can be imported
    sys.modules.setdefault("redis", types.ModuleType("redis"))

    # import worker after setting up the fake redis module
    from worker import worker as w

    # monkeypatch the YouTubeResearcher used by the worker to a dummy
    monkeypatch.setattr("worker.worker.YouTubeResearcher", DummyResearcher)

    job = {
        "id": "test-job-1",
        "payload": {
            "prompt_id": "pr-007",
            "topic_or_person": "test topic",
            "max_results": 1,
        },
    }

    result = w.process_job(job)
    assert result["id"] == "test-job-1"
    assert "response" in result
    assert isinstance(result["response"], list)
    assert result["response"][0]["videoId"] == "vid1"
