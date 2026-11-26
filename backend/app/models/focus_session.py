from datetime import datetime
from uuid import uuid4

from sqlalchemy import CheckConstraint, DateTime, Double, ForeignKey, Index, Integer, String
from sqlalchemy.dialects.mysql import DATETIME
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.user import utcnow

PRECISE_TIME = DateTime().with_variant(DATETIME(fsp=6), "mysql")


class FocusSession(Base):
    __tablename__ = "focus_sessions"
    __table_args__ = (
        CheckConstraint(
            "mode IN ('pomodoro', 'countdown', 'stopwatch', 'scheduled')", name="focus_mode"
        ),
        CheckConstraint("kind IN ('focus', 'break')", name="focus_kind"),
        CheckConstraint(
            "status IN ('scheduled', 'running', 'paused', 'completed', 'cancelled')",
            name="focus_status",
        ),
        CheckConstraint("elapsed_seconds >= 0", name="focus_elapsed"),
        CheckConstraint(
            "(mode IN ('stopwatch','scheduled') AND duration_seconds IS NULL) OR "
            "(mode IN ('pomodoro','countdown') AND duration_seconds BETWEEN 60 AND 86400)",
            name="focus_duration",
        ),
        CheckConstraint(
            "(status IN ('scheduled', 'running', 'paused') AND active_user_id IS NOT NULL "
            "AND active_user_id = user_id) OR "
            "(status IN ('completed', 'cancelled') AND active_user_id IS NULL)",
            name="focus_active",
        ),
        Index("ix_focus_user_started", "user_id", "started_at", "id"),
        {"mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_unicode_ci"},
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    # MySQL permits multiple NULLs in a unique key, but only one active row per user.
    active_user_id: Mapped[str | None] = mapped_column(String(36), unique=True)
    task_id: Mapped[str | None] = mapped_column(ForeignKey("tasks.id", ondelete="SET NULL"))
    title: Mapped[str] = mapped_column(String(200), default="", server_default="")
    window_start: Mapped[datetime | None] = mapped_column(PRECISE_TIME)
    window_end: Mapped[datetime | None] = mapped_column(PRECISE_TIME)
    occurrence_key: Mapped[str | None] = mapped_column(String(48), unique=True)
    mode: Mapped[str] = mapped_column(String(16))
    kind: Mapped[str] = mapped_column(String(16), default="focus")
    status: Mapped[str] = mapped_column(String(16), default="running")
    duration_seconds: Mapped[int | None] = mapped_column(Integer)
    elapsed_seconds: Mapped[float] = mapped_column(Double, default=0)
    started_at: Mapped[datetime] = mapped_column(PRECISE_TIME, default=utcnow)
    segment_started_at: Mapped[datetime | None] = mapped_column(PRECISE_TIME)
    ended_at: Mapped[datetime | None] = mapped_column(PRECISE_TIME)
    updated_at: Mapped[datetime] = mapped_column(PRECISE_TIME, default=utcnow, onupdate=utcnow)
