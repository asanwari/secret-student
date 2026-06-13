from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from uuid import uuid4

from app.config import BASE_DIR
from app.image_validation import decode_image_data_url
from app.schemas import Question


DEBUG_DIR = BASE_DIR / "debug_submissions"
AVATAR_DIR = BASE_DIR / "data" / "avatars"


def save_submitted_image(user_id: int, question: Question, image_data_url: str) -> str:
    media_type, image_bytes = decode_image_data_url(image_data_url)
    DEBUG_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    base_name = f"{stamp}_user{user_id}_{question.id}_{uuid4().hex[:8]}"
    image_path = DEBUG_DIR / f"{base_name}.{_extension(media_type)}"
    meta_path = DEBUG_DIR / f"{base_name}.json"
    image_path.write_bytes(image_bytes)
    meta_path.write_text(
        json.dumps(
            {
                "user_id": user_id,
                "question": question.model_dump(),
                "image_path": str(image_path),
            },
            indent=2,
        )
    )
    return str(image_path)


def save_avatar_image(username: str, image_data_url: str) -> str:
    media_type, image_bytes = decode_image_data_url(image_data_url)
    AVATAR_DIR.mkdir(parents=True, exist_ok=True)
    safe_username = "".join(ch for ch in username if ch.isalnum() or ch in {"_", "-"})
    path = AVATAR_DIR / f"{safe_username}_{uuid4().hex[:8]}.{_extension(media_type)}"
    path.write_bytes(image_bytes)
    return str(path)


def _extension(media_type: str) -> str:
    return "jpg" if media_type == "jpeg" else media_type

