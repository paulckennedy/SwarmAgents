### Multi-stage Dockerfile: build llama.cpp in a builder stage and copy the binary into a slim runtime image

FROM python:3.10-slim AS builder
WORKDIR /build

# Install build tools for compiling llama.cpp
RUN apt-get update && apt-get install -y --no-install-recommends \
	build-essential \
	git \
	ca-certificates \
	wget \
	&& rm -rf /var/lib/apt/lists/*

# Clone and build llama.cpp
RUN git clone https://github.com/ggerganov/llama.cpp.git /build/llama.cpp && \
	cd /build/llama.cpp && make

FROM python:3.10-slim
WORKDIR /app

# Copy the built llama.cpp binary from the builder stage (if present)
COPY --from=builder /build/llama.cpp/main /app/llama.cpp/main
RUN chmod +x /app/llama.cpp/main || true

# Install runtime Python deps
COPY requirements.txt /app/requirements.txt
RUN pip install -r /app/requirements.txt

# Copy application code
COPY . /app

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8001"]
