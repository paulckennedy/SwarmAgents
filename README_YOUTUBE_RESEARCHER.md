YouTube Researcher Agent

Purpose
- Search YouTube (Data API v3) for videos related to a topic or person.
- Return a curated JSON array of video records ready for ingestion by a vector DB.

Quick start
1. Create a virtualenv and install dependencies:

```powershell
python -m venv .venv; .\.venv\Scripts\Activate.ps1; pip install -r requirements.txt
```

2. Set your API key (PowerShell):

```powershell
$env:YOUTUBE_API_KEY = 'YOUR_API_KEY'
# optionally set vector DB ingestion endpoint
$env:VECTOR_DB_URL = 'http://localhost:8000/ingest'
```

3. Run a quick search:

```powershell
python -m agents.youtube_researcher "climate change" --max 5
```

Notes
- The module uses the public YouTube Data API. Ensure your API key has quota.
- For unit testing, the tests mock network calls and do not require a live API key.

Running locally with Redis (dev)

1. Start Redis for local dev using docker-compose (from project root):

```powershell
docker compose -f docker-compose.dev.yml up -d
```

2. Run the API locally (optional):

```powershell
pip install -r requirements.txt
uvicorn api.main:app --reload --port 8000
```

3. To enqueue a YouTube research job to Redis, POST to `/tasks` on the API with payload:

```json
{
	"prompt_id": "pr-007",
	"topic_or_person": "climate change",
	"max_results": 10
}
```

Then run the worker (in another shell):

```powershell
python worker/worker.py
```
