from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


AnswerType = Literal["numeric", "text"]
AttemptMode = Literal["quiz", "practice", "boss"]


class LessonStep(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    body: str = Field(min_length=1, max_length=1200)
    example: str = Field(default="", max_length=500)


class Question(BaseModel):
    id: str
    question: str = Field(min_length=1, max_length=800)
    answer_type: AnswerType
    expected_answer: str = Field(min_length=1, max_length=240)
    acceptable_answers: list[str] = Field(default_factory=list)
    rubric: str = Field(default="", max_length=1000)
    difficulty: Literal["easy", "medium", "hard"] = "easy"
    explanation: str = Field(default="", max_length=1000)


class BossMission(BaseModel):
    boss_name: str
    briefing: str
    questions: list[Question]


class LessonPackage(BaseModel):
    topic: str
    learner_level: str
    lesson_steps: list[LessonStep]
    quiz_questions: list[Question]
    boss_mission: BossMission


class VerificationResult(BaseModel):
    correct: bool
    confidence: float = Field(ge=0, le=1)
    feedback: str
    observed_answer: str = ""


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=40, pattern=r"^[A-Za-z0-9_\-]+$")
    password: str = Field(min_length=4, max_length=200)
    learner_level: str = Field(min_length=1, max_length=80)
    avatar_image_data_url: str | None = Field(default=None, min_length=32)


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=40)
    password: str = Field(min_length=1, max_length=200)


class GameStateResponse(BaseModel):
    current_location: str
    onboarding_complete: bool
    active_topic: str | None
    latest_mission_id: int | None
    player_health: int
    boss_progress: dict


class UserResponse(BaseModel):
    id: int
    username: str
    learner_level: str
    avatar_image_path: str | None
    current_day: int


class AuthResponse(BaseModel):
    user: UserResponse
    game_state: GameStateResponse


class MeResponse(AuthResponse):
    latest_lesson: dict | None = None


class StartLessonRequest(BaseModel):
    topic: str = Field(min_length=1, max_length=120)


class LessonResponse(BaseModel):
    id: int
    topic: str
    learner_level: str
    lesson_steps: list[LessonStep]
    quiz_questions: list[Question]
    boss_mission: BossMission
    status: str


class AskTeacherRequest(BaseModel):
    step_index: int = Field(ge=0)
    question: str = Field(min_length=1, max_length=500)
    history: list["TeacherChatMessage"] = Field(default_factory=list, max_length=12)


class TeacherChatMessage(BaseModel):
    role: Literal["student", "teacher"]
    content: str = Field(min_length=1, max_length=1200)


class AskTeacherResponse(BaseModel):
    answer: str


class SubmitAnswerRequest(BaseModel):
    lesson_id: int
    question_id: str
    mode: AttemptMode
    answer_text: str | None = Field(default=None, max_length=1000)
    image_data_url: str | None = Field(default=None, min_length=32)


class SubmitAnswerResponse(BaseModel):
    result: VerificationResult
    next_question: Question | None = None
    completed: bool = False


class BossStartRequest(BaseModel):
    lesson_id: int


class BossStartResponse(BaseModel):
    lesson_id: int
    boss_name: str
    briefing: str
    question: Question
    question_index: int
    total_questions: int
    mistakes_remaining: int


class BossSubmitResponse(BaseModel):
    result: VerificationResult
    boss_name: str
    defeated: bool
    lost: bool
    question: Question | None
    question_index: int
    total_questions: int
    mistakes_remaining: int


class LocationUpdateRequest(BaseModel):
    location: str = Field(min_length=1, max_length=80)
    story_milestone: str | None = Field(default=None, max_length=80)


class HealthResponse(BaseModel):
    ok: bool
    provider: str
    model: str
