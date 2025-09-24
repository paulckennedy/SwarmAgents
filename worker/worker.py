import redis
import json
import os
import time
import requests
from agents.youtube_researcher import YouTubeResearcher, QuotaExceeded
from datetime import datetime
from typing import Optional


def call_model_runner(prompt: str) -> str:
    runner_url = os.getenv('MODEL_RUNNER_URL', 'http://model_runner:8001/generate')
    try:
        resp = requests.post(runner_url, json={'prompt': prompt}, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        return data.get('response') or data.get('result') or str(data)
    except Exception as e:
        print('Model runner call failed:', e)
        return f"(fallback-mock) Echo: {prompt}"


def process_job(job: dict, researcher_factory=None) -> dict:
    job_id = job.get('id')
    payload = job.get('payload', {})
    prompt = payload.get('prompt', '')
    # If the job explicitly requests the YouTube Researcher prompt (pr-007) or type
    prompt_id = payload.get('prompt_id') or payload.get('id')
    try:
        if prompt_id == 'pr-007' or payload.get('agent') == 'youtube_researcher' or 'youtube' in (payload.get('tags') or []):
            # expected payload fields: topic_or_person, max_results, depth_of_search, filters
            topic = payload.get('topic_or_person') or payload.get('query') or prompt
            max_results = int(payload.get('max_results', 25))
            depth = int(payload.get('depth_of_search', 1))
            filters = payload.get('filters')
            researcher = researcher_factory() if researcher_factory is not None else YouTubeResearcher()
            # note: researcher.search expects 'depth' not 'depth_of_search'
            records = researcher.search(topic, max_results=max_results, depth=depth, filters=filters)
            result = {
                'id': job_id,
                'response': records,
                'finished_at': datetime.utcnow().isoformat() + 'Z'
            }
        else:
            response = call_model_runner(prompt)
            result = {
                'id': job_id,
                'response': response,
                'finished_at': datetime.utcnow().isoformat() + 'Z'
            }
    except Exception as e:
        # Let QuotaExceeded bubble up so main() can schedule a retry
        if isinstance(e, QuotaExceeded):
            raise
        result = {
            'id': job_id,
            'error': str(e),
            'finished_at': datetime.utcnow().isoformat() + 'Z'
        }
    return result


def main():
    REDIS_HOST = os.getenv('REDIS_HOST', 'redis')
    REDIS_PORT = int(os.getenv('REDIS_PORT', 6379))
    r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0)
    print('Worker started, waiting for tasks...')
    while True:
        run_once(r)


def run_once(r: Optional[redis.Redis] = None, blpop_timeout: int = 5, researcher_factory=None, process_job_fn=None) -> bool:
    """Run one iteration of the worker loop against the provided redis connection.

    Returns True if a job was processed (or scheduled), False if no job was available.
    """
    REDIS_HOST = os.getenv('REDIS_HOST', 'redis')
    REDIS_PORT = int(os.getenv('REDIS_PORT', 6379))
    if r is None:
        r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0)

    # move any due delayed jobs into the tasks queue
    try:
        now = time.time()
        due = r.zrangebyscore('delayed_jobs', 0, now)
        for member in due:
            # atomically remove and push back to tasks
            try:
                r.zrem('delayed_jobs', member)
                r.rpush('tasks', member)
            except Exception:
                # ignore per-member failures
                pass
    except Exception:
        # best-effort; don't crash worker if Redis interaction fails briefly
        pass

    item = r.blpop('tasks', timeout=blpop_timeout)
    if not item:
        return False

    _, raw = item
    # raw may be bytes in some redis clients
    raw_decoded = raw.decode() if isinstance(raw, (bytes, bytearray)) else raw
    job = json.loads(raw_decoded)
    print('Processing job', job.get('id'))
    try:
        if process_job_fn is not None:
            result = process_job_fn(job)
        else:
            result = process_job(job, researcher_factory=researcher_factory)
        r.set(f"job:{job.get('id')}", json.dumps(result))
        print('Job completed', job.get('id'))
    except QuotaExceeded as q:
        # schedule a delayed retry
        retry_after = q.retry_after if (q.retry_after and q.retry_after > 0) else 60
        retry_at = time.time() + retry_after
        # store original job JSON as member in sorted set with score=retry_at
        try:
            r.zadd('delayed_jobs', {raw_decoded: retry_at})
            # set job status to deferred with retry hint
            r.set(f"job:{job.get('id')}", json.dumps({'id': job.get('id'), 'deferred': True, 'retry_after': retry_after, 'scheduled_at': retry_at}))
            print(f"Job {job.get('id')} deferred for {retry_after} seconds")
        except Exception as ex:
            print('Failed to schedule delayed job:', ex)
            # fallback: mark job with error
            r.set(f"job:{job.get('id')}", json.dumps({'id': job.get('id'), 'error': str(q)}))

    return True


if __name__ == '__main__':
    main()
