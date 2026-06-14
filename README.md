---
title: Secret Student
emoji: "\U0001F30D"
colorFrom: purple
colorTo: gray
sdk: docker
app_port: 7860
pinned: false
license: mit
short_description: "Retro game: play as a student with a secret identity!"
---

# Secret Student

Secret Student is a Gradio-hosted retro learning game for the Hugging Face Build Small Hackathon. A player registers as a school kid with a secret identity, learns a topic at school, gets a mission call at home, and fights a boss at `{player_name}'s Grandma's House`.

The app uses a custom Phaser frontend embedded in a Gradio shell, with FastAPI routes for game data and a SQLite database for persistence.

## Run Locally

```bash
uv sync
cp .env.example .env
LLM_PROVIDER=mock uv run uvicorn main:app --reload --host 0.0.0.0 --port 7860
```

Open:

```text
http://127.0.0.1:7860
```

To open the game from another device on the same Wi-Fi network, use the
laptop's local network address instead, for example:

```text
http://192.168.1.123:7860
```

The address may change when the laptop reconnects to Wi-Fi. On macOS, find it
under System Settings > Wi-Fi > Details > TCP/IP, or run `ifconfig en0`.

Mock mode is fully playable without a model endpoint.

## Model Configuration

Choose the model runtime at application startup:

```text
LLM_RUNTIME=mock                # no external model; deterministic demo content
LLM_RUNTIME=external            # Modal or another OpenAI-compatible endpoint
LLM_RUNTIME=embedded_llamacpp   # llama.cpp runs beside the app in one container
LLM_RUNTIME=embedded_dual_llamacpp # separate text and vision llama.cpp servers
```

`LLM_PROVIDER` remains supported for older local `.env` files, but
`LLM_RUNTIME` takes precedence.

### External Or Modal

The external mode works with Modal, a public llama.cpp server, or another
OpenAI-compatible chat-completions endpoint:

Nemotron example:

```bash
LLM_RUNTIME=external
LLM_BASE_URL=https://your-modal-app.modal.run
LLM_API_KEY=replace-with-the-model-server-key
LLM_MODEL=ggml-org/NVIDIA-Nemotron-3-Nano-Omni:Q4_K_M
```

MiniCPM-V 4.6 example, matching the model used during local development:

```bash
LLM_RUNTIME=external
LLM_BASE_URL=https://your-public-minicpm-endpoint
LLM_API_KEY=replace-with-the-model-server-key
LLM_MODEL=openbmb/MiniCPM-V-4.6
```

Deploy the included Modal llama.cpp server:

```bash
uv sync --extra modal
modal setup
modal secret create secret-student-llm \
  LLAMA_ARG_API_KEY=replace-with-a-long-random-key \
  HF_TOKEN=hf_your_token
uv run --extra modal modal deploy scripts/deploy_llamacpp_modal.py
```

The deploy command prints the URL to use as `LLM_BASE_URL`. The Modal script
defaults to an L40S, persistent model caches, and the pinned
`ghcr.io/ggml-org/llama.cpp:server-cuda-b9049` image. Override its model or GPU
with `MODAL_LLAMA_CPP_MODEL_REF` and `MODAL_LLAMA_CPP_GPU` before deployment.
For MiniCPM-V on Modal, set `MODAL_LLAMA_CPP_MODEL_REF` to a compatible
MiniCPM-V 4.6 GGUF repository and quantization before running `modal deploy`.

### Embedded llama.cpp

The Docker image contains both Secret Student and `llama-server`. The startup
supervisor launches and health-checks the model before serving the game:

Nemotron example:

```bash
LLM_RUNTIME=embedded_llamacpp
LLAMA_CPP_MODEL_REF=ggml-org/NVIDIA-Nemotron-3-Nano-Omni:Q4_K_M
LLAMA_CPP_API_KEY=replace-with-a-long-random-key
LLAMA_CPP_CTX_SIZE=8192
LLAMA_CPP_GPU_LAYERS=999
LLAMA_CPP_STARTUP_TIMEOUT=900
LLM_MODEL=ggml-org/NVIDIA-Nemotron-3-Nano-Omni:Q4_K_M
```

MiniCPM-V 4.6 example:

```bash
LLM_RUNTIME=embedded_llamacpp
LLAMA_CPP_MODEL_REF=your-minicpm-v-4.6-gguf-repository:your-quantization
LLAMA_CPP_API_KEY=replace-with-a-long-random-key
LLAMA_CPP_CTX_SIZE=8192
LLAMA_CPP_GPU_LAYERS=999
LLM_MODEL=openbmb/MiniCPM-V-4.6
```

`LLAMA_CPP_MODEL_REF` tells llama.cpp which GGUF package to download.
`LLM_MODEL` is the model identifier sent in OpenAI-compatible API requests.
They may differ. For handwritten image verification, the selected MiniCPM-V
GGUF package must include or reference its multimodal projector and be supported
by the pinned llama.cpp build.

The Space must use regular GPU hardware for this mode. Hugging Face ZeroGPU is
available only to Gradio SDK Spaces using dynamically decorated GPU functions;
it cannot provide a long-lived GPU to this Docker supervisor. Persistent Space
storage is recommended because model caches live under `/data`.

### Dual-model Space runtime

The recommended L4 configuration uses Qwen3-8B for lesson generation and
teacher chat, and MiniCPM-V only for handwritten-answer extraction:

```bash
LLM_RUNTIME=embedded_dual_llamacpp
LLAMA_CPP_MODEL_PATH=/data/models/qwen3-8b/Qwen3-8B-Q4_K_M.gguf
VISION_LLAMA_CPP_MODEL_PATH=/data/models/minicpm-v-4_5/MiniCPM-V-4_5-Q4_K_M.gguf
VISION_LLAMA_CPP_MMPROJ_PATH=/data/models/minicpm-v-4_5/mmproj-model-f16.gguf
```

Upload those completed files to the mounted bucket once. The runtime reads them
directly on every restart. Fallback `-hf` downloads use `/tmp/llama.cpp` because
bucket mounts do not support the atomic cache rename used by llama.cpp.

The preload helper is designed for a Hugging Face Job or another machine where
the bucket is mounted at `/data`:

```bash
uv run python scripts/preload_space_models.py
```

It downloads to local temporary storage first and then copies completed files
to `/data/models`, safely resuming by checking existing file sizes.

Run `uv run python set_env_for_space.py --runtime embedded_dual_llamacpp` to
configure both local servers. Use empty `--llama-model-path` and
`--vision-llama-model-path` values only when intentionally using ephemeral
Hub downloads instead of preloaded bucket files.

For local NVIDIA Docker testing with a separate llama.cpp service:

```bash
docker compose -f compose.yaml -f compose.llamacpp.yaml up --build
```

The lesson generator requests structured JSON and parses it into Pydantic classes. Text and numeric answers are checked deterministically first. Drawn answers are sent to the vision model only when the player submits notebook handwriting.

## LLM Traces

Every OpenAI-compatible model call records its request, full response, parse or
repair step, schema validation, timing, and final status. For local debugging:

```bash
TRACE_DESTINATION=local
TRACE_DIR=debug_traces
```

Failed API responses include a trace ID. Find the matching JSON file under
`debug_traces/`; malformed model JSON is retained there before any automatic
repair is attempted. Image data is replaced by a hash and API keys are never
written to traces.

To publish completed traces to a Hugging Face dataset repository instead:

```bash
TRACE_DESTINATION=hub
TRACE_HUB_REPO_ID=your-name/secret-student-traces
TRACE_HUB_TOKEN=hf_your_write_token
TRACE_HUB_PRIVATE=true
TRACE_HUB_INCLUDE_CONTENT=false
```

Hub traces remove the internal user ID. Prompts and raw completions are also
removed unless `TRACE_HUB_INCLUDE_CONTENT=true`; review traces carefully before
enabling that option, especially when testing with real learners.

## Key Routes

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

```bash
uv run pytest
```

## Hugging Face Space

This repository is configured as a Docker Space. Set one of the following in
**Settings > Variables and secrets**.

After a push to the Space's `main` branch, Hugging Face automatically rebuilds
the Docker image and runs its `CMD`, which starts `python -m app.runtime`. A
Factory reboot is useful after changing Variables or Secrets.

Modal/external variables:

```text
LLM_RUNTIME=external
LLM_BASE_URL=https://your-modal-app.modal.run
LLM_MODEL=ggml-org/NVIDIA-Nemotron-3-Nano-Omni:Q4_K_M
# Or: openbmb/MiniCPM-V-4.6
```

Modal/external secrets:

```text
LLM_API_KEY=your-model-server-key
APP_SECRET=your-game-session-secret
```

Embedded variables:

```text
LLM_RUNTIME=embedded_llamacpp
LLAMA_CPP_MODEL_REF=your-gguf-repository:quantization
LLM_MODEL=openbmb/MiniCPM-V-4.6
LLAMA_CPP_CTX_SIZE=8192
LLAMA_CPP_GPU_LAYERS=999
```

Embedded secrets:

```text
LLAMA_CPP_API_KEY=your-internal-model-key
HF_TOKEN=your-hugging-face-token
APP_SECRET=your-game-session-secret
```

The Space starts through:

```bash
python -m app.runtime
```

The Gradio root embeds `/game`, which serves the custom Phaser app. Static files are under `frontend/static`.
