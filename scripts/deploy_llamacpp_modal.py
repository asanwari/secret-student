from __future__ import annotations

from contextlib import asynccontextmanager
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import time
from urllib.error import URLError
from urllib.request import Request as UrlRequest
from urllib.request import urlopen

import modal
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
import httpx
from starlette.background import BackgroundTask

try:
    from scripts.llamacpp_modal_config import (
        DeploymentConfig,
        ModalAppConfig,
        ModelConfig,
        load_deployment_config,
    )
except ModuleNotFoundError:
    from llamacpp_modal_config import (  # type: ignore[no-redef]
        DeploymentConfig,
        ModalAppConfig,
        ModelConfig,
        load_deployment_config,
    )


MINUTES = 60
DEFAULT_CONFIG_PATH = Path("config/modal-models.yaml")
SERVER_BIN = os.getenv("MODAL_LLAMA_CPP_SERVER_BIN", "/app/llama-server")


def deployment_from_environment() -> DeploymentConfig:
    configured_path = os.getenv("MODAL_LLAMA_CPP_CONFIG", "").strip()
    if configured_path:
        return load_deployment_config(configured_path)
    if DEFAULT_CONFIG_PATH.is_file():
        return load_deployment_config(DEFAULT_CONFIG_PATH)

    app_config = ModalAppConfig(
        name=os.getenv("MODAL_LLAMA_CPP_APP_NAME", ModalAppConfig.name),
        gpu=os.getenv("MODAL_LLAMA_CPP_GPU", ModalAppConfig.gpu),
        image=os.getenv("MODAL_LLAMA_CPP_IMAGE", ModalAppConfig.image),
        secret_name=os.getenv(
            "MODAL_LLAMA_CPP_SECRET_NAME", ModalAppConfig.secret_name
        ),
        timeout_minutes=int(
            os.getenv("MODAL_LLAMA_CPP_TIMEOUT_MINUTES", "15")
        ),
        scaledown_minutes=int(
            os.getenv("MODAL_LLAMA_CPP_SCALEDOWN_MINUTES", "15")
        ),
        startup_timeout_seconds=int(
            os.getenv("MODAL_LLAMA_CPP_STARTUP_TIMEOUT", "900")
        ),
        max_concurrent_inputs=int(
            os.getenv("MODAL_LLAMA_CPP_MAX_CONCURRENT_INPUTS", "12")
        ),
    )
    model = ModelConfig(
        route="",
        role="text",
        model_ref=os.getenv(
            "MODAL_LLAMA_CPP_MODEL_REF", "openbmb/MiniCPM-V-4_5-gguf:Q4_K_M"
        ),
        port=8001,
        ctx_size=int(os.getenv("MODAL_LLAMA_CPP_CTX_SIZE", "8192")),
        gpu_layers=int(os.getenv("MODAL_LLAMA_CPP_GPU_LAYERS", "999")),
        threads=int(os.getenv("MODAL_LLAMA_CPP_THREADS", "8")),
        parallel=int(os.getenv("MODAL_LLAMA_CPP_PARALLEL", "2")),
        extra_args=tuple(
            shlex.split(os.getenv("MODAL_LLAMA_CPP_EXTRA_ARGS", ""))
        ),
    )
    return DeploymentConfig(
        app=app_config,
        models=(model,),
        source="legacy environment variables",
        legacy=True,
    )


DEPLOYMENT = deployment_from_environment()
APP_CONFIG = DEPLOYMENT.app
RUNTIME_CONFIG_PATH = "/root/config/modal-models.yaml"

app = modal.App(APP_CONFIG.name)
hf_cache = modal.Volume.from_name("secret-student-hf-cache", create_if_missing=True)
llama_cache = modal.Volume.from_name(
    "secret-student-llamacpp-cache", create_if_missing=True
)
image = (
    modal.Image.from_registry(APP_CONFIG.image, add_python="3.12")
    .entrypoint([])
    .pip_install(
        "fastapi>=0.136.3",
        "httpx>=0.28.1",
        "uvicorn[standard]>=0.49.0",
    )
    .add_local_python_source("scripts.llamacpp_modal_config", copy=True)
    .env(
        {
            "HF_XET_HIGH_PERFORMANCE": "1",
            "LLAMA_CACHE": "/root/.cache/llama.cpp",
        }
    )
)
if not DEPLOYMENT.legacy:
    image = image.add_local_file(
        DEPLOYMENT.source,
        RUNTIME_CONFIG_PATH,
        copy=True,
    ).env({"MODAL_LLAMA_CPP_CONFIG": RUNTIME_CONFIG_PATH})


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


def build_server_command(
    model: ModelConfig, server_bin: str, api_key: str
) -> list[str]:
    return [
        server_bin,
        "--host",
        "127.0.0.1",
        "--port",
        str(model.port),
        "-hf",
        model.model_ref,
        "--ctx-size",
        str(model.ctx_size),
        "--n-gpu-layers",
        str(model.gpu_layers),
        "--threads",
        str(model.threads),
        "--parallel",
        str(model.parallel),
        "--api-key",
        api_key,
        *model.extra_args,
    ]


def start_model_servers(api_key: str) -> dict[str, subprocess.Popen]:
    server_bin = resolve_llama_server_bin()
    processes: dict[str, subprocess.Popen] = {}
    try:
        for model in DEPLOYMENT.models:
            command = build_server_command(model, server_bin, api_key)
            label = model.route or "root"
            printable = ["<redacted>" if value == api_key else value for value in command]
            print(f"Starting llama.cpp model {label}: {' '.join(printable)}")
            processes[model.route] = subprocess.Popen(
                command, start_new_session=True
            )
        wait_for_model_servers(processes, api_key)
        return processes
    except BaseException:
        stop_model_servers(processes)
        raise


def wait_for_model_servers(
    processes: dict[str, subprocess.Popen], api_key: str
) -> None:
    pending = {model.route: model for model in DEPLOYMENT.models}
    deadline = time.monotonic() + APP_CONFIG.startup_timeout_seconds
    headers = {"Authorization": f"Bearer {api_key}"}
    while pending and time.monotonic() < deadline:
        for route, model in tuple(pending.items()):
            process = processes[route]
            return_code = process.poll()
            if return_code is not None:
                raise RuntimeError(
                    f"llama-server for {route or 'root'} exited during startup "
                    f"with code {return_code}."
                )
            try:
                health_url = f"http://127.0.0.1:{model.port}/health"
                with urlopen(UrlRequest(health_url, headers=headers), timeout=2) as response:
                    if response.status < 500:
                        print(f"llama.cpp model {route or 'root'} is ready on port {model.port}")
                        pending.pop(route)
            except (OSError, URLError):
                pass
        if pending:
            time.sleep(2)
    if pending:
        routes = ", ".join(route or "root" for route in pending)
        raise TimeoutError(
            f"llama-server models did not become ready within "
            f"{APP_CONFIG.startup_timeout_seconds}s: {routes}"
        )


def stop_model_servers(processes: dict[str, subprocess.Popen]) -> None:
    for process in processes.values():
        if process.poll() is None:
            process.terminate()
    deadline = time.monotonic() + 15
    for process in processes.values():
        if process.poll() is not None:
            continue
        try:
            process.wait(timeout=max(0.1, deadline - time.monotonic()))
        except subprocess.TimeoutExpired:
            process.kill()


def create_proxy_app(api_key: str):
    processes: dict[str, subprocess.Popen] = {}
    client: httpx.AsyncClient | None = None
    models_by_route = {model.route: model for model in DEPLOYMENT.models}

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        nonlocal processes, client
        processes = start_model_servers(api_key)
        client = httpx.AsyncClient(timeout=None)
        try:
            yield
        finally:
            if client is not None:
                await client.aclose()
            stop_model_servers(processes)

    proxy = FastAPI(title="Secret Student llama.cpp router", lifespan=lifespan)

    @proxy.get("/health")
    async def aggregate_health():
        statuses = {
            (route or "root"): {
                "model_ref": models_by_route[route].model_ref,
                "port": models_by_route[route].port,
                "running": process.poll() is None,
                "return_code": process.poll(),
            }
            for route, process in processes.items()
        }
        ready = len(statuses) == len(models_by_route) and all(
            status["running"] for status in statuses.values()
        )
        return JSONResponse(
            status_code=200 if ready else 503,
            content={"ready": ready, "models": statuses},
        )

    async def forward(request: Request, route: str, path: str):
        if client is None:
            raise HTTPException(status_code=503, detail="Model router is starting.")
        model = models_by_route.get(route)
        if model is None:
            raise HTTPException(status_code=404, detail=f"Unknown model route: {route}")
        process = processes.get(route)
        if process is None or process.poll() is not None:
            raise HTTPException(
                status_code=503, detail=f"Model route {route or 'root'} is unavailable."
            )

        target = f"http://127.0.0.1:{model.port}/{path}"
        if request.url.query:
            target = f"{target}?{request.url.query}"
        excluded_request_headers = {"host", "content-length", "connection"}
        headers = {
            key: value
            for key, value in request.headers.items()
            if key.lower() not in excluded_request_headers
        }
        upstream_request = client.build_request(
            request.method,
            target,
            headers=headers,
            content=await request.body(),
        )
        upstream = await client.send(upstream_request, stream=True)
        excluded_response_headers = {
            "content-length",
            "connection",
            "keep-alive",
            "proxy-authenticate",
            "proxy-authorization",
            "te",
            "trailers",
            "transfer-encoding",
            "upgrade",
        }
        response_headers = {
            key: value
            for key, value in upstream.headers.items()
            if key.lower() not in excluded_response_headers
        }
        return StreamingResponse(
            upstream.aiter_raw(),
            status_code=upstream.status_code,
            headers=response_headers,
            background=BackgroundTask(upstream.aclose),
        )

    if DEPLOYMENT.legacy:

        @proxy.api_route(
            "/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]
        )
        async def forward_legacy(request: Request, path: str):
            return await forward(request, "", path)

    else:

        @proxy.api_route(
            "/{route}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]
        )
        async def forward_route_root(request: Request, route: str):
            return await forward(request, route, "")

        @proxy.api_route(
            "/{route}/{path:path}",
            methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        )
        async def forward_route(request: Request, route: str, path: str):
            return await forward(request, route, path)

    return proxy


@app.function(
    image=image,
    gpu=APP_CONFIG.gpu,
    timeout=APP_CONFIG.timeout_minutes * MINUTES,
    scaledown_window=APP_CONFIG.scaledown_minutes * MINUTES,
    secrets=[modal.Secret.from_name(APP_CONFIG.secret_name)],
    volumes={
        "/root/.cache/huggingface": hf_cache,
        "/root/.cache/llama.cpp": llama_cache,
    },
)
@modal.concurrent(max_inputs=APP_CONFIG.max_concurrent_inputs)
@modal.asgi_app()
def serve():
    api_key = (
        os.getenv("LLAMA_ARG_API_KEY", "").strip()
        or os.getenv("LLM_API_KEY", "").strip()
    )
    if not api_key:
        raise RuntimeError(
            f"Modal secret {APP_CONFIG.secret_name!r} must contain "
            "LLAMA_ARG_API_KEY or LLM_API_KEY."
        )
    return create_proxy_app(api_key)


@app.local_entrypoint()
async def main() -> None:
    url = (await serve.get_web_url.aio()).rstrip("/")
    print(f"Modal config={DEPLOYMENT.source}")
    for model in DEPLOYMENT.models:
        base_url = url if DEPLOYMENT.legacy else f"{url}/{model.route}"
        if model.role == "text":
            print(f"LLM_BASE_URL={base_url}")
            print(f"LLM_MODEL={model.model_ref}")
        elif model.role == "vision":
            print(f"VISION_LLM_BASE_URL={base_url}")
            print(f"VISION_LLM_MODEL={model.model_ref}")
        else:
            variable = f"{model.route.upper().replace('-', '_')}_BASE_URL"
            print(f"{variable}={base_url}")
        print(f"MODEL_ROUTE {model.route or '/'} -> {model.model_ref}")
    print(f"Modal GPU={APP_CONFIG.gpu}; llama.cpp image={APP_CONFIG.image}")
