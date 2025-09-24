<<<<<<< HEAD
# SwarmAgents
=======
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
>>>>>>> 936debd (Add YouTube researcher quota handling, worker DI, tests, and VS Code settings)
