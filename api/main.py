from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
import redis
import uuid
import json
import os

app = FastAPI()

# Serve the web UI (mounted from ./webui)
if os.path.isdir('webui'):
    app.mount('/ui', StaticFiles(directory='webui'), name='webui')

REDIS_HOST = os.getenv('REDIS_HOST', 'redis')
REDIS_PORT = int(os.getenv('REDIS_PORT', 6379))

r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0)

@app.post('/tasks')
def create_task(payload: dict):
    job_id = str(uuid.uuid4())
    job = {'id': job_id, 'payload': payload}
    r.rpush('tasks', json.dumps(job))
    return {'id': job_id}

@app.get('/status/{job_id}')
def get_status(job_id: str):
    res = r.get(f'job:{job_id}')
    if not res:
        return {'status': 'pending'}
    return json.loads(res)

@app.get('/')
def root():
    return {'status': 'ok'}


# Demo endpoint: run a YouTube research search synchronously (useful for testing)
@app.post('/youtube_search')
def youtube_search(payload: dict):
    """Payload example:
    {"query": "climate change", "max_results": 10, "depth_of_search": 1}
    """
    from agents.youtube_researcher import YouTubeResearcher
    query = payload.get('query') or payload.get('topic_or_person')
    if not query:
        return {'error': 'query is required'}
    try:
        rch = YouTubeResearcher()
        records = rch.search(query, max_results=int(payload.get('max_results', 10)), depth_of_search=int(payload.get('depth_of_search', 1)), filters=payload.get('filters'))
        return {'count': len(records), 'results': records}
    except Exception as e:
        return {'error': str(e)}
