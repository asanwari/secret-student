from __future__ import annotations

import uuid

from fastapi.testclient import TestClient

from app.api import app
from app.database import init_db
from app.image_validation import validate_image_data_url
from app.llm_clients import MockLLMClient, _normalize_confidence, create_llm_client
from app.config import Settings


PNG_DATA_URL = (
    "data:image/png;base64,"
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII="
)


def unique_username() -> str:
    return f"agent_{uuid.uuid4().hex[:10]}"


def register(client: TestClient, username: str | None = None) -> dict:
    response = client.post(
        "/api/auth/register",
        json={
            "username": username or unique_username(),
            "password": "secret123",
            "learner_level": "Primary school",
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def start_lesson(client: TestClient, topic: str = "decimal addition") -> dict:
    response = client.post("/api/lesson/start", json={"topic": topic})
    assert response.status_code == 200, response.text
    return response.json()


def test_provider_selection_mock():
    client = create_llm_client(Settings(llm_provider="mock"))
    assert isinstance(client, MockLLMClient)


def test_validate_image_data_url_accepts_png():
    assert validate_image_data_url(PNG_DATA_URL) == PNG_DATA_URL


def test_normalize_confidence_handles_words_and_numbers():
    assert _normalize_confidence("high") == 0.9
    assert _normalize_confidence("medium") == 0.6
    assert _normalize_confidence("85%") == 0.85
    assert _normalize_confidence("0.42") == 0.42


def test_register_login_and_duplicate_username():
    init_db()
    username = unique_username()
    with TestClient(app) as client:
        register(client, username)
        duplicate = client.post(
            "/api/auth/register",
            json={
                "username": username,
                "password": "secret123",
                "learner_level": "Primary school",
            },
        )
        assert duplicate.status_code == 409

    with TestClient(app) as client:
        bad_login = client.post(
            "/api/auth/login",
            json={"username": username, "password": "wrong"},
        )
        assert bad_login.status_code == 401

        login = client.post(
            "/api/auth/login",
            json={"username": username, "password": "secret123"},
        )
        assert login.status_code == 200
        assert login.json()["user"]["username"] == username


def test_full_mock_game_flow_boss_win():
    init_db()
    with TestClient(app) as client:
        register(client)
        lesson = start_lesson(client)
        assert lesson["lesson_steps"]
        assert len(lesson["quiz_questions"]) >= 1
        assert len(lesson["boss_mission"]["questions"]) >= 1

        quiz_question = lesson["quiz_questions"][0]
        quiz_response = client.post(
            "/api/quiz/submit",
            json={
                "lesson_id": lesson["id"],
                "question_id": quiz_question["id"],
                "mode": "quiz",
                "answer_text": quiz_question["expected_answer"],
            },
        )
        assert quiz_response.status_code == 200, quiz_response.text
        assert quiz_response.json()["result"]["correct"] is True

        boss_start = client.post("/api/boss/start", json={"lesson_id": lesson["id"]})
        assert boss_start.status_code == 200, boss_start.text
        boss_payload = boss_start.json()

        defeated = False
        while not defeated:
            question = boss_payload["question"]
            boss_submit = client.post(
                "/api/boss/submit",
                json={
                    "lesson_id": lesson["id"],
                    "question_id": question["id"],
                    "mode": "boss",
                    "answer_text": question["expected_answer"],
                },
            )
            assert boss_submit.status_code == 200, boss_submit.text
            boss_payload = boss_submit.json()
            defeated = boss_payload["defeated"]
        assert boss_payload["lost"] is False


def test_boss_loss_path_allows_rest():
    init_db()
    with TestClient(app) as client:
        register(client)
        lesson = start_lesson(client)
        boss_start = client.post("/api/boss/start", json={"lesson_id": lesson["id"]})
        question = boss_start.json()["question"]

        lost = False
        for _ in range(3):
            response = client.post(
                "/api/boss/submit",
                json={
                    "lesson_id": lesson["id"],
                    "question_id": question["id"],
                    "mode": "boss",
                    "answer_text": "not the answer",
                },
            )
            assert response.status_code == 200, response.text
            payload = response.json()
            lost = payload["lost"]
            if payload["question"]:
                question = payload["question"]
        assert lost is True

        rested = client.post(
            "/api/state/location",
            json={"location": "home", "story_milestone": "rest"},
        )
        assert rested.status_code == 200
        assert rested.json()["player_health"] == 3


def test_drawn_answer_submission_uses_mock_vision():
    init_db()
    with TestClient(app) as client:
        register(client)
        lesson = start_lesson(client)
        question = lesson["quiz_questions"][0]
        response = client.post(
            "/api/quiz/submit",
            json={
                "lesson_id": lesson["id"],
                "question_id": question["id"],
                "mode": "quiz",
                "image_data_url": PNG_DATA_URL,
            },
        )
        assert response.status_code == 200, response.text
        assert response.json()["result"]["correct"] is True
