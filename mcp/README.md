# MCP YouTube Researcher

This folder contains a small FastAPI MCP wrapper around the `YouTubeResearcher` agent.

Endpoints:

- GET /health — health check

- GET /meta — service metadata and capabilities

- POST /call — run a search and return standardized VideoRecord results

Environment variables:
- `YOUTUBE_API_KEY` — your YouTube Data API key (optional if `YOUTUBE_TEST_MODE` is set)
- `YOUTUBE_TEST_MODE` — set to `1` to enable deterministic mock results for local development

Run locally (requires the project `requirements.txt`):

```bash
# from project root
source .venv/bin/activate
pip install -r requirements.txt
uvicorn mcp.youtube_researcher_server:app --reload --port 8002
```

Example call:

```bash
curl -sS -X POST http://localhost:8002/call -H 'Content-Type: application/json' -d '{"id":"job-1","query":"solar energy","max_results":3}' | jq
```

Docker-compose entry (already included in `docker-compose.yml`): `mcp` service on port 8002.
