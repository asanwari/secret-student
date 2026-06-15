# Secret Student Technical Guide

This guide covers local development, inference runtimes, model storage,
deployment, tracing, and testing. For the hackathon story and demo links, see
the [main README](../README.md).

## Architecture

Secret Student combines:

- A custom Phaser, HTML, CSS, and JavaScript game under `frontend/static/`.
- A Gradio shell that hosts the game at `/game`.
- FastAPI routes for authentication, lessons, chat, quizzes, boss battles, and
  world state.
- SQLite persistence for users, appearance, lessons, questions, and progress.
- OpenAI-compatible LLM clients with separate text and vision routing.
- llama.cpp servers that can run embedded, in Docker Compose, or behind Modal.

Typed answers always take precedence. When the text field is nonblank, the API
routes only its value to the text model. The notebook image is used only when
the player submits no text.

## Local Development

Install dependencies and create a local environment file:

```bash
uv sync
cp .env.example .env
```

Run the deterministic mock mode:

```bash
LLM_RUNTIME=mock uv run uvicorn main:app --reload --host 0.0.0.0 --port 7860
```

Open `http://127.0.0.1:7860`. Other devices on the same network can use the
computer's LAN address, such as `http://192.168.1.123:7860`.

## Runtime Modes

`LLM_RUNTIME` selects the inference topology:

```text
mock                     Deterministic content with no model server
external                 One OpenAI-compatible external endpoint
embedded_llamacpp        One llama.cpp server beside the application
embedded_dual_llamacpp   Separate text and vision llama.cpp servers
```

`LLM_PROVIDER` remains available for older `.env` files, but `LLM_RUNTIME`
takes precedence.

### External Endpoint

Use Modal, another llama.cpp server, or any compatible chat-completions API:

```bash
LLM_RUNTIME=external
LLM_BASE_URL=https://your-model-server.example
LLM_API_KEY=replace-with-the-server-key
LLM_MODEL=Qwen/Qwen3-8B-GGUF:Q4_K_M
```

### One Embedded llama.cpp Server

The Docker image includes `llama-server`. The runtime starts it, waits for its
health endpoint, then launches the application:

```bash
LLM_RUNTIME=embedded_llamacpp
LLAMA_CPP_MODEL_REF=Qwen/Qwen3-8B-GGUF:Q4_K_M
LLAMA_CPP_API_KEY=replace-with-a-long-random-key
LLAMA_CPP_CTX_SIZE=8192
LLAMA_CPP_GPU_LAYERS=999
LLAMA_CPP_STARTUP_TIMEOUT=900
LLM_MODEL=Qwen/Qwen3-8B-GGUF:Q4_K_M
```

`LLAMA_CPP_MODEL_REF` controls the GGUF downloaded by llama.cpp. `LLM_MODEL` is
the identifier sent in API requests; the two values may differ.

### Dual Embedded llama.cpp Servers

The recommended full setup runs Qwen3-8B for text and MiniCPM-V 4.5 for
handwriting:

```bash
LLM_RUNTIME=embedded_dual_llamacpp

LLM_MODEL=Qwen/Qwen3-8B-GGUF:Q4_K_M
LLAMA_CPP_MODEL_REF=Qwen/Qwen3-8B-GGUF:Q4_K_M
LLAMA_CPP_MODEL_PATH=/data/models/qwen3-8b/Qwen3-8B-Q4_K_M.gguf

VISION_LLM_MODEL=openbmb/MiniCPM-V-4_5-gguf:Q4_K_M
VISION_LLAMA_CPP_MODEL_REF=openbmb/MiniCPM-V-4_5-gguf:Q4_K_M
VISION_LLAMA_CPP_MODEL_PATH=/data/models/minicpm-v-4_5/MiniCPM-V-4_5-Q4_K_M.gguf
VISION_LLAMA_CPP_MMPROJ_PATH=/data/models/minicpm-v-4_5/mmproj-model-f16.gguf
```

All model references, paths, ports, context sizes, GPU layers, thread counts,
and startup timeouts are configurable in `.env`. See `.env.example` and
`app/config.py` for the complete list.

For local NVIDIA Docker testing with a separate llama.cpp service:

```bash
docker compose -f compose.yaml -f compose.llamacpp.yaml up --build
```

## Persistent Model Storage

Hugging Face Spaces can mount persistent storage at `/data`. Download each model
once and point the runtime at its completed GGUF file. This avoids repeating a
multi-gigabyte download after every sleep or rebuild.

The preload helper downloads to temporary local storage and then copies complete
files into `/data/models`. It checks existing sizes before replacing files:

```bash
uv run python scripts/preload_space_models.py
```

The helper reads these optional overrides:

```text
TEXT_MODEL_REPO
TEXT_MODEL_FILE
TEXT_MODEL_DESTINATION
VISION_MODEL_REPO
VISION_MODEL_FILE
VISION_MODEL_DESTINATION
VISION_MMPROJ_FILE
VISION_MMPROJ_DESTINATION
```

If a configured local path is absent, the runtime can fall back to its Hub model
reference. llama.cpp's temporary Hub cache uses `/tmp/llama.cpp` because some
mounted storage systems do not support the atomic rename behavior used by the
cache downloader.

## Configure the Hugging Face Space

The repository includes a helper for setting Space variables and secrets:

```bash
uv run python set_env_for_space.py --runtime embedded_dual_llamacpp
```

Model selection remains configurable through its CLI options or corresponding
environment variables. Empty model-path arguments intentionally select
ephemeral Hub downloads instead of preloaded `/data/models` files.

The Space is a Docker Space and starts with:

```bash
python -m app.runtime
```

A push to the Space's `main` branch triggers a rebuild. Use a Factory reboot
after changing variables or secrets when the existing container does not pick
them up.

Regular GPU hardware is required for the embedded runtime. ZeroGPU cannot host
a long-lived llama.cpp supervisor inside this Docker topology.

## Modal Deployment

Install the optional dependency and authenticate:

```bash
uv sync --extra modal
modal setup
modal secret create secret-student-llm \
  LLAMA_ARG_API_KEY=replace-with-a-long-random-key \
  HF_TOKEN=hf_your-token
```

Copy the example configuration and edit the model list as needed:

```bash
cp config/modal-models.example.yaml config/modal-models.yaml
```

Each model gets a unique `route`, a Hub GGUF `model_ref`, and optional
llama.cpp overrides. Models marked with `role: text` and `role: vision` can be
applied directly to a Space by `set_env_for_space.py`; additional routes remain
available to other clients.

Deploy every configured model in one Modal GPU container:

```bash
MODAL_LLAMA_CPP_CONFIG=config/modal-models.yaml \
uv run --extra modal modal deploy scripts/deploy_llamacpp_modal.py
```

The command prints a base URL for every route, such as `/text` and `/vision`.
A small FastAPI proxy forwards each route to its own internal llama.cpp server
and exposes aggregate status at `/health`. All servers share the configured
GPU, API key, image, and persistent caches.

Configure a CPU-hosted Space to use the routed models:

```bash
uv run python set_env_for_space.py \
  --runtime external \
  --modal-config config/modal-models.yaml \
  --shared-inference-url https://your-deployment.modal.run
```

Smoke-test every configured route after deployment:

```bash
uv run python scripts/test_llamacpp_modal.py \
  --config config/modal-models.yaml \
  --base-url https://your-deployment.modal.run
```

The tester checks aggregate and per-model health, sends a short chat request to
each route, and includes a tiny generated image for models with `role: vision`.
It reads `LLM_API_KEY` from the repository `.env`; `--api-key` remains available
as an explicit override.

Configure the local `.env` to use the same routed deployment while preserving
unrelated local settings:

```bash
uv run python set_env_local.py \
  --modal-config config/modal-models.yaml \
  --shared-inference-url https://your-deployment.modal.run
```

The helper reuses the existing `LLM_API_KEY` from `.env` for both model roles.

For backwards compatibility, omitting `MODAL_LLAMA_CPP_CONFIG` and leaving
`config/modal-models.yaml` absent starts one root-routed model using the legacy
`MODAL_LLAMA_CPP_*` environment variables.

## Structured Generation and Repair

Lesson generation requests a JSON object constrained by a schema. The client:

1. Extracts and parses the model response.
2. Repairs common malformed JSON locally.
3. Normalizes known safe field aliases.
4. Validates the object with Pydantic and content-specific rules.
5. If necessary, sends the invalid object and exact errors to a constrained
   repair prompt.
6. Validates the repaired object again before persistence.

Content rules enforce lesson structure, word limits, available media, question
counts, and concrete grading fields. Invalid output never enters game state.

## LLM Traces

Every model call records its request metadata, response, parse or repair step,
schema validation, timing, and final status.

Local traces:

```bash
TRACE_DESTINATION=local
TRACE_DIR=debug_traces
```

Failed API responses include a trace ID. Image payloads are replaced by hashes,
and API keys are never recorded.

Hub traces:

```bash
TRACE_DESTINATION=hub
TRACE_HUB_REPO_ID=your-name/secret-student-traces
TRACE_HUB_TOKEN=hf_your-write-token
TRACE_HUB_PRIVATE=false
TRACE_HUB_INCLUDE_CONTENT=false
```

Public traces remove the internal user ID. Prompts and raw completions remain
redacted unless `TRACE_HUB_INCLUDE_CONTENT=true`. Review every trace before
publishing content collected from real learners.

## Key API Routes

- `POST /api/auth/register`
- `POST /api/auth/login`
- `GET /api/me`
- `POST /api/lesson/start`
- `GET /api/lesson/{lesson_id}`
- `POST /api/lesson/{lesson_id}/ask`
- `POST /api/quiz/submit`
- `POST /api/boss/start`
- `POST /api/boss/submit`
- `POST /api/state/location`

## Tests

Run the complete test suite:

```bash
uv run pytest
```

The suite covers API behavior, registration and appearance persistence,
structured lesson normalization and repair, trace redaction, typed-versus-drawn
answer routing, explicit quiz progression, feedback states, responsive UI
structures, and tablet pointer controls.
