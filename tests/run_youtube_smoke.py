import os
import json
import requests

os.environ['YOUTUBE_API_KEY'] = 'DUMMY'

from agents.youtube_researcher import YouTubeResearcher

SEARCH_SAMPLE = {
    "items": [
        {"id": {"videoId": "vid1"}, "snippet": {"title": "Test Video 1", "description": "desc1", "channelTitle": "Chan A", "publishedAt": "2020-01-01T00:00:00Z"}},
        {"id": {"videoId": "vid2"}, "snippet": {"title": "Test Video 2", "description": "desc2", "channelTitle": "Chan B", "publishedAt": "2021-01-01T00:00:00Z"}}
    ]
}
VIDEOS_SAMPLE = {
    "items": [
        {"id": "vid1", "snippet": {"title": "Test Video 1", "description": "desc1", "channelTitle": "Chan A", "publishedAt": "2020-01-01T00:00:00Z"}, "contentDetails": {"duration": "PT2M30S"}, "statistics": {"viewCount": "1000"}},
        {"id": "vid2", "snippet": {"title": "Test Video 2", "description": "desc2", "channelTitle": "Chan B", "publishedAt": "2021-01-01T00:00:00Z"}, "contentDetails": {"duration": "PT1M"}, "statistics": {"viewCount": "2500"}}
    ]
}

class DummyResponse:
    def __init__(self, json_data, status_code=200):
        self._json = json_data
        self.status_code = status_code
    def json(self):
        return self._json
    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


def fake_get(url, params=None, timeout=None):
    if 'search' in url:
        return DummyResponse(SEARCH_SAMPLE)
    if 'videos' in url:
        return DummyResponse(VIDEOS_SAMPLE)
    return DummyResponse({}, status_code=404)

requests.get = fake_get

if __name__ == '__main__':
    r = YouTubeResearcher()
    results = r.search('test query', max_results=2, depth_of_search=1)
    print(json.dumps(results, indent=2))
