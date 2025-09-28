from agents.youtube_researcher import YouTubeResearcher


class DummyResponse:
    def __init__(self, json_data, status_code=200):
        self._json = json_data
        self.status_code = status_code

    def json(self):
        return self._json

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


# Sample search response and videos response
SEARCH_SAMPLE = {
    "items": [
        {
            "id": {"videoId": "vid1"},
            "snippet": {
                "title": "Test Video 1",
                "description": "desc1",
                "channelTitle": "Chan A",
                "publishedAt": "2020-01-01T00:00:00Z",
            },
        },
        {
            "id": {"videoId": "vid2"},
            "snippet": {
                "title": "Test Video 2",
                "description": "desc2",
                "channelTitle": "Chan B",
                "publishedAt": "2021-01-01T00:00:00Z",
            },
        },
    ]
}
VIDEOS_SAMPLE = {
    "items": [
        {
            "id": "vid1",
            "snippet": {
                "title": "Test Video 1",
                "description": "desc1",
                "channelTitle": "Chan A",
                "publishedAt": "2020-01-01T00:00:00Z",
            },
            "contentDetails": {"duration": "PT2M30S"},
            "statistics": {"viewCount": "1000"},
        },
        {
            "id": "vid2",
            "snippet": {
                "title": "Test Video 2",
                "description": "desc2",
                "channelTitle": "Chan B",
                "publishedAt": "2021-01-01T00:00:00Z",
            },
            "contentDetails": {"duration": "PT1M"},
            "statistics": {"viewCount": "2500"},
        },
    ]
}


def fake_get(url, params=None, timeout=None):
    # return search result for search url, videos result for videos url
    if "search" in url:
        return DummyResponse(SEARCH_SAMPLE)
    if "videos" in url:
        return DummyResponse(VIDEOS_SAMPLE)
    return DummyResponse({}, status_code=404)


def test_search_monkeypatch(monkeypatch):
    monkeypatch.setenv("YOUTUBE_API_KEY", "DUMMY")
    monkeypatch.setattr("requests.get", fake_get)
    r = YouTubeResearcher()
    results = r.search("test query", max_results=2, depth_of_search=1)
    assert isinstance(results, list)
    assert len(results) == 2
    for rec in results:
        assert "videoId" in rec
        assert "title" in rec
        assert "description" in rec
        assert "channelTitle" in rec
        assert "publishedAt" in rec
        assert "duration" in rec
        assert "viewCount" in rec
        assert "relevanceScore" in rec
