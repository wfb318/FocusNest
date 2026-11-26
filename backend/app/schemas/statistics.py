from datetime import date, datetime, timezone
from typing import Literal

from pydantic import BaseModel, field_serializer


class FocusSummary(BaseModel):
    seconds: float = 0
    completed: int = 0
    active: int = 0


class DailyFocus(FocusSummary):
    date: date


class FocusModeSummary(FocusSummary):
    mode: Literal["pomodoro", "countdown", "stopwatch", "scheduled"]


class TaskSummary(BaseModel):
    total: int
    todo: int
    doing: int
    done: int
    overdue: int
    completion_rate: float | None


class StatisticsRead(BaseModel):
    start_date: date
    end_date: date
    timezone: str
    today: date
    server_now: datetime
    focus: FocusSummary
    tasks: TaskSummary
    daily: list[DailyFocus]
    modes: list[FocusModeSummary]

    @field_serializer("server_now")
    def serialize_time(self, value: datetime) -> str:
        return value.replace(tzinfo=timezone.utc).isoformat()
