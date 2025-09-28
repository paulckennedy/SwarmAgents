# Twitter Researcher Agent

Purpose

- Search Twitter (API v2 Recent Search) for tweets about a topic or person.
- Return a curated JSON array of tweet records suitable for ingestion into a vector DB or downstream
  processing.

Quick start

1. Create a virtualenv and install dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

1. Set your Twitter bearer token (bash):

```bash
# IMPORTANT: do NOT commit real API keys. Export them at runtime instead.
export TWITTER_BEARER_TOKEN='YOUR_BEARER_TOKEN_HERE'
# optionally set vector DB ingestion endpoint
export VECTOR_DB_URL='http://localhost:8000/ingest'
```

1. Run a quick search (test-mode available  see notes):

```bash
python -m agents.twitter_researcher "climate change" --max 5
```

What this module does

- Uses Twitter API v2 when `TWITTER_BEARER_TOKEN` is set; otherwise falls back to canned test-mode
  results (useful for CI and unit tests).
- Maps Twitter v2 responses into a simplified record with fields like `id`, `text`, `author`,
  `created_at`, `url`, and `public_metrics` (retweet/like counts).
- Raises `RateLimitExceeded` when Twitter returns rate-limit information; workers will detect this
  and optionally retry with backoff.

Environment & configuration

- TWITTER_BEARER_TOKEN: (optional) bearer token for Twitter API v2. If unset, the agent runs in a
  test-mode that returns canned records.
- TWITTER_TEST_MODE: set to `1` to force canned responses for local development / CI regardless of
  bearer token.
- VECTOR_DB_URL: (optional) HTTP endpoint to POST results for ingestion.
- TWITTER_MCP_URL: (optional) URL of the MCP (FastAPI) server that can run the agent remotely; the
  worker falls back to local agent if MCP is not available.

docker compose -f docker-compose.dev.yml up -d Running locally with Redis (dev)

1. Start Redis for local dev using docker-compose (from project root):

```bash
docker compose -f docker-compose.dev.yml up -d
```

1. Run the API locally (optional):

```bash
pip install -r requirements.txt
uvicorn api.main:app --reload --port 8000
```

1. To enqueue a Twitter research job to Redis, POST to `/tasks` on the API with payload similar to
   other agents:

```json
{
  "prompt_id": "pr-twitter",
  "query": "climate change",
  "max_results": 10
}
```

Then run the worker in another shell to process jobs:

```bash
python worker/worker.py
```

MCP server

- This repository includes an MCP FastAPI wrapper for the Twitter agent at
  `mcp/twitter_researcher_server.py`.
- If you prefer to run the Twitter agent as a service, set `TWITTER_MCP_URL` in the worker to point
  at that server; the worker uses MCP calls when configured.

Tests

- Unit tests for the Twitter agent are located under `tests/` and mock network calls. They do not
  require a live Twitter token.
- Integration tests that actually hit the Twitter API are marked with the `twitter` pytest marker.
To run integration tests you'll need a real `TWITTER_BEARER_TOKEN` set in the environment and then
run:

```bash
pytest -q -m twitter
```

Example tweet record

When the agent maps Twitter v2 responses it emits records shaped like this example (keys may vary
slightly depending on fields requested):

```json
{
  "id": "1723456789012345678",
  "text": "Climate change is accelerating. Here's what to watch for...",
  "author": "example_user",
  "created_at": "2025-09-01T12:34:56.000Z",
  "url": "https://twitter.com/example_user/status/1723456789012345678",
  "public_metrics": {
    "retweet_count": 12,
    "reply_count": 3,
    "like_count": 45,
    "quote_count": 1
  }
}
```

Notes / gotchas

- Twitter API rate limits are enforced server-side. The agent raises `RateLimitExceeded` with
  suggested `retry_after` seconds; the worker's retry logic will handle gracefully.
- Do not check secrets into source control. Use GitHub Actions secrets or environment management
  locally.
- The agent maps `public_metrics` (likes, retweets, replies, quotes) into the record; if you change
  the mapping be sure to update the tests under `tests/test_twitter_api_mapping.py`.

Useful files

- `agents/twitter_researcher.py` — core agent implementation
- `mcp/twitter_researcher_server.py` — FastAPI wrapper (MCP)
- `worker/worker.py` — worker integration and delayed-retry/backoff handling
- `tests/test_twitter_researcher.py`, `tests/test_twitter_api_mapping.py` — unit tests

If something's missing

Open an issue or PR with the improvement you want (examples: add more fields to the tweet record,
support other Twitter endpoints, or add streaming ingestion).

Enjoy! — contributors
