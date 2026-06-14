from __future__ import annotations

import pytest

from app.config import Settings, get_settings
from app.runtime import build_llama_cpp_command


@pytest.fixture(autouse=True)
def isolate_runtime_environment(monkeypatch):
    monkeypatch.setattr("app.config.load_env", lambda: None)
    for name in (
        "LLM_RUNTIME",
        "LLM_PROVIDER",
        "LLM_BASE_URL",
        "LLM_API_KEY",
        "LLM_MODEL",
        "LLAMA_CPP_HOST",
        "LLAMA_CPP_PORT",
        "LLAMA_CPP_API_KEY",
        "LLAMA_CPP_MODEL_REF",
    ):
        monkeypatch.delenv(name, raising=False)


def test_external_runtime_uses_openai_compatible_endpoint(monkeypatch):
    monkeypatch.setenv("LLM_RUNTIME", "external")
    monkeypatch.setenv("LLM_BASE_URL", "https://example.modal.run/")
    monkeypatch.setenv("LLM_API_KEY", "modal-key")
    monkeypatch.setenv("LLM_MODEL", "example/model")

    settings = get_settings()

    assert settings.llm_runtime == "external"
    assert settings.llm_provider == "openai_compatible"
    assert settings.llm_base_url == "https://example.modal.run"
    assert settings.llm_api_key == "modal-key"


def test_embedded_runtime_points_client_at_local_llama_cpp(monkeypatch):
    monkeypatch.setenv("LLM_RUNTIME", "embedded_llamacpp")
    monkeypatch.setenv("LLAMA_CPP_HOST", "127.0.0.1")
    monkeypatch.setenv("LLAMA_CPP_PORT", "8123")
    monkeypatch.setenv("LLAMA_CPP_API_KEY", "internal-key")
    monkeypatch.setenv("LLAMA_CPP_MODEL_REF", "example/model:Q4_K_M")
    monkeypatch.delenv("LLM_MODEL", raising=False)

    settings = get_settings()

    assert settings.llm_provider == "openai_compatible"
    assert settings.llm_base_url == "http://127.0.0.1:8123"
    assert settings.llm_api_key == "internal-key"
    assert settings.llm_model == "example/model:Q4_K_M"


def test_embedded_llama_cpp_command_contains_runtime_settings():
    settings = Settings(
        llm_runtime="embedded_llamacpp",
        llm_base_url="http://127.0.0.1:8001",
        llama_cpp_server_bin="/app/llama-server",
        llama_cpp_model_ref="example/model:Q4_K_M",
        llama_cpp_host="127.0.0.1",
        llama_cpp_port=8001,
        llama_cpp_api_key="secret-key",
        llama_cpp_ctx_size=4096,
        llama_cpp_gpu_layers=999,
        llama_cpp_threads=6,
        llama_cpp_parallel=2,
        llama_cpp_extra_args="--flash-attn on --no-webui",
    )

    command = build_llama_cpp_command(settings)

    assert command[0] == "/app/llama-server"
    assert command[command.index("-hf") + 1] == "example/model:Q4_K_M"
    assert command[command.index("--ctx-size") + 1] == "4096"
    assert command[command.index("--api-key") + 1] == "secret-key"
    assert command[-3:] == ["--flash-attn", "on", "--no-webui"]


def test_legacy_provider_selects_external_runtime(monkeypatch):
    monkeypatch.delenv("LLM_RUNTIME", raising=False)
    monkeypatch.setenv("LLM_PROVIDER", "openai_compatible")
    monkeypatch.setenv("LLM_BASE_URL", "https://legacy.example")

    settings = get_settings()

    assert settings.llm_runtime == "external"
    assert settings.llm_base_url == "https://legacy.example"
