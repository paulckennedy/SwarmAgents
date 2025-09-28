# Running a real model runner locally (llama.cpp example)

1. Build llama.cpp on Jetson (aarch64)

git clone https://github.com/ggerganov/llama.cpp cd llama.cpp make

1. Place a quantized ggml model into `Projects/SwarmAgents/model_runner/models/` (e.g., `ggml-
   model-q4_0.bin`).

1. Modify `model_runner/app.py` to invoke the `./main` binary in `llama.cpp` with the model path and
   capture output.

1. For better performance, consider compiling llama.cpp with AVX/FPU flags disabled or follow port-
   specific guides for Orin.

1. Alternatively, build a TensorRT/ONNX runtime and expose it via this FastAPI app.

If you'd like, I can add the llama.cpp invocation example into `model_runner/app.py` now (requires a
model file placed in `model_runner/models`).
