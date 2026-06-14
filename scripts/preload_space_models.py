from __future__ import annotations

import argparse
from pathlib import Path
import shutil

from huggingface_hub import hf_hub_download


FILES = (
    (
        "Qwen/Qwen3-8B-GGUF",
        "Qwen3-8B-Q4_K_M.gguf",
        "qwen3-8b/Qwen3-8B-Q4_K_M.gguf",
    ),
    (
        "openbmb/MiniCPM-V-4_5-gguf",
        "MiniCPM-V-4_5-Q4_K_M.gguf",
        "minicpm-v-4_5/MiniCPM-V-4_5-Q4_K_M.gguf",
    ),
    (
        "openbmb/MiniCPM-V-4_5-gguf",
        "mmproj-model-f16.gguf",
        "minicpm-v-4_5/mmproj-model-f16.gguf",
    ),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Preload Secret Student GGUF files into a mounted Space bucket."
    )
    parser.add_argument("--destination", type=Path, default=Path("/data/models"))
    parser.add_argument("--cache-dir", type=Path, default=Path("/tmp/hf-model-cache"))
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
    for repo_id, filename, relative_destination in FILES:
        copy_model(
            repo_id,
            filename,
            args.destination / relative_destination,
            args.cache_dir,
        )


if __name__ == "__main__":
    main()
