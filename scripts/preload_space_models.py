from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil

from huggingface_hub import hf_hub_download


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Preload Secret Student GGUF files into a mounted Space bucket."
    )
    parser.add_argument("--destination", type=Path, default=Path("/data/models"))
    parser.add_argument("--cache-dir", type=Path, default=Path("/tmp/hf-model-cache"))
    parser.add_argument(
        "--text-repo",
        default=os.getenv("TEXT_MODEL_REPO", "Qwen/Qwen3-8B-GGUF"),
    )
    parser.add_argument(
        "--text-file",
        default=os.getenv("TEXT_MODEL_FILE", "Qwen3-8B-Q4_K_M.gguf"),
    )
    parser.add_argument(
        "--text-destination",
        default=os.getenv(
            "TEXT_MODEL_DESTINATION", "qwen3-8b/Qwen3-8B-Q4_K_M.gguf"
        ),
    )
    parser.add_argument(
        "--vision-repo",
        default=os.getenv("VISION_MODEL_REPO", "openbmb/MiniCPM-V-4_5-gguf"),
    )
    parser.add_argument(
        "--vision-file",
        default=os.getenv("VISION_MODEL_FILE", "MiniCPM-V-4_5-Q4_K_M.gguf"),
    )
    parser.add_argument(
        "--vision-destination",
        default=os.getenv(
            "VISION_MODEL_DESTINATION",
            "minicpm-v-4_5/MiniCPM-V-4_5-Q4_K_M.gguf",
        ),
    )
    parser.add_argument(
        "--mmproj-file",
        default=os.getenv("VISION_MMPROJ_FILE", "mmproj-model-f16.gguf"),
    )
    parser.add_argument(
        "--mmproj-destination",
        default=os.getenv(
            "VISION_MMPROJ_DESTINATION", "minicpm-v-4_5/mmproj-model-f16.gguf"
        ),
    )
    return parser.parse_args()


def copy_model(repo_id: str, filename: str, destination: Path, cache_dir: Path) -> None:
    source = Path(
        hf_hub_download(repo_id=repo_id, filename=filename, cache_dir=cache_dir)
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() and destination.stat().st_size == source.stat().st_size:
        print(f"Already present: {destination}")
        return

    print(f"Copying {repo_id}/{filename} -> {destination}")
    with source.open("rb") as source_file, destination.open("wb") as destination_file:
        shutil.copyfileobj(source_file, destination_file, length=16 * 1024 * 1024)
    if destination.stat().st_size != source.stat().st_size:
        raise RuntimeError(f"Incomplete copy: {destination}")


def main() -> None:
    args = parse_args()
    files = (
        (args.text_repo, args.text_file, args.text_destination),
        (args.vision_repo, args.vision_file, args.vision_destination),
        (args.vision_repo, args.mmproj_file, args.mmproj_destination),
    )
    for repo_id, filename, relative_destination in files:
        copy_model(
            repo_id,
            filename,
            args.destination / relative_destination,
            args.cache_dir,
        )


if __name__ == "__main__":
    main()
