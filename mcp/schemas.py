from __future__ import annotations

from typing import Any, List, Optional

from pydantic import BaseModel, Field


class VideoRecord(BaseModel):
    videoId: str
    url: Optional[str]
    title: Optional[str]
    description: Optional[str]
    channelTitle: Optional[str]
    publishedAt: Optional[str]
    durationSeconds: Optional[int]
    duration: Optional[int]
    viewCount: Optional[int]
    relevanceScore: Optional[float]
    suggestedTags: Optional[List[str]]


class CallRequest(BaseModel):
    id: Optional[str] = Field(None, description="Optional job id to correlate")
    query: str
    max_results: Optional[int] = 10
    depth: Optional[int] = 1
    filters: Optional[Any] = None


class CallResponse(BaseModel):
    id: Optional[str]
    response: Optional[List[VideoRecord]]
    finished_at: Optional[str]


class ErrorResponse(BaseModel):
    id: Optional[str]
    error: str
    retry_after: Optional[float] = None


class MetaResponse(BaseModel):
    name: str
    version: str
    capabilities: List[str]
