from __future__ import annotations

import argparse
import os
from pathlib import Path

from scripts.llamacpp_modal_config import load_deployment_config


DEFAULT_ENV_PATH = Path(".env")
DEFAULT_MODAL_CONFIG = Path("config/modal-models.yaml")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Configure local Secret Student inference from a Modal YAML deployment."
    )
    parser.add_argument("--env-file", type=Path, default=DEFAULT_ENV_PATH)
    parser.add_argument("--modal-config", type=Path, default=DEFAULT_MODAL_CONFIG)
    parser.add_argument(
        "--shared-inference-url",
        required=True,
        help="Public Modal deployment root URL, without /text or /vision.",
    )
    parser.add_argument(
        "--api-key",
        default="",
        help="Override the existing LLM_API_KEY from the env file.",
    )
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def read_env_values(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def build_modal_env(
    modal_config: Path,
    shared_inference_url: str,
    api_key: str,
) -> dict[str, str]:
    deployment = load_deployment_config(modal_config)
    roles = {model.role: model for model in deployment.models if model.role}
    text_model = roles.get("text")
    if text_model is None:
        raise SystemExit("Modal config must contain one model with role: text.")
    vision_model = roles.get("vision", text_model)
    base_url = shared_inference_url.strip().rstrip("/")
    if not base_url:
        raise SystemExit("--shared-inference-url must not be empty.")
    if not api_key.strip():
        raise SystemExit(
            "No API key found. Set LLM_API_KEY in .env or pass --api-key."
        )

    return {
        "LLM_RUNTIME": "external",
        "LLM_PROVIDER": "openai_compatible",
        "LLM_BASE_URL": f"{base_url}/{text_model.route}",
        "LLM_API_KEY": api_key.strip(),
        "LLM_MODEL": text_model.model_ref,
        "VISION_LLM_BASE_URL": f"{base_url}/{vision_model.route}",
        "VISION_LLM_API_KEY": api_key.strip(),
        "VISION_LLM_MODEL": vision_model.model_ref,
    }


def update_env_text(existing_text: str, updates: dict[str, str]) -> str:
    remaining = dict(updates)
    output: list[str] = []
    for raw_line in existing_text.splitlines():
        stripped = raw_line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            key = stripped.split("=", 1)[0].strip()
            if key in remaining:
                output.append(f"{key}={remaining.pop(key)}")
                continue
        output.append(raw_line)

    if remaining:
        if output and output[-1]:
            output.append("")
        output.append("# Modal external inference")
        output.extend(f"{key}={value}" for key, value in remaining.items())
    return "\n".join(output).rstrip() + "\n"


def main() -> None:
    args = parse_args()
    existing_values = read_env_values(args.env_file)
    api_key = (
        args.api_key.strip()
        or existing_values.get("LLM_API_KEY", "").strip()
        or os.getenv("LLM_API_KEY", "").strip()
    )
    updates = build_modal_env(
        args.modal_config,
        args.shared_inference_url,
        api_key,
    )

    if args.dry_run:
        for key, value in updates.items():
            printable = "<redacted>" if key.endswith("API_KEY") else value
            print(f"{key}={printable}")
        return

    existing_text = args.env_file.read_text() if args.env_file.exists() else ""
    args.env_file.write_text(update_env_text(existing_text, updates))
    print(f"Updated {args.env_file} for external Modal inference.")
    print(f"LLM_BASE_URL={updates['LLM_BASE_URL']}")
    print(f"VISION_LLM_BASE_URL={updates['VISION_LLM_BASE_URL']}")


if __name__ == "__main__":
    main()
