from __future__ import annotations

from abc import ABC, abstractmethod
import json
import logging
import re
from uuid import uuid4

import httpx

from app.config import Settings
from app.schemas import (
    BossMission,
    LessonPackage,
    LessonStep,
    Question,
    VerificationResult,
)


logger = logging.getLogger(__name__)


class LLMClient(ABC):
    @abstractmethod
    async def generate_lesson_package(
        self,
        topic: str,
        learner_level: str,
        quiz_count: int,
        boss_count: int,
    ) -> LessonPackage:
        raise NotImplementedError

    @abstractmethod
    async def answer_teacher_question(
        self,
        topic: str,
        learner_level: str,
        lesson_steps: list[LessonStep],
        step_index: int,
        question: str,
    ) -> str:
        raise NotImplementedError

    @abstractmethod
    async def verify_drawn_answer(
        self, question: Question, image_data_url: str
    ) -> VerificationResult:
        raise NotImplementedError


class MockLLMClient(LLMClient):
    async def generate_lesson_package(
        self,
        topic: str,
        learner_level: str,
        quiz_count: int,
        boss_count: int,
    ) -> LessonPackage:
        clean_topic = topic.strip()
        steps = [
            LessonStep(
                title=f"Secret briefing: {clean_topic}",
                body=(
                    f"{clean_topic} is today's school skill and secret-agent tool. "
                    "Start by spotting the important numbers or words."
                ),
                example="Agent note: read the question twice, then solve one small step.",
            ),
            LessonStep(
                title="Try a tiny example",
                body="For number missions, line up the values carefully. For word missions, answer in one clear sentence.",
                example="2 + 3 = 5, because two steps and three steps make five steps.",
            ),
            LessonStep(
                title="Check your work",
                body="A Secret Student always checks the answer before reporting back.",
                example="If the mission says 4 + 1, count 4 then 1 more: 5.",
            ),
        ]
        quiz = [
            _mock_question(clean_topic, index, "easy")
            for index in range(max(1, quiz_count))
        ]
        boss_questions = [
            _mock_question(clean_topic, index + 10, "hard")
            for index in range(max(1, boss_count))
        ]
        boss = BossMission(
            boss_name=_boss_name(clean_topic),
            briefing=(
                f"{_boss_name(clean_topic)} is scrambling every clue about {clean_topic}. "
                "Answer the questions to shut down the confusion ray."
            ),
            questions=boss_questions,
        )
        return LessonPackage(
            topic=clean_topic,
            learner_level=learner_level,
            lesson_steps=steps,
            quiz_questions=quiz,
            boss_mission=boss,
        )

    async def answer_teacher_question(
        self,
        topic: str,
        learner_level: str,
        lesson_steps: list[LessonStep],
        step_index: int,
        question: str,
    ) -> str:
        return (
            f"Great question. In mock mode, the teacher says: connect '{question}' "
            f"back to {topic}, then try one small example before the full answer."
        )

    async def verify_drawn_answer(
        self, question: Question, image_data_url: str
    ) -> VerificationResult:
        return VerificationResult(
            correct=True,
            confidence=0.8,
            observed_answer=question.expected_answer,
            feedback=f"Mock vision accepts the drawing as {question.expected_answer}.",
        )


class OpenAICompatibleLLMClient(LLMClient):
    def __init__(self, settings: Settings) -> None:
        if not settings.llm_base_url:
            raise ValueError("LLM_BASE_URL is required for openai_compatible mode.")
        self.settings = settings

    async def generate_lesson_package(
        self,
        topic: str,
        learner_level: str,
        quiz_count: int,
        boss_count: int,
    ) -> LessonPackage:
        # This single batched prompt is the key latency optimization: one model call
        # returns the lesson, quiz, boss name, and boss questions as structured JSON.
        prompt = (
            "Return only compact JSON matching this shape: "
            "{topic, learner_level, lesson_steps:[{title, body, example}], "
            "quiz_questions:[{id, question, answer_type, expected_answer, acceptable_answers, rubric, difficulty, explanation}], "
            "boss_mission:{boss_name, briefing, questions:[same question shape]}}. "
            "Use answer_type numeric for math answers that can be compared exactly; otherwise use text. "
            f"Create 6 to 10 short lesson steps, {quiz_count} quiz questions, and {boss_count} harder boss questions. "
            f"Topic: {topic}. Learner level: {learner_level}."
        )
        data = await self._chat_json(
            [
                {
                    "role": "system",
                    "content": "You create child-friendly lessons for a retro secret-agent school game.",
                },
                {"role": "user", "content": prompt},
            ],
            max_tokens=5000,
            log_label="generate_lesson_package",
        )
        normalized = _ensure_question_ids(data)
        return LessonPackage.model_validate(normalized)

    async def answer_teacher_question(
        self,
        topic: str,
        learner_level: str,
        lesson_steps: list[LessonStep],
        step_index: int,
        question: str,
    ) -> str:
        step = lesson_steps[min(step_index, len(lesson_steps) - 1)] if lesson_steps else None
        prompt = (
            "Answer the learner's question in 2-4 short, encouraging sentences. "
            "Do not reveal hidden reasoning. "
            f"Topic: {topic}. Learner level: {learner_level}. "
            f"Current step: {step.model_dump() if step else {}}. "
            f"Learner question: {question}"
        )
        data = await self._chat_json(
            [
                {"role": "system", "content": "You are a kind classroom teacher."},
                {
                    "role": "user",
                    "content": f"Return JSON with one key, answer. {prompt}",
                },
            ],
            max_tokens=700,
            log_label="answer_teacher_question",
        )
        return str(data.get("answer", "")).strip() or "Try one smaller example first, then build up."

    async def verify_drawn_answer(
        self, question: Question, image_data_url: str
    ) -> VerificationResult:
        prompt = (
            "Look at the handwritten answer in the image. Compare it with the expected answer. "
            "Return only JSON with keys correct boolean, confidence number 0-1, feedback string, observed_answer string. "
            f"Question: {question.question}. Expected answer: {question.expected_answer}. Rubric: {question.rubric}"
        )
        data = await self._chat_json(
            [
                {"role": "system", "content": "You grade children's handwritten answers kindly."},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": image_data_url}},
                    ],
                },
            ],
            max_tokens=700,
            log_label="verify_drawn_answer",
        )
        return VerificationResult(
            correct=bool(data.get("correct", False)),
            confidence=_normalize_confidence(data.get("confidence", 0)),
            feedback=str(data.get("feedback", "")).strip() or "I checked your work.",
            observed_answer=str(data.get("observed_answer", "")).strip(),
        )

    async def _chat_json(self, messages: list[dict], max_tokens: int, log_label: str) -> dict:
        payload: dict = {
            "model": self.settings.llm_model,
            "messages": messages,
            "temperature": 0.2,
            "max_tokens": max_tokens,
            "response_format": {"type": "json_object"},
        }
        if self.settings.llm_enable_thinking:
            payload["chat_template_kwargs"] = {"enable_thinking": True}

        headers = {"Content-Type": "application/json"}
        if self.settings.llm_api_key:
            headers["Authorization"] = f"Bearer {self.settings.llm_api_key}"

        async with httpx.AsyncClient(timeout=180) as client:
            response = await client.post(
                f"{self.settings.llm_base_url}/v1/chat/completions",
                headers=headers,
                json=payload,
            )
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                raise RuntimeError(
                    f"LLM chat request failed with HTTP {response.status_code}: {response.text}"
                ) from exc
        content = response.json()["choices"][0]["message"]["content"]
        logger.info("LLM response for %s: %r", log_label, content)
        return _extract_json_object(content)


def create_llm_client(settings: Settings) -> LLMClient:
    if settings.llm_provider == "mock":
        return MockLLMClient()
    if settings.llm_provider == "openai_compatible":
        return OpenAICompatibleLLMClient(settings)
    raise ValueError(f"Unsupported LLM_PROVIDER: {settings.llm_provider}")


def _mock_question(topic: str, index: int, difficulty: str) -> Question:
    left = 2 + index
    right = 3 if difficulty == "easy" else 7
    answer = left + right
    return Question(
        id=f"mock-{difficulty}-{index}",
        question=f"Agent math check for {topic}: what is {left} + {right}?",
        answer_type="numeric",
        expected_answer=str(answer),
        acceptable_answers=[str(answer)],
        rubric=f"Accept the number {answer}.",
        difficulty=difficulty,  # type: ignore[arg-type]
        explanation=f"{left} + {right} = {answer}.",
    )


def _boss_name(topic: str) -> str:
    clean = re.sub(r"[^A-Za-z0-9 ]", "", topic).strip().title() or "Mystery"
    return f"The {clean} Phantom"


def _extract_json_object(content: str | dict) -> dict:
    if isinstance(content, dict):
        return content
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", content, re.DOTALL)
        if not match:
            raise ValueError("Model response did not contain JSON.")
        return json.loads(match.group(0))


def _ensure_question_ids(data: dict) -> dict:
    for key in ("quiz_questions",):
        for question in data.get(key, []):
            question.setdefault("id", str(uuid4()))
    mission = data.get("boss_mission", {})
    for question in mission.get("questions", []):
        question.setdefault("id", str(uuid4()))
    return data


def _normalize_confidence(value: object) -> float:
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    if isinstance(value, int | float):
        return max(0.0, min(float(value), 1.0))
    if value is None:
        return 0.0
    text = str(value).strip().lower()
    if text in {"high", "very high"}:
        return 0.9
    if text in {"medium", "moderate"}:
        return 0.6
    if text in {"low", "uncertain"}:
        return 0.3
    number_match = re.search(r"\d+(?:\.\d+)?", text)
    if not number_match:
        return 0.0
    number = float(number_match.group(0))
    if "%" in text or number > 1:
        number /= 100
    return max(0.0, min(number, 1.0))
