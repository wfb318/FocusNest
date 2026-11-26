from datetime import date
from uuid import uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class WeeklySchedule(Base):
    __tablename__ = "weekly_schedules"
    __table_args__ = (
        CheckConstraint("weekday BETWEEN 0 AND 6", name="schedule_weekday"),
        CheckConstraint(
            "start_minute >= 0 AND end_minute <= 1440 AND start_minute < end_minute",
            name="schedule_times",
        ),
        Index("ix_schedule_user_dates", "user_id", "effective_from", "effective_until"),
        {"mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_unicode_ci"},
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String(200))
    notes: Mapped[str] = mapped_column(Text, default="")
    weekday: Mapped[int] = mapped_column(Integer)
    start_minute: Mapped[int] = mapped_column(Integer)
    end_minute: Mapped[int] = mapped_column(Integer)
    timezone: Mapped[str] = mapped_column(String(64))
    effective_from: Mapped[date] = mapped_column(Date)
    effective_until: Mapped[date | None] = mapped_column(Date)
    task_id: Mapped[str | None] = mapped_column(ForeignKey("tasks.id", ondelete="SET NULL"))
    timer_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    remind_start: Mapped[bool] = mapped_column(Boolean, default=True)
    remind_end: Mapped[bool] = mapped_column(Boolean, default=True)
    revision: Mapped[int] = mapped_column(Integer, default=1)


class ScheduleException(Base):
    __tablename__ = "schedule_exceptions"
    __table_args__ = (
        UniqueConstraint("schedule_id", "occurrence_date", name="uq_schedule_exception_date"),
        {"mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_unicode_ci"},
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    schedule_id: Mapped[str] = mapped_column(ForeignKey("weekly_schedules.id", ondelete="CASCADE"))
    occurrence_date: Mapped[date] = mapped_column(Date)
    skipped: Mapped[bool] = mapped_column(Boolean, default=False)
    replaced: Mapped[bool] = mapped_column(Boolean, server_default="0")
    title: Mapped[str] = mapped_column(String(200))
    notes: Mapped[str] = mapped_column(Text, default="")
    start_minute: Mapped[int] = mapped_column(Integer)
    end_minute: Mapped[int] = mapped_column(Integer)
    task_id: Mapped[str | None] = mapped_column(ForeignKey("tasks.id", ondelete="SET NULL"))
    timer_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    remind_start: Mapped[bool] = mapped_column(Boolean, default=True)
    remind_end: Mapped[bool] = mapped_column(Boolean, default=True)


class ScheduleTemplate(Base):
    __tablename__ = "schedule_templates"
    __table_args__ = (
        UniqueConstraint("user_id", "name", name="uq_schedule_template_name"),
        {"mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_unicode_ci"},
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(80))
    entries: Mapped[list[dict]] = mapped_column(JSON)


class ScheduleWeekPlan(Base):
    __tablename__ = "schedule_week_plans"
    __table_args__ = {"mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_unicode_ci"}

    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    week_start: Mapped[date] = mapped_column(Date, primary_key=True)
    template_id: Mapped[str | None] = mapped_column(
        ForeignKey("schedule_templates.id", ondelete="SET NULL")
    )
    reviewed: Mapped[bool] = mapped_column(Boolean, default=False)
