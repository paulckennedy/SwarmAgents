# SwarmAgents

This repository is a local prototype for orchestrating small, focused AI "agents" that perform research and ingestion tasks, with safety checks and validation for the prompt templates used to drive the agents.

The project is organized as a set of agents plus a worker pattern and utilities for managing and validating prompts used to drive LLMs or local model runners.

## Key features (current state)

- Agents: modular agent classes under `agents/`. Notable agents implemented:
  - `youtube_researcher.py` — performs YouTube-style search and curates records for ingestion (includes quota/backoff handling and retry scheduling).
  - `graph_rag.py` — Neo4j-backed GraphRAG adapter for ingesting and querying graph-based RAG stores.
- Centralized prompts: `prompts.json` stores all prompt templates and examples.
- Prompt rendering: `agents/prompts.py` uses Jinja2 for templating, with optional StrictUndefined behavior to surface missing variables.
- Prompt validation: optional schema validation that verifies examples match declared variables and simple type checks.
- CLI utilities:
  - `scripts/render_prompt.py` — render a prompt by id (for debugging and prompt development).
  - `scripts/validate_prompts.py` — validate one or more `prompts.json` files, supports `--autofix` (safe, conservative fixes), `--report-json` to write a report, and `--strict` for strict Jinja rendering.
- Tests: full pytest suite covering agents, prompt rendering and validation. Tests live in `tests/` and are executed with `pytest`.
- CI: GitHub Actions workflow at `.github/workflows/ci.yml` runs tests and prompt validation, uploads validation reports, and can create an autofix PR when appropriate.

## Repository layout (high-level)

- `agents/`
  - `prompts.py` - PromptStore (Jinja2), validation and helper `set_default_promptstore()`
  - `youtube_researcher.py` - YouTube researcher agent
  - `graph_rag.py` - Neo4j GraphRAG adapter
- `scripts/`
  - `render_prompt.py` - CLI to render a prompt
  - `validate_prompts.py` - prompt validation CLI (autofix, report JSON)
- `tests/` - pytest suite
- `prompts.json` - centralized prompt templates and examples
- `.github/workflows/ci.yml` - CI pipeline (tests + prompt validation)

## Quick start (development)

### Prerequisites

- Python 3.11 (this repo is developed and tested on Conda/Anaconda Python 3.11 on Windows and Linux).
- Install dependencies:

```powershell
python -m pip install -r requirements.txt
```

### Run tests

```powershell
python -m pytest -q
```

### Render a prompt (example)

```powershell
python -m scripts.render_prompt pr-007 --vars tests/example_pr_007.json
```

### Validate prompts (basic)

```powershell
python -m scripts.validate_prompts --paths prompts.json --report-json validation-report.json
```

### Validate prompts with autofix (safe fixes)

```powershell
python -m scripts.validate_prompts --paths prompts.json --autofix --report-json validation-report.json
```

## Features: PromptStore and validation

- PromptStore (`agents.prompts.PromptStore`) loads `prompts.json` and provides:
  - `render(prompt_id, variables)` — renders a Jinja2 template.
  - `list_prompts()` / `get(prompt_id)` helpers.
  - `strict` mode: enable StrictUndefined by passing `strict=True` or setting `PROMPTS_STRICT=1` to fail on missing variables.
  - `validate_schema` mode: optional schema validation controlled by `PROMPTS_VALIDATE_SCHEMA=1` or by passing `validate_schema=True` to the constructor.
  - `set_default_promptstore()` helper to programmatically override the module-level `ps` default used by other modules.

### Validation checks (conservative):

- Ensures `id`, `prompt_template`, `variables`, and (if present) `tags` are the expected types.
- Confirms each `example` contains all declared variables.
- Performs basic type checks for common fields such as `persona` (str), `max_results` and `depth_of_search` (int), and `filters` (str or object).
- Attempts a non-strict Jinja2 render of each example to surface template errors.

## CLI: `scripts/validate_prompts.py` details

- Accepts `--paths` (one or more prompt files) — default is `prompts.json`.
- `--autofix` performs conservative, safe fixes in-place:
  - Coerces numeric strings for `max_results` and `depth_of_search` to integers when safe.
  - Parses JSON-like `filters` strings when they appear to be serialized JSON.
- `--report-json FILE` writes a JSON report with per-file success/failure and error messages.
- Exit codes: 0 on success, 2 on validation failures.

## CI integration

- The GitHub Actions workflow runs tests, then runs prompt validation and uploads `validation-report.json` as an artifact.
- The workflow also attempts autofix and creates an automatic PR with fixes using `peter-evans/create-pull-request` when changes are made.

## Development notes and next steps

- The worker uses a Redis-backed queue and supports deferred retry scheduling for quota/backoff scenarios. See `worker/` for details.
- `graph_rag.py` is a Neo4j-based ingestion/query helper; to enable it you need a Neo4j instance and the `neo4j` driver installed (already in `requirements.txt`).
- If you want stronger schema validation (types or shapes for all fields) I can add JSON Schema validation or pydantic models for the prompt structure.

## Contributing

- Run tests before opening a PR: `python -m pytest -q`.
- Use `python -m scripts.validate_prompts --autofix` to run conservative fixes and generate a validation report.

If you'd like, I can:

- Add a pre-commit hook to run prompt validation locally.
- Extend autofix rules (e.g., floats, boolean coercion, common normalizations).
- Add GitHub Action artifacts or reviewers for the autofix PRs.

Questions or next work you want me to implement? Open an issue or ask here and I’ll take it on.
SwarmAgents — fully-local prototype

Goal

Scaffold a minimal, fully-local swarm of AI agents that runs on your Jetson AGX Orin (or similar aarch64 machine). This prototype focuses on orchestration and local model integration patterns; for now the model client is a mock that you can replace with a llama.cpp / ggml / TensorRT-based runner later.

Contents

- `docker-compose.yml` — services: redis, api, worker (volumes mount local code).
- `api/` — FastAPI app exposing a task endpoint and status endpoint.
- `worker/` — simple worker that pulls tasks from Redis and invokes a local model client.
- `model_runner/` — notes and instructions for running local models (llama.cpp, TensorRT, quantization tips).
- `requirements.txt` — Python deps for the api and worker.

Prerequisites on Jetson Orin

- JetPack installed (matching your L4T) with CUDA, cuDNN, TensorRT.
- Docker + NVIDIA Container Toolkit (nvidia-docker) for GPU-accelerated containers.
- Python 3.10+ if running outside containers.
- NVMe mounted for persistent storage.

Quick start (dev)

1. On the Jetson, from this folder run:

   docker-compose up --build

   This will start Redis, the API (FastAPI/uvicorn) and a worker process.

2. Create a task (example):

   curl -X POST "http://localhost:8000/tasks" -H "Content-Type: application/json" -d "{\"prompt\": \"Summarize water chemistry basics\"}"

   This returns a job id. Poll `/status/{id}` for the result.

Replacing the mock model with a real local runner

- See `model_runner/README.md` for options (llama.cpp/ggml for CPU, TensorRT/ONNX for GPU acceleration, and notes on quantization and performance on Orin).

Notes

- The compose file uses generic `python:3.10-slim` images; on Jetson you may prefer arm64-specific images or running the services directly on the host.
- The current worker uses a very small mock model client. I can add a llama.cpp invocation example that runs a ggml quantized model if you'd like.

Next steps I can do now

- Add a small local model runner that calls `llama.cpp` (requires building `llama.cpp` for aarch64 on the Orin).
- Add a simple web UI to submit tasks and view results.
- Add more agent personas and a tools registry.

Tell me which of the next steps to implement.