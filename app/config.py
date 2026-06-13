from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[1]
ENV_PATH = BASE_DIR / ".env"


def load_env(path: Path = ENV_PATH) -> None:
    if not path.exists():
        return

    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _read_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def _read_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    app_secret: str = "secret-student-dev-secret"
    database_url: str = "sqlite:///./data/secret_student.sqlite3"
    llm_provider: str = "mock"
    llm_base_url: str = ""
    llm_api_key: str = ""
    llm_model: str = "openbmb/MiniCPM-V-4.6"
    llm_enable_thinking: bool = False
    quiz_question_count: int = 5
    boss_question_count: int = 10
    boss_max_mistakes: int = 3
    cors_origins: tuple[str, ...] = (
        "http://127.0.0.1:7860",
        "http://localhost:7860",
        "http://127.0.0.1:8000",
        "http://localhost:8000",
    )


def get_settings() -> Settings:
    load_env()
    cors_value = os.getenv("CORS_ORIGINS", "")
    cors_origins = tuple(
        origin.strip() for origin in cors_value.split(",") if origin.strip()
    ) or Settings.cors_origins

    return Settings(
        app_secret=os.getenv("APP_SECRET", Settings.app_secret),
        database_url=os.getenv("DATABASE_URL", Settings.database_url),
        llm_provider=os.getenv("LLM_PROVIDER", Settings.llm_provider).strip().lower(),
        llm_base_url=os.getenv("LLM_BASE_URL", "").strip().rstrip("/"),
        llm_api_key=os.getenv("LLM_API_KEY", "").strip(),
        llm_model=os.getenv("LLM_MODEL", Settings.llm_model).strip(),
        llm_enable_thinking=_read_bool("LLM_ENABLE_THINKING", False),
        quiz_question_count=_read_int("QUIZ_QUESTION_COUNT", Settings.quiz_question_count),
        boss_question_count=_read_int("BOSS_QUESTION_COUNT", Settings.boss_question_count),
        boss_max_mistakes=_read_int("BOSS_MAX_MISTAKES", Settings.boss_max_mistakes),
        cors_origins=cors_origins,
    )

