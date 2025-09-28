from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, cast

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from agents.youtube_researcher import APIError, QuotaExceeded, YouTubeResearcher

from .schemas import CallRequest, CallResponse, ErrorResponse, MetaResponse, VideoRecord


app = FastAPI()


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.get("/meta", response_model=MetaResponse)
def meta() -> Dict[str, Any]:
    return MetaResponse(name="youtube_researcher", version="0.1", capabilities=["search"]).model_dump()


@app.post("/call", response_model=CallResponse)
def call(req: CallRequest) -> Any:
    researcher = YouTubeResearcher()
    try:
        # researcher.search returns a sequence of TypedDict-like records
        raw = cast(List[Dict[str, Any]], researcher.search(
            req.query, max_results=req.max_results or 10, depth=req.depth or 1, filters=req.filters
        ))

        # Convert raw dicts into Pydantic VideoRecord models for response
        records: List[VideoRecord] = [VideoRecord(**r) for r in raw]

        return CallResponse(id=req.id, response=records, finished_at=datetime.now(timezone.utc).isoformat())
    except QuotaExceeded as q:
        body = ErrorResponse(id=req.id, error="quota", retry_after=q.retry_after).model_dump()
        headers: Dict[str, str] = {}
        if q.retry_after:
            headers["Retry-After"] = str(int(q.retry_after))
        return JSONResponse(status_code=429, content=body, headers=headers)
    except APIError as a:
        body = ErrorResponse(id=req.id, error=str(a)).model_dump()
        return JSONResponse(status_code=502, content=body)
    except Exception as e:  # pragma: no cover - defensive
        body = ErrorResponse(id=req.id, error=f"internal: {e}").model_dump()
        return JSONResponse(status_code=500, content=body)
