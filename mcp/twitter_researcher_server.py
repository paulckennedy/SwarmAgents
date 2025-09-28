from __future__ import annotations

import os
import json
from typing import Any, Dict, List, cast

from fastapi import FastAPI, HTTPException, Response
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder

from mcp.schemas_twitter import CallRequest, CallResponse, MetaResponse, TweetRecord
from agents.twitter_researcher import TwitterResearcher, RateLimitExceeded

app = FastAPI()


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.get("/meta")
def meta() -> MetaResponse:
    return MetaResponse(name="twitter_researcher", version="0.1")


@app.post("/call")
def call(req: CallRequest) -> JSONResponse:
    tr = TwitterResearcher(api_key=os.getenv("TWITTER_API_KEY"))
    try:
        results = tr.search(req.query)
    except RateLimitExceeded as e:
        # Tell caller to retry after e.retry_after seconds
        headers = {"Retry-After": str(int(e.retry_after))}
        raise HTTPException(status_code=429, detail="rate limited", headers=headers)
    except Exception as e:  # pragma: no cover - surface unknown errors
        raise HTTPException(status_code=500, detail=str(e))

    # convert results into Pydantic models; ensure url strings validate as HttpUrl
    tweets: List[TweetRecord] = []
    for r in results:
        # normalize and coerce fields to concrete types for Pydantic
        r_copy = dict(r)
        r_typed = cast(Dict[str, Any], r_copy)
        # coerce expected fields into typed dict
        r_typed["id"] = str(r_typed.get("id", ""))
        r_typed["url"] = str(r_typed.get("url", ""))
        r_typed["text"] = str(r_typed.get("text", ""))
        r_typed["author"] = str(r_typed.get("author", ""))
        r_typed["created_at"] = str(r_typed.get("created_at", ""))
        # coerce numeric fields safely
        try:
            r_typed["like_count"] = int(r_typed.get("like_count", 0) or 0)
        except Exception:
            r_typed["like_count"] = 0
        try:
            r_typed["retweet_count"] = int(r_typed.get("retweet_count", 0) or 0)
        except Exception:
            r_typed["retweet_count"] = 0
        try:
            r_typed["reply_count"] = int(r_typed.get("reply_count", 0) or 0)
        except Exception:
            r_typed["reply_count"] = 0
        r_typed["lang"] = str(r_typed.get("lang", ""))
        tweets.append(TweetRecord(**r_typed))
    resp_model = CallResponse(results=tweets)
    return JSONResponse(content=jsonable_encoder(resp_model))
