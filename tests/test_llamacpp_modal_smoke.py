from __future__ import annotations

from scripts.llamacpp_modal_config import ModelConfig
from scripts.test_llamacpp_modal import build_chat_payload, parse_args, response_text


def model(role: str = "") -> ModelConfig:
    return ModelConfig(
        route=role or "helper",
        role=role,
        model_ref=f"example/{role or 'helper'}",
        port=8001,
    )


def test_text_payload_uses_plain_content():
    payload = build_chat_payload(model("text"), 32)

    assert isinstance(payload["messages"][0]["content"], str)
    assert payload["max_tokens"] == 32


def test_vision_payload_contains_data_url_image():
    payload = build_chat_payload(model("vision"), 64)
    content = payload["messages"][0]["content"]

    assert content[1]["type"] == "image_url"
    assert content[1]["image_url"]["url"].startswith("data:image/png;base64,")


def test_response_text_reads_openai_compatible_content():
    payload = {"choices": [{"message": {"content": " working "}}]}

    assert response_text(payload) == "working"


def test_parse_args_loads_api_key_from_dotenv(monkeypatch, tmp_path):
    dotenv = tmp_path / ".env"
    dotenv.write_text("LLM_API_KEY=dotenv-key\n")
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("LLAMA_ARG_API_KEY", raising=False)
    monkeypatch.setattr(
        "scripts.test_llamacpp_modal.load_env",
        lambda: __import__("app.config", fromlist=["load_env"]).load_env(dotenv),
    )
    monkeypatch.setattr("sys.argv", ["test_llamacpp_modal.py"])

    args = parse_args()

    assert args.api_key == "dotenv-key"
