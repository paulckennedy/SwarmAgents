"""YouTube Researcher agent

Production-ready implementation with quota-aware scheduling, persistent retry state,
and resilient error handling.

Features:
- Respects HTTP 429 responses and Retry-After header.
- Persists 'blocked_until' state to a simple JSON file in ~/.swarmagents/youtube_state.json
  so multiple processes can coordinate backoff.
- Raises QuotaExceeded with a retry_after hint so orchestrators (workers/schedulers)
  can schedule retries appropriately.
- Small, dependency-light (requests, stdlib only).
"""

import json
import logging
import math
import os
import random
import re
import time
from typing import Any, Dict, List, Optional, cast

import requests

from .types import VideoRecord
from .agent_base import AgentBase

GraphRAG: Optional[type] = None
try:
    # Import GraphRAG if available. If import fails, leave GraphRAG as None
    from agents.graph_rag import GraphRAG as _GraphRAG

    GraphRAG = _GraphRAG
except Exception:
    GraphRAG = None

# prompt store helper
ps: Optional[Any] = None
try:
    from .prompts import ps as _ps

    ps = _ps
except Exception:
    ps = None

YOUTUBE_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
YOUTUBE_VIDEOS_URL = "https://www.googleapis.com/youtube/v3/videos"


class QuotaExceeded(Exception):
    """Raised when the YouTube API quota / rate limit is exceeded and caller should retry later."""

    def __init__(
        self, retry_after: Optional[float] = None, message: Optional[str] = None
    ):
        self.retry_after = retry_after
        super().__init__(message or f"Quota exceeded; retry after {retry_after}")


class APIError(Exception):
    """Generic API error wrapper"""


def _load_state(path: str) -> Dict[str, Any]:
    try:
        if not os.path.exists(path):
            return {}

        # Prefer filelock (cross-platform) if installed
        try:
            from filelock import FileLock, Timeout

            lock_path = path + ".lock"
            lock = FileLock(lock_path, timeout=0.1)
            try:
                logging.debug("Acquiring filelock for read: %s", lock_path)
                with lock:
                    logging.debug("Filelock acquired for read: %s", lock_path)
                    with open(path, "r", encoding="utf-8") as f:
                        return cast(Dict[str, Any], json.load(f))
            except Timeout:
                logging.debug("Could not acquire file lock for reading %s", path)
                # best-effort read without lock
                with open(path, "r", encoding="utf-8") as f:
                    return cast(Dict[str, Any], json.load(f))
        except Exception:
            # filelock not available; try POSIX fcntl lock
            try:
                import fcntl

                with open(path, "r", encoding="utf-8") as f:
                    try:
                        fcntl.flock(f.fileno(), fcntl.LOCK_SH)
                    except Exception:
                        pass
                    try:
                        return cast(Dict[str, Any], json.load(f))
                    finally:
                        try:
                            fcntl.flock(f.fileno(), fcntl.LOCK_UN)
                        except Exception:
                            pass
            except Exception:
                # fallback plain read
                with open(path, "r", encoding="utf-8") as f:
                    return cast(Dict[str, Any], json.load(f))
    except Exception:
        return {}


def _save_state(path: str, data: Dict[str, Any]) -> None:
    try:
        tmp = path + ".tmp"
        d = os.path.dirname(path)
        os.makedirs(d, exist_ok=True)

        # Write to temp and fsync
        with open(tmp, "w", encoding="utf-8") as ftmp:
            json.dump(data, ftmp)
            ftmp.flush()
            try:
                os.fsync(ftmp.fileno())
            except Exception:
                pass

        # Prefer filelock for cross-platform exclusive locking during replace
        try:
            from filelock import FileLock, Timeout

            lock_path = path + ".lock"
            lock = FileLock(lock_path, timeout=1.0)
            try:
                logging.debug("Acquiring filelock for write: %s", lock_path)
                with lock:
                    logging.debug("Filelock acquired for write: %s", lock_path)
                    os.replace(tmp, path)
            except Timeout:
                logging.debug("Could not acquire file lock for writing %s", path)
                # fallback to atomic replace without lock
                os.replace(tmp, path)
            return
        except Exception:
            # filelock not available; fall back to POSIX fcntl when possible
            pass

        try:
            import fcntl

            if os.path.exists(path):
                with open(path, "r+", encoding="utf-8") as fdst:
                    try:
                        fcntl.flock(fdst.fileno(), fcntl.LOCK_EX)
                    except Exception:
                        pass
                    try:
                        os.replace(tmp, path)
                    finally:
                        try:
                            fcntl.flock(fdst.fileno(), fcntl.LOCK_UN)
                        except Exception:
                            pass
            else:
                os.replace(tmp, path)
            return
        except Exception:
            # final fallback: atomic replace
            os.replace(tmp, path)
            return
    except Exception:
        # best-effort; do not fail the caller on state save
        return


class YouTubeResearcher(AgentBase):
    """Performs simple YouTube searches and returns curated records.

    The class is safe to instantiate without an API key for offline testing; any
    operation that requires the YouTube API will raise a RuntimeError when no key
    is configured.
    """

    def __init__(
        self, api_key: Optional[str] = None, vector_db_url: Optional[str] = None
    ):
        self.api_key = api_key or os.environ.get("YOUTUBE_API_KEY")
        self.vector_db_url = vector_db_url or os.environ.get("VECTOR_DB_URL")
        # persistent state path for quota/backoff info
        self._state_dir = os.path.join(os.path.expanduser("~"), ".swarmagents")
        os.makedirs(self._state_dir, exist_ok=True)
        self._state_file = os.path.join(self._state_dir, "youtube_state.json")

    # --- persistent-block helpers ---
    def is_blocked_until(self) -> Optional[float]:
        """Return the blocked_until timestamp (epoch seconds) or None."""
        st = _load_state(self._state_file)
        return st.get("blocked_until")

    def clear_block(self) -> None:
        """Clear any persisted block state."""
        st = _load_state(self._state_file)
        if "blocked_until" in st:
            del st["blocked_until"]
            _save_state(self._state_file, st)

    def _set_blocked_until(self, when: float) -> None:
        st = _load_state(self._state_file)
        st["blocked_until"] = when
        _save_state(self._state_file, st)

    # --- low-level API call with quota handling ---
    def _call_api(self, url: str, params: Dict[str, Any]) -> Dict[str, Any]:
        if not self.api_key:
            raise RuntimeError("No YOUTUBE_API_KEY configured for live API calls")

        params = params.copy()
        params["key"] = self.api_key

        # Check persisted block
        now = time.time()
        blocked_until = self.is_blocked_until()
        if blocked_until and now < blocked_until:
            raise QuotaExceeded(retry_after=blocked_until - now)

        # Retry loop with exponential backoff; respect Retry-After header
        backoff = 1.0
        max_attempts = 6
        for attempt in range(1, max_attempts + 1):
            try:
                resp = requests.get(url, params=params, timeout=15)
            except requests.RequestException as exc:
                if attempt == max_attempts:
                    raise APIError(str(exc)) from exc
                time.sleep(backoff + random.random() * 0.1)
                backoff = min(backoff * 2, 30)
                continue

            status = getattr(resp, "status_code", None)

            # If rate-limited, parse Retry-After and persist block
            if status == 429:
                retry_after = None
                try:
                    ra = resp.headers.get("Retry-After")
                    if ra is not None:
                        # Retry-After may be seconds or HTTP-date; try seconds first
                        try:
                            retry_after = float(ra)
                        except Exception:
                            # try parsing HTTP-date
                            from email.utils import parsedate_to_datetime

                            dt = parsedate_to_datetime(ra)
                            retry_after = dt.timestamp() - now
                except Exception:
                    retry_after = None

                # persist a conservative blocked_until (now + retry_after or backoff window)
                block_seconds = (
                    retry_after
                    if (retry_after and retry_after > 0)
                    else max(backoff, 60)
                )
                blocked_until_val = now + block_seconds
                self._set_blocked_until(blocked_until_val)
                raise QuotaExceeded(retry_after=block_seconds)

            # Other non-200 statuses
            if status is None or status >= 500:
                # server error -> retry
                if attempt == max_attempts:
                    raise APIError(f"HTTP {status} from {url}")
                time.sleep(backoff + random.random() * 0.1)
                backoff = min(backoff * 2, 30)
                continue

            if status >= 400:
                # client error (not rate-limit)
                raise APIError(f"HTTP {status} from {url}: {resp.text}")

            # successful
            try:
                return cast(Dict[str, Any], resp.json())
            except Exception as exc:
                raise APIError("Invalid JSON from API") from exc

        raise APIError("Exceeded retry attempts")

    # --- utility parsers / scoring ---
    @staticmethod
    def _iso8601_duration_to_seconds(dur: str) -> int:
        # Very small ISO8601 duration parser supporting PT#H#M#S
        if not dur:
            return 0
        m = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", dur)
        if not m:
            return 0
        hours = int(m.group(1) or 0)
        mins = int(m.group(2) or 0)
        secs = int(m.group(3) or 0)
        return hours * 3600 + mins * 60 + secs

    @staticmethod
    def _compute_relevance(
        title: Optional[str], description: Optional[str], view_count: int
    ) -> float:
        # simple heuristic: length-normalized keyword presence + log(view_count)
        s = ((title or "") + " " + (description or "")).lower()
        keywords = [
            "interview",
            "talk",
            "lecture",
            "webinar",
            "presentation",
            "documentary",
        ]
        score = 0.0
        for k in keywords:
            if k in s:
                score += 1.0
        # add view_count contribution
        try:
            score += math.log1p(view_count) / 10.0
        except Exception:
            pass
        return float(score)

    @staticmethod
    def _extract_tags(title: Optional[str], description: Optional[str]) -> List[str]:
        txt = ((title or "") + " " + (description or "")).lower()
        # crude tokenization
        toks = re.findall(r"[a-z0-9]{3,}", txt)
        # frequency map
        freq: Dict[str, int] = {}
        for t in toks:
            freq[t] = freq.get(t, 0) + 1
        # return top 6 tokens
        tags = sorted(freq.keys(), key=lambda k: freq[k], reverse=True)[:6]
        return tags

    # --- main public method ---
    def search(
        self,
        query: str,
        max_results: int = 10,
        depth: int = 2,
        filters: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> List[VideoRecord]:
        """Search for videos matching `query` and return a list of record dicts.

        - query: search text
        - max_results: maximum final records to return
        - depth: how many pages of search results to fetch (YouTube returns 5-50 results/page)
        - filters: optional dict for extra search params (e.g., "videoDuration":"short")
        """
        if not query:
            return []

        # Local test/mock mode: return deterministic canned results when set.
        test_mode = os.environ.get("YOUTUBE_TEST_MODE", "").lower()
        if test_mode in ("1", "true", "yes"):
            collected = []
            now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            n = min(int(max_results), 5)
            for i in range(n):
                vid_id = f"mock-{i}-{re.sub(r'[^a-z0-9]+', '-', query.lower())[:20]}"
                record = {
                    "videoId": vid_id,
                    "url": f"https://www.youtube.com/watch?v={vid_id}",
                    "title": f"Mock result {i+1} for '{query}'",
                    "description": f"This is a mocked description for '{query}', result {i+1}.",
                    "channelTitle": "Mock Channel",
                    "publishedAt": now_iso,
                    "durationSeconds": 60 + i * 10,
                    "duration": 60 + i * 10,
                    "viewCount": 100 + i * 10,
                    "relevanceScore": float(1.0 + i * 0.1),
                    "suggestedTags": [
                        "mock",
                        "test",
                        query.split()[0].lower() if query.split() else "",
                    ],
                }
                collected.append(record)
            return cast(List[VideoRecord], collected)

        filters = filters or {}
        collected = []

        # page tokens loop
        params: Dict[str, Any] = {
            "part": "snippet",
            "q": query,
            "type": "video",
            "maxResults": 25,
        }
        params.update(filters)

        next_page_token = None
        pages = 0
        # support alias depth_of_search from callers/tests
        depth = int(kwargs.get("depth_of_search", depth))
        while pages < depth:
            if next_page_token:
                params["pageToken"] = next_page_token

            data = self._call_api(YOUTUBE_SEARCH_URL, params)
            next_page_token = data.get("nextPageToken")
            pages += 1

            items = data.get("items", [])
            if not items:
                break

            # Collect video ids to batch fetch details
            video_ids = [
                it["id"]["videoId"]
                for it in items
                if it.get("id") and it["id"].get("videoId")
            ]
            if not video_ids:
                continue

            # fetch video details (contentDetails, statistics)
            vid_params = {
                "part": "snippet,contentDetails,statistics",
                "id": ",".join(video_ids),
            }
            vid_data = self._call_api(YOUTUBE_VIDEOS_URL, vid_params)
            vitems = {v["id"]: v for v in vid_data.get("items", [])}

            for it in items:
                vid = it.get("id", {}).get("videoId")
                if not vid:
                    continue
                v = vitems.get(vid)
                if not v:
                    continue

                snip = it.get("snippet", {})
                content = v.get("contentDetails", {})
                stats = v.get("statistics", {})
                view_count = int(stats.get("viewCount") or 0)
                duration = self._iso8601_duration_to_seconds(
                    content.get("duration", "")
                )

                record = {
                    "videoId": vid,
                    "url": f"https://www.youtube.com/watch?v={vid}",
                    "title": snip.get("title"),
                    "description": (snip.get("description") or "").strip(),
                    "channelTitle": snip.get("channelTitle"),
                    "publishedAt": snip.get("publishedAt"),
                    "durationSeconds": duration,
                    # legacy field used in some tests/consumers
                    "duration": duration,
                    "viewCount": view_count,
                    "relevanceScore": self._compute_relevance(
                        snip.get("title"), snip.get("description"), view_count
                    ),
                    "suggestedTags": self._extract_tags(
                        snip.get("title"), snip.get("description")
                    ),
                }

                collected.append(record)
                if len(collected) >= max_results:
                    break

            if len(collected) >= max_results:
                break

            if not next_page_token:
                break

            # small polite pause between pages
            time.sleep(0.2 + random.random() * 0.1)

        # after collecting pages, return trimmed results
        return cast(List[VideoRecord], collected[:max_results])

    # --- optional: render an LLM prompt using the central prompts.json ---
    def make_search_prompt(
        self,
        query: str,
        max_results: int = 10,
        depth: int = 2,
        filters: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Render the YouTube Researcher prompt (pr-007) from prompts.json.

        This is a convenience for downstream enrichment or for sending to a model runner.
        If the prompts store isn't available, returns an informative fallback string.
        """
        vars = {
            "persona": "YouTube Research Expert",
            "topic_or_person": query,
            "max_results": max_results,
            "depth_of_search": depth,
            "filters": filters or "",
        }
        return self.render_prompt("pr-007", vars)

    # Optional helper to push to vector DB; left small and best-effort.
    def post_to_vector_db(self, records: List[Dict[str, Any]]) -> bool:
        # If configured with a neo4j URI, use the GraphRAG agent
        if (
            self.vector_db_url
            and self.vector_db_url.startswith("neo4j://")
            and GraphRAG is not None
        ):
            try:
                # GraphRAG expects URI, user, password via env or defaults
                g = GraphRAG(uri=self.vector_db_url)
                ok = g.ingest(records)
                g.close()
                return bool(ok)
            except Exception:
                return False

        if not self.vector_db_url:
            raise RuntimeError("No VECTOR_DB_URL configured")
        try:
            resp = requests.post(
                self.vector_db_url, json={"objects": records}, timeout=10
            )
            return bool(200 <= resp.status_code < 300)
        except Exception:
            return False


if __name__ == "__main__":
    # quick local smoke run (will raise if no API key present)
    r = YouTubeResearcher()
    try:
        res = r.search("kennedy energy", max_results=5)
        print(json.dumps(res, indent=2))
    except QuotaExceeded as q:
        print("QuotaExceeded; retry in", q.retry_after)
    except Exception as e:
        print("Error:", e)
