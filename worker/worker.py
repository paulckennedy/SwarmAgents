import json
import logging
import os
import time
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, cast

import redis
import requests

from agents.types import JobPayload, JobResult, VideoRecord
from agents.youtube_researcher import APIError, QuotaExceeded, YouTubeResearcher
from agents.twitter_researcher import TwitterResearcher, RateLimitExceeded
from worker.redis_helpers import blpop as rh_blpop
from worker.redis_helpers import rpush as rh_rpush
from worker.redis_helpers import set_ as rh_set
from worker.redis_helpers import zadd as rh_zadd
from worker.redis_helpers import zrangebyscore
from worker.redis_helpers import zrem as rh_zrem


def call_model_runner(prompt: str) -> str:
    runner_url = os.getenv("MODEL_RUNNER_URL", "http://model_runner:8001/generate")
    try:
        resp = requests.post(runner_url, json={"prompt": prompt}, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        return data.get("response") or data.get("result") or str(data)
    except Exception as e:
        print("Model runner call failed:", e)
        return f"(fallback-mock) Echo: {prompt}"


def process_job(
    job: Dict[str, Any], researcher_factory: Optional[Callable[[], Any]] = None
) -> JobResult:
    job_id = job.get("id")
    payload = cast(JobPayload, job.get("payload", {}))
    # Narrow dynamic types from payload to concrete types for the type checker
    prompt = str(payload.get("prompt") or "")
    # If the job explicitly requests the YouTube Researcher prompt (pr-007) or type
    prompt_id = payload.get("prompt_id") or payload.get("id")

    try:
        agent_field = payload.get("agent")
        tags_field = payload.get("tags") or []
        # Normalize types
        prompt_id = str(prompt_id) if prompt_id is not None else ""
        agent_field = str(agent_field) if agent_field is not None else ""
        if isinstance(tags_field, (bytes, str)):
            tags_iter = [str(tags_field)]
        elif isinstance(tags_field, list):
            tags_iter = [str(t) for t in tags_field]
        else:
            tags_iter = []

        # Twitter researcher jobs
        if (
            prompt_id == "pr-twitter"
            or agent_field == "twitter_researcher"
            or "twitter" in tags_iter
        ):
            topic = payload.get("topic_or_person") or payload.get("query") or prompt
            # ensure numeric values for max_results/depth
            mr_val = payload.get("max_results")
            if isinstance(mr_val, (int, float, str)):
                try:
                    max_results = int(mr_val)
                except Exception:
                    max_results = 25
            else:
                max_results = 25

            d_val = (
                payload.get("depth_of_search")
                if payload.get("depth_of_search") is not None
                else payload.get("depth")
            )
            if isinstance(d_val, (int, float, str)):
                try:
                    depth = int(d_val)
                except Exception:
                    depth = 1
            else:
                depth = 1
            filters = payload.get("filters")

            # If an MCP endpoint is configured, call it instead of local class
            mcp_url = os.getenv("TWITTER_MCP_URL")
            if mcp_url:
                try:
                    payload_req = {
                        "id": job_id,
                        "query": topic,
                        "max_results": max_results,
                        "depth": depth,
                        "filters": filters,
                    }
                    resp = requests.post(
                        f"{mcp_url.rstrip('/')}/call", json=payload_req, timeout=30
                    )
                    if resp.status_code == 200:
                        records = cast(List[Dict[str, Any]], resp.json().get("response") or [])
                    elif resp.status_code == 429:
                        # translate to RateLimitExceeded so caller can schedule retry
                        ra = resp.headers.get("Retry-After")
                        try:
                            retry_after = float(ra) if ra is not None else None
                        except Exception:
                            retry_after = None
                        raise RateLimitExceeded(int(retry_after) if retry_after is not None else 60)
                    else:
                        # other error -> raise APIError so fallback can happen
                        raise APIError(f"MCP error {resp.status_code}: {resp.text}")
                except RateLimitExceeded:
                    # bubble up to let caller schedule retry
                    raise
                except Exception as e:
                    # fallback to local researcher if MCP unreachable
                    logging.debug(
                        "MCP call failed, falling back to local twitter researcher: %s", e
                    )
                    researcher = (
                        researcher_factory()
                        if researcher_factory is not None
                        else TwitterResearcher()
                    )
                    records = cast(List[Dict[str, Any]], researcher.search(topic))
            else:
                researcher = (
                    researcher_factory()
                    if researcher_factory is not None
                    else TwitterResearcher()
                )
                records = cast(List[Dict[str, Any]], researcher.search(topic))

            result = cast(
                JobResult,
                {
                    "id": job_id,
                    "response": records,
                    "finished_at": datetime.now(timezone.utc).isoformat(),
                },
            )

        # YouTube researcher jobs
        elif (
            prompt_id == "pr-007"
            or agent_field == "youtube_researcher"
            or "youtube" in tags_iter
        ):
            # expected payload fields: topic_or_person, max_results, depth_of_search, filters
            topic = payload.get("topic_or_person") or payload.get("query") or prompt
            # ensure numeric values for max_results/depth
            mr_val = payload.get("max_results")
            if isinstance(mr_val, (int, float, str)):
                try:
                    max_results = int(mr_val)
                except Exception:
                    max_results = 25
            else:
                max_results = 25
            # support alias depth_of_search
            d_val = (
                payload.get("depth_of_search")
                if payload.get("depth_of_search") is not None
                else payload.get("depth")
            )
            if isinstance(d_val, (int, float, str)):
                try:
                    depth = int(d_val)
                except Exception:
                    depth = 1
            else:
                depth = 1
            filters = payload.get("filters")

            # If an MCP endpoint is configured, call it instead of local class
            mcp_url = os.getenv("YOUTUBE_MCP_URL")
            if mcp_url:
                try:
                    payload_req = {
                        "id": job_id,
                        "query": topic,
                        "max_results": max_results,
                        "depth": depth,
                        "filters": filters,
                    }
                    resp = requests.post(
                        f"{mcp_url.rstrip('/')}/call", json=payload_req, timeout=30
                    )
                    if resp.status_code == 200:
                        records = cast(List[Dict[str, Any]], resp.json().get("response") or [])
                    elif resp.status_code == 429:
                        # translate to QuotaExceeded so caller can schedule retry
                        ra = resp.headers.get("Retry-After")
                        try:
                            retry_after = float(ra) if ra is not None else None
                        except Exception:
                            retry_after = None
                        raise QuotaExceeded(retry_after=retry_after)
                    else:
                        # other error -> raise APIError
                        raise APIError(f"MCP error {resp.status_code}: {resp.text}")
                except QuotaExceeded:
                    # bubble up to let caller schedule retry
                    raise
                except Exception as e:
                    # fallback to local researcher if MCP unreachable
                    logging.debug(
                        "MCP call failed, falling back to local researcher: %s", e
                    )
                    researcher = (
                        researcher_factory()
                        if researcher_factory is not None
                        else YouTubeResearcher()
                    )
                    try:
                        records = cast(List[Dict[str, Any]], researcher.search(
                            topic, max_results=max_results, depth=depth, filters=filters
                        ))
                    except TypeError:
                        records = cast(List[Dict[str, Any]], researcher.search(
                            topic,
                            max_results=max_results,
                            depth_of_search=depth,
                            filters=filters,
                        ))
            else:
                researcher = (
                    researcher_factory()
                    if researcher_factory is not None
                    else YouTubeResearcher()
                )
                # Try calling researcher.search with the canonical signature, but
                # some test doubles or older agents accept 'depth_of_search' instead.
                try:
                    records = cast(List[Dict[str, Any]], researcher.search(
                        topic, max_results=max_results, depth=depth, filters=filters
                    ))
                except TypeError:
                    # fallback for researcher implementations that expect depth_of_search
                    records = cast(List[Dict[str, Any]], researcher.search(
                        topic,
                        max_results=max_results,
                        depth_of_search=depth,
                        filters=filters,
                    ))

                result = cast(
                JobResult,
                {
                    "id": job_id,
                    "response": records,
                    "finished_at": datetime.now(timezone.utc).isoformat(),
                },
            )
        else:
            response = call_model_runner(prompt)
            result = cast(
                JobResult,
                {
                    "id": job_id,
                    "response": response,
                    "finished_at": datetime.now(timezone.utc).isoformat(),
                },
            )
    except (QuotaExceeded, RateLimitExceeded) as q:
        # Let QuotaExceeded/RateLimitExceeded bubble up so main() can schedule a retry
        raise
    except Exception as e:
        # For other exceptions, return an error result (but don't raise)
        result = cast(
            JobResult,
            {
                "id": job_id,
                "error": str(e),
                "finished_at": datetime.now(timezone.utc).isoformat(),
            },
        )

    return result


def main() -> None:
    REDIS_HOST = os.getenv("REDIS_HOST", "redis")
    REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
    r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0)
    print("Worker started, waiting for tasks...")
    while True:
        run_once(r)


def run_once(
    r: Optional[redis.Redis] = None,
    blpop_timeout: int = 5,
    researcher_factory: Optional[Callable[[], Any]] = None,
    process_job_fn: Optional[Callable[[Dict[str, Any]], JobResult]] = None,
) -> bool:
    """Run one iteration of the worker loop against the provided redis connection.

    Returns True if a job was processed (or scheduled), False if no job was available.
    """
    REDIS_HOST = os.getenv("REDIS_HOST", "redis")
    REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
    if r is None:
        r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0)

    # move any due delayed jobs into the tasks queue
    try:
        now = time.time()
        due = zrangebyscore(r, "delayed_jobs", 0, now)
        # zrangebyscore may return a list of bytes; iterate safely
        for member in due:
            # atomically remove and push back to tasks
            try:
                rh_zrem(r, "delayed_jobs", member)
                rh_rpush(r, "tasks", member)
            except Exception:
                # ignore per-member failures
                pass
    except Exception:
        # best-effort; don't crash worker if Redis interaction fails briefly
        pass

    # redis-py expects a list of keys for blpop
    blpop_item = rh_blpop(r, ["tasks"], timeout=blpop_timeout)
    if not blpop_item:
        return False

    _, raw = blpop_item
    # raw may be bytes in some redis clients
    raw_decoded = raw.decode() if isinstance(raw, (bytes, bytearray)) else raw
    raw_str = raw_decoded if isinstance(raw_decoded, str) else str(raw_decoded)
    job = cast(Dict[str, Any], json.loads(raw_str))
    print("Processing job", job.get("id"))
    try:
        if process_job_fn is not None:
            result = process_job_fn(job)
        else:
            result = process_job(job, researcher_factory=researcher_factory)
        rh_set(r, f"job:{job.get('id')}", json.dumps(result))
        print("Job completed", job.get("id"))
        # Persist the result to disk for later inspection/processing only on success
        try:
            if result.get("error"):
                # Do not persist error results to runs/ (keep them only in Redis)
                return True

            runs_jobs_dir = os.path.join(os.getcwd(), "runs", "jobs")
            os.makedirs(runs_jobs_dir, exist_ok=True)
            # Ensure each video record has a URL field if it's a list of dicts
            resp = result.get("response")
            if isinstance(resp, list):
                for rec in cast(List[VideoRecord], resp):
                    try:
                        vid = rec.get("videoId")
                        if vid and not rec.get("url"):
                            rec["url"] = f"https://www.youtube.com/watch?v={vid}"
                    except Exception:
                        pass

            # write a stable 'last' file and a timestamped snapshot
            stable_fname = os.path.join(runs_jobs_dir, f"last_job_{job.get('id')}.json")
            with open(stable_fname, "w", encoding="utf-8") as fh:
                json.dump(result, fh, indent=2)

            # timestamped snapshot for archival
            try:
                from datetime import datetime as _dt
                from datetime import timezone as _tz

                ts = _dt.now(_tz.utc).strftime("%Y%m%dT%H%M%SZ")
                snap_fname = os.path.join(
                    runs_jobs_dir, f"job_{job.get('id')}_{ts}.json"
                )
                with open(snap_fname, "w", encoding="utf-8") as sfh:
                    json.dump(result, sfh, indent=2)
            except Exception:
                pass
        except Exception as ex:
            print("Failed to write job to runs/:", ex)
    except (QuotaExceeded, RateLimitExceeded) as q:
        # schedule a delayed retry
        retry_after = q.retry_after if (q.retry_after and q.retry_after > 0) else 60
        retry_at = time.time() + retry_after
        # store original job JSON as member in sorted set with score=retry_at
        try:
            # store the original JSON string as the member in delayed_jobs
            mapping: Dict[str, float] = {raw_str: retry_at}
            rh_zadd(r, "delayed_jobs", mapping)
            # set job status to deferred with retry hint
            rh_set(
                r,
                f"job:{job.get('id')}",
                json.dumps(
                    {
                        "id": job.get("id"),
                        "deferred": True,
                        "retry_after": retry_after,
                        "scheduled_at": retry_at,
                    }
                ),
            )
            print(f"Job {job.get('id')} deferred for {retry_after} seconds")
        except Exception as ex:
            print("Failed to schedule delayed job:", ex)
            # fallback: mark job with error
            rh_set(
                r,
                f"job:{job.get('id')}",
                json.dumps({"id": job.get("id"), "error": str(q)}),
            )

    return True


if __name__ == "__main__":
    main()
