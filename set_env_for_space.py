from __future__ import annotations

import argparse
from getpass import getpass
import os
import secrets

from huggingface_hub import HfApi


DEFAULT_SPACE = "asanwari/secret-student"
DEFAULT_TEXT_MODEL_REF = "Qwen/Qwen3-8B-GGUF:Q4_K_M"
DEFAULT_MINI_CPM_REF = "openbmb/MiniCPM-V-4_5-gguf:Q4_K_M"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Bulk configure Secret Student Space variables and secrets."
    )
    parser.add_argument("--space", default=DEFAULT_SPACE)
    parser.add_argument(
        "--runtime",
        choices=("mock", "external", "embedded_llamacpp", "embedded_dual_llamacpp"),
        default="embedded_dual_llamacpp",
    )
    parser.add_argument("--base-url", default=os.getenv("LLM_BASE_URL", ""))
    parser.add_argument(
        "--model",
        default=os.getenv("LLM_MODEL", DEFAULT_TEXT_MODEL_REF),
        help="Model name sent in OpenAI-compatible requests.",
    )
    parser.add_argument(
        "--llama-model-ref",
        default=os.getenv("LLAMA_CPP_MODEL_REF", DEFAULT_TEXT_MODEL_REF),
        help="GGUF repository and quantization downloaded by embedded llama.cpp.",
    )
    parser.add_argument(
        "--llama-model-path",
        default=os.getenv(
            "LLAMA_CPP_MODEL_PATH",
            "/data/models/qwen3-8b/Qwen3-8B-Q4_K_M.gguf",
        ),
    )
    parser.add_argument("--ctx-size", type=int, default=8192)
    parser.add_argument("--gpu-layers", type=int, default=999)
    parser.add_argument("--threads", type=int, default=8)
    parser.add_argument("--parallel", type=int, default=1)
    parser.add_argument("--startup-timeout", type=int, default=900)
    parser.add_argument("--extra-args", default="")
    parser.add_argument(
        "--vision-base-url", default=os.getenv("VISION_LLM_BASE_URL", "")
    )
    parser.add_argument(
        "--vision-model",
        default=os.getenv("VISION_LLM_MODEL", DEFAULT_MINI_CPM_REF),
    )
    parser.add_argument(
        "--vision-llama-model-ref",
        default=os.getenv("VISION_LLAMA_CPP_MODEL_REF", DEFAULT_MINI_CPM_REF),
    )
    parser.add_argument(
        "--vision-llama-model-path",
        default=os.getenv(
            "VISION_LLAMA_CPP_MODEL_PATH",
            "/data/models/minicpm-v-4_5/MiniCPM-V-4_5-Q4_K_M.gguf",
        ),
    )
    parser.add_argument(
        "--vision-mmproj-path",
        default=os.getenv(
            "VISION_LLAMA_CPP_MMPROJ_PATH",
            "/data/models/minicpm-v-4_5/mmproj-model-f16.gguf",
        ),
    )
    parser.add_argument("--vision-port", type=int, default=8002)
    parser.add_argument("--vision-ctx-size", type=int, default=4096)
    parser.add_argument("--vision-gpu-layers", type=int, default=999)
    parser.add_argument("--vision-extra-args", default="")
    parser.add_argument("--quiz-count", type=int, default=5)
    parser.add_argument("--boss-count", type=int, default=10)
    parser.add_argument("--boss-max-mistakes", type=int, default=3)
    parser.add_argument(
        "--database-url",
        default="sqlite:////data/secret_student.sqlite3",
        help="Uses Hugging Face persistent storage when it is attached at /data.",
    )
    parser.add_argument("--trace-destination", choices=("off", "local", "hub"), default="local")
    parser.add_argument("--trace-dir", default="/data/debug_traces")
    parser.add_argument("--trace-hub-repo-id", default="")
    parser.add_argument("--trace-hub-private", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--trace-hub-include-content", action="store_true")
    parser.add_argument("--enable-thinking", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--no-prompt",
        action="store_true",
        help="Read secrets only from environment variables and never prompt.",
    )
    return parser.parse_args()


def bool_text(value: bool) -> str:
    return "true" if value else "false"


def secret_value(name: str, prompt: str, *, generate: bool = False, no_prompt: bool = False) -> str:
    value = os.getenv(name, "").strip()
    if value or no_prompt:
        return value
    if generate:
        entered = getpass(f"{prompt} (leave blank to generate): ").strip()
        return entered or secrets.token_urlsafe(48)
    return getpass(f"{prompt} (leave blank to skip): ").strip()


def build_variables(args: argparse.Namespace) -> dict[str, str]:
    variables = {
        "DATABASE_URL": args.database_url,
        "LLM_RUNTIME": args.runtime,
        "LLM_PROVIDER": "mock" if args.runtime == "mock" else "openai_compatible",
        "LLM_MODEL": args.model,
        "VISION_LLM_MODEL": args.vision_model,
        "LLM_ENABLE_THINKING": bool_text(args.enable_thinking),
        "TRACE_DESTINATION": args.trace_destination,
        "TRACE_DIR": args.trace_dir,
        "TRACE_HUB_REPO_ID": args.trace_hub_repo_id,
        "TRACE_HUB_PRIVATE": bool_text(args.trace_hub_private),
        "TRACE_HUB_INCLUDE_CONTENT": bool_text(args.trace_hub_include_content),
        "QUIZ_QUESTION_COUNT": str(args.quiz_count),
        "BOSS_QUESTION_COUNT": str(args.boss_count),
        "BOSS_MAX_MISTAKES": str(args.boss_max_mistakes),
    }

    if args.runtime == "external":
        if not args.base_url:
            raise SystemExit("--base-url or LLM_BASE_URL is required for external runtime.")
        variables["LLM_BASE_URL"] = args.base_url.rstrip("/")
        variables["VISION_LLM_BASE_URL"] = (
            args.vision_base_url or args.base_url
        ).rstrip("/")

    if args.runtime in {"embedded_llamacpp", "embedded_dual_llamacpp"}:
        variables.update(
            {
                "LLAMA_CPP_SERVER_BIN": "/app/llama-server",
                "LLAMA_CPP_MODEL_REF": args.llama_model_ref,
                "LLAMA_CPP_MODEL_PATH": args.llama_model_path,
                "LLAMA_CPP_HOST": "127.0.0.1",
                "LLAMA_CPP_PORT": "8001",
                "LLAMA_CPP_CTX_SIZE": str(args.ctx_size),
                "LLAMA_CPP_GPU_LAYERS": str(args.gpu_layers),
                "LLAMA_CPP_THREADS": str(args.threads),
                "LLAMA_CPP_PARALLEL": str(args.parallel),
                "LLAMA_CPP_STARTUP_TIMEOUT": str(args.startup_timeout),
                "LLAMA_CPP_EXTRA_ARGS": args.extra_args,
            }
        )
    if args.runtime == "embedded_dual_llamacpp":
        variables.update(
            {
                "VISION_LLAMA_CPP_MODEL_REF": args.vision_llama_model_ref,
                "VISION_LLAMA_CPP_MODEL_PATH": args.vision_llama_model_path,
                "VISION_LLAMA_CPP_MMPROJ_PATH": args.vision_mmproj_path,
                "VISION_LLAMA_CPP_PORT": str(args.vision_port),
                "VISION_LLAMA_CPP_CTX_SIZE": str(args.vision_ctx_size),
                "VISION_LLAMA_CPP_GPU_LAYERS": str(args.vision_gpu_layers),
                "VISION_LLAMA_CPP_EXTRA_ARGS": args.vision_extra_args,
            }
        )
    return variables


def build_secrets(args: argparse.Namespace) -> dict[str, str]:
    configured = {
        "APP_SECRET": secret_value(
            "APP_SECRET",
            "APP_SECRET",
            generate=True,
            no_prompt=args.no_prompt,
        )
    }
    if args.runtime == "external":
        configured["LLM_API_KEY"] = secret_value(
            "LLM_API_KEY", "External LLM API key", no_prompt=args.no_prompt
        )
        configured["VISION_LLM_API_KEY"] = secret_value(
            "VISION_LLM_API_KEY",
            "Vision LLM API key (leave blank to reuse LLM_API_KEY)",
            no_prompt=args.no_prompt,
        )
    if args.runtime in {"embedded_llamacpp", "embedded_dual_llamacpp"}:
        configured["LLAMA_CPP_API_KEY"] = secret_value(
            "LLAMA_CPP_API_KEY",
            "Internal llama.cpp API key",
            generate=True,
            no_prompt=args.no_prompt,
        )
        configured["HF_TOKEN"] = secret_value(
            "HF_TOKEN", "Hugging Face token for model downloads", no_prompt=args.no_prompt
        )
    if args.runtime == "embedded_dual_llamacpp":
        configured["VISION_LLAMA_CPP_API_KEY"] = secret_value(
            "VISION_LLAMA_CPP_API_KEY",
            "Internal vision llama.cpp API key (leave blank to reuse LLAMA_CPP_API_KEY)",
            no_prompt=args.no_prompt,
        )
    if args.trace_destination == "hub":
        configured["TRACE_HUB_TOKEN"] = secret_value(
            "TRACE_HUB_TOKEN", "Trace dataset write token", no_prompt=args.no_prompt
        )
    return {key: value for key, value in configured.items() if value}


def main() -> None:
    args = parse_args()
    variables = build_variables(args)
    space_secrets = build_secrets(args)

    print(f"Configuring {args.space} for runtime={args.runtime}")
    if args.dry_run:
        for key, value in variables.items():
            print(f"VARIABLE {key}={value}")
        for key in space_secrets:
            print(f"SECRET   {key}=<redacted>")
        return

    api = HfApi()
    for key, value in variables.items():
        api.add_space_variable(args.space, key, value)
        print(f"Variable set: {key}")
    for key, value in space_secrets.items():
        api.add_space_secret(args.space, key, value)
        print(f"Secret set: {key}")

    print("Done. Hugging Face will restart the Space after configuration changes.")


if __name__ == "__main__":
    main()
