from __future__ import annotations

from abc import ABC, abstractmethod
import json
import logging
import re
from uuid import uuid4

import httpx
from json_repair import repair_json
from pydantic import ValidationError

from app.config import Settings
from app.llm_tracing import LLMTraceError, TraceRun
from app.schemas import (
    BossMission,
    LessonPackage,
    LessonStep,
    Question,
    TeacherChatMessage,
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
        trace_context: dict | None = None,
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
        history: list[TeacherChatMessage],
        trace_context: dict | None = None,
    ) -> str:
        raise NotImplementedError

    @abstractmethod
    async def verify_drawn_answer(
        self,
        question: Question,
        image_data_url: str,
        trace_context: dict | None = None,
    ) -> VerificationResult:
        raise NotImplementedError

    @abstractmethod
    async def verify_text_answer(
        self,
        question: Question,
        answer_text: str,
        trace_context: dict | None = None,
    ) -> VerificationResult:
        raise NotImplementedError


class MockLLMClient(LLMClient):
    async def generate_lesson_package(
        self,
        topic: str,
        learner_level: str,
        quiz_count: int,
        boss_count: int,
        trace_context: dict | None = None,
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
            LessonStep(
                title="Explain the clue",
                body="Say why your method works using the key idea from the lesson.",
                example="I combined the two groups, so the total is the sum of both groups.",
            ),
            LessonStep(
                title="Avoid the trap",
                body="Check the operation, units, and important vocabulary before choosing an answer.",
                example="A careful agent answers the exact question instead of a nearby one.",
            ),
            LessonStep(
                title="Mission recap",
                body=f"Recall the main idea of {clean_topic}, one useful method, and one way to check the result.",
                example="You are ready when you can solve a small example without hints.",
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
        history: list[TeacherChatMessage],
        trace_context: dict | None = None,
    ) -> str:
        return (
            f"Great follow-up. In mock mode, the teacher says: connect '{question}' "
            f"back to {topic}, then try one small example before the full answer."
        )

    async def verify_drawn_answer(
        self,
        question: Question,
        image_data_url: str,
        trace_context: dict | None = None,
    ) -> VerificationResult:
        return VerificationResult(
            correct=True,
            confidence=0.8,
            observed_answer=question.expected_answer,
            feedback=f"Mock vision accepts the drawing as {question.expected_answer}.",
        )

    async def verify_text_answer(
        self,
        question: Question,
        answer_text: str,
        trace_context: dict | None = None,
    ) -> VerificationResult:
        observed = answer_text.strip()
        expected = [question.expected_answer, *question.acceptable_answers]
        correct = observed.casefold() in {value.strip().casefold() for value in expected}
        return VerificationResult(
            correct=correct,
            confidence=1.0 if correct else 0.2,
            observed_answer=observed,
            feedback=question.explanation if correct else f"Expected: {question.expected_answer}. {question.explanation}",
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
        trace_context: dict | None = None,
    ) -> LessonPackage:
        # This single batched prompt is the key latency optimization: one model call
        # returns the lesson, quiz, boss name, and boss questions as structured JSON.
        prompt = (
            "Return only one complete compact JSON object matching this shape: "
            "{topic, learner_level, lesson_steps:[{title, body, example}], "
            "quiz_questions:[{id, question, answer_type, expected_answer, acceptable_answers, rubric, difficulty, explanation}], "
            "boss_mission:{boss_name, briefing, questions:[same question shape]}}. "
            "For every question, answer_type must be exactly 'numeric' or 'text'. "
            "expected_answer and every acceptable_answers item must always be JSON strings, even for numbers. "
            "Every question must include all listed fields. Use difficulty easy or medium for quizzes and hard for bosses. "
            "Create a coherent teaching sequence: introduction, core explanation, guided example, deeper practice, recap, then quiz preparation. "
            "Each step's body plus example must be substantial but concise, usually 60 to 120 words and never more than 150 words, with vocabulary and examples appropriate for the learner level. "
            "The experience is text-only: never tell the learner to look at or use an image, map, chart, diagram, video, worksheet, book, object, or other material that is not included in the step text. "
            "Every quiz and boss question must be answerable from the lesson. Prefer numeric answers or short canonical text answers whenever the topic permits; never ask for opinions, drawings, visual identification, or open-ended discussion. "
            f"Create 6 to 10 lesson steps, exactly {quiz_count} quiz questions, and exactly {boss_count} harder boss questions. "
            f"Topic: {topic}. Learner level: {learner_level}."
        )

        def validate_package(value: dict) -> dict:
            package = LessonPackage.model_validate(_ensure_question_ids(value))
            _validate_lesson_counts(package, quiz_count, boss_count)
            return package.model_dump()

        async def repair_invalid_package(
            invalid_data: dict, validation_error: Exception
        ) -> dict:
            compact_errors = (
                validation_error.errors(include_url=False, include_input=False)
                if isinstance(validation_error, ValidationError)
                else str(validation_error)
            )
            repair_prompt = (
                "Repair the following lesson JSON so it satisfies the schema. "
                "Preserve usable lesson content, correct factual mistakes, and fill every missing field. "
                f"Return exactly {quiz_count} quiz questions and exactly {boss_count} boss questions. "
                "Do not leave any question without an answer_type and expected_answer. "
                "Keep a coherent teaching sequence, keep every step at 150 words or fewer, remove references to unavailable media or materials, and make every question concrete and answerable from the lesson. "
                f"Validation errors: {json.dumps(compact_errors, ensure_ascii=True)}. "
                f"Invalid JSON: {json.dumps(invalid_data, ensure_ascii=True)}"
            )
            return await self._chat_json(
                [
                    {
                        "role": "system",
                        "content": "You repair structured educational JSON without omitting fields.",
                    },
                    {"role": "user", "content": repair_prompt},
                ],
                max_tokens=5000,
                log_label="repair_lesson_package",
                trace_context={
                    **(trace_context or {}),
                    "repair_of": "generate_lesson_package",
                },
                enable_thinking=False,
                response_format=_lesson_response_format(quiz_count, boss_count),
                normalizer=lambda value: _normalize_lesson_package(
                    value, quiz_count, boss_count
                ),
                validator=validate_package,
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
            trace_context=trace_context,
            enable_thinking=False,
            response_format=_lesson_response_format(quiz_count, boss_count),
            normalizer=lambda value: _normalize_lesson_package(
                value, quiz_count, boss_count
            ),
            validator=validate_package,
            repairer=repair_invalid_package,
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
        history: list[TeacherChatMessage],
        trace_context: dict | None = None,
    ) -> str:
        step = lesson_steps[min(step_index, len(lesson_steps) - 1)] if lesson_steps else None
        conversation = [message.model_dump() for message in history[-10:]]
        prompt = (
            "Answer the learner's question in 2-4 short, encouraging sentences. "
            "Treat it as a continuation of the conversation when history is present. "
            "Do not reveal hidden reasoning. "
            f"Topic: {topic}. Learner level: {learner_level}. "
            f"Current step: {step.model_dump() if step else {}}. "
            f"Recent conversation: {conversation}. "
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
            trace_context=trace_context,
            validator=_validate_teacher_answer,
        )
        return str(data.get("answer", "")).strip() or "Try one smaller example first, then build up."

    async def verify_drawn_answer(
        self,
        question: Question,
        image_data_url: str,
        trace_context: dict | None = None,
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
            max_tokens=300,
            log_label="verify_drawn_answer",
            trace_context=trace_context,
            enable_thinking=False,
            response_format=_verification_response_format(),
            validator=_validate_verification_payload,
            use_vision_model=True,
        )
        return VerificationResult(
            correct=bool(data.get("correct", False)),
            confidence=_normalize_confidence(data.get("confidence", 0)),
            feedback=str(data.get("feedback", "")).strip() or "I checked your work.",
            observed_answer=str(data.get("observed_answer", "")).strip(),
        )

    async def verify_text_answer(
        self,
        question: Question,
        answer_text: str,
        trace_context: dict | None = None,
    ) -> VerificationResult:
        prompt = (
            "Grade the student's typed answer using only the question, expected answer, "
            "acceptable answers, and rubric. Accept equivalent wording and numerically "
            "equivalent values, but do not accept a materially different answer. Return "
            "only JSON with keys correct boolean, confidence number 0-1, feedback string, "
            "observed_answer string. "
            f"Question: {question.question}. Expected answer: {question.expected_answer}. "
            f"Acceptable answers: {question.acceptable_answers}. Rubric: {question.rubric}. "
            f"Student answer: {answer_text.strip()}"
        )
        data = await self._chat_json(
            [
                {"role": "system", "content": "You grade children's typed answers accurately and kindly."},
                {"role": "user", "content": prompt},
            ],
            max_tokens=300,
            log_label="verify_text_answer",
            trace_context=trace_context,
            enable_thinking=False,
            response_format=_verification_response_format(),
            validator=_validate_verification_payload,
        )
        return VerificationResult(
            correct=bool(data.get("correct", False)),
            confidence=_normalize_confidence(data.get("confidence", 0)),
            feedback=str(data.get("feedback", "")).strip() or "I checked your answer.",
            observed_answer=str(data.get("observed_answer", "")).strip() or answer_text.strip(),
        )

    async def _chat_json(
        self,
        messages: list[dict],
        max_tokens: int,
        log_label: str,
        trace_context: dict | None = None,
        enable_thinking: bool | None = None,
        response_format: dict | None = None,
        normalizer=None,
        validator=None,
        repairer=None,
        use_vision_model: bool = False,
    ) -> dict:
        trace = TraceRun(self.settings, log_label, trace_context)
        base_url = (
            self.settings.vision_llm_base_url
            if use_vision_model
            else self.settings.llm_base_url
        )
        api_key = (
            self.settings.vision_llm_api_key
            if use_vision_model
            else self.settings.llm_api_key
        )
        model = (
            self.settings.vision_llm_model
            if use_vision_model
            else self.settings.llm_model
        )
        payload: dict = {
            "model": model,
            "messages": messages,
            "temperature": 0.2,
            "max_tokens": max_tokens,
            "response_format": response_format or {"type": "json_object"},
        }
        thinking_enabled = (
            self.settings.llm_enable_thinking
            if enable_thinking is None
            else enable_thinking
        )
        if self.settings.llm_enable_thinking or enable_thinking is not None:
            payload["chat_template_kwargs"] = {
                "enable_thinking": thinking_enabled
            }

        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        trace.event(
            "request",
            endpoint=f"{base_url}/v1/chat/completions",
            messages=messages,
            parameters={key: value for key, value in payload.items() if key != "messages"},
        )
        try:
            async with httpx.AsyncClient(timeout=180) as client:
                response = await client.post(
                    f"{base_url}/v1/chat/completions",
                    headers=headers,
                    json=payload,
                )
                response.raise_for_status()
            completion = response.json()
            choice = completion["choices"][0]
            content = choice["message"]["content"]
            trace.event(
                "response",
                http_status=response.status_code,
                response_id=completion.get("id"),
                finish_reason=choice.get("finish_reason"),
                usage=completion.get("usage"),
                response_body=completion,
                raw_content=content,
            )
            logger.info("LLM response for %s: %r", log_label, content)

            if not content or not str(content).strip():
                finish_reason = choice.get("finish_reason")
                if finish_reason == "length":
                    raise ValueError(
                        "Model used the full generation token limit without producing "
                        "a response. Disable thinking or raise max_tokens."
                    )
                raise ValueError("Model returned an empty response.")

            parsed, repaired_content, initial_error = _extract_json_object(content)
            if repaired_content is not None:
                trace.event(
                    "json_repair",
                    initial_error=initial_error,
                    repaired_content=repaired_content,
                )
            else:
                trace.event("json_parse", outcome="valid_json")

            if normalizer is not None:
                parsed, changes = normalizer(parsed)
                if changes:
                    trace.event("normalization", changes=changes)

            if validator is not None:
                try:
                    parsed = validator(parsed)
                    trace.event("validation", outcome="valid", parsed_output=parsed)
                except Exception as validation_error:
                    trace.event(
                        "validation",
                        outcome="invalid",
                        error_type=type(validation_error).__name__,
                        message=str(validation_error),
                    )
                    if repairer is None:
                        raise
                    parsed = await repairer(parsed, validation_error)
                    parsed = validator(parsed)
                    trace.event(
                        "model_repair",
                        outcome="valid",
                        parsed_output=parsed,
                    )
            trace.finish("succeeded", repaired=repaired_content is not None)
            return parsed
        except Exception as exc:
            trace.event("error", error_type=type(exc).__name__, message=str(exc))
            trace.finish("failed")
            if isinstance(exc, LLMTraceError):
                raise
            if isinstance(exc, httpx.HTTPStatusError):
                message = (
                    f"LLM chat request failed with HTTP {exc.response.status_code}: "
                    f"{exc.response.text}"
                )
            else:
                message = str(exc) or type(exc).__name__
            raise LLMTraceError(message, trace.trace_id) from exc


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


def _extract_json_object(content: str | dict) -> tuple[dict, str | None, str | None]:
    if isinstance(content, dict):
        return content, None, None
    cleaned = content.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        value = json.loads(cleaned)
        if not isinstance(value, dict):
            raise ValueError("Model response JSON must be an object.")
        return value, None, None
    except (json.JSONDecodeError, ValueError) as initial_exc:
        repaired = repair_json(cleaned)
        value = json.loads(repaired)
        if not isinstance(value, dict):
            raise ValueError("Repaired model response JSON must be an object.")
        return value, repaired, str(initial_exc)


def _validate_teacher_answer(data: dict) -> dict:
    answer = str(data.get("answer", "")).strip()
    if not answer:
        raise ValueError("Teacher response is missing a non-empty answer.")
    return {"answer": answer}


def _validate_verification_payload(data: dict) -> dict:
    required = {"correct", "confidence", "feedback", "observed_answer"}
    missing = sorted(required - data.keys())
    if missing:
        raise ValueError(f"Verification response is missing fields: {', '.join(missing)}")
    return data


def _validate_lesson_counts(
    package: LessonPackage, quiz_count: int, boss_count: int
) -> None:
    errors: list[str] = []
    if not 6 <= len(package.lesson_steps) <= 10:
        errors.append(
            f"lesson_steps must contain 6 to 10 items; received {len(package.lesson_steps)}"
        )
    if len(package.quiz_questions) != quiz_count:
        errors.append(
            f"quiz_questions must contain exactly {quiz_count} items; "
            f"received {len(package.quiz_questions)}"
        )
    if len(package.boss_mission.questions) != boss_count:
        errors.append(
            f"boss_mission.questions must contain exactly {boss_count} items; "
            f"received {len(package.boss_mission.questions)}"
        )
    unavailable_patterns = (
        r"\b(?:look at|study|inspect|use|refer to|based on) (?:the |this |a )?(?:image|picture|map|chart|diagram|video|worksheet|book|object)\b",
        r"\b(?:shown|pictured|illustrated) (?:above|below|here)\b",
    )
    for index, step in enumerate(package.lesson_steps):
        word_count = len(re.findall(r"\b[\w'-]+\b", f"{step.body} {step.example}"))
        if word_count > 150:
            errors.append(f"lesson_steps[{index}] exceeds 150 words; received {word_count}")
        content = f"{step.body} {step.example}".lower()
        if any(re.search(pattern, content) for pattern in unavailable_patterns):
            errors.append(f"lesson_steps[{index}] references unavailable media or materials")
    vague_stems = ("what do you think", "how do you feel", "discuss ", "draw ", "look at ")
    for path, questions in (
        ("quiz_questions", package.quiz_questions),
        ("boss_mission.questions", package.boss_mission.questions),
    ):
        for index, question in enumerate(questions):
            lowered = question.question.strip().lower()
            if any(stem in lowered for stem in vague_stems):
                errors.append(f"{path}[{index}] is not a concrete text-only question")
            if question.answer_type == "text" and len(question.expected_answer.split()) > 20:
                errors.append(f"{path}[{index}] expected text answer is not short and canonical")
    if errors:
        raise ValueError("; ".join(errors))


def _normalize_lesson_package(
    data: dict,
    quiz_count: int | None = None,
    boss_count: int | None = None,
) -> tuple[dict, list[str]]:
    """Normalize harmless model aliases without inventing educational content."""
    changes: list[str] = []

    def normalize_questions(questions: object, path: str, difficulty: str) -> None:
        if not isinstance(questions, list):
            return
        for index, question in enumerate(questions):
            if not isinstance(question, dict):
                continue
            question_path = f"{path}[{index}]"
            if "answer_type" not in question and "question_type" in question:
                question["answer_type"] = question.pop("question_type")
                changes.append(f"{question_path}.question_type -> answer_type")

            raw_type = str(question.get("answer_type", "")).strip().lower()
            aliases = {
                "number": "numeric",
                "integer": "numeric",
                "float": "numeric",
                "decimal": "numeric",
                "string": "text",
                "free_text": "text",
            }
            if raw_type in aliases:
                question["answer_type"] = aliases[raw_type]
                changes.append(
                    f"{question_path}.answer_type: {raw_type!r} -> {aliases[raw_type]!r}"
                )

            if "id" in question and not isinstance(question["id"], str):
                original_id = question["id"]
                question["id"] = str(original_id)
                changes.append(f"{question_path}.id: {type(original_id).__name__} -> str")

            if "expected_answer" in question and not isinstance(
                question["expected_answer"], str
            ):
                original = question["expected_answer"]
                question["expected_answer"] = str(original)
                changes.append(
                    f"{question_path}.expected_answer: {type(original).__name__} -> str"
                )

            acceptable = question.get("acceptable_answers")
            if acceptable is not None and isinstance(acceptable, list):
                normalized_answers = [str(answer) for answer in acceptable]
                if normalized_answers != acceptable:
                    question["acceptable_answers"] = normalized_answers
                    changes.append(f"{question_path}.acceptable_answers: values -> str")

            if not question.get("difficulty"):
                question["difficulty"] = difficulty
                changes.append(f"{question_path}.difficulty: missing -> {difficulty!r}")

    quiz_questions = data.get("quiz_questions")
    if quiz_count is not None and isinstance(quiz_questions, list) and len(quiz_questions) > quiz_count:
        del quiz_questions[quiz_count:]
        changes.append(f"quiz_questions: trimmed to {quiz_count}")
    normalize_questions(quiz_questions, "quiz_questions", "easy")
    mission = data.get("boss_mission")
    if isinstance(mission, dict):
        boss_questions = mission.get("questions")
        if boss_count is not None and isinstance(boss_questions, list) and len(boss_questions) > boss_count:
            del boss_questions[boss_count:]
            changes.append(f"boss_mission.questions: trimmed to {boss_count}")
        normalize_questions(boss_questions, "boss_mission.questions", "hard")
    return data, changes


def _lesson_response_format(quiz_count: int, boss_count: int) -> dict:
    question_properties = {
        "id": {"type": "string"},
        "question": {"type": "string"},
        "answer_type": {"type": "string", "enum": ["numeric", "text"]},
        "expected_answer": {"type": "string"},
        "acceptable_answers": {"type": "array", "items": {"type": "string"}},
        "rubric": {"type": "string"},
        "difficulty": {"type": "string", "enum": ["easy", "medium", "hard"]},
        "explanation": {"type": "string"},
    }
    question_schema = {
        "type": "object",
        "properties": question_properties,
        "required": list(question_properties),
        "additionalProperties": False,
    }
    lesson_step_properties = {
        "title": {"type": "string"},
        "body": {"type": "string"},
        "example": {"type": "string"},
    }
    schema = {
        "type": "object",
        "properties": {
            "topic": {"type": "string"},
            "learner_level": {"type": "string"},
            "lesson_steps": {
                "type": "array",
                "minItems": 6,
                "maxItems": 10,
                "items": {
                    "type": "object",
                    "properties": lesson_step_properties,
                    "required": list(lesson_step_properties),
                    "additionalProperties": False,
                },
            },
            "quiz_questions": {
                "type": "array",
                "minItems": quiz_count,
                "maxItems": quiz_count,
                "items": question_schema,
            },
            "boss_mission": {
                "type": "object",
                "properties": {
                    "boss_name": {"type": "string"},
                    "briefing": {"type": "string"},
                    "questions": {
                        "type": "array",
                        "minItems": boss_count,
                        "maxItems": boss_count,
                        "items": question_schema,
                    },
                },
                "required": ["boss_name", "briefing", "questions"],
                "additionalProperties": False,
            },
        },
        "required": [
            "topic",
            "learner_level",
            "lesson_steps",
            "quiz_questions",
            "boss_mission",
        ],
        "additionalProperties": False,
    }
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "secret_student_lesson_package",
            "strict": True,
            "schema": schema,
        },
    }


def _verification_response_format() -> dict:
    properties = {
        "correct": {"type": "boolean"},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "feedback": {"type": "string"},
        "observed_answer": {"type": "string"},
    }
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "secret_student_answer_verification",
            "strict": True,
            "schema": {
                "type": "object",
                "properties": properties,
                "required": list(properties),
                "additionalProperties": False,
            },
        },
    }


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
