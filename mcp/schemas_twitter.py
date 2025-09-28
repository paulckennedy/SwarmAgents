from __future__ import annotations

from typing import List

from pydantic import BaseModel, HttpUrl


class TweetRecord(BaseModel):
    id: str
    url: HttpUrl
    text: str
    author: str
    created_at: str
    like_count: int
    retweet_count: int
    reply_count: int
    lang: str


class CallRequest(BaseModel):
    query: str


class CallResponse(BaseModel):
    results: List[TweetRecord]


class MetaResponse(BaseModel):
    name: str
    version: str
