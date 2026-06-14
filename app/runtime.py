from __future__ import annotations

import logging
import os
import shlex
import signal
import subprocess
import sys
import time
from urllib.error import URLError
from urllib.request import Request, urlopen

import uvicorn

from app.config import Settings, get_settings


logger = logging.getLogger(__name__)


def build_llama_cpp_command(settings: Settings) -> list[str]:
    command = [
        settings.llama_cpp_server_bin,
        "--host",
        settings.llama_cpp_host,
        "--port",
        str(settings.llama_cpp_port),
        "-hf",
        settings.llama_cpp_model_ref,
        "--ctx-size",
        str(settings.llama_cpp_ctx_size),
        "--n-gpu-layers",
        str(settings.llama_cpp_gpu_layers),
        "--threads",
        str(settings.llama_cpp_threads),
        "--parallel",
        str(settings.llama_cpp_parallel),
    ]
    if settings.llama_cpp_api_key:
        command.extend(["--api-key", settings.llama_cpp_api_key])
    if settings.llama_cpp_extra_args:
        command.extend(shlex.split(settings.llama_cpp_extra_args))
    return command


def wait_for_llama_cpp(settings: Settings, process: subprocess.Popen) -> None:
    deadline = time.monotonic() + settings.llama_cpp_startup_timeout
    health_url = f"{settings.llm_base_url}/health"
    headers = {}
    if settings.llama_cpp_api_key:
        headers["Authorization"] = f"Bearer {settings.llama_cpp_api_key}"

    while time.monotonic() < deadline:
        return_code = process.poll()
        if return_code is not None:
            raise RuntimeError(f"llama-server exited during startup with code {return_code}.")
        try:
            with urlopen(Request(health_url, headers=headers), timeout=5) as response:
                if response.status < 500:
                    logger.info("Embedded llama.cpp is ready at %s", settings.llm_base_url)
                    return
        except (OSError, URLError):
            time.sleep(2)
    raise TimeoutError(
        f"llama-server did not become ready within {settings.llama_cpp_startup_timeout}s."
    )


def start_embedded_llama_cpp(settings: Settings) -> subprocess.Popen:
    command = build_llama_cpp_command(settings)
    printable = [
        "<redacted>" if part == settings.llama_cpp_api_key else part
        for part in command
    ]
    logger.info("Starting embedded llama.cpp: %s", " ".join(printable))
    process = subprocess.Popen(command, start_new_session=True)
    wait_for_llama_cpp(settings, process)
    return process


def stop_process(process: subprocess.Popen | None) -> None:
    if process is None or process.poll() is not None:
        return
    try:
        os.killpg(process.pid, signal.SIGTERM)
        process.wait(timeout=15)
    except (ProcessLookupError, subprocess.TimeoutExpired):
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass


def main() -> None:
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    settings = get_settings()
    if settings.llm_runtime not in {"mock", "external", "embedded_llamacpp"}:
        raise ValueError(
            "LLM_RUNTIME must be mock, external, or embedded_llamacpp; "
            f"received {settings.llm_runtime!r}."
        )
    if settings.llm_runtime == "external" and not settings.llm_base_url:
        raise ValueError("LLM_BASE_URL is required when LLM_RUNTIME=external.")

    model_process: subprocess.Popen | None = None
    try:
        if settings.llm_runtime == "embedded_llamacpp":
            model_process = start_embedded_llama_cpp(settings)
        uvicorn.run(
            "main:app",
            host=os.getenv("HOST", "0.0.0.0"),
            port=int(os.getenv("PORT", "7860")),
            log_level=os.getenv("LOG_LEVEL", "info").lower(),
        )
    finally:
        stop_process(model_process)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
