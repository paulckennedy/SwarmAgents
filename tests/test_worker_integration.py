import sys
import types
import pytest

# Provide a minimal dummy redis module so the worker module can be imported in test
sys.modules.setdefault('redis', types.ModuleType('redis'))

from worker import worker as w


class DummyResearcher:
    def __init__(self, *a, **k):
        pass

    def search(self, topic_or_person, max_results=25, depth_of_search=1, filters=None):
        return [{
            'videoId': 'vid1', 'title': 'T1', 'description': 'd1', 'channelTitle': 'C1', 'publishedAt': '2020-01-01T00:00:00Z', 'duration': 60, 'viewCount': 100
        }]


def test_worker_processes_youtube_job(monkeypatch):
    # monkeypatch process_job to use DummyResearcher instead of real
    monkeypatch.setattr('worker.worker.YouTubeResearcher', DummyResearcher)

    job = {
        'id': 'test-job-1',
        'payload': {
            'prompt_id': 'pr-007',
            'topic_or_person': 'test topic',
            'max_results': 1
        }
    }
    result = w.process_job(job)
    assert result['id'] == 'test-job-1'
    assert 'response' in result
    assert isinstance(result['response'], list)
    assert result['response'][0]['videoId'] == 'vid1'
    assert result['id'] == 'test-job-1'
