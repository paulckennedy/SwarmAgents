import redis
import json
import os
import time
import requests
from agents.youtube_researcher import YouTubeResearcher, QuotaExceeded
from datetime import datetime, timezone
from typing import Optional, Any, Dict


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


def process_job(job: Dict[str, Any], researcher_factory=None) -> Dict[str, Any]:
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
            # Try calling researcher.search with the canonical signature, but
            # some test doubles or older agents accept 'depth_of_search' instead.
            try:
                records = researcher.search(topic, max_results=max_results, depth=depth, filters=filters)
            except TypeError:
                # fallback for researcher implementations that expect depth_of_search
                records = researcher.search(topic, max_results=max_results, depth_of_search=depth, filters=filters)
            result = {
                'id': job_id,
                'response': records,
                'finished_at': datetime.now(timezone.utc).isoformat()
            }
        else:
            response = call_model_runner(prompt)
            result = {
                'id': job_id,
                'response': response,
                'finished_at': datetime.now(timezone.utc).isoformat()
            }
    except Exception as e:
        # Let QuotaExceeded bubble up so main() can schedule a retry
        if isinstance(e, QuotaExceeded):
            raise
            result = {
            'id': job_id,
            'error': str(e),
            'finished_at': datetime.now(timezone.utc).isoformat()
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
        # Persist the result to disk for later inspection/processing only on success
        try:
            if result.get('error'):
                # Do not persist error results to runs/ (keep them only in Redis)
                return True

            runs_dir = os.path.join(os.getcwd(), 'runs')
            os.makedirs(runs_dir, exist_ok=True)
            # Ensure each video record has a URL field if it's a list of dicts
            resp = result.get('response')
            if isinstance(resp, list):
                for item in resp:
                    try:
                        vid = item.get('videoId')
                        if vid and not item.get('url'):
                            item['url'] = f"https://www.youtube.com/watch?v={vid}"
                    except Exception:
                        pass

            # write a stable 'last' file and a timestamped snapshot
            stable_fname = os.path.join(runs_dir, f"last_job_{job.get('id')}.json")
            with open(stable_fname, 'w', encoding='utf-8') as fh:
                json.dump(result, fh, indent=2)

            # timestamped snapshot for archival
            try:
                from datetime import datetime as _dt
                ts = _dt.utcnow().strftime('%Y%m%dT%H%M%SZ')
                snap_fname = os.path.join(runs_dir, f"job_{job.get('id')}_{ts}.json")
                with open(snap_fname, 'w', encoding='utf-8') as sfh:
                    json.dump(result, sfh, indent=2)
            except Exception:
                pass
        except Exception as ex:
            print('Failed to write job to runs/:', ex)
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
