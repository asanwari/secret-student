from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    learner_level: Mapped[str] = mapped_column(String(80))
    avatar_image_path: Mapped[str | None] = mapped_column(String(300), nullable=True)
    current_day: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    state: Mapped["GameState"] = relationship(back_populates="user", uselist=False)
    lessons: Mapped[list["Lesson"]] = relationship(back_populates="user")


class GameState(Base):
    __tablename__ = "game_states"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True, index=True)
    current_location: Mapped[str] = mapped_column(String(80), default="school")
    onboarding_complete: Mapped[bool] = mapped_column(Boolean, default=False)
    active_topic: Mapped[str | None] = mapped_column(String(120), nullable=True)
    latest_mission_id: Mapped[int | None] = mapped_column(
        ForeignKey("lessons.id"), nullable=True
    )
    player_health: Mapped[int] = mapped_column(Integer, default=3)
    boss_progress: Mapped[dict] = mapped_column(JSON, default=dict)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    user: Mapped[User] = relationship(back_populates="state")


class Lesson(Base):
    __tablename__ = "lessons"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    topic: Mapped[str] = mapped_column(String(120), index=True)
    learner_level: Mapped[str] = mapped_column(String(80))
    lesson_steps: Mapped[list] = mapped_column(JSON)
    quiz_questions: Mapped[list] = mapped_column(JSON)
    boss_questions: Mapped[list] = mapped_column(JSON)
    boss_name: Mapped[str] = mapped_column(String(120))
    boss_briefing: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(40), default="lesson_ready")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    user: Mapped[User] = relationship(back_populates="lessons")
    attempts: Mapped[list["Attempt"]] = relationship(back_populates="lesson")


class Attempt(Base):
    __tablename__ = "attempts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    lesson_id: Mapped[int] = mapped_column(ForeignKey("lessons.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    mode: Mapped[str] = mapped_column(String(20))
    question_id: Mapped[str] = mapped_column(String(80), index=True)
    submitted_answer: Mapped[str] = mapped_column(Text, default="")
    submitted_image_path: Mapped[str | None] = mapped_column(String(300), nullable=True)
    correct: Mapped[bool] = mapped_column(Boolean)
    feedback: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    lesson: Mapped[Lesson] = relationship(back_populates="attempts")
