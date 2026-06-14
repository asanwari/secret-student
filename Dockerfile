ARG LLAMA_CPP_IMAGE=ghcr.io/ggml-org/llama.cpp:server-cuda-b9049
FROM ${LLAMA_CPP_IMAGE}

USER root
RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        python3 python3-pip python3-venv ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
RUN python3 -m venv /app/.venv \
    && /app/.venv/bin/pip install --no-cache-dir uv \
    && /app/.venv/bin/uv sync --frozen --no-dev

COPY . .

ENV HOST=0.0.0.0 \
    PORT=7860 \
    PATH=/app/.venv/bin:$PATH \
    LLAMA_CPP_SERVER_BIN=/app/llama-server \
    HF_XET_HIGH_PERFORMANCE=1 \
    HF_HOME=/data/huggingface \
    LLAMA_CACHE=/tmp/llama.cpp

# The llama.cpp image normally launches llama-server directly. Secret Student's
# supervisor starts one or two servers for embedded runtimes, then starts Uvicorn.
ENTRYPOINT []
CMD ["python", "-m", "app.runtime"]
