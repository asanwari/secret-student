from __future__ import annotations

import logging
from fastapi import Cookie, Depends, FastAPI, Header, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db, init_db
from app.debug_submissions import save_avatar_image, save_submitted_image
from app.image_validation import validate_image_data_url
from app.llm_clients import create_llm_client
from app.models import Attempt, GameState, Lesson, User
from app.schemas import (
    AskTeacherRequest,
    AskTeacherResponse,
    AuthResponse,
    BossMission,
    CharacterAppearance,
    BossStartRequest,
    BossStartResponse,
    BossSubmitResponse,
    GameStateResponse,
    HealthResponse,
    LessonResponse,
    LessonStep,
    LocationUpdateRequest,
    LoginRequest,
    MeResponse,
    Question,
    RegisterRequest,
    StartLessonRequest,
    SubmitAnswerRequest,
    SubmitAnswerResponse,
    UserResponse,
    VerificationResult,
)
from app.security import create_session_token, hash_password, parse_session_token, verify_password


logger = logging.getLogger(__name__)
settings = get_settings()
llm_client = create_llm_client(settings)

app = FastAPI(title="Secret Student API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup() -> None:
    init_db()


@app.get("/api/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(
        ok=True,
        runtime=settings.llm_runtime,
        provider=settings.llm_provider,
        model=settings.llm_model,
    )


@app.post("/api/auth/register", response_model=AuthResponse)
async def register(
    request: RegisterRequest,
    response: Response,
    db: Session = Depends(get_db),
) -> AuthResponse:
    existing = db.scalar(select(User).where(User.username == request.username))
    if existing is not None:
        raise HTTPException(status_code=409, detail="Username is already taken.")

    avatar_path = None
    if request.avatar_image_data_url:
        avatar_path = save_avatar_image(request.username, request.avatar_image_data_url)

    user = User(
        username=request.username,
        password_hash=hash_password(request.password),
        learner_level=request.learner_level,
        avatar_image_path=avatar_path,
        shirt_color=request.character_appearance.shirt_color,
        pants_color=request.character_appearance.pants_color,
        hair_color=request.character_appearance.hair_color,
    )
    db.add(user)
    db.flush()
    state = GameState(user_id=user.id, current_location="school", onboarding_complete=False)
    db.add(state)
    db.commit()
    db.refresh(user)
    token = create_session_token(user.id)
    _set_auth_cookie(response, token)
    return _auth_response(user, state, token)


@app.post("/api/auth/login", response_model=AuthResponse)
async def login(
    request: LoginRequest,
    response: Response,
    db: Session = Depends(get_db),
) -> AuthResponse:
    user = db.scalar(select(User).where(User.username == request.username))
    if user is None or not verify_password(request.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid username or password.")
    state = _ensure_state(db, user)
    token = create_session_token(user.id)
    _set_auth_cookie(response, token)
    return _auth_response(user, state, token)


@app.post("/api/auth/logout")
async def logout(response: Response) -> dict:
    response.delete_cookie("secret_student_token")
    return {"ok": True}


async def _current_user(
    db: Session = Depends(get_db),
    secret_student_token: str | None = Cookie(default=None),
    authorization: str | None = Header(default=None),
) -> User:
    token = secret_student_token
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1]
    if not token:
        raise HTTPException(status_code=401, detail="Not logged in.")
    user_id = parse_session_token(token)
    if user_id is None:
        raise HTTPException(status_code=401, detail="Invalid session.")
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="Unknown user.")
    return user


@app.get("/api/me", response_model=MeResponse)
async def me(
    user: User = Depends(_current_user),
    db: Session = Depends(get_db),
) -> MeResponse:
    state = _ensure_state(db, user)
    latest = _latest_lesson(db, user.id)
    payload = _auth_response(user, state).model_dump()
    payload["latest_lesson"] = _lesson_response(latest).model_dump() if latest else None
    return MeResponse.model_validate(payload)


@app.post("/api/lesson/start", response_model=LessonResponse)
async def start_lesson(
    request: StartLessonRequest,
    user: User = Depends(_current_user),
    db: Session = Depends(get_db),
) -> LessonResponse:
    try:
        package = await llm_client.generate_lesson_package(
            request.topic,
            user.learner_level,
            settings.quiz_question_count,
            settings.boss_question_count,
            trace_context={
                "user_id": user.id,
                "topic": request.topic,
                "learner_level": user.learner_level,
            },
        )
    except Exception as exc:
        logger.exception("Lesson package generation failed.")
        raise HTTPException(status_code=502, detail=f"Lesson generation failed: {exc}") from exc

    lesson = Lesson(
        user_id=user.id,
        topic=package.topic,
        learner_level=package.learner_level,
        lesson_steps=[step.model_dump() for step in package.lesson_steps],
        quiz_questions=[question.model_dump() for question in package.quiz_questions],
        boss_questions=[
            question.model_dump() for question in package.boss_mission.questions
        ],
        boss_name=package.boss_mission.boss_name,
        boss_briefing=package.boss_mission.briefing,
        villain_image_url=package.boss_mission.villain_image_url,
        status="lesson_ready",
    )
    db.add(lesson)
    db.flush()
    state = _ensure_state(db, user)
    state.active_topic = lesson.topic
    state.latest_mission_id = lesson.id
    state.current_location = "school"
    state.boss_progress = {}
    db.commit()
    db.refresh(lesson)
    return _lesson_response(lesson)


@app.get("/api/lesson/latest", response_model=LessonResponse | None)
async def get_latest_lesson(
    user: User = Depends(_current_user),
    db: Session = Depends(get_db),
) -> LessonResponse | None:
    latest = _latest_lesson(db, user.id)
    return _lesson_response(latest) if latest else None


@app.get("/api/lesson/{lesson_id}", response_model=LessonResponse)
async def get_lesson(
    lesson_id: int,
    user: User = Depends(_current_user),
    db: Session = Depends(get_db),
) -> LessonResponse:
    return _lesson_response(_owned_lesson(db, user.id, lesson_id))


@app.post("/api/lesson/{lesson_id}/ask", response_model=AskTeacherResponse)
async def ask_teacher(
    lesson_id: int,
    request: AskTeacherRequest,
    user: User = Depends(_current_user),
    db: Session = Depends(get_db),
) -> AskTeacherResponse:
    lesson = _owned_lesson(db, user.id, lesson_id)
    try:
        answer = await llm_client.answer_teacher_question(
            lesson.topic,
            lesson.learner_level,
            [LessonStep.model_validate(step) for step in lesson.lesson_steps],
            request.step_index,
            request.question,
            request.history,
            trace_context={"user_id": user.id, "lesson_id": lesson.id},
        )
    except Exception:
        # A teacher follow-up should never block the playable loop in demo mode.
        logger.exception("Teacher follow-up failed.")
        answer = "Try one smaller example, then return to the mission question."
    return AskTeacherResponse(answer=answer)


@app.post("/api/quiz/submit", response_model=SubmitAnswerResponse)
async def submit_quiz_answer(
    request: SubmitAnswerRequest,
    user: User = Depends(_current_user),
    db: Session = Depends(get_db),
) -> SubmitAnswerResponse:
    lesson = _owned_lesson(db, user.id, request.lesson_id)
    question = _find_question(lesson, request.question_id)
    result, image_path = await _verify_answer(user.id, question, request)
    db.add(
        Attempt(
            lesson_id=lesson.id,
            user_id=user.id,
            mode=request.mode,
            question_id=question.id,
            submitted_answer=request.answer_text or "",
            submitted_image_path=image_path,
            correct=result.correct,
            feedback=result.feedback,
        )
    )

    if request.mode == "quiz":
        lesson.status = "quiz_started"
    db.commit()

    next_question = _next_quiz_question(db, lesson, user.id, request.mode)
    completed = next_question is None
    if completed and request.mode == "quiz":
        lesson.status = "quiz_complete"
        db.commit()
    return SubmitAnswerResponse(result=result, next_question=next_question, completed=completed)


@app.post("/api/boss/start", response_model=BossStartResponse)
async def start_boss(
    request: BossStartRequest,
    user: User = Depends(_current_user),
    db: Session = Depends(get_db),
) -> BossStartResponse:
    lesson = _owned_lesson(db, user.id, request.lesson_id)
    questions = _boss_questions(lesson)
    if not questions:
        raise HTTPException(status_code=400, detail="This lesson has no boss questions.")
    state = _ensure_state(db, user)
    state.current_location = "hq"
    state.boss_progress = {
        "lesson_id": lesson.id,
        "index": 0,
        "mistakes": 0,
        "defeated": False,
        "lost": False,
    }
    lesson.status = "boss_started"
    db.commit()
    return BossStartResponse(
        lesson_id=lesson.id,
        boss_name=lesson.boss_name,
        briefing=lesson.boss_briefing,
        question=questions[0],
        question_index=1,
        total_questions=len(questions),
        mistakes_remaining=settings.boss_max_mistakes,
    )


@app.post("/api/boss/submit", response_model=BossSubmitResponse)
async def submit_boss_answer(
    request: SubmitAnswerRequest,
    user: User = Depends(_current_user),
    db: Session = Depends(get_db),
) -> BossSubmitResponse:
    lesson = _owned_lesson(db, user.id, request.lesson_id)
    state = _ensure_state(db, user)
    progress = dict(state.boss_progress or {})
    if progress.get("lesson_id") != lesson.id:
        raise HTTPException(status_code=400, detail="Start the boss battle first.")

    questions = _boss_questions(lesson)
    index = int(progress.get("index", 0))
    if index >= len(questions):
        raise HTTPException(status_code=400, detail="Boss battle is already complete.")

    question = questions[index]
    result, image_path = await _verify_answer(user.id, question, request)
    db.add(
        Attempt(
            lesson_id=lesson.id,
            user_id=user.id,
            mode="boss",
            question_id=question.id,
            submitted_answer=request.answer_text or "",
            submitted_image_path=image_path,
            correct=result.correct,
            feedback=result.feedback,
        )
    )

    mistakes = int(progress.get("mistakes", 0)) + (0 if result.correct else 1)
    next_index = index + 1 if result.correct else index
    defeated = next_index >= len(questions)
    lost = mistakes >= settings.boss_max_mistakes and not defeated
    progress.update(
        {
            "index": next_index,
            "mistakes": mistakes,
            "defeated": defeated,
            "lost": lost,
        }
    )
    state.boss_progress = progress
    if defeated:
        lesson.status = "boss_defeated"
    elif lost:
        lesson.status = "boss_lost"
        state.player_health = 0
    db.commit()

    next_question = None if defeated or lost else questions[next_index]
    return BossSubmitResponse(
        result=result,
        boss_name=lesson.boss_name,
        defeated=defeated,
        lost=lost,
        question=next_question,
        question_index=min(next_index + 1, len(questions)),
        total_questions=len(questions),
        mistakes_remaining=max(settings.boss_max_mistakes - mistakes, 0),
    )


@app.post("/api/state/location", response_model=GameStateResponse)
async def update_location(
    request: LocationUpdateRequest,
    user: User = Depends(_current_user),
    db: Session = Depends(get_db),
) -> GameStateResponse:
    state = _ensure_state(db, user)
    state.current_location = request.location
    if request.story_milestone == "onboarding_complete":
        state.onboarding_complete = True
    if request.story_milestone == "rest":
        state.player_health = 3
        if state.boss_progress:
            progress = dict(state.boss_progress)
            progress["lost"] = False
            state.boss_progress = progress
    db.commit()
    db.refresh(state)
    return _state_response(state)


def _set_auth_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        "secret_student_token",
        token,
        httponly=True,
        secure=True,
        samesite="none",
        max_age=60 * 60 * 24 * 30,
    )


def _ensure_state(db: Session, user: User) -> GameState:
    state = db.scalar(select(GameState).where(GameState.user_id == user.id))
    if state is None:
        state = GameState(user_id=user.id)
        db.add(state)
        db.commit()
        db.refresh(state)
    return state


def _auth_response(
    user: User, state: GameState, session_token: str | None = None
) -> AuthResponse:
    return AuthResponse(
        user=_user_response(user),
        game_state=_state_response(state),
        session_token=session_token,
    )


def _user_response(user: User) -> UserResponse:
    return UserResponse(
        id=user.id,
        username=user.username,
        learner_level=user.learner_level,
        avatar_image_path=user.avatar_image_path,
        character_appearance=CharacterAppearance(
            shirt_color=user.shirt_color or "red",
            pants_color=user.pants_color or "navy",
            hair_color=user.hair_color or "dark_brown",
        ),
        current_day=user.current_day,
    )


def _state_response(state: GameState) -> GameStateResponse:
    return GameStateResponse(
        current_location=state.current_location,
        onboarding_complete=state.onboarding_complete,
        active_topic=state.active_topic,
        latest_mission_id=state.latest_mission_id,
        player_health=state.player_health,
        boss_progress=state.boss_progress or {},
    )


def _lesson_response(lesson: Lesson) -> LessonResponse:
    boss_questions = [Question.model_validate(q) for q in lesson.boss_questions]
    return LessonResponse(
        id=lesson.id,
        topic=lesson.topic,
        learner_level=lesson.learner_level,
        lesson_steps=lesson.lesson_steps,
        quiz_questions=[Question.model_validate(q) for q in lesson.quiz_questions],
        boss_mission=BossMission(
            boss_name=lesson.boss_name,
            briefing=lesson.boss_briefing,
            questions=boss_questions,
            villain_image_url=lesson.villain_image_url,
        ),
        status=lesson.status,
    )


def _latest_lesson(db: Session, user_id: int) -> Lesson | None:
    return db.scalar(
        select(Lesson).where(Lesson.user_id == user_id).order_by(Lesson.id.desc())
    )


def _owned_lesson(db: Session, user_id: int, lesson_id: int) -> Lesson:
    lesson = db.get(Lesson, lesson_id)
    if lesson is None or lesson.user_id != user_id:
        raise HTTPException(status_code=404, detail="Lesson not found.")
    return lesson


def _quiz_questions(lesson: Lesson) -> list[Question]:
    return [Question.model_validate(q) for q in lesson.quiz_questions]


def _boss_questions(lesson: Lesson) -> list[Question]:
    return [Question.model_validate(q) for q in lesson.boss_questions]


def _find_question(lesson: Lesson, question_id: str) -> Question:
    for question in [*_quiz_questions(lesson), *_boss_questions(lesson)]:
        if question.id == question_id:
            return question
    raise HTTPException(status_code=404, detail="Question not found.")


async def _verify_answer(
    user_id: int, question: Question, request: SubmitAnswerRequest
) -> tuple[VerificationResult, str | None]:
    if request.answer_text:
        try:
            return await llm_client.verify_text_answer(
                question,
                request.answer_text,
                trace_context={"user_id": user_id, "question_id": question.id},
            ), None
        except Exception as exc:
            logger.exception("Text answer verification failed.")
            raise HTTPException(status_code=502, detail=f"Answer verification failed: {exc}") from exc
    if not request.image_data_url:
        raise HTTPException(status_code=400, detail="Submit answer_text or image_data_url.")
    image_data_url = validate_image_data_url(request.image_data_url)
    image_path = save_submitted_image(user_id, question, image_data_url)
    try:
        return await llm_client.verify_drawn_answer(
            question,
            image_data_url,
            trace_context={"user_id": user_id, "question_id": question.id},
        ), image_path
    except Exception as exc:
        logger.exception("Vision answer verification failed.")
        raise HTTPException(status_code=502, detail=f"Answer verification failed: {exc}") from exc


def _verify_text_answer(question: Question, answer_text: str) -> VerificationResult:
    observed = answer_text.strip()
    expected_values = [question.expected_answer, *question.acceptable_answers]
    if question.answer_type == "numeric":
        correct = any(_numbers_match(observed, expected) for expected in expected_values)
    else:
        normalized = _normalize_text(observed)
        correct = any(normalized == _normalize_text(expected) for expected in expected_values)
    return VerificationResult(
        correct=correct,
        confidence=1.0 if correct else 0.2,
        observed_answer=observed,
        feedback=question.explanation
        if correct
        else f"Good try. Expected: {question.expected_answer}. {question.explanation}",
    )


def _numbers_match(left: str, right: str) -> bool:
    try:
        return abs(float(left.replace(",", ".")) - float(right.replace(",", "."))) < 0.0001
    except ValueError:
        return _normalize_text(left) == _normalize_text(right)


def _normalize_text(value: str) -> str:
    return " ".join(value.strip().lower().split())


def _next_quiz_question(
    db: Session, lesson: Lesson, user_id: int, mode: str
) -> Question | None:
    if mode not in {"quiz", "practice"}:
        return None
    questions = _quiz_questions(lesson)
    answered_ids = {
        attempt.question_id
        for attempt in db.scalars(
            select(Attempt).where(
                Attempt.lesson_id == lesson.id,
                Attempt.user_id == user_id,
                Attempt.mode == mode,
            )
        )
    }
    for question in questions:
        if question.id not in answered_ids:
            return question
    return None
