from __future__ import annotations

import base64
import hashlib
import hmac
import time

from passlib.context import CryptContext

from app.config import get_settings


password_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return password_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return password_context.verify(password, password_hash)


def create_session_token(user_id: int) -> str:
    timestamp = str(int(time.time()))
    payload = f"{user_id}:{timestamp}"
    signature = _sign(payload)
    token = f"{payload}:{signature}".encode()
    return base64.urlsafe_b64encode(token).decode()


def parse_session_token(token: str) -> int | None:
    try:
        decoded = base64.urlsafe_b64decode(token.encode()).decode()
        user_id_text, timestamp_text, signature = decoded.split(":", 2)
    except Exception:
        return None

    payload = f"{user_id_text}:{timestamp_text}"
    if not hmac.compare_digest(_sign(payload), signature):
        return None
    try:
        return int(user_id_text)
    except ValueError:
        return None


def _sign(payload: str) -> str:
    secret = get_settings().app_secret.encode()
    return hmac.new(secret, payload.encode(), hashlib.sha256).hexdigest()

