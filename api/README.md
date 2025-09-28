# API

Endpoints:

- POST /tasks — submit a task; body: {"prompt": "..."}
- GET /status/{id} — retrieve job status/result
- GET / — health check
- GET /ui — static web UI served by the API that posts tasks

Run (dev):

- docker-compose up --build

Notes:

- The worker calls the model_runner at http://model_runner:8001/generate
- Replace the model_runner mock with a llama.cpp or TensorRT-backed runner for real inference.
