from unittest.mock import patch

import requests

from agents.twitter_researcher import TwitterResearcher


def test_twitter_api_mapping_with_includes() -> None:
    sample_resp = {
        "data": [
            {"id": "111", "text": "hello", "author_id": "10", "created_at": "2025-01-01T00:00:00Z", "lang": "en"}
        ],
        "includes": {
            "users": [
                {"id": "10", "username": "alice", "public_metrics": {"like_count": 5, "retweet_count": 1, "reply_count": 0}}
            ]
        }
    }

    class FakeResp:
        status_code = 200

        def json(self):
            return sample_resp

        def raise_for_status(self):
            return None

    with patch("requests.get", return_value=FakeResp()):
        tr = TwitterResearcher(api_key="dummy")
        results = tr.search("something")
        assert len(results) == 1
    from typing import Any, Dict

    r = dict(results[0])  # type: Dict[str, Any]
    assert r["id"] == "111"
    assert r["author"] == "alice"
    assert r["like_count"] == 5
    assert r["retweet_count"] == 1
    assert "alice/status/111" in r["url"]
