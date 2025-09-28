from typing import Any, Dict, List, TypedDict


class VideoRecord(TypedDict, total=False):
    videoId: str
    url: str
    title: str
    description: str
    channelTitle: str
    publishedAt: str
    durationSeconds: int
    duration: int
    viewCount: int
    relevanceScore: float
    suggestedTags: List[str]


class TweetRecord(TypedDict, total=False):
    id: str
    url: str
    text: str
    author: str
    created_at: str
    like_count: int
    retweet_count: int
    reply_count: int
    lang: str


class JobPayload(TypedDict, total=False):
    prompt_id: str
    agent: str
    topic_or_person: str
    query: str
    max_results: int
    depth_of_search: int
    filters: Dict[str, Any]


class JobResult(TypedDict, total=False):
    id: str
    response: Any
    finished_at: str
    error: str
    deferred: bool
    retry_after: float
    scheduled_at: float
