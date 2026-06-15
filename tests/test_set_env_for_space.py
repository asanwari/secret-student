from __future__ import annotations

import sys

import pytest

from set_env_for_space import build_secrets, build_variables, parse_args


def parse_test_args(monkeypatch, *arguments):
    monkeypatch.setattr(sys, "argv", ["set_env_for_space.py", *arguments])
    return parse_args()


def test_modal_config_sets_external_role_routes(monkeypatch):
    args = parse_test_args(
        monkeypatch,
        "--runtime",
        "external",
        "--modal-config",
        "config/modal-models.example.yaml",
        "--shared-inference-url",
        "https://example.modal.run/",
        "--no-prompt",
    )

    variables = build_variables(args)

    assert variables["LLM_BASE_URL"] == "https://example.modal.run/text"
    assert variables["VISION_LLM_BASE_URL"] == "https://example.modal.run/vision"
    assert variables["LLM_MODEL"] == "Qwen/Qwen3-8B-GGUF:Q4_K_M"
    assert variables["VISION_LLM_MODEL"] == "openbmb/MiniCPM-V-4_5-gguf:Q4_K_M"


def test_modal_config_requires_shared_url(monkeypatch):
    args = parse_test_args(
        monkeypatch,
        "--runtime",
        "external",
        "--modal-config",
        "config/modal-models.example.yaml",
    )

    with pytest.raises(SystemExit, match="shared-inference-url"):
        build_variables(args)


def test_modal_config_reuses_external_api_key(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "shared-key")
    args = parse_test_args(
        monkeypatch,
        "--runtime",
        "external",
        "--modal-config",
        "config/modal-models.example.yaml",
        "--shared-inference-url",
        "https://example.modal.run",
        "--no-prompt",
    )

    secrets = build_secrets(args)

    assert secrets["LLM_API_KEY"] == "shared-key"
    assert secrets["VISION_LLM_API_KEY"] == "shared-key"
