from __future__ import annotations

import json
import time
from typing import Any, Dict, List, Optional, cast
import email.utils
from datetime import datetime, timezone

import requests

from filelock import FileLock

from .types import TweetRecord

# Minimal, local-only rate-limit/backoff persistence file.
STATE_FILE = "runs/twitter_researcher_state.json"


class RateLimitExceeded(Exception):
    def __init__(self, retry_after: int) -> None:
        super().__init__(f"rate limited; retry after {retry_after}s")
        self.retry_after = retry_after


class TwitterResearcher:
    """A simple Twitter researcher agent.

    - test mode: set TWITTER_TEST_MODE=1 to get canned results
    - _call_api handles RateLimit (HTTP 429 simulation) and returns list of TweetRecord
    """

    def __init__(self, api_key: Optional[str] = None) -> None:
        self.api_key = api_key
        self._state: Dict[str, Any] = self._load_state()

    def _load_state(self) -> Dict[str, Any]:
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return cast(Dict[str, Any], json.load(f))
        except FileNotFoundError:
            return {}

    def _save_state(self) -> None:
        lock = FileLock(STATE_FILE + ".lock")
        with lock:
            with open(STATE_FILE, "w", encoding="utf-8") as f:
                json.dump(self._state, f, indent=2)

    def _call_api(self, query: str) -> List[Dict[str, Any]]:
        """Placeholder for real Twitter API call.

        This implementation simulates a rate-limited response if the internal
        state has 'blocked_until' in the future.
        """
        blocked_until = cast(int, self._state.get("blocked_until", 0))
        now = int(time.time())
        if blocked_until and blocked_until > now:
            # tell caller to retry after remaining seconds
            raise RateLimitExceeded(blocked_until - now)

        # Test mode shortcut: return canned records to allow fast unit tests.
        if query == "__TEST__":
            return [
                {
                    "id": "12345",
                    "url": "https://twitter.com/example/status/12345",
                    "text": "This is a test tweet",
                    "author": "example",
                    "created_at": "2025-01-01T00:00:00Z",
                    "like_count": 10,
                    "retweet_count": 2,
                    "reply_count": 1,
                    "lang": "en",
                }
            ]

        # If a bearer token is available, call Twitter API v2 recent search.
        bearer = self.api_key or None
        if bearer is None:
            # check env var as a fallback
            import os

            bearer = os.getenv("TWITTER_BEARER_TOKEN")

        if bearer:
            headers = {"Authorization": f"Bearer {bearer}"}
            params = {
                "query": query,
                "max_results": 10,
                "tweet.fields": "public_metrics,created_at,lang,author_id",
                "expansions": "author_id",
                "user.fields": "username,name,public_metrics",
            }
            try:
                resp = requests.get(
                    "https://api.twitter.com/2/tweets/search/recent",
                    headers=headers,
                    params=params,
                    timeout=15,
                )
                if resp.status_code == 429:
                    # Parse Retry-After header which may be seconds or HTTP-date
                    ra = resp.headers.get("Retry-After")
                    retry_after = None
                    if ra is not None:
                        try:
                            retry_after = int(ra)
                        except Exception:
                            try:
                                # HTTP-date format
                                parsed = email.utils.parsedate_to_datetime(ra)
                                retry_after = int((parsed - datetime.now(timezone.utc)).total_seconds())
                            except Exception:
                                retry_after = None
                    # persist blocked_until if we have a numeric retry_after
                    if retry_after and retry_after > 0:
                        self._state["blocked_until"] = int(time.time()) + int(retry_after)
                        try:
                            self._save_state()
                        except Exception:
                            pass
                    raise RateLimitExceeded(int(retry_after) if retry_after is not None else 60)

                resp.raise_for_status()
                data = resp.json()
                # Build a map of users from includes for easy lookup
                users_map: Dict[str, Dict[str, Any]] = {}
                includes = data.get("includes") or {}
                for u in includes.get("users", []):
                    users_map[str(u.get("id"))] = u

                # map Twitter v2 response to a list of dicts with expected keys
                results: List[Dict[str, Any]] = []
                for t in data.get("data", []):
                    tid = t.get("id")
                    text = t.get("text")
                    author_id = str(t.get("author_id") or "")
                    user = users_map.get(author_id, {})
                    pub = user.get("public_metrics", {}) if isinstance(user, dict) else {}
                    results.append(
                        {
                            "id": str(tid),
                            "url": f"https://twitter.com/{user.get('username')}/status/{tid}" if user.get("username") else f"https://twitter.com/i/web/status/{tid}",
                            "text": str(text or ""),
                            "author": str(user.get("username") or author_id),
                            "created_at": t.get("created_at", ""),
                            "like_count": int(pub.get("like_count") or pub.get("likes") or 0),
                            "retweet_count": int(pub.get("retweet_count") or pub.get("retweets") or 0),
                            "reply_count": int(pub.get("reply_count") or pub.get("replies") or 0),
                            "lang": t.get("lang", ""),
                        }
                    )
                return results
            except RateLimitExceeded:
                raise
            except Exception:
                # on any API failure, fall back to empty list (caller may fallback)
                return []

        # no bearer token -> conservative empty result by default
        return []

    def search(self, query: str) -> List[TweetRecord]:
        """Search tweets matching `query` and return TweetRecord list.

        Raises RateLimitExceeded when the API indicates a retry-after.
        """
        raw = self._call_api(query)
        # convert to TweetRecord TypedDicts
        results: List[TweetRecord] = []
        for r in raw:
            tr: TweetRecord = {
                "id": str(r.get("id", "")),
                "url": str(r.get("url", "")),
                "text": str(r.get("text", "")),
                "author": str(r.get("author", "")),
                "created_at": str(r.get("created_at", "")),
                "like_count": int(r.get("like_count", 0)),
                "retweet_count": int(r.get("retweet_count", 0)),
                "reply_count": int(r.get("reply_count", 0)),
                "lang": str(r.get("lang", "")),
            }
            results.append(tr)
        return results


__all__ = ["TwitterResearcher", "RateLimitExceeded"]
