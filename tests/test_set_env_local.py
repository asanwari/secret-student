from __future__ import annotations

from pathlib import Path

from set_env_local import build_modal_env, read_env_values, update_env_text


CONFIG = Path("config/modal-models.example.yaml")


def test_build_modal_env_maps_yaml_roles():
    updates = build_modal_env(CONFIG, "https://example.modal.run/", "secret")

    assert updates["LLM_RUNTIME"] == "external"
    assert updates["LLM_BASE_URL"] == "https://example.modal.run/text"
    assert updates["VISION_LLM_BASE_URL"] == "https://example.modal.run/vision"
    assert updates["LLM_MODEL"] == "Qwen/Qwen3-8B-GGUF:Q4_K_M"
    assert updates["VISION_LLM_API_KEY"] == "secret"


def test_update_env_text_preserves_unrelated_lines():
    existing = "# local settings\nDATABASE_URL=sqlite:///local.sqlite3\nLLM_RUNTIME=mock\n"
    updates = {
        "LLM_RUNTIME": "external",
        "LLM_BASE_URL": "https://example.modal.run/text",
    }

    result = update_env_text(existing, updates)

    assert "# local settings" in result
    assert "DATABASE_URL=sqlite:///local.sqlite3" in result
    assert "LLM_RUNTIME=external" in result
    assert "LLM_BASE_URL=https://example.modal.run/text" in result


def test_read_env_values_handles_quotes(tmp_path):
    env_path = tmp_path / ".env"
    env_path.write_text("LLM_API_KEY='secret-key'\n")

    assert read_env_values(env_path)["LLM_API_KEY"] == "secret-key"
