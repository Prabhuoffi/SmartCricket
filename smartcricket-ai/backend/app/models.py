"""Database tables, matching Section 5.5 of the project report."""
from datetime import date, datetime, timezone

from sqlalchemy import JSON, Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base

JsonType = JSON().with_variant(JSONB(), "postgresql")


def now():
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), default="player")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

    media: Mapped[list["Media"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class Media(Base):
    __tablename__ = "media"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    type: Mapped[str] = mapped_column(String(10))  # image | video
    file_path: Mapped[str] = mapped_column(Text)
    original_name: Mapped[str] = mapped_column(String(255), default="")
    session_label: Mapped[str | None] = mapped_column(String(100), nullable=True)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

    user: Mapped[User] = relationship(back_populates="media")
    analyses: Mapped[list["Analysis"]] = relationship(back_populates="media", cascade="all, delete-orphan")


class ReferenceClip(Base):
    __tablename__ = "reference_clips"
    id: Mapped[int] = mapped_column(primary_key=True)
    shot: Mapped[str] = mapped_column(String(30))
    file_path: Mapped[str] = mapped_column(Text)
    angles: Mapped[dict | None] = mapped_column(JsonType, nullable=True)
    added_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)


class Analysis(Base):
    __tablename__ = "analyses"
    id: Mapped[int] = mapped_column(primary_key=True)
    media_id: Mapped[int] = mapped_column(ForeignKey("media.id", ondelete="CASCADE"), index=True)
    mode: Mapped[str] = mapped_column(String(10))  # image | video
    model: Mapped[str] = mapped_column(String(30))
    shot: Mapped[str | None] = mapped_column(String(30), nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    uncertain: Mapped[bool] = mapped_column(Boolean, default=False)
    top3: Mapped[list | None] = mapped_column(JsonType, nullable=True)
    angles: Mapped[dict | None] = mapped_column(JsonType, nullable=True)
    attention: Mapped[list | None] = mapped_column(JsonType, nullable=True)
    summary: Mapped[dict | None] = mapped_column(JsonType, nullable=True)
    output_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    reference_id: Mapped[int | None] = mapped_column(ForeignKey("reference_clips.id"), nullable=True)
    dtw: Mapped[dict | None] = mapped_column(JsonType, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

    media: Mapped[Media] = relationship(back_populates="analyses")
    messages: Mapped[list["CoachMessage"]] = relationship(back_populates="analysis", cascade="all, delete-orphan",
                                                          order_by="CoachMessage.id")


class CoachMessage(Base):
    __tablename__ = "coach_messages"
    id: Mapped[int] = mapped_column(primary_key=True)
    analysis_id: Mapped[int] = mapped_column(ForeignKey("analyses.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(10))  # user | coach
    text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

    analysis: Mapped[Analysis] = relationship(back_populates="messages")


class ModelEvaluation(Base):
    __tablename__ = "model_evaluations"
    id: Mapped[int] = mapped_column(primary_key=True)
    model_name: Mapped[str] = mapped_column(String(30))
    accuracy: Mapped[float | None] = mapped_column(Float, nullable=True)
    macro_f1: Mapped[float | None] = mapped_column(Float, nullable=True)
    precision: Mapped[float | None] = mapped_column(Float, nullable=True)
    recall: Mapped[float | None] = mapped_column(Float, nullable=True)
    ece_before: Mapped[float | None] = mapped_column(Float, nullable=True)
    ece_after: Mapped[float | None] = mapped_column(Float, nullable=True)
    ms_per_clip: Mapped[float | None] = mapped_column(Float, nullable=True)
    evaluated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


# ---------------------------------------------------------------- adaptive coaching (training plan, check-ins, quiz)

class DailyLog(Base):
    """The player's morning check-in: balls faced yesterday, soreness and how they feel."""
    __tablename__ = "daily_logs"
    __table_args__ = (UniqueConstraint("user_id", "day"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    day: Mapped[date] = mapped_column(Date)
    balls_faced: Mapped[int | None] = mapped_column(Integer, nullable=True)
    soreness: Mapped[str | None] = mapped_column(String(10), nullable=True)  # none | mild | stop
    feeling: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 1 (low) to 5 (great)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class PlanDrill(Base):
    """One drill in a player's daily plan."""
    __tablename__ = "plan_drills"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    day: Mapped[date] = mapped_column(Date, index=True)
    code: Mapped[str] = mapped_column(String(30))
    title: Mapped[str] = mapped_column(String(120))
    dose: Mapped[str] = mapped_column(String(40))
    reason: Mapped[str] = mapped_column(Text)
    difficulty: Mapped[int] = mapped_column(Integer, default=2)  # 1 easy, 2 normal, 3 hard
    done: Mapped[bool] = mapped_column(Boolean, default=False)
    done_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class QuizAnswer(Base):
    __tablename__ = "quiz_answers"
    __table_args__ = (UniqueConstraint("user_id", "day"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    day: Mapped[date] = mapped_column(Date)
    question: Mapped[str] = mapped_column(String(20))
    choice: Mapped[int] = mapped_column(Integer)
    correct: Mapped[bool] = mapped_column(Boolean)


class Reflection(Base):
    """The player's answer to the coach's question about one analysis ("How did it feel?")."""
    __tablename__ = "reflections"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    analysis_id: Mapped[int] = mapped_column(ForeignKey("analyses.id", ondelete="CASCADE"), unique=True)
    question: Mapped[str] = mapped_column(Text)
    answer: Mapped[str] = mapped_column(String(30))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class WeeklyReport(Base):
    __tablename__ = "weekly_reports"
    __table_args__ = (UniqueConstraint("user_id", "week_start"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    week_start: Mapped[date] = mapped_column(Date)
    text: Mapped[str] = mapped_column(Text)
    stats: Mapped[dict | None] = mapped_column(JsonType, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class TrainingChat(Base):
    """The player's free chat with the coach on the Training page (not tied to one analysis)."""
    __tablename__ = "training_chats"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(10))  # user | coach
    text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class LiveSession(Base):
    """A saved live-mirror session: what was practised, for how long, and the best moments (no images)."""
    __tablename__ = "live_sessions"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    day: Mapped[date] = mapped_column(Date, index=True)
    drill_id: Mapped[int | None] = mapped_column(ForeignKey("plan_drills.id", ondelete="SET NULL"), nullable=True)
    title: Mapped[str] = mapped_column(String(120))
    duration_s: Mapped[int] = mapped_column(Integer)
    reps: Mapped[int] = mapped_column(Integer, default=0)
    hold_s: Mapped[int] = mapped_column(Integer, default=0)
    completed: Mapped[bool] = mapped_column(Boolean, default=False)
    stats: Mapped[dict | None] = mapped_column(JsonType, nullable=True)   # best angle, ghost match, stroke match
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class PracticeGoal(Base):
    """One player-selected measurement goal, with a baseline and optional retest."""
    __tablename__ = "practice_goals"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(120))
    notes: Mapped[str] = mapped_column(Text, default="")
    focus_joint: Mapped[str] = mapped_column(String(30))
    target_deg: Mapped[float | None] = mapped_column(Float, nullable=True)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="active")
    baseline_id: Mapped[int | None] = mapped_column(ForeignKey("analyses.id", ondelete="SET NULL"), nullable=True)
    retest_id: Mapped[int | None] = mapped_column(ForeignKey("analyses.id", ondelete="SET NULL"), nullable=True)
    baseline_frame: Mapped[int | None] = mapped_column(Integer, nullable=True)
    retest_frame: Mapped[int | None] = mapped_column(Integer, nullable=True)
    same_setup: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)

    baseline: Mapped[Analysis | None] = relationship(foreign_keys=[baseline_id])
    retest: Mapped[Analysis | None] = relationship(foreign_keys=[retest_id])


class PlayerProfile(Base):
    """Player-stated preferences for repeatable captures, separate from measurements."""
    __tablename__ = "player_profiles"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    handedness: Mapped[str] = mapped_column(String(20), default="unspecified")
    experience: Mapped[str] = mapped_column(String(20), default="unspecified")
    camera_view: Mapped[str] = mapped_column(String(20), default="side-on")
    focus: Mapped[str] = mapped_column(String(120), default="")
    notes: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)
