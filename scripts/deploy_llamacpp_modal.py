from __future__ import annotations

import os
import shlex
import shutil
import subprocess

import modal


APP_NAME = os.getenv("MODAL_LLAMA_CPP_APP_NAME", "secret-student-llamacpp")
MODEL_REF = os.getenv(
    "MODAL_LLAMA_CPP_MODEL_REF",
    "openbmb/MiniCPM-V-4_5-gguf:Q4_K_M",
)
GPU = os.getenv("MODAL_LLAMA_CPP_GPU", "L40S")
CTX_SIZE = os.getenv("MODAL_LLAMA_CPP_CTX_SIZE", "8192")
GPU_LAYERS = os.getenv("MODAL_LLAMA_CPP_GPU_LAYERS", "999")
THREADS = os.getenv("MODAL_LLAMA_CPP_THREADS", "8")
PARALLEL = os.getenv("MODAL_LLAMA_CPP_PARALLEL", "2")
SECRET_NAME = os.getenv("MODAL_LLAMA_CPP_SECRET_NAME", "secret-student-llm")
IMAGE = os.getenv(
    "MODAL_LLAMA_CPP_IMAGE",
    "ghcr.io/ggml-org/llama.cpp:server-cuda-b9049",
)
SERVER_BIN = os.getenv("MODAL_LLAMA_CPP_SERVER_BIN", "/app/llama-server")
EXTRA_ARGS = shlex.split(os.getenv("MODAL_LLAMA_CPP_EXTRA_ARGS", ""))
PORT = 8000
MINUTES = 60


app = modal.App(APP_NAME)
hf_cache = modal.Volume.from_name("secret-student-hf-cache", create_if_missing=True)
llama_cache = modal.Volume.from_name(
    "secret-student-llamacpp-cache", create_if_missing=True
)
image = (
    modal.Image.from_registry(IMAGE, add_python="3.12")
    .entrypoint([])
    .env(
        {
            "HF_XET_HIGH_PERFORMANCE": "1",
            "LLAMA_CACHE": "/root/.cache/llama.cpp",
        }
    )
)


@app.function(
    image=image,
    gpu=GPU,
    timeout=15 * MINUTES,
    scaledown_window=15 * MINUTES,
    secrets=[modal.Secret.from_name(SECRET_NAME)],
    volumes={
        "/root/.cache/huggingface": hf_cache,
        "/root/.cache/llama.cpp": llama_cache,
    },
)
@modal.concurrent(max_inputs=12)
@modal.web_server(port=PORT, startup_timeout=15 * MINUTES)
def serve() -> None:
    api_key = (
        os.getenv("LLAMA_ARG_API_KEY", "").strip()
        or os.getenv("LLM_API_KEY", "").strip()
    )
    if not api_key:
        raise RuntimeError(
            f"Modal secret {SECRET_NAME!r} must contain LLAMA_ARG_API_KEY or LLM_API_KEY."
        )

    server_bin = resolve_llama_server_bin()
    command = [
        server_bin,
        "--host",
        "0.0.0.0",
        "--port",
        str(PORT),
        "-hf",
        MODEL_REF,
        "--ctx-size",
        CTX_SIZE,
        "--n-gpu-layers",
        GPU_LAYERS,
        "--threads",
        THREADS,
        "--parallel",
        PARALLEL,
        "--api-key",
        api_key,
        *EXTRA_ARGS,
    ]
    print(
        "Starting llama.cpp:",
        " ".join("<redacted>" if value == api_key else value for value in command),
    )
    subprocess.Popen(command)


def resolve_llama_server_bin() -> str:
    candidates = [
        SERVER_BIN,
        shutil.which("llama-server") or "",
        "/app/llama-server",
        "/usr/local/bin/llama-server",
    ]
    for candidate in candidates:
        if candidate and os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate
    raise FileNotFoundError(f"Could not find llama-server. Tried: {candidates}")


@app.local_entrypoint()
async def main() -> None:
    url = await serve.get_web_url.aio()
    print(f"LLM_BASE_URL={url}")
    print(f"LLM_MODEL={MODEL_REF}")
    print(f"Modal GPU={GPU}; llama.cpp image={IMAGE}")
