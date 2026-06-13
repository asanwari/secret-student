from __future__ import annotations

import base64
import binascii
import re


DATA_URL_RE = re.compile(r"^data:image/(png|jpeg|jpg|webp);base64,(?P<data>[A-Za-z0-9+/=\n\r]+)$")


def validate_image_data_url(image_data_url: str) -> str:
    match = DATA_URL_RE.match(image_data_url.strip())
    if not match:
        raise ValueError("Expected a PNG, JPEG, or WebP image data URL.")
    try:
        base64.b64decode(match.group("data"), validate=True)
    except binascii.Error as exc:
        raise ValueError("Image data URL contained invalid base64.") from exc
    return image_data_url.strip()


def decode_image_data_url(image_data_url: str) -> tuple[str, bytes]:
    validated = validate_image_data_url(image_data_url)
    media_type = validated.split(";", 1)[0].removeprefix("data:image/")
    raw_data = validated.split(",", 1)[1]
    return media_type.replace("jpg", "jpeg"), base64.b64decode(raw_data)

