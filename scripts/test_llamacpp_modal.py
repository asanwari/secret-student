from __future__ import annotations

import argparse
import base64
import os
from pathlib import Path
import sys
import time

import httpx

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.config import load_env

__test__ = False

try:
    from scripts.llamacpp_modal_config import ModelConfig, load_deployment_config
except ModuleNotFoundError:
    from llamacpp_modal_config import ModelConfig, load_deployment_config


# A 1x1 white PNG is enough to verify that the vision request path accepts
# OpenAI-compatible image content without requiring a fixture file.
TEST_IMAGE_DATA_URL = "data:image/png;base64," + base64.b64encode(
    base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Wl2nWQAAAAASUVORK5CYII="
    )
).decode("ascii")


def parse_args() -> argparse.Namespace:
    load_env()
    parser = argparse.ArgumentParser(
        description="Smoke-test every model route in a YAML Modal deployment."
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path(os.getenv("MODAL_LLAMA_CPP_CONFIG", "config/modal-models.yaml")),
    )
    parser.add_argument(
        "--base-url",
        default=os.getenv("MODAL_LLAMA_CPP_BASE_URL", ""),
        help="Deployment root URL, without a model route.",
    )
    parser.add_argument(
        "--api-key",
        default=(
            os.getenv("LLM_API_KEY", "")
            or os.getenv("LLAMA_ARG_API_KEY", "")
        ),
    )
    parser.add_argument("--timeout", type=float, default=900.0)
    parser.add_argument("--max-tokens", type=int, default=64)
    return parser.parse_args()


def build_chat_payload(model: ModelConfig, max_tokens: int) -> dict:
    if model.role == "vision":
        content: str | list[dict] = [
            {
                "type": "text",
                "text": "Describe this test image in one short sentence.",
            },
            {"type": "image_url", "image_url": {"url": TEST_IMAGE_DATA_URL}},
        ]
    else:
        content = "Reply with exactly: model route is working"
    return {
        "model": model.model_ref,
        "messages": [{"role": "user", "content": content}],
        "temperature": 0,
        "max_tokens": max_tokens,
    }


def response_text(payload: dict) -> str:
    try:
        return str(payload["choices"][0]["message"]["content"]).strip()
    except (KeyError, IndexError, TypeError) as exc:
        raise ValueError("Response does not contain choices[0].message.content") from exc


def test_model(
    client: httpx.Client,
    base_url: str,
    model: ModelConfig,
    max_tokens: int,
) -> str:
    route_url = f"{base_url}/{model.route}"
    health = client.get(f"{route_url}/health")
    health.raise_for_status()
    response = client.post(
        f"{route_url}/v1/chat/completions",
        json=build_chat_payload(model, max_tokens),
    )
    response.raise_for_status()
    return response_text(response.json())


def main() -> int:
    args = parse_args()
    if not args.base_url.strip():
        raise SystemExit(
            "--base-url or MODAL_LLAMA_CPP_BASE_URL is required. "
            "Use the deployment root URL, without /text or another model route."
        )
    if not args.api_key.strip():
        raise SystemExit(
            "--api-key, LLM_API_KEY, or LLAMA_ARG_API_KEY is required."
        )
    if args.timeout <= 0:
        raise SystemExit("--timeout must be positive.")
    if args.max_tokens <= 0:
        raise SystemExit("--max-tokens must be positive.")

    deployment = load_deployment_config(args.config)
    base_url = args.base_url.rstrip("/")
    headers = {"Authorization": f"Bearer {args.api_key}"}
    failures = 0
    started = time.monotonic()
    print(f"Testing {len(deployment.models)} model route(s) at {base_url}")

    with httpx.Client(headers=headers, timeout=args.timeout) as client:
        try:
            health = client.get(f"{base_url}/health")
            health.raise_for_status()
            print("PASS aggregate health")
        except Exception as exc:
            failures += 1
            print(f"FAIL aggregate health: {exc}", file=sys.stderr)

        for model in deployment.models:
            label = f"{model.route} ({model.model_ref})"
            try:
                answer = test_model(
                    client, base_url, model, max_tokens=args.max_tokens
                )
                print(f"PASS {label}: {answer}")
            except Exception as exc:
                failures += 1
                print(f"FAIL {label}: {exc}", file=sys.stderr)

    elapsed = time.monotonic() - started
    if failures:
        print(f"Smoke test failed: {failures} check(s) failed in {elapsed:.1f}s")
        return 1
    print(f"All model routes passed in {elapsed:.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
