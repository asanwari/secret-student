from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[1]
ENV_PATH = BASE_DIR / ".env"


def load_env(path: Path = ENV_PATH) -> None:
    if not path.exists():
        return

    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _read_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def _read_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    app_secret: str = "secret-student-dev-secret"
    database_url: str = "sqlite:///./data/secret_student.sqlite3"
    llm_runtime: str = "mock"
    llm_provider: str = "mock"
    llm_base_url: str = ""
    llm_api_key: str = ""
    llm_model: str = "openbmb/MiniCPM-V-4.6"
    llm_enable_thinking: bool = False
    llama_cpp_server_bin: str = "/app/llama-server"
    llama_cpp_model_ref: str = "ggml-org/gemma-3-1b-it-GGUF:Q4_K_M"
    llama_cpp_host: str = "127.0.0.1"
    llama_cpp_port: int = 8001
    llama_cpp_api_key: str = "local-dev-key"
    llama_cpp_ctx_size: int = 8192
    llama_cpp_gpu_layers: int = 999
    llama_cpp_threads: int = 8
    llama_cpp_parallel: int = 1
    llama_cpp_startup_timeout: int = 900
    llama_cpp_extra_args: str = ""
    trace_destination: str = "local"
    trace_dir: str = "debug_traces"
    trace_hub_repo_id: str = ""
    trace_hub_token: str = ""
    trace_hub_private: bool = True
    trace_hub_include_content: bool = False
    quiz_question_count: int = 5
    boss_question_count: int = 10
    boss_max_mistakes: int = 3
    cors_origins: tuple[str, ...] = (
        "http://127.0.0.1:7860",
        "http://localhost:7860",
        "http://127.0.0.1:8000",
        "http://localhost:8000",
    )


def get_settings() -> Settings:
    load_env()
    llm_runtime = os.getenv("LLM_RUNTIME", "").strip().lower()
    legacy_provider = os.getenv("LLM_PROVIDER", Settings.llm_provider).strip().lower()
    if not llm_runtime:
        llm_runtime = "mock" if legacy_provider == "mock" else "external"

    llama_cpp_host = os.getenv("LLAMA_CPP_HOST", Settings.llama_cpp_host).strip()
    llama_cpp_port = _read_int("LLAMA_CPP_PORT", Settings.llama_cpp_port)
    llama_cpp_api_key = os.getenv(
        "LLAMA_CPP_API_KEY", Settings.llama_cpp_api_key
    ).strip()
    if llm_runtime == "mock":
        llm_provider = "mock"
        llm_base_url = ""
    elif llm_runtime == "embedded_llamacpp":
        llm_provider = "openai_compatible"
        llm_base_url = f"http://{llama_cpp_host}:{llama_cpp_port}"
    else:
        llm_provider = "openai_compatible"
        llm_base_url = os.getenv("LLM_BASE_URL", "").strip().rstrip("/")

    cors_value = os.getenv("CORS_ORIGINS", "")
    cors_origins = tuple(
        origin.strip() for origin in cors_value.split(",") if origin.strip()
    ) or Settings.cors_origins

    return Settings(
        app_secret=os.getenv("APP_SECRET", Settings.app_secret),
        database_url=os.getenv("DATABASE_URL", Settings.database_url),
        llm_runtime=llm_runtime,
        llm_provider=llm_provider,
        llm_base_url=llm_base_url,
        llm_api_key=(
            llama_cpp_api_key
            if llm_runtime == "embedded_llamacpp"
            else os.getenv("LLM_API_KEY", "").strip()
        ),
        llm_model=os.getenv(
            "LLM_MODEL",
            os.getenv("LLAMA_CPP_MODEL_REF", Settings.llm_model),
        ).strip(),
        llm_enable_thinking=_read_bool("LLM_ENABLE_THINKING", False),
        llama_cpp_server_bin=os.getenv(
            "LLAMA_CPP_SERVER_BIN", Settings.llama_cpp_server_bin
        ).strip(),
        llama_cpp_model_ref=os.getenv(
            "LLAMA_CPP_MODEL_REF", Settings.llama_cpp_model_ref
        ).strip(),
        llama_cpp_host=llama_cpp_host,
        llama_cpp_port=llama_cpp_port,
        llama_cpp_api_key=llama_cpp_api_key,
        llama_cpp_ctx_size=_read_int("LLAMA_CPP_CTX_SIZE", Settings.llama_cpp_ctx_size),
        llama_cpp_gpu_layers=_read_int(
            "LLAMA_CPP_GPU_LAYERS", Settings.llama_cpp_gpu_layers
        ),
        llama_cpp_threads=_read_int("LLAMA_CPP_THREADS", Settings.llama_cpp_threads),
        llama_cpp_parallel=_read_int("LLAMA_CPP_PARALLEL", Settings.llama_cpp_parallel),
        llama_cpp_startup_timeout=_read_int(
            "LLAMA_CPP_STARTUP_TIMEOUT", Settings.llama_cpp_startup_timeout
        ),
        llama_cpp_extra_args=os.getenv("LLAMA_CPP_EXTRA_ARGS", "").strip(),
        trace_destination=os.getenv("TRACE_DESTINATION", Settings.trace_destination)
        .strip()
        .lower(),
        trace_dir=os.getenv("TRACE_DIR", Settings.trace_dir).strip(),
        trace_hub_repo_id=os.getenv("TRACE_HUB_REPO_ID", "").strip(),
        trace_hub_token=os.getenv("TRACE_HUB_TOKEN", "").strip(),
        trace_hub_private=_read_bool("TRACE_HUB_PRIVATE", True),
        trace_hub_include_content=_read_bool("TRACE_HUB_INCLUDE_CONTENT", False),
        quiz_question_count=_read_int("QUIZ_QUESTION_COUNT", Settings.quiz_question_count),
        boss_question_count=_read_int("BOSS_QUESTION_COUNT", Settings.boss_question_count),
        boss_max_mistakes=_read_int("BOSS_MAX_MISTAKES", Settings.boss_max_mistakes),
        cors_origins=cors_origins,
    )
