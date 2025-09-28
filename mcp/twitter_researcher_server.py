from __future__ import annotations

import os
import json
from typing import Any, Dict, List

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

    # convert results into Pydantic models
    tweets: List[TweetRecord] = [TweetRecord(**r) for r in results]
    # Use jsonable_encoder to ensure types like HttpUrl are converted to strings
    resp_model = CallResponse(results=tweets)
    return JSONResponse(content=jsonable_encoder(resp_model))
