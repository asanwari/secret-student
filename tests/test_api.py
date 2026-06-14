from __future__ import annotations

import asyncio
import json
import uuid
from types import SimpleNamespace

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine, inspect, text

from app.api import app
from app.database import init_db
import app.database as database_module
from app.image_validation import validate_image_data_url
from app.llm_clients import (
    MockLLMClient,
    OpenAICompatibleLLMClient,
    _lesson_response_format,
    _normalize_lesson_package,
    _validate_lesson_counts,
    _verification_response_format,
    _normalize_confidence,
    create_llm_client,
)
from app.config import Settings
from app.schemas import BossMission, LessonPackage, Question


PNG_DATA_URL = (
    "data:image/png;base64,"
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII="
)


@pytest.fixture(autouse=True)
def use_mock_api_llm(monkeypatch):
    # API flow tests remain deterministic even when the developer's .env points
    # at a real local model for manual end-to-end testing.
    monkeypatch.setattr("app.api.llm_client", MockLLMClient())


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
    payload = response.json()
    client.headers["Authorization"] = f"Bearer {payload['session_token']}"
    return payload


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


def test_lesson_normalizer_accepts_common_numeric_aliases():
    payload = {
        "quiz_questions": [
            {
                "answer_type": "number",
                "expected_answer": 50,
                "acceptable_answers": [50, "fifty"],
            }
        ],
        "boss_mission": {
            "questions": [{"answer_type": "integer", "expected_answer": 5}]
        },
    }

    normalized, changes = _normalize_lesson_package(payload)

    quiz = normalized["quiz_questions"][0]
    boss = normalized["boss_mission"]["questions"][0]
    assert quiz["answer_type"] == "numeric"
    assert quiz["expected_answer"] == "50"
    assert quiz["acceptable_answers"] == ["50", "fifty"]
    assert quiz["difficulty"] == "easy"
    assert boss["answer_type"] == "numeric"
    assert boss["expected_answer"] == "5"
    assert boss["difficulty"] == "hard"
    assert len(changes) == 7


def test_lesson_normalizer_handles_trace_field_aliases_and_extra_questions():
    payload = {
        "quiz_questions": [
            {"id": 1, "question_type": "number", "expected_answer": "1969"}
        ],
        "boss_mission": {
            "questions": [
                {"id": index, "question": f"Question {index}"}
                for index in range(6, 21)
            ]
        },
    }

    normalized, changes = _normalize_lesson_package(payload, 5, 10)

    quiz = normalized["quiz_questions"][0]
    assert quiz["id"] == "1"
    assert quiz["answer_type"] == "numeric"
    assert "question_type" not in quiz
    assert len(normalized["boss_mission"]["questions"]) == 10
    assert normalized["boss_mission"]["questions"][0]["id"] == "6"
    assert "boss_mission.questions: trimmed to 10" in changes


def test_lesson_response_format_requires_exact_question_counts():
    response_format = _lesson_response_format(5, 10)
    schema = response_format["json_schema"]["schema"]

    assert response_format["type"] == "json_schema"
    assert schema["properties"]["quiz_questions"]["minItems"] == 5
    assert schema["properties"]["quiz_questions"]["maxItems"] == 5
    boss_questions = schema["properties"]["boss_mission"]["properties"]["questions"]
    assert boss_questions["minItems"] == 10
    assert boss_questions["maxItems"] == 10
    required = boss_questions["items"]["required"]
    assert "answer_type" in required
    assert "expected_answer" in required


def test_verification_response_format_is_strict():
    response_format = _verification_response_format()
    schema = response_format["json_schema"]["schema"]

    assert response_format["type"] == "json_schema"
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == {
        "correct",
        "confidence",
        "feedback",
        "observed_answer",
    }


def test_lesson_count_validation_rejects_short_model_output():
    package = LessonPackage.model_validate(
        {
            "topic": "history",
            "learner_level": "Primary school",
            "lesson_steps": [
                {"title": f"Step {index}", "body": "Body", "example": "Example"}
                for index in range(6)
            ],
            "quiz_questions": [],
            "boss_mission": {
                "boss_name": "Boss",
                "briefing": "Briefing",
                "questions": [],
            },
        }
    )

    with pytest.raises(ValueError, match="exactly 5 items"):
        _validate_lesson_counts(package, 5, 10)


def test_lesson_generation_disables_thinking_for_structured_output(tmp_path, monkeypatch):
    captured_payload = {}
    valid_package = {
        "topic": "addition",
        "learner_level": "Primary school",
        "lesson_steps": [
            {"title": f"Step {index}", "body": "Learn", "example": "1 + 1 = 2"}
            for index in range(6)
        ],
        "quiz_questions": [
            {
                "id": f"q{index}",
                "question": "What is 1 + 1?",
                "answer_type": "numeric",
                "expected_answer": "2",
                "acceptable_answers": ["2"],
                "rubric": "Accept 2",
                "difficulty": "easy",
                "explanation": "One plus one is two.",
            }
            for index in range(5)
        ],
        "boss_mission": {
            "boss_name": "Adder",
            "briefing": "Defeat the Adder.",
            "questions": [
                {
                    "id": f"b{index}",
                    "question": "What is 2 + 2?",
                    "answer_type": "numeric",
                    "expected_answer": "4",
                    "acceptable_answers": ["4"],
                    "rubric": "Accept 4",
                    "difficulty": "hard",
                    "explanation": "Two plus two is four.",
                }
                for index in range(10)
            ],
        },
    }

    class FakeResponse:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return {
                "id": "structured-test",
                "choices": [
                    {"finish_reason": "stop", "message": {"content": json.dumps(valid_package)}}
                ],
                "usage": {},
            }

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def post(self, *args, **kwargs):
            captured_payload.update(kwargs["json"])
            return FakeResponse()

    monkeypatch.setattr("app.llm_clients.httpx.AsyncClient", FakeAsyncClient)
    client = OpenAICompatibleLLMClient(
        Settings(
            llm_provider="openai_compatible",
            llm_base_url="http://model.test",
            llm_enable_thinking=True,
            trace_destination="local",
            trace_dir=str(tmp_path),
        )
    )

    package = asyncio.run(
        client.generate_lesson_package("addition", "Primary school", 5, 10)
    )

    assert package.topic == "addition"
    assert captured_payload["chat_template_kwargs"] == {"enable_thinking": False}
    assert captured_payload["response_format"]["type"] == "json_schema"


def test_malformed_llm_json_is_repaired_and_traced(tmp_path, monkeypatch):
    malformed = '{"answer": "Line up the decimal points" "extra": true}'

    class FakeResponse:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return {
                "id": "completion-test",
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {"content": malformed},
                    }
                ],
                "usage": {"prompt_tokens": 10, "completion_tokens": 8},
            }

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def post(self, *args, **kwargs):
            return FakeResponse()

    monkeypatch.setattr("app.llm_clients.httpx.AsyncClient", FakeAsyncClient)
    settings = Settings(
        llm_provider="openai_compatible",
        llm_base_url="http://model.test",
        trace_destination="local",
        trace_dir=str(tmp_path),
    )
    client = OpenAICompatibleLLMClient(settings)

    result = asyncio.run(
        client._chat_json(
            [{"role": "user", "content": "Return JSON."}],
            max_tokens=50,
            log_label="repair_test",
            validator=lambda data: data,
        )
    )

    assert result["answer"] == "Line up the decimal points"
    trace_files = list(tmp_path.glob("*.json"))
    assert len(trace_files) == 1
    trace = json.loads(trace_files[0].read_text())
    assert trace["status"] == "succeeded"
    assert trace["repaired"] is True
    assert any(event["type"] == "response" for event in trace["events"])
    repair_event = next(event for event in trace["events"] if event["type"] == "json_repair")
    assert "Expecting" in repair_event["initial_error"]
    response_event = next(event for event in trace["events"] if event["type"] == "response")
    assert response_event["raw_content"] == malformed


def test_trace_redacts_image_data(tmp_path):
    from app.llm_tracing import TraceRun

    trace = TraceRun(
        Settings(trace_destination="local", trace_dir=str(tmp_path)),
        "image_test",
    )
    trace.event("request", image=PNG_DATA_URL, authorization="secret")
    trace.finish("succeeded")

    contents = next(tmp_path.glob("*.json")).read_text()
    assert PNG_DATA_URL not in contents
    assert "<image-data-url sha256=" in contents
    assert '"authorization": "<redacted>"' in contents


def test_register_login_and_duplicate_username():
    init_db()
    username = unique_username()
    with TestClient(app) as client:
        registered = register(client, username)
        assert registered["session_token"]
        auth_cookie = client.cookies.get("secret_student_token")
        assert auth_cookie.strip('"') == registered["session_token"]

        # Space embeds can block third-party cookies. The returned bearer token
        # must authenticate independently of the cookie set during registration.
        client.cookies.clear()
        bearer_me = client.get(
            "/api/me",
            headers={"Authorization": f"Bearer {registered['session_token']}"},
        )
        assert bearer_me.status_code == 200
        assert bearer_me.json()["user"]["username"] == username

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
        assert login.json()["session_token"]


def test_character_appearance_defaults_and_custom_palette_persist():
    init_db()
    with TestClient(app) as client:
        default_user = register(client)
        assert default_user["user"]["character_appearance"] == {
            "shirt_color": "red",
            "pants_color": "navy",
            "hair_color": "dark_brown",
        }

    with TestClient(app) as client:
        response = client.post(
            "/api/auth/register",
            json={
                "username": unique_username(),
                "password": "secret123",
                "learner_level": "Primary school",
                "character_appearance": {
                    "shirt_color": "teal",
                    "pants_color": "plum",
                    "hair_color": "auburn",
                },
            },
        )
        assert response.status_code == 200
        assert response.json()["user"]["character_appearance"] == {
            "shirt_color": "teal",
            "pants_color": "plum",
            "hair_color": "auburn",
        }


def test_character_appearance_rejects_unknown_palette_values():
    init_db()
    with TestClient(app) as client:
        response = client.post(
            "/api/auth/register",
            json={
                "username": unique_username(),
                "password": "secret123",
                "learner_level": "Primary school",
                "character_appearance": {
                    "shirt_color": "invisible",
                    "pants_color": "navy",
                    "hair_color": "dark_brown",
                },
            },
        )
        assert response.status_code == 422


def test_sqlite_upgrade_adds_appearance_and_villain_columns(tmp_path, monkeypatch):
    database_url = f"sqlite:///{tmp_path / 'legacy.sqlite3'}"
    legacy_engine = create_engine(database_url)
    with legacy_engine.begin() as connection:
        connection.execute(text("CREATE TABLE users (id INTEGER PRIMARY KEY, username VARCHAR(40))"))
        connection.execute(text("CREATE TABLE lessons (id INTEGER PRIMARY KEY, boss_name VARCHAR(120))"))

    monkeypatch.setattr(database_module, "engine", legacy_engine)
    monkeypatch.setattr(database_module, "settings", SimpleNamespace(database_url=database_url))
    database_module._upgrade_sqlite_schema()

    inspector = inspect(legacy_engine)
    assert {"shirt_color", "pants_color", "hair_color"} <= {
        column["name"] for column in inspector.get_columns("users")
    }
    assert "villain_image_url" in {
        column["name"] for column in inspector.get_columns("lessons")
    }


def test_lesson_validation_rejects_long_steps_and_missing_media():
    base = {
        "topic": "history",
        "learner_level": "Primary school",
        "lesson_steps": [
            {"title": f"Step {index}", "body": "Clear lesson text.", "example": "A concrete example."}
            for index in range(6)
        ],
        "quiz_questions": [],
        "boss_mission": {"boss_name": "Boss", "briefing": "Briefing", "questions": []},
    }
    base["lesson_steps"][0]["body"] = "word " * 151
    package = LessonPackage.model_validate(base)
    with pytest.raises(ValueError, match="exceeds 150 words"):
        _validate_lesson_counts(package, 0, 0)

    base["lesson_steps"][0]["body"] = "Look at the map and identify the location."
    package = LessonPackage.model_validate(base)
    with pytest.raises(ValueError, match="unavailable media"):
        _validate_lesson_counts(package, 0, 0)


def test_villain_image_url_accepts_safe_sources_and_drops_unsafe_ones():
    safe = BossMission(boss_name="Boss", briefing="Brief", questions=[], villain_image_url="https://images.example/villain.png")
    unsafe = BossMission(boss_name="Boss", briefing="Brief", questions=[], villain_image_url="javascript:alert(1)")
    assert safe.villain_image_url == "https://images.example/villain.png"
    assert unsafe.villain_image_url is None


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


def test_drawn_verification_routes_to_vision_model(tmp_path, monkeypatch):
    captured = {}

    class FakeResponse:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return {
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {
                            "content": json.dumps(
                                {
                                    "correct": True,
                                    "confidence": 0.9,
                                    "feedback": "Correct.",
                                    "observed_answer": "5",
                                }
                            )
                        },
                    }
                ]
            }

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def post(self, url, **kwargs):
            captured.update(url=url, headers=kwargs["headers"], payload=kwargs["json"])
            return FakeResponse()

    monkeypatch.setattr("app.llm_clients.httpx.AsyncClient", FakeAsyncClient)
    client = OpenAICompatibleLLMClient(
        Settings(
            llm_provider="openai_compatible",
            llm_base_url="http://text.test",
            llm_model="text-model",
            vision_llm_base_url="http://vision.test",
            vision_llm_api_key="vision-key",
            vision_llm_model="vision-model",
            trace_destination="local",
            trace_dir=str(tmp_path),
        )
    )
    question = Question(
        id="q1",
        question="What is 2 + 3?",
        answer_type="numeric",
        expected_answer="5",
        acceptable_answers=["5"],
        rubric="The written answer is 5.",
        difficulty="easy",
        explanation="Two plus three is five.",
    )

    result = asyncio.run(client.verify_drawn_answer(question, PNG_DATA_URL))

    assert result.correct is True
    assert captured["url"] == "http://vision.test/v1/chat/completions"
    assert captured["headers"]["Authorization"] == "Bearer vision-key"
    assert captured["payload"]["model"] == "vision-model"
